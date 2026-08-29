import os
import logging
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from config import GDRIVE_FOLDER_ID, GOOGLE_SHEET_ID

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

SHEET_HEADERS = [
    "Інститут", "Тип", "Аудиторія", "Посилання",
    "Дата створення", "Дата заходу", "Статус"
]

_auth_initialized = False
_active_sheet_id = GOOGLE_SHEET_ID


def get_active_sheet_id() -> str:
    """Return the current active spreadsheet ID (may differ from config if auto-created)."""
    return _active_sheet_id or GOOGLE_SHEET_ID


def _init_auth_files():
    """Write env variables to auth files once per process.

    Always overwrites existing files on first call to ensure
    that environment variables (e.g. on Railway) take precedence
    over any files that may exist in the working directory.
    """
    global _auth_initialized
    if _auth_initialized:
        return
    _auth_initialized = True

    for env_var, filename in [("GOOGLE_CREDENTIALS", "credentials.json"),
                              ("GOOGLE_TOKEN", "token.json")]:
        data = os.environ.get(env_var)
        if data:
            with open(filename, "w") as f:
                f.write(data)


def get_creds():
    _init_auth_files()

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                logger.error(
                    "Не вдалося оновити Google токен: %s\n"
                    "Можливі причини:\n"
                    "1. OAuth consent screen в Google Cloud Console в режимі 'Testing' "
                    "(refresh token дійсний лише 7 днів)\n"
                    "2. Токен було відкликано\n"
                    "Рішення: згенеруйте новий token.json локально та оновіть "
                    "змінну GOOGLE_TOKEN на Railway", e
                )
                raise
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


def upload_petition_to_drive(file_path: str) -> str:
    try:
        creds = get_creds()
        service = build("drive", "v3", credentials=creds)
        file_metadata = {"name": os.path.basename(file_path), "parents": [GDRIVE_FOLDER_ID]}
        media = MediaFileUpload(file_path,
                                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        file = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()
        file_id = file.get('id')
        web_view_link = file.get('webViewLink')

        if file_id:
            permission = {'type': 'anyone', 'role': 'reader'}
            service.permissions().create(fileId=file_id, body=permission).execute()
            print(f"Файл {file_id} зроблено публічно доступним для читання.")
        return web_view_link
    except HttpError as error:
        logger.error(f"Помилка при завантаженні клопотання: {error}")
        return None
    except Exception as error:
        logger.error(f"Несподівана помилка при завантаженні клопотання: {error}")
        return None


def _create_spreadsheet(creds) -> str:
    """Create a new Google Sheet with headers in the Drive folder."""
    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Create spreadsheet
    spreadsheet = sheets_service.spreadsheets().create(body={
        "properties": {"title": "Клопотання — статус"},
        "sheets": [{
            "properties": {"title": "Клопотання"},
        }]
    }).execute()
    new_id = spreadsheet['spreadsheetId']
    sheet_id = spreadsheet['sheets'][0]['properties']['sheetId']
    logger.info(f"Створено нову таблицю: {new_id}")

    # Add headers
    sheets_service.spreadsheets().values().update(
        spreadsheetId=new_id,
        range="'Клопотання'!A1",
        valueInputOption='RAW',
        body={'values': [SHEET_HEADERS]}
    ).execute()

    # Format header row: bold + light grey background
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=new_id,
        body={"requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0, "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)"
            }
        }]}
    ).execute()

    # Move to Drive folder
    if GDRIVE_FOLDER_ID:
        try:
            drive_service.files().update(
                fileId=new_id,
                addParents=GDRIVE_FOLDER_ID,
                removeParents='root',
                fields='id, parents'
            ).execute()
        except HttpError as e:
            logger.warning(f"Не вдалося перемістити таблицю в папку: {e}")

    # Make publicly accessible
    try:
        drive_service.permissions().create(
            fileId=new_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
    except HttpError as e:
        logger.warning(f"Не вдалося зробити таблицю публічною: {e}")

    logger.info(
        f"НОВА ТАБЛИЦЯ СТВОРЕНА!\n"
        f"ID: {new_id}\n"
        f"Посилання: https://docs.google.com/spreadsheets/d/{new_id}/edit\n"
        f"Оновіть змінну GOOGLE_SHEET_ID на Railway цим значенням: {new_id}"
    )
    return new_id


def _ensure_spreadsheet(creds):
    """Check if the spreadsheet exists and is accessible. Create if not."""
    global _active_sheet_id

    if _active_sheet_id:
        try:
            service = build("sheets", "v4", credentials=creds)
            service.spreadsheets().get(
                spreadsheetId=_active_sheet_id
            ).execute()
            return _active_sheet_id
        except HttpError as e:
            logger.warning(
                f"Таблиця {_active_sheet_id} недоступна (status={e.resp.status}). "
                f"Створюю нову..."
            )
        except Exception as e:
            logger.warning(f"Помилка доступу до таблиці: {e}. Створюю нову...")

    # Create new spreadsheet
    new_id = _create_spreadsheet(creds)
    _active_sheet_id = new_id
    return new_id


def append_row_to_google_sheet(data_row: list):
    try:
        creds = get_creds()
        sheet_id = _ensure_spreadsheet(creds)
        if not sheet_id:
            logger.error("Не вдалося отримати або створити таблицю.")
            return

        service = build("sheets", "v4", credentials=creds)
        logger.info(f"Спроба додати рядок до таблиці {sheet_id}: {data_row}")

        # Get the first sheet name to use explicitly in the range
        spreadsheet_meta = service.spreadsheets().get(
            spreadsheetId=sheet_id
        ).execute()
        sheets = spreadsheet_meta.get('sheets', [])
        if not sheets:
            logger.error("Таблиця не містить жодного аркуша.")
            return

        first_sheet = sheets[0]
        sheet_title = first_sheet['properties']['title']
        tab_id = first_sheet['properties']['sheetId']
        logger.info(f"Перший аркуш: '{sheet_title}' (sheetId={tab_id})")

        # 1. Append data using explicit sheet name
        append_result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{sheet_title}'!A1",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': [data_row]}
        ).execute()
        logger.info(f"Успішно додано рядок: {append_result}")

        # 2. Get the row number for formatting
        updated_range = append_result.get('updates', {}).get('updatedRange', '')
        if not updated_range or '!' not in updated_range:
            logger.warning(f"Не вдалося отримати updatedRange: {append_result}")
            return

        row_part = updated_range.split('!')[1].split(':')[0]
        row_number = int(''.join(filter(str.isdigit, row_part)))
        logger.info(f"Доданий рядок: {row_number}")

        # 3. Format row with red background ("not ready")
        formatting_request = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": tab_id,
                            "startRowIndex": row_number - 1,
                            "endRowIndex": row_number
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {
                                    "red": 1.0, "green": 0.6, "blue": 0.6
                                }
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                }
            ]
        }

        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body=formatting_request
        ).execute()
        logger.info(f"Рядок {row_number} успішно відформатовано.")

    except HttpError as error:
        logger.error(f"Помилка при роботі з Google Таблицею: {error}")
        logger.error(f"Деталі: status={error.resp.status}, content={error.content.decode()}")
    except Exception as error:
        logger.error(f"Несподівана помилка при роботі з Google Таблицею: {error}", exc_info=True)