"""Обробник кнопки 'Контакти приймальної комісії'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


CONTACTS_TEXT = (
    "\U0001f4de *Контакти приймальної комісії НУЛП*\n\n"
    "\U0001f4cd *Адреса:* вул\\. С\\. Бандери, 12, м\\. Львів, 79013\n"
    "\U0001f4de *Телефон:* \\+38 \\(032\\) 258\\-25\\-03\n"
    "\U0001f4e7 *Email:* pk@lpnu\\.ua\n"
    "\U0001f310 *Сайт:* [lpnu\\.ua/pk](https://lpnu\\.ua/pk)\n\n"
    "\U0001f552 *Графік роботи:*\n"
    "Пн\\-Пт: 9:00 \\- 17:00\n"
    "Сб: 10:00 \\- 14:00\n"
    "Нд: вихідний"
)


def build_back_to_main_keyboard():
    """Кнопка назад до головного меню."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")]
    ])


async def handle_contacts(query):
    """Показує контакти приймальної комісії."""
    keyboard = build_back_to_main_keyboard()
    await query.edit_message_text(
        CONTACTS_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
