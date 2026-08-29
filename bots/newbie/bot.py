"""
Telegram-бот інформації для вступників НУЛП (Львівська Політехніка).
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from handlers.main_menu import show_main_menu, start_command
from handlers.bachelor import BACHELOR_SECTIONS, handle_bachelor_menu, handle_bachelor_section
from handlers.master import MASTER_SECTIONS, handle_master_menu, handle_master_section
from handlers.university_life import handle_uni_life_menu, handle_self_gov_detail
from handlers.institutes_menu import handle_institutes_menu, handle_institute_detail
from handlers.contacts import handle_contacts
from handlers.dormitories import handle_dormitories

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник команди /help."""
    text = (
        "\U0001f4a1 *Як користуватися ботом:*\n\n"
        "\U0001f539 /start \\- Головне меню\n"
        "\U0001f539 /help \\- Ця довідка\n\n"
        "Використовуйте кнопки меню для навігації\\!"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Центральний роутер для всіх inline-кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # Головне меню
    if data == "back_main":
        await show_main_menu(query)
        return

    # Меню розділів
    if data == "menu_uni_life":
        await handle_uni_life_menu(query)
        return

    if data == "menu_dorms":
        await handle_dormitories(query)
        return

    if data == "menu_bachelor":
        await handle_bachelor_menu(query)
        return

    if data == "menu_master":
        await handle_master_menu(query)
        return

    if data == "menu_institutes":
        await handle_institutes_menu(query)
        return

    if data == "menu_contacts":
        await handle_contacts(query)
        return

    # Самоврядування інституту
    if data.startswith("selfgov_"):
        await handle_self_gov_detail(query, data[8:])
        return

    # Деталі інституту
    if data.startswith("inst_"):
        await handle_institute_detail(query, data[5:])
        return

    # Розділи бакалаврату
    if data in BACHELOR_SECTIONS:
        await handle_bachelor_section(query, data)
        return

    # Розділи магістратури
    if data in MASTER_SECTIONS:
        await handle_master_section(query, data)
        return


def main():
    """Запуск бота."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError(
            "BOT_TOKEN не знайдено! Створіть файл .env з BOT_TOKEN=your_token"
        )

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Бот запущено!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
