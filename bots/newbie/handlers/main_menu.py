"""Головне меню бота."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


def build_main_menu_keyboard():
    """Головне меню після /start."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f33f Вступ до Бакалаврату", callback_data="menu_bachelor")],
        [InlineKeyboardButton("\U0001f4da Вступ до Магістратури", callback_data="menu_master")],
        [InlineKeyboardButton("\U0001f3e2 Наші Інститути", callback_data="menu_institutes")],
        [InlineKeyboardButton("\U0001f3d3 Що є цікавого в університеті", callback_data="menu_uni_life")],
        [InlineKeyboardButton("\U0001f3e0 Гуртожитки", callback_data="menu_dorms")],
        [InlineKeyboardButton("\U0001f4de Контакти приймальної комісії", callback_data="menu_contacts")],
    ])


MAIN_MENU_TEXT = (
    "\U0001f3e0 *Головне меню*\n\n"
    "Оберіть потрібну опцію з меню нижче:"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник команди /start."""
    keyboard = build_main_menu_keyboard()
    await update.message.reply_text(
        MAIN_MENU_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def show_main_menu(query):
    """Повернення до головного меню через callback."""
    keyboard = build_main_menu_keyboard()
    await query.edit_message_text(
        MAIN_MENU_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )
