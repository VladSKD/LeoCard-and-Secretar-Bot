"""Обробник кнопки 'Порахувати конкурсний бал'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import escape_md


# Шаблон — замініть текст та посилання на актуальні
SCORE_TEXT = (
    "\U0001f9ee *Порахувати конкурсний бал*\n\n"
    "Текст з поясненням як порахувати конкурсний бал\\.\n\n"
    "Текст з формулою розрахунку та коефіцієнтами\\.\n\n"
    "\U0001f517 Посилання: https://lpnu\\.ua/"
)


def build_back_to_main_keyboard():
    """Кнопка назад до головного меню."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")]
    ])


async def handle_competition_score(query):
    """Показує інформацію про розрахунок конкурсного балу."""
    keyboard = build_back_to_main_keyboard()
    await query.edit_message_text(
        SCORE_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
