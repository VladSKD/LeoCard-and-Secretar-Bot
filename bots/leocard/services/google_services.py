import gspread
import os
import io
import json
import logging
import re
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from config import GoogleConfig

logger = logging.getLogger(__name__)
google_config = GoogleConfig()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = google_config.credentials_file
TOKEN_FILE = google_config.token_file


def _write_json_from_env(env_value: str, file_path: str) -> None:
    """Write JSON from env var to file if file doesn't exist."""
    if env_value and not os.path.exists(file_path):
        try:
            data = json.loads(env_value)
            with open(file_path, 'w') as f:
                json.dump(data, f)
            logger.info(f"Записано {file_path} зі змінної середовища.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Не вдалося записати {file_path}: {e}")


def _ensure_credentials_files() -> None:
    """Materialize credentials/token from env vars if they don't exist as files."""
    _write_json_from_env(google_config.credentials_json, CREDENTIALS_FILE)
    _write_json_from_env(google_config.token_json, TOKEN_FILE)


def _authorize_fresh():
    """Отримати новий токен через OAuth flow, використовуючи credentials.json.

    На сервері (без дисплея) це не спрацює — потрібно оновити GOOGLE_TOKEN_JSON
    env var зі свіжим токеном, отриманим локально.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        raise RuntimeError(
            "credentials.json не знайдено і GOOGLE_CREDENTIALS_JSON не задано. "
            "Потрібно оновити GOOGLE_TOKEN_JSON з валідним токеном."
        )
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        return flow.run_local_server(port=0)
    except Exception as e:
        raise RuntimeError(
            f"Не вдалося пройти OAuth авторизацію: {e}. "
            "На сервері потрібно оновити GOOGLE_TOKEN_JSON env var "
            "зі свіжим токеном (отримати локально через OAuth flow)."
        )


# --- Логіка авторизації OAuth 2.0 ---
def get_credentials():
    _ensure_credentials_files()

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Не вдалося оновити токен: {e}")
                # Truncate the invalid token file (os.remove fails on
                # Docker bind-mounts with EBUSY, so we clear in-place).
                try:
                    with open(TOKEN_FILE, 'w') as f:
                        f.truncate(0)
                except OSError:
                    pass
                # Пробуємо отримати новий токен через OAuth flow
                creds = _authorize_fresh()
        else:
            creds = _authorize_fresh()
        if creds:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        else:
            raise RuntimeError("Не вдалося отримати Google credentials.")
    return creds


def get_drive_service():
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds) if creds else None


def get_sheets_client():
    creds = get_credentials()
    return gspread.authorize(creds) if creds else None


# --- Допоміжні функції ---
def find_file_by_name(service, name: str, parent_id: str, mime_type: str = None):
    query = f"name='{name}' and '{parent_id}' in parents and trashed=false"
    if mime_type:
        query += f" and mimeType='{mime_type}'"
    response = service.files().list(q=query, fields='files(id, name)', supportsAllDrives=True,
                                    includeItemsFromAllDrives=True).execute()
    files = response.get('files', [])
    return files[0].get('id') if files else None


def get_or_create_folder(service, folder_name: str, parent_id: str):
    folder_id = find_file_by_name(service, folder_name, parent_id=parent_id,
                                  mime_type='application/vnd.google-apps.folder')
    if folder_id:
        return folder_id
    logger.info(f"Папка '{folder_name}' не знайдена. Створюємо нову...")
    file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    folder = service.files().create(body=file_metadata, fields='id', supportsAllDrives=True).execute()
    return folder.get('id')


def _create_spreadsheet_from_template(drive_service, sheets_client, parent_folder_id, spreadsheet_name):
    try:
        file_metadata = {'name': spreadsheet_name, 'parents': [parent_folder_id],
                         'mimeType': 'application/vnd.google-apps.spreadsheet'}
        new_spreadsheet_file = drive_service.files().create(body=file_metadata, fields='id',
                                                            supportsAllDrives=True).execute()
        new_spreadsheet_id = new_spreadsheet_file.get('id')
        new_spreadsheet = sheets_client.open_by_key(new_spreadsheet_id)
        default_sheet = new_spreadsheet.sheet1
        template_spreadsheet = sheets_client.open_by_key(google_config.template_spreadsheet_id)
        template_sheet = template_spreadsheet.sheet1
        template_sheet.copy_to(new_spreadsheet_id)
        new_spreadsheet.del_worksheet(default_sheet)
        final_sheet = new_spreadsheet.sheet1
        final_sheet.update_title("Аркуш1")
        logger.info(f"Створено таблицю '{spreadsheet_name}' з шаблону зі збереженням форматування.")
        return final_sheet
    except Exception as error:
        logger.error(f"Не вдалося створити/заповнити таблицю для партії: {error}", exc_info=True)
        raise error


# --- Функція перевірки ліміту ---
def get_or_create_party_folder(drive_service, sheets_client, root_folder_id: str):
    logger.info("Пошук активної папки для партії...")
    query = f"name contains 'партія' and '{root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    response = drive_service.files().list(q=query, fields='files(id, name, createdTime)', orderBy="createdTime desc",
                                          supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    party_folders = response.get('files', [])

    latest_party_number = 0
    latest_internal_number = 0

    if party_folders:
        latest_folder = party_folders[0]
        latest_folder_id = latest_folder['id']
        latest_folder_name = latest_folder['name']
        match = re.search(r'(\d+)\s*партія\s*\((\d+)\)', latest_folder_name)
        if match:
            latest_party_number = int(match.group(1))
            latest_internal_number = int(match.group(2))

        spreadsheet_name = google_config.party_spreadsheet_name_template.format(latest_party_number)
        spreadsheet_id = find_file_by_name(drive_service, spreadsheet_name, parent_id=latest_folder_id)

        if spreadsheet_id:
            try:
                worksheet = sheets_client.open_by_key(spreadsheet_id).worksheet("Аркуш1")
                # Рахуємо рядки з даними (після 2 рядків заголовків)
                all_values = worksheet.get_all_values()
                data_rows_count = 0
                for i, row in enumerate(all_values):
                    if i >= 2 and any(cell for cell in row):
                        data_rows_count += 1

                logger.info(f"Перевірка партії '{latest_folder_name}': знайдено {data_rows_count} записів.")
                if data_rows_count < 50:
                    logger.info("В поточній партії є місце.")
                    return latest_folder_id, worksheet
                else:
                    logger.info("Поточна партія заповнена (>= 50 записів).")
            except Exception as e:
                logger.warning(f"Проблема з таблицею '{spreadsheet_name}': {e}. Створюю таблицю заново...")
                worksheet = _create_spreadsheet_from_template(drive_service, sheets_client, latest_folder_id,
                                                              spreadsheet_name)
                return latest_folder_id, worksheet
        else:
            logger.warning(
                f"Папка '{latest_folder_name}' існує, але таблиці '{spreadsheet_name}' в ній не знайдено. Створюю таблицю...")
            worksheet = _create_spreadsheet_from_template(drive_service, sheets_client, latest_folder_id,
                                                          spreadsheet_name)
            return latest_folder_id, worksheet

    # Створюємо нову партію
    new_party_number = latest_party_number + 1
    new_internal_number = latest_internal_number + 1
    new_party_folder_name = google_config.party_folder_name_template.format(new_party_number, new_internal_number)
    logger.info(f"Створення нової папки для партії: '{new_party_folder_name}'")
    new_party_folder_id = get_or_create_folder(drive_service, new_party_folder_name, root_folder_id)
    new_spreadsheet_name = google_config.party_spreadsheet_name_template.format(new_party_number)
    worksheet = _create_spreadsheet_from_template(drive_service, sheets_client, new_party_folder_id,
                                                  new_spreadsheet_name)
    return new_party_folder_id, worksheet


# --- Запис у таблицю партії ---
def add_user_to_party_sheet(worksheet, user_data: dict, pdf_url: str):
    """Додає дані користувача в таблицю партії, згідно з шаблоном."""
    try:
        passport_data = user_data.get('passport_data', {})
        full_name = passport_data.get('full_name', '').strip()
        parts = [p for p in full_name.split() if p]
        surname = parts[0] if len(parts) > 0 else ''
        name = parts[1] if len(parts) > 1 else ''
        patronymic = ' '.join(parts[2:]) if len(parts) > 2 else ''

        city = passport_data.get('city', '')
        street = passport_data.get('street', '')
        building_flat = passport_data.get('building_flat', '')

        if city == 'N/A': city = ''
        if street == 'N/A': street = ''
        if building_flat == 'N/A': building_flat = ''

        # Якщо місто порожнє, але в адресі є Львів - ставимо Львів
        if not city and 'львів' in passport_data.get('residency_address', '').lower():
            city = 'Львів'

        # Колонки згідно шаблону партії (A-X):
        # A: Реєстр. номер, B: Категорія, C: Прізвище, D: Ім'я, E: По батькові,
        # F: Телефон, G: Email, H: Адреса, I: Країна, J: Індекс,
        # K: Місто, L: Вулиця, M: Будинок/кв, N: Зміст, O: Форма отримання,
        # P: Адресовано до, Q: Коментар, R: Результат, S: ID (УНЗР),
        # T: Посилання на документ, U: Дата народження, V: Стать,
        # W: Профіль отримувача, X: Закінчення дії профіля
        row = [
            "", "",                                                     # A-B: номер, категорія
            surname, name, patronymic,                                  # C-E
            user_data.get('phone_number', ''),                          # F: телефон
            passport_data.get('politech_email', ''),                    # G: email
            passport_data.get('residency_address', ''),                 # H: адреса
            "Україна", "",                                              # I-J: країна, індекс
            city, street, building_flat,                                # K-M: місто, вулиця, буд.
            "Отримання пільгової транспортної картки ЛеоКарт",          # N: зміст
            "Особисто",                                                 # O: форма отримання
            "", "", "",                                                 # P-R: адресовано, коментар, результат
            passport_data.get('record_no', ''),                         # S: ID (УНЗР)
            pdf_url or '',                                              # T: посилання на документ
            passport_data.get('date_of_birth', ''),                     # U: дата народження
            passport_data.get('gender', ''),                            # V: стать
            user_data.get('level', ''),                                 # W: профіль отримувача
            user_data.get("student_card_valid_until", ""),              # X: закінчення дії профіля
        ]

        all_values = worksheet.get_all_values()
        insert_index = 3
        for i, r in enumerate(all_values):
            if i >= 2 and (not r or (len(r) < 3 or (not r[0] and not r[2]))):
                insert_index = i + 1
                break
        else:
            insert_index = len(all_values) + 1

        worksheet.insert_row(row, index=insert_index, value_input_option='USER_ENTERED')
        logger.info(f"Дані для користувача {full_name} додано в таблицю партії в рядок {insert_index}.")
    except Exception as e:
        logger.error(f"Помилка під час запису в таблицю партії: {e}", exc_info=True)


# --- Запис у загальну таблицю ---
def add_user_to_sheet(worksheet, user_data: dict, telegram_id: int, folder_url: str):
    """Додає дані в загальну таблицю."""
    try:
        passport_data = user_data.get('passport_data', {})
        full_name = passport_data.get('full_name', '').strip()
        parts = [p for p in full_name.split() if p]
        surname = parts[0] if len(parts) > 0 else ''
        name = parts[1] if len(parts) > 1 else ''
        patronymic = ' '.join(parts[2:]) if len(parts) > 2 else ''

        raw_address = passport_data.get('residency_address', 'N/A')
        city = passport_data.get('city', 'N/A')
        street = passport_data.get('street', 'N/A')
        building_flat = passport_data.get('building_flat', 'N/A')

        row = [
            str(telegram_id), surname, name, patronymic,
            user_data.get('phone_number', 'N/A'),
            passport_data.get('politech_email', 'N/A'),
            passport_data.get('record_no', 'N/A'),
            passport_data.get('date_of_birth', 'N/A'),
            passport_data.get('gender', 'N/A'),
            user_data.get("student_card_valid_until", "N/A"),
            user_data.get('photo_3x4_link', 'N/A'),
            folder_url,
            raw_address, city, street, building_flat,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            passport_data.get('tax_id', 'N/A'),
            user_data.get('level', 'N/A'),
        ]
        worksheet.append_row(row, value_input_option='USER_ENTERED')
        logger.info(f"Дані для користувача {telegram_id} успішно додано в загальну Google Sheet.")
    except Exception as e:
        logger.error(f"Помилка під час запису в загальну Google Sheet: {e}", exc_info=True)


# --- Створення/отримання аркуша (ВИПРАВЛЕНО ТУТ) ---
def get_or_create_worksheet(spreadsheet_name: str, worksheet_name: str, parent_folder_id: str):
    drive_service = get_drive_service()
    sheets_client = get_sheets_client()
    if not drive_service or not sheets_client: return None

    spreadsheet_id = find_file_by_name(drive_service, spreadsheet_name, parent_id=parent_folder_id,
                                       mime_type='application/vnd.google-apps.spreadsheet')

    if spreadsheet_id:
        spreadsheet = sheets_client.open_by_key(spreadsheet_id)
    else:
        file_metadata = {'name': spreadsheet_name, 'parents': [parent_folder_id],
                         'mimeType': 'application/vnd.google-apps.spreadsheet'}
        new_spreadsheet_file = drive_service.files().create(body=file_metadata, fields='id',
                                                            supportsAllDrives=True).execute()
        spreadsheet = sheets_client.open_by_key(new_spreadsheet_file.get('id'))

    def ensure_headers(ws):
        header = ["Telegram ID", "Прізвище", "Ім'я", "По батькові", "Телефон", "Електронна пошта", "УНЗР",
                  "Дата народження", "Стать", "Термін дійсності Студентського квитка", "Фото", "Скани документів",
                  "Повна адреса", "Місто", "Вулиця", "Номер будинку, квартира", "дата", "РНОКПП", "Рівень освіти"]
        try:
            first_row = ws.row_values(1)
            if not first_row:
                ws.insert_row(header, 1)
            elif first_row[0] == "Telegram ID" and first_row != header:
                # Існуючий заголовок — оновлюємо на місці (не зсуваємо дані)
                ws.update('A1', [header])
            elif first_row[0] != "Telegram ID":
                # Немає заголовка — вставляємо
                ws.insert_row(header, 1)
        except Exception:
            ws.insert_row(header, 1)

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        ensure_headers(worksheet)
        return worksheet
    except gspread.WorksheetNotFound:
        # --- ВИПРАВЛЕНО: add_worksheet (мала 'w') ---
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="100", cols="20")
        ensure_headers(worksheet)
        return worksheet


def upload_file_to_drive(service, folder_id: str, filename: str, file_buffer: io.BytesIO, mimetype='image/jpeg'):
    file_metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaIoBaseUpload(file_buffer, mimetype=mimetype, resumable=True)
    file_buffer.seek(0)
    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink',
                                  supportsAllDrives=True).execute()
    logger.info(f"Файл '{filename}' завантажено з ID: {file.get('id')}")
    return file.get('id'), file.get('webViewLink')