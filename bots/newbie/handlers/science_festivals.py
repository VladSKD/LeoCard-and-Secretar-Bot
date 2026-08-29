"""Обробник кнопки 'Наукові фестини'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import escape_md


# Шаблон — замініть текст та посилання на актуальні
SCIENCE_TEXT = (
    "\U0001f52c *Наукові фестини*\n\n"
    "Текст про наукові фестини, заходи, дати проведення\\.\n\n"
    "Текст з описом подій та можливостей для учасників\\.\n\n"
    "\U0001f517 Посилання: https://lpnu\\.ua/"
)


def build_back_to_main_keyboard():
    """Кнопка назад до головного меню."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")]
    ])


async def handle_science_festivals(query):
    """Показує інформацію про наукові фестини."""
    keyboard = build_back_to_main_keyboard()
    await query.edit_message_text(
        SCIENCE_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
