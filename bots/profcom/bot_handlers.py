import os
import random
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile

from ai_processor import get_structured_data_from_ai
from docx_processor import create_petition
from google_services import upload_petition_to_drive, append_row_to_google_sheet, get_active_sheet_id
from validator import validate_petition_data
from config import GOOGLE_SHEET_ID
from bot_content import ZEROV_SONNETS
from chat_notifications import add_chat, remove_chat, is_chat_subscribed, get_all_chats

logger = logging.getLogger(__name__)


class PetitionCreation(StatesGroup):
    choosing_template_type = State()
    waiting_for_details = State()


type_selection_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Клопотання на одноразову аудиторію")],
        [KeyboardButton(text="Клопотання на аудиторію протягом семестру")],
        [KeyboardButton(text="Клопотання на звільнення від занять")],
        [KeyboardButton(text="Приклади клопотань")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

PETITION_TYPES = {
    "Клопотання на одноразову аудиторію": {
        "template": "template_onetime.docx",
        "type": "onetime"
    },
    "Клопотання на аудиторію протягом семестру": {
        "template": "template_long.docx",
        "type": "longterm"
    },
    "Клопотання на звільнення від занять": {
        "template": "template_exemption.docx",
        "type": "exemption"
    }
}

PETITION_TYPE_DISPLAY = {
    "onetime": "Одноразова аудиторія",
    "longterm": "Аудиторія на семестр",
    "exemption": "Звільнення від занять",
}

ONETIME_EXAMPLE = (
    "**Приклад запиту:**\n"
    "`Потрібна 215 аудиторія у 4 корпусі на 25 жовтня 2025 року "
    "з 14:50 до 18:00 для проведення репетиції акустичного вечора. "
    "Відповідальні: члени проєктного відділу Колегії та профкому студентів "
    "- Шкіль Анастасія та Лось Анастасія.`\n\n"
    "**Що потрібно вказати:**\n"
    "1. Номер аудиторії та корпус\n"
    "2. Дату проведення та час (початок і кінець)\n"
    "3. Назву заходу\n"
    "4. Відповідальних (посада та ПІБ)\n"
    "5. Інститут (бажано, але не обов'язково)"
)

EXEMPTION_EXAMPLE = (
    "**Приклад запиту:**\n"
    "`Потрібно звільнити від занять Роксолану Петришин (АР-34) "
    "10 травня 2025 року для участі у фестивалі Весна Політехніки 2025.`\n\n"
    "**Що потрібно вказати:**\n"
    "1. ПІБ студентів та їхні групи\n"
    "2. Дату звільнення\n"
    "3. Назву заходу (причину)\n\n"
    "Інститут та директора бот визначить автоматично за групою студента."
)

LONGTERM_EXAMPLE = (
    "**Приклад запиту:**\n"
    "`Потрібна 321 аудиторія в головному корпусі щовівторка протягом "
    "осіннього семестру 2025/2026 року з 16:25 до 20:50 для засідань "
    "Колегії та профбюро студентів ІКТА. Відповідальна: Голова Колегії "
    "та профбюро студентів ІКТА - Ірина Грицай.\n"
    "Інститут що робить клопотання - ІКТА (цей рядок не обов'язковий)`\n\n"
    "**Що потрібно вказати:**\n"
    "1. Номер аудиторії та корпус\n"
    "2. День тижня та семестр (осінній/весняний)\n"
    "3. Час (початок і кінець)\n"
    "4. Назву заходу\n"
    "5. Відповідальних (посада та ПІБ)\n"
    "6. Інститут (який робить клопотання, бажано але не обов'язково)"
)


async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    start_message = (
        "Привіт! Я допоможу створити клопотання.\n"
        "Обери тип клопотання:"
    )
    await message.answer(start_message, reply_markup=type_selection_keyboard)
    await state.set_state(PetitionCreation.choosing_template_type)


async def send_sonnet_handler(message: Message):
    sonnet = random.choice(ZEROV_SONNETS)
    await message.answer(f"Тримай трохи класики від Зерова:\n{sonnet}")


async def notify_handler(message: Message):
    """Toggle notifications for the current chat (groups AND private)."""
    chat_id = message.chat.id
    if is_chat_subscribed(chat_id):
        remove_chat(chat_id)
        await message.answer("Сповіщення вимкнено для цього чату.")
    else:
        add_chat(chat_id)
        await message.answer("Сповіщення увімкнено для цього чату.\n"
                             "Сюди приходитимуть оповіщення від усіх ботів.")


def _format_user_mention(user) -> str:
    """Format a Telegram user mention."""
    full_name = user.full_name or "Невідомий"
    if user.username:
        return f"{full_name} (@{user.username})"
    return f"[{full_name}](tg://user?id={user.id})"


def _build_notification_text(petition_type: str, structured_data: dict,
                             drive_link: str, sheet_link: str,
                             user_mention: str) -> str:
    """Build a notification message about a new petition."""
    type_display = PETITION_TYPE_DISPLAY.get(petition_type, petition_type)

    lines = [f"📋 *Нове клопотання*\n", f"*Тип:* {type_display}"]

    if petition_type == "onetime":
        room = structured_data.get("auditorium_number", "")
        building = structured_data.get("building_info", "")
        event = structured_data.get("event_name", "")
        date = structured_data.get("event_date", "")
        start = structured_data.get("start_time", "")
        end = structured_data.get("end_time", "")
        if room and building:
            lines.append(f"*Аудиторія:* {room}, корпус {building}")
        if event:
            lines.append(f"*Захід:* {event}")
        if date:
            lines.append(f"*Дата:* {date}")
        if start and end:
            lines.append(f"*Час:* {start} — {end}")

    elif petition_type == "longterm":
        room = structured_data.get("auditorium_number", "")
        building = structured_data.get("building_info", "")
        event = structured_data.get("event_name", "")
        period = structured_data.get("period_and_time_description", "")
        if room and building:
            lines.append(f"*Аудиторія:* {room}, корпус {building}")
        if event:
            lines.append(f"*Захід:* {event}")
        if period:
            lines.append(f"*Період:* {period}")

    elif petition_type == "exemption":
        students = structured_data.get("students", [])
        event = structured_data.get("event_name", "")
        date = structured_data.get("event_date", "")
        if students:
            student_strs = [f"{s.get('name', '')} ({s.get('group', '')})" for s in students]
            lines.append(f"*Студенти:* {', '.join(student_strs)}")
        if event:
            lines.append(f"*Захід:* {event}")
        if date:
            lines.append(f"*Дата:* {date}")

    lines.append("")
    lines.append(f"[📄 Клопотання]({drive_link})")
    lines.append(f"[📊 Таблиця зі статусом]({sheet_link})")
    lines.append("")
    lines.append(f"*Створив:* {user_mention}")

    return "\n".join(lines)


async def send_error_notification(bot: Bot, user, user_text: str,
                                  error: Exception) -> None:
    """Send error details to all subscribed chats so the secretary is aware."""
    chats = get_all_chats()
    if not chats:
        return

    user_mention = _format_user_mention(user)
    text = (
        f"⚠️ *Помилка при створенні клопотання*\n\n"
        f"*Користувач:* {user_mention}\n"
        f"*ID:* `{user.id}`\n\n"
        f"*Текст запиту:*\n{user_text}\n\n"
        f"*Помилка:* `{error}`"
    )

    for chat_id in chats:
        try:
            await bot.send_message(
                chat_id, text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.warning(f"Не вдалося надіслати сповіщення про помилку в чат {chat_id}: {e}")


async def send_chat_notifications(bot: Bot, petition_type: str,
                                  structured_data: dict, drive_link: str,
                                  sheet_link: str, user) -> None:
    """Send petition notification to all subscribed chats."""
    chats = get_all_chats()
    if not chats:
        return

    user_mention = _format_user_mention(user)
    text = _build_notification_text(petition_type, structured_data,
                                    drive_link, sheet_link, user_mention)

    for chat_id in chats:
        try:
            await bot.send_message(
                chat_id, text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.warning(f"Не вдалося надіслати сповіщення в чат {chat_id}: {e}")
            if "chat not found" in str(e).lower() or "bot was kicked" in str(e).lower():
                remove_chat(chat_id)
                logger.info(f"Чат {chat_id} видалено зі списку сповіщень.")


async def template_type_chosen_handler(message: Message, state: FSMContext):
    choice = message.text

    # Send example files
    if choice == "Приклади клопотань":
        example_files = [
            ("examples/example_onetime.docx", "Приклад: одноразова аудиторія"),
            ("examples/example_longterm.docx", "Приклад: аудиторія на семестр"),
            ("examples/example_exemption.docx", "Приклад: звільнення від занять"),
        ]
        for file_path, caption in example_files:
            if os.path.exists(file_path):
                await message.answer_document(
                    FSInputFile(file_path),
                    caption=caption
                )
        await message.answer(
            "Обери тип клопотання:",
            reply_markup=type_selection_keyboard
        )
        return

    if choice not in PETITION_TYPES:
        await message.answer(
            "Будь ласка, обери один з варіантів на кнопках.",
            reply_markup=type_selection_keyboard
        )
        return

    petition_info = PETITION_TYPES[choice]
    await state.update_data(
        template_name=petition_info["template"],
        petition_type=petition_info["type"],
        user_choice_text=choice
    )

    prompt_message = "Тепер надішли всю інформацію одним повідомленням.\n\n"

    examples = {
        "onetime": ONETIME_EXAMPLE,
        "longterm": LONGTERM_EXAMPLE,
        "exemption": EXEMPTION_EXAMPLE,
    }
    prompt_message += examples.get(petition_info["type"], ONETIME_EXAMPLE)

    await message.answer(
        prompt_message,
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(PetitionCreation.waiting_for_details)


async def process_details_handler(message: Message, state: FSMContext):
    user_data = await state.get_data()
    template_name = user_data.get("template_name")
    petition_type = user_data.get("petition_type")

    processing_msg = await message.answer("Аналізую запит...")

    try:
        structured_data = get_structured_data_from_ai(message.text, petition_type)
    except Exception as e:
        await processing_msg.edit_text(
            "Виникла помилка, ми сповістили про ваше клопотання секретаря, "
            "завітайте в 235 ауд Головного навчального корпусу."
        )
        try:
            await send_error_notification(message.bot, message.from_user, message.text, e)
        except Exception as notify_err:
            logger.error(f"Помилка при надсиланні сповіщення про помилку: {notify_err}")
        return

    is_valid, error_message = validate_petition_data(structured_data, petition_type)

    if not is_valid:
        await processing_msg.edit_text(
            f"Не вдалося створити клопотання: {error_message}\n\n"
            f"Надішли запит ще раз з усією необхідною інформацією.",
            parse_mode="Markdown"
        )
        try:
            await send_error_notification(
                message.bot, message.from_user, message.text,
                Exception(f"Валідація не пройшла: {error_message}")
            )
        except Exception as notify_err:
            logger.error(f"Помилка при надсиланні сповіщення про помилку: {notify_err}")
        return

    # Institute hint only for non-exemption types
    if petition_type != "exemption" and not structured_data.get("institute"):
        await message.answer(
            "Інститут не вказано - це не критично, але для звітності краще вказувати."
        )

    file_path = None
    try:
        await processing_msg.edit_text("Генерую документ...")
        file_path = create_petition(template_name, structured_data)

        await processing_msg.edit_text("Завантажую на Google Drive...")
        drive_link = upload_petition_to_drive(file_path)

        if drive_link:
            sheet_link = f"https://docs.google.com/spreadsheets/d/{get_active_sheet_id()}/edit"

            final_message = (
                f"Клопотання створено!\n\n"
                f"[Клопотання (Google Drive)]({drive_link})\n\n"
                f"[Таблиця зі статусом]({sheet_link})"
            )

            await processing_msg.edit_text(
                final_message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

            # Send notifications to subscribed chats
            try:
                await send_chat_notifications(
                    message.bot, petition_type, structured_data,
                    drive_link, sheet_link, message.from_user
                )
            except Exception as e:
                logger.error(f"Помилка при надсиланні сповіщень: {e}")

            # Log to spreadsheet
            room_num = structured_data.get("auditorium_number", "")
            building_info = structured_data.get("building_info", "")
            if room_num and building_info:
                if building_info.lower().strip() in ('головний', 'гнк'):
                    corpus_str = "гнк"
                else:
                    corpus_str = f"{building_info}-нк"
                full_room_str = f"{room_num}, {corpus_str}"
            else:
                full_room_str = "Звільнення"

            if petition_type in ("onetime", "exemption"):
                event_date_str = structured_data.get("event_date", "")
                date_parts = event_date_str.split()
                short_date = f"{date_parts[0]} {date_parts[1]}" if len(date_parts) >= 2 else event_date_str
            else:
                short_date = "Семестр"

            # For exemption, use institute_name; for others, use abbreviation
            if petition_type == "exemption":
                institute_display = structured_data.get("institute_name", "Не вказано")
            else:
                institute_display = structured_data.get("institute", "Не вказано")

            create_date = datetime.now().strftime("%d.%m.%Y")
            petition_type_display = PETITION_TYPE_DISPLAY.get(petition_type, petition_type)

            data_to_log = [
                institute_display,
                petition_type_display,
                full_room_str,
                drive_link,
                create_date,
                short_date,
                ""
            ]
            try:
                append_row_to_google_sheet(data_to_log)
            except Exception as e:
                print(f"Помилка при логуванні в таблицю: {e}")

        else:
            await processing_msg.edit_text(
                "Виникла помилка, ми сповістили про ваше клопотання секретаря, "
                "завітайте в 235 ауд Головного навчального корпусу."
            )
            try:
                await send_error_notification(
                    message.bot, message.from_user, message.text,
                    Exception("Не вдалося завантажити на Google Drive")
                )
            except Exception as notify_err:
                logger.error(f"Помилка при надсиланні сповіщення про помилку: {notify_err}")

    except Exception as e:
        await processing_msg.edit_text(
            "Виникла помилка, ми сповістили про ваше клопотання секретаря, "
            "завітайте в 235 ауд Головного навчального корпусу."
        )
        try:
            await send_error_notification(message.bot, message.from_user, message.text, e)
        except Exception as notify_err:
            logger.error(f"Помилка при надсиланні сповіщення про помилку: {notify_err}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"Тимчасовий файл {file_path} видалено.")

    await state.clear()


def register_handlers(dp: Dispatcher):
    dp.message.register(start_handler, CommandStart())
    dp.message.register(send_sonnet_handler, Command("sonnet"))
    dp.message.register(notify_handler, Command("notify"))
    dp.message.register(template_type_chosen_handler, PetitionCreation.choosing_template_type)
    dp.message.register(process_details_handler, PetitionCreation.waiting_for_details)
