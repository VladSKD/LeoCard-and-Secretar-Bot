import logging
import os
import io
import sys
import json
import re
from datetime import datetime

from dotenv import load_dotenv

# --- Імпорти ---
from services.ocr import OCRService
from services.pdf import PDFService
from services.validators import Validators

from services import google_services
from utils.parsers import normalize_date, is_valid_lpnu_email, is_valid_full_name, parse_residency_extract
from utils.helpers import image_to_bytes

load_dotenv()

from telegram import BotCommand, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    PicklePersistence,
)
from config import BotConfig, GoogleConfig, FileNames, Messages, Buttons

bot_config = BotConfig.from_env()
google_config = GoogleConfig()
fn = FileNames()
msg = Messages()
btn = Buttons()

TELEGRAM_BOT_TOKEN = bot_config.bot_token
GOOGLE_ROOT_FOLDER_ID = bot_config.google_root_folder_id
PAYMENT_URL = bot_config.payment_url
ADMIN_CHAT_ID = bot_config.admin_chat_id
SAMPLE_FORM_PATH = bot_config.sample_form_path
INSTRUCTION_PATH = bot_config.instruction_path
PERSISTENCE_FILEPATH = bot_config.persistence_path

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

if not all([TELEGRAM_BOT_TOKEN, GOOGLE_ROOT_FOLDER_ID]):
    sys.exit("КРИТИЧНА ПОМИЛКА: Не всі змінні середовища налаштовано!")


def ensure_google_auth_on_startup() -> None:
    try:
        creds = google_services.get_credentials()
        if not creds: raise RuntimeError("Немає кредо.")
        logger.info("Google Auth: ОК.")
    except Exception as e:
        logger.error(f"Google Auth Error: {e}")
        sys.exit("Зупинка через помилку Google Auth.")



# --- СТАНИ ---
(
    SELECT_LEVEL, SELECT_ASSISTANCE, ASK_PREVIOUS_CARD, AWAITING_PASSPORT_FRONT,
    AWAITING_PASSPORT_BACK, AWAITING_TAX_ID_PHOTO, AWAITING_FULL_NAME,
    AWAITING_FULL_NAME_CONFIRMATION, AWAITING_STUDENT_ID, AWAITING_POLITECH_EMAIL,
    AWAITING_PHONE_NUMBER, AWAITING_PHOTO_3X4, AWAITING_RESIDENCY_EXTRACT,
    AWAITING_FILLED_FORMS, AWAITING_PAYMENT_CHOICE, AWAITING_PAYMENT_RECEIPT,
    AWAITING_STUDENT_VALID_UNTIL, AWAITING_CERTIFICATE_PHOTO,
) = range(18)


# --- KLAVIATURY (Helper) ---
def get_back_keyboard(other_buttons=None):
    if other_buttons is None:
        return ReplyKeyboardMarkup([[btn.back]], resize_keyboard=True)
    return ReplyKeyboardMarkup(other_buttons + [[btn.back]], resize_keyboard=True, one_time_keyboard=True)


def _reject(text: str):
    """Per-state rejection: returns handler that sends a specific hint message."""
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(text)
    return handler


# --- HELP ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ Бот для подачі документів на ЛеоКарт.\n\n"
        "Команди:\n"
        "/start — розпочати подачу документів\n"
        "/help — ця довідка\n"
        "/cancel — скасувати поточну заявку\n\n"
        "Якщо виникли проблеми — пишіть:\n"
        "@relimusii або @hmelnykk"
    )


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Розпочати подачу документів"),
        BotCommand("help", "Допомога та контакти"),
        BotCommand("cancel", "Скасувати поточну заявку"),
    ])


# --- START FLOW ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    reply_keyboard = [[btn.bachelor], [btn.master]]
    await update.message.reply_text(msg.greeting,
                                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True,
                                                                     resize_keyboard=True))
    return SELECT_LEVEL


async def select_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["level"] = update.message.text
    question = "Чи був у вас учнівський ЛеоКарт?" if update.message.text == btn.bachelor else "Чи був у вас студентський ЛеоКарт?"
    await update.message.reply_text(question, reply_markup=get_back_keyboard([[btn.yes, btn.no]]))
    return ASK_PREVIOUS_CARD


async def ask_previous_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == btn.yes:
        await update.message.reply_text(msg.renew_card, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    await update.message.reply_text(msg.ask_assistance,
                                    reply_markup=get_back_keyboard([[btn.help_me], [btn.do_myself]]))
    return SELECT_ASSISTANCE


async def select_assistance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == btn.do_myself:
        await update.message.reply_text(msg.self_service, reply_markup=ReplyKeyboardRemove())
        try:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(SAMPLE_FORM_PATH, "rb"),
                                            caption="Бланк заяви")
        except Exception as e:
            logger.error(f"Failed to send sample form '{SAMPLE_FORM_PATH}': {e}")
        try:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(INSTRUCTION_PATH, "rb"),
                                            caption="Інструкція із заповнення")
        except Exception as e:
            logger.error(f"Failed to send instruction '{INSTRUCTION_PATH}': {e}")
        return ConversationHandler.END

    await update.message.reply_text(msg.start_assistance.format(photo_hint=msg.photo_hint),
                                    reply_markup=get_back_keyboard())
    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id,
                                     photo=open("examples/id_front_example.jpg", "rb"), caption="Приклад")
    except:
        pass
    return AWAITING_PASSPORT_FRONT


async def handle_passport_front(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    file_buffer = io.BytesIO()
    await photo_file.download_to_memory(file_buffer)
    context.user_data[fn.passport_front] = file_buffer

    file_buffer.seek(0)
    try:
        front_data = OCRService.extract_id_front(file_buffer)
    except Exception as e:
        logger.error(f"OCR extract_id_front failed: {e}")
        front_data = {}
    context.user_data.setdefault("passport_data", {}).update({k: v for k, v in front_data.items() if v})

    if not front_data.get("record_no"):
        await update.message.reply_text(
            "⚠️ Не вдалося автоматично розпізнати УНЗР. Фото збережено, продовжуємо далі.",
            reply_markup=get_back_keyboard())

    await update.message.reply_text("Тепер надішліть фото зворотної сторони.", reply_markup=get_back_keyboard())
    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id,
                                     photo=open("examples/id_back_example.jpg", "rb"))
    except:
        pass
    return AWAITING_PASSPORT_BACK


async def handle_passport_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    file_buffer = io.BytesIO()
    await photo_file.download_to_memory(file_buffer)
    context.user_data[fn.passport_back] = file_buffer

    file_buffer.seek(0)
    try:
        back_data = OCRService.extract_id_back(file_buffer)
    except Exception as e:
        logger.error(f"OCR extract_id_back failed: {e}")
        back_data = {}
    context.user_data.setdefault("passport_data", {}).update({k: v for k, v in back_data.items() if v})

    await update.message.reply_text(msg.ask_residency, reply_markup=get_back_keyboard())
    return AWAITING_RESIDENCY_EXTRACT


async def handle_residency_extract(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.document or update.message.document.mime_type != "application/pdf":
        await update.message.reply_text("Будь ласка, надішліть саме PDF файл витягу.", reply_markup=get_back_keyboard())
        return AWAITING_RESIDENCY_EXTRACT

    file = await update.message.document.get_file()
    pdf_buffer = io.BytesIO()
    await file.download_to_memory(pdf_buffer)
    context.user_data[fn.residency_extract] = pdf_buffer

    pdf_buffer.seek(0)
    try:
        text = PDFService.extract_text(pdf_buffer)
        extracted = parse_residency_extract(text)
    except Exception as e:
        logger.error(f"Residency extract parsing failed: {e}")
        extracted = {}
    passport_data = context.user_data.setdefault("passport_data", {})

    for key, value in extracted.items():
        if value:
            if key not in passport_data or passport_data[key] is None:
                passport_data[key] = value
            if key in ["full_name", "residency_address", "city", "street", "building_flat"]:
                passport_data[key] = value

    if not passport_data.get("tax_id"):
        await update.message.reply_text("Не знайдено РНОКПП. Надішліть фото коду.", reply_markup=get_back_keyboard())
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open("examples/tin_example.jpg", "rb"))
        except:
            pass
        return AWAITING_TAX_ID_PHOTO

    full_name = passport_data.get("full_name")
    if full_name:
        await update.message.reply_text(f"Ми розпізнали ПІБ: {full_name}. Все правильно?",
                                        reply_markup=get_back_keyboard([[btn.yes, btn.no]]))
        return AWAITING_FULL_NAME_CONFIRMATION
    else:
        await update.message.reply_text("Не вдалося розпізнати ПІБ. Введіть вручну.", reply_markup=get_back_keyboard())
        return AWAITING_FULL_NAME


async def handle_tax_id_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    file_buffer = io.BytesIO()
    await photo_file.download_to_memory(file_buffer)
    context.user_data[fn.tax_id] = file_buffer

    full_name = context.user_data.setdefault("passport_data", {}).get("full_name")
    if full_name:
        await update.message.reply_text(f"ПІБ: {full_name}. Все правильно?",
                                        reply_markup=get_back_keyboard([[btn.yes, btn.no]]))
        return AWAITING_FULL_NAME_CONFIRMATION
    else:
        await update.message.reply_text("Введіть ваше ПІБ.", reply_markup=get_back_keyboard())
        return AWAITING_FULL_NAME


async def handle_full_name_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == btn.yes:
        await update.message.reply_text(msg.ask_politech_email, reply_markup=get_back_keyboard())
        return AWAITING_POLITECH_EMAIL
    else:
        await update.message.reply_text("Введіть ПІБ ще раз.", reply_markup=get_back_keyboard())
        return AWAITING_FULL_NAME


async def handle_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not is_valid_full_name(text):
        await update.message.reply_text(
            "Введіть повне ПІБ (лише літери, мінімум 2 слова, до 100 символів).",
            reply_markup=get_back_keyboard())
        return AWAITING_FULL_NAME
    context.user_data.setdefault("passport_data", {})["full_name"] = text
    await update.message.reply_text(msg.ask_politech_email, reply_markup=get_back_keyboard())
    return AWAITING_POLITECH_EMAIL


async def handle_politech_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip().lower()
    if len(email) > 100 or not is_valid_lpnu_email(email):
        await update.message.reply_text(msg.invalid_email, reply_markup=get_back_keyboard())
        return AWAITING_POLITECH_EMAIL
    context.user_data.setdefault("passport_data", {})["politech_email"] = email
    await update.message.reply_text(msg.ask_phone, reply_markup=get_back_keyboard())
    return AWAITING_PHONE_NUMBER


async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip().replace(" ", "")
    if not re.fullmatch(r'^\+?380\d{9}$', phone):
        await update.message.reply_text("Невірний номер (+380...).", reply_markup=get_back_keyboard())
        return AWAITING_PHONE_NUMBER
    context.user_data["phone_number"] = phone
    await update.message.reply_text(msg.ask_photo_3x4, reply_markup=get_back_keyboard())
    return AWAITING_PHOTO_3X4  # <--- Виправлено тут


async def handle_photo_3x4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    file_buffer = io.BytesIO()
    await photo_file.download_to_memory(file_buffer)
    context.user_data[fn.photo_3x4] = file_buffer
    
    # Додаємо кнопку "В мене нема студентського" до клавіатури
    keyboard = get_back_keyboard([[btn.no_student_id]])
    await update.message.reply_text("Надішліть фото студентського.", reply_markup=keyboard)
    
    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id,
                                     photo=open("examples/student_id_example.png", "rb"))
    except:
        pass
    return AWAITING_STUDENT_ID


async def handle_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    file_buffer = io.BytesIO()
    await photo_file.download_to_memory(file_buffer)
    context.user_data[fn.student_id] = file_buffer

    # Прізвище для перевірки (fuzzy search)
    passport_data = context.user_data.get("passport_data", {})
    full_name = passport_data.get("full_name", "")
    surname = full_name.split()[0] if full_name else None

    file_buffer.seek(0)
    try:
        ocr_result = OCRService.extract_student_valid_until(file_buffer, expected_surname=surname)
    except Exception as e:
        logger.error(f"OCR extract_student_valid_until failed: {e}")
        ocr_result = {}

    valid_until = ocr_result.get("date")
    surname_matched = ocr_result.get("surname_matched")

    # Якщо прізвище не зійшлося (тільки коли OCR працював і прізвище не None)
    if surname and surname_matched is not None and not surname_matched:
        await update.message.reply_text(
            f"⚠️ Увага! На фото студентського квитка не знайдено прізвища **{surname}**.\n"
            "Переконайтеся, що ви надсилаєте **свій** студентський квиток і фото чітке.\n\n"
            "Спробуйте ще раз.",
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
        return AWAITING_STUDENT_ID

    if valid_until:
        context.user_data["student_card_valid_until"] = valid_until
        await update.message.reply_text(f"Дійсний до: {valid_until}. Надішліть 1 сторінку заяви.",
                                        reply_markup=get_back_keyboard())
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id,
                                         photo=open("./examples/document_page_1_example.jpg", "rb"))
        except:
            pass
        context.user_data["filled_forms"] = []
        return AWAITING_FILLED_FORMS
    else:
        await update.message.reply_text("Введіть дату дійсності студентського (DD.MM.YYYY):",
                                        reply_markup=get_back_keyboard())
        return AWAITING_STUDENT_VALID_UNTIL


async def handle_no_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Надішліть фото вашої довідки (або іншого документа-замінника).", reply_markup=get_back_keyboard())
    
    # Надсилаємо приклад, як ви і просили
    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open("examples/no_student_id_doc.jpg", "rb"))
    except:
        pass

    return AWAITING_CERTIFICATE_PHOTO

async def handle_certificate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    file_buffer = io.BytesIO()
    await photo_file.download_to_memory(file_buffer)
    
    # Зберігаємо на місце студентського квитка
    context.user_data[fn.student_id] = file_buffer

    # Питаємо дату
    await update.message.reply_text(
        "Документ збережено!\nВведіть дату дійсності вашого документа у форматі ДД.ММ.РРРР:",
        reply_markup=get_back_keyboard()
    )
    return AWAITING_STUDENT_VALID_UNTIL

async def handle_student_valid_until(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    norm = normalize_date(update.message.text.strip())
    if not norm:
        await update.message.reply_text("Невірний формат. Введіть ДД.ММ.РРРР.", reply_markup=get_back_keyboard())
        return AWAITING_STUDENT_VALID_UNTIL
    try:
        dt = datetime.strptime(norm, "%d.%m.%Y").date()
        today = datetime.today().date()
        if dt < today:
            await update.message.reply_text("Ця дата вже минула. Введіть актуальну дату.",
                                            reply_markup=get_back_keyboard())
            return AWAITING_STUDENT_VALID_UNTIL
        if dt.year > today.year + 10:
            await update.message.reply_text("Дата занадто далека. Перевірте та введіть коректну дату.",
                                            reply_markup=get_back_keyboard())
            return AWAITING_STUDENT_VALID_UNTIL
    except ValueError:
        await update.message.reply_text("Невірний формат. Введіть ДД.ММ.РРРР.", reply_markup=get_back_keyboard())
        return AWAITING_STUDENT_VALID_UNTIL
    context.user_data["student_card_valid_until"] = norm
    await update.message.reply_text("Надішліть 1 сторінку заяви.", reply_markup=get_back_keyboard())
    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id,
                                     photo=open("./examples/document_page_1_example.jpg", "rb"))
    except:
        pass
    context.user_data["filled_forms"] = []
    return AWAITING_FILLED_FORMS


async def handle_filled_forms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    file_buffer = io.BytesIO()
    await photo_file.download_to_memory(file_buffer)
    forms = context.user_data.setdefault("filled_forms", [])

    if len(forms) == 0:
        forms.append(file_buffer)
        await update.message.reply_text("Отримано 1 сторінку. Надішліть 2 сторінку.", reply_markup=get_back_keyboard())
        
        # --- Додано відправку прикладу 2 сторінки ---
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id,
                                         photo=open("./examples/document_page_2_example.jpg", "rb"))
        except:
            pass
        # ---------------------------------------------
            
        return AWAITING_FILLED_FORMS
    else:
        forms.append(file_buffer)
        await update.message.reply_text("Вже оплатили?", reply_markup=get_back_keyboard([[btn.yes], [btn.no]]))
        return AWAITING_PAYMENT_CHOICE


async def handle_payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == btn.yes:
        await update.message.reply_text("Надішліть квитанцію.", reply_markup=get_back_keyboard())
    else:
        await update.message.reply_text(f"Оплатіть тут: {PAYMENT_URL}\nНадішліть квитанцію.",
                                        reply_markup=get_back_keyboard())
    return AWAITING_PAYMENT_RECEIPT


async def handle_payment_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_buffer = io.BytesIO()
    mimetype = "image/jpeg"
    if update.message.document:
        if update.message.document.mime_type != "application/pdf":
            await update.message.reply_text("Тільки PDF або фото.", reply_markup=get_back_keyboard())
            return AWAITING_PAYMENT_RECEIPT
        file = await update.message.document.get_file()
        mimetype = "application/pdf"
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
    else:
        await update.message.reply_text("Надішліть файл.", reply_markup=get_back_keyboard())
        return AWAITING_PAYMENT_RECEIPT

    await file.download_to_memory(file_buffer)
    context.user_data[fn.payment_receipt] = file_buffer
    context.user_data["payment_receipt_mimetype"] = mimetype

    # Validation Check
    file_buffer.seek(0)
    if not Validators.validate_payment_receipt(file_buffer, context.user_data, mimetype):
        await update.message.reply_text("Прізвище не знайдено в квитанції. Спробуйте ще раз.",
                                        reply_markup=get_back_keyboard())
        return AWAITING_PAYMENT_RECEIPT

    await update.message.reply_text("Обробка...", reply_markup=ReplyKeyboardRemove())

    # --- Processing & Upload Logic ---
    try:
        all_files = {
            fn.passport_front: context.user_data.get(fn.passport_front),
            fn.passport_back: context.user_data.get(fn.passport_back),
            fn.student_id: context.user_data.get(fn.student_id),
            fn.tax_id: context.user_data.get(fn.tax_id),
            fn.residency_extract: context.user_data.get(fn.residency_extract),
            fn.photo_3x4: context.user_data.get(fn.photo_3x4),
            fn.form_page_1: context.user_data.get("filled_forms", [None])[0],
            fn.form_page_2: context.user_data.get("filled_forms", [None, None])[1],
            fn.payment_receipt: context.user_data.get(fn.payment_receipt),
        }

        # Seek всіх буферів на початок перед створенням PDF
        for key, buf in all_files.items():
            if buf:
                buf.seek(0)

        combined_pdf = PDFService.create_combined_pdf(all_files, mimetype)
        photo_3x4 = all_files.get(fn.photo_3x4)  # Вже оброблено

        p_data = context.user_data.get("passport_data", {})
        rec_no = p_data.get("record_no", f"u{update.effective_user.id}")
        f_name = p_data.get("full_name", f"u{update.effective_user.id}")

        drive = google_services.get_drive_service()
        sheets = google_services.get_sheets_client()

        root = google_services.get_or_create_folder(drive, google_config.parties_root_folder_name,
                                                    GOOGLE_ROOT_FOLDER_ID)
        party_folder, party_sheet = google_services.get_or_create_party_folder(drive, sheets, root)

        stud_folder = google_services.get_or_create_folder(drive,
                                                           google_config.student_folder_name_template.format(f_name,
                                                                                                             rec_no),
                                                           party_folder)

        _, pdf_url = google_services.upload_file_to_drive(drive, stud_folder, f"{rec_no}_1.pdf", combined_pdf,
                                                          "application/pdf")

        photo_url = None
        if photo_3x4:
            _, photo_url = google_services.upload_file_to_drive(drive, stud_folder, f"{rec_no}.jpg", photo_3x4,
                                                                "image/jpeg")

        google_services.add_user_to_party_sheet(party_sheet, context.user_data, pdf_url)

        main_root = google_services.get_or_create_folder(drive, google_config.main_documents_folder,
                                                         GOOGLE_ROOT_FOLDER_ID)
        main_ws = google_services.get_or_create_worksheet(google_config.main_database_sheet,
                                                          google_config.main_worksheet_name, main_root)

        stud_folder_link = drive.files().get(fileId=stud_folder, fields='webViewLink',
                                             supportsAllDrives=True).execute().get('webViewLink')
        context.user_data["photo_3x4_link"] = photo_url
        google_services.add_user_to_sheet(main_ws, context.user_data, update.effective_user.id, stud_folder_link)

        await update.message.reply_text("Готово! Документи подано.")

        # Notify shared chats — minimal info only (no links, no personal data).
        try:
            from shared.notifications import get_notification_chats
            now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
            for _cid in get_notification_chats():
                try:
                    await context.bot.send_message(
                        _cid,
                        f"📋 Нова заявка ЛеоКарт\n"
                        f"Студент: {f_name}\n"
                        f"Час: {now_str}",
                    )
                except Exception:
                    pass
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Upload Error: {e}", exc_info=True)
        if ADMIN_CHAT_ID: await context.bot.send_message(ADMIN_CHAT_ID, f"Error: {e}")
        await update.message.reply_text("Сталася помилка при завантаженні.")

    context.user_data.clear()
    return ConversationHandler.END


# --- BACK FUNCTIONS ---
async def back_to_start(update, context):
    return await start(update, context)


async def back_to_level(update, context):
    reply_keyboard = [[btn.bachelor], [btn.master]]
    await update.message.reply_text(msg.greeting,
                                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True,
                                                                     resize_keyboard=True))
    return SELECT_LEVEL


async def back_to_ask_previous(update, context):
    level = context.user_data.get("level", btn.bachelor)
    question = "Чи був у вас учнівський ЛеоКарт?" if level == btn.bachelor else "Чи був у вас студентський ЛеоКарт?"
    await update.message.reply_text(question, reply_markup=get_back_keyboard([[btn.yes, btn.no]]))
    return ASK_PREVIOUS_CARD


async def back_to_select_assistance(update, context):
    await update.message.reply_text(msg.ask_assistance,
                                    reply_markup=get_back_keyboard([[btn.help_me], [btn.do_myself]]))
    return SELECT_ASSISTANCE


async def back_to_passport_front(update, context):
    await update.message.reply_text("Надішліть фото лицьової сторони ID-картки.", reply_markup=get_back_keyboard())
    return AWAITING_PASSPORT_FRONT


async def back_to_passport_back(update, context):
    await update.message.reply_text("Надішліть фото зворотної сторони.", reply_markup=get_back_keyboard())
    return AWAITING_PASSPORT_BACK


async def back_to_residency(update, context):
    await update.message.reply_text(msg.ask_residency, reply_markup=get_back_keyboard())
    return AWAITING_RESIDENCY_EXTRACT


async def back_to_tax_id_or_residency(update, context):
    if not context.user_data.get("passport_data", {}).get("tax_id"):
        await update.message.reply_text("Надішліть фото РНОКПП.", reply_markup=get_back_keyboard())
        return AWAITING_TAX_ID_PHOTO
    return await back_to_residency(update, context)


async def back_to_full_name_confirm(update, context):
    full_name = context.user_data.get("passport_data", {}).get("full_name")
    if full_name:
        await update.message.reply_text(f"ПІБ: {full_name}. Все вірно?",
                                        reply_markup=get_back_keyboard([[btn.yes, btn.no]]))
        return AWAITING_FULL_NAME_CONFIRMATION
    else:
        await update.message.reply_text("Введіть ПІБ.", reply_markup=get_back_keyboard())
        return AWAITING_FULL_NAME


async def back_to_email(update, context):
    await update.message.reply_text(msg.ask_politech_email, reply_markup=get_back_keyboard())
    return AWAITING_POLITECH_EMAIL


async def back_to_phone(update, context):
    await update.message.reply_text(msg.ask_phone, reply_markup=get_back_keyboard())
    return AWAITING_PHONE_NUMBER


async def back_to_photo_3x4(update, context):
    await update.message.reply_text(msg.ask_photo_3x4, reply_markup=get_back_keyboard())
    return AWAITING_PHOTO_3X4  # <--- Виправлено тут (було X, має бути X, це константа)


async def back_to_student_id(update, context):
    keyboard = get_back_keyboard([[btn.no_student_id]])
    await update.message.reply_text("Надішліть фото студентського.", reply_markup=keyboard)
    return AWAITING_STUDENT_ID


async def back_to_forms(update, context):
    context.user_data["filled_forms"] = []
    await update.message.reply_text("Надішліть 1 сторінку заяви.", reply_markup=get_back_keyboard())
    return AWAITING_FILLED_FORMS


async def back_to_payment_choice(update, context):
    await update.message.reply_text("Вже оплатили?", reply_markup=get_back_keyboard([[btn.yes], [btn.no]]))
    return AWAITING_PAYMENT_CHOICE


# --- MAIN ---
async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    ensure_google_auth_on_startup()
    try:
        os.makedirs(os.path.dirname(PERSISTENCE_FILEPATH) or ".", exist_ok=True)
    except:
        pass

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .persistence(PicklePersistence(PERSISTENCE_FILEPATH))
        .post_init(post_init)
        .build()
    )

    back_filter = filters.Regex(f'^{re.escape(btn.back)}$')
    _no_cmd = filters.ALL & ~filters.COMMAND

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_LEVEL: [
                MessageHandler(filters.Regex(f'^({btn.bachelor}|{btn.master})$'), select_level),
                MessageHandler(_no_cmd, _reject("Оберіть рівень освіти кнопкою.")),
            ],
            ASK_PREVIOUS_CARD: [
                MessageHandler(back_filter, back_to_start),
                MessageHandler(filters.Regex(f'^({btn.yes}|{btn.no})$'), ask_previous_card),
                MessageHandler(_no_cmd, _reject("Оберіть 'Так' або 'Ні'.")),
            ],
            SELECT_ASSISTANCE: [
                MessageHandler(back_filter, back_to_level),
                MessageHandler(filters.Regex(f'^({btn.help_me}|{btn.do_myself})$'), select_assistance),
                MessageHandler(_no_cmd, _reject("Оберіть варіант кнопкою.")),
            ],
            AWAITING_PASSPORT_FRONT: [
                MessageHandler(back_filter, back_to_select_assistance),
                MessageHandler(filters.PHOTO, handle_passport_front),
                MessageHandler(_no_cmd, _reject("Надішліть фото лицьової сторони ID-картки.")),
            ],
            AWAITING_PASSPORT_BACK: [
                MessageHandler(back_filter, back_to_passport_front),
                MessageHandler(filters.PHOTO, handle_passport_back),
                MessageHandler(_no_cmd, _reject("Надішліть фото зворотної сторони ID-картки.")),
            ],
            AWAITING_RESIDENCY_EXTRACT: [
                MessageHandler(back_filter, back_to_passport_back),
                MessageHandler(filters.Document.PDF, handle_residency_extract),
                MessageHandler(_no_cmd, _reject("Надішліть PDF-файл витягу з Дії.")),
            ],
            AWAITING_TAX_ID_PHOTO: [
                MessageHandler(back_filter, back_to_residency),
                MessageHandler(filters.PHOTO, handle_tax_id_photo),
                MessageHandler(_no_cmd, _reject("Надішліть фото РНОКПП.")),
            ],
            AWAITING_FULL_NAME_CONFIRMATION: [
                MessageHandler(back_filter, back_to_tax_id_or_residency),
                MessageHandler(filters.Regex(f'^({btn.yes}|{btn.no})$'), handle_full_name_confirmation),
                MessageHandler(_no_cmd, _reject("Оберіть 'Так' або 'Ні'.")),
            ],
            AWAITING_FULL_NAME: [
                MessageHandler(back_filter, back_to_tax_id_or_residency),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_full_name),
            ],
            AWAITING_POLITECH_EMAIL: [
                MessageHandler(back_filter, back_to_full_name_confirm),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_politech_email),
                MessageHandler(_no_cmd, _reject("Введіть email @lpnu.ua.")),
            ],
            AWAITING_PHONE_NUMBER: [
                MessageHandler(back_filter, back_to_email),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number),
                MessageHandler(_no_cmd, _reject("Введіть номер +380XXXXXXXXX.")),
            ],
            AWAITING_PHOTO_3X4: [
                MessageHandler(back_filter, back_to_phone),
                MessageHandler(filters.PHOTO, handle_photo_3x4),
                MessageHandler(_no_cmd, _reject("Надішліть фото 3x4.")),
            ],
            AWAITING_STUDENT_ID: [
                MessageHandler(back_filter, back_to_photo_3x4),
                MessageHandler(filters.Regex(f'^{re.escape(btn.no_student_id)}$'), handle_no_student_id),
                MessageHandler(filters.PHOTO, handle_student_id),
                MessageHandler(_no_cmd, _reject("Надішліть фото студентського квитка.")),
            ],
            AWAITING_CERTIFICATE_PHOTO: [
                MessageHandler(back_filter, back_to_student_id),
                MessageHandler(filters.PHOTO, handle_certificate_photo),
                MessageHandler(_no_cmd, _reject("Надішліть фото довідки.")),
            ],
            AWAITING_STUDENT_VALID_UNTIL: [
                MessageHandler(back_filter, back_to_student_id),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_student_valid_until),
            ],
            AWAITING_FILLED_FORMS: [
                MessageHandler(back_filter, back_to_student_id),
                MessageHandler(filters.PHOTO, handle_filled_forms),
                MessageHandler(_no_cmd, _reject("Надішліть фото сторінки заяви.")),
            ],
            AWAITING_PAYMENT_CHOICE: [
                MessageHandler(back_filter, back_to_forms),
                MessageHandler(filters.Regex(f'^({btn.yes}|{btn.no})$'), handle_payment_choice),
                MessageHandler(_no_cmd, _reject("Оберіть 'Так' або 'Ні'.")),
            ],
            AWAITING_PAYMENT_RECEIPT: [
                MessageHandler(back_filter, back_to_payment_choice),
                MessageHandler(filters.PHOTO | filters.Document.PDF, handle_payment_receipt),
                MessageHandler(_no_cmd, _reject("Надішліть фото або PDF квитанції.")),
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel), CommandHandler("help", help_command)],
        per_user=True,
        persistent=True,
        name="leocard_main_conv",
    )

    async def error_handler(update, context):
        logger.error(f"Unhandled exception: {context.error}", exc_info=context.error)
        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(ADMIN_CHAT_ID, f"Unhandled error: {context.error}")
            except Exception:
                pass

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_error_handler(error_handler)
    logger.info("Start polling...")
    app.run_polling()


if __name__ == "__main__":
    main()