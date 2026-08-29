"""Обробник кнопки 'Гуртожитки'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import escape_md


DORMS_TEXT = (
    "\U0001f3e0 *Гуртожитки*\n\n"
    "Інформація про гуртожитки Львівської Політехніки: "
    "поселення, умови проживання, контакти\\.\n\n"
    "\U0001f4cd *Адреса:* вул\\. Професорська, 1\n\n"
    "\U0001f4de *Контакти:* \\+380 \\(XX\\) XXX\\-XX\\-XX\n\n"
    "\U0001f4dd *Як поселитися:*\n"
    "1\\. Подати заяву на поселення\n"
    "2\\. Отримати направлення\n"
    "3\\. Оформити документи\n\n"
    "\U0001f517 Детальніше: https://lpnu\\.ua/"
)


def build_back_to_main_keyboard():
    """Кнопка назад до головного меню."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")]
    ])


async def handle_dormitories(query):
    """Показує інформацію про гуртожитки."""
    keyboard = build_back_to_main_keyboard()
    await query.edit_message_text(
        DORMS_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
