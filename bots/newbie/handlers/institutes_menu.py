"""Обробник кнопки 'Наші Інститути'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from institutes import INSTITUTES
from utils import escape_md

INSTITUTES_PER_ROW = 2


def build_institutes_keyboard():
    """Клавіатура зі списком інститутів + кнопка назад."""
    keyboard = []
    row = []
    for key, inst in INSTITUTES.items():
        btn = InlineKeyboardButton(
            f"{inst['emoji']} {inst['short']}",
            callback_data=f"inst_{key}",
        )
        row.append(btn)
        if len(row) == INSTITUTES_PER_ROW:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def get_institutes_list_text():
    """Формує текст зі списком інститутів."""
    lines = [
        "\U0001f3e2 *Інститути Львівської Політехніки*\n",
    ]
    for key, inst in INSTITUTES.items():
        name = escape_md(inst["name"])
        lines.append(f"{inst['emoji']} *{inst['short']}* \\- {name}")
    lines.append(
        "\n\U0001f447 Натисніть на назву, аби дізнатись контакти та більше інформації"
    )
    return "\n".join(lines)


def get_institute_detail(key):
    """Детальна інформація про інститут."""
    inst = INSTITUTES[key]

    specs = "\n".join(f"  \U0001f539 {escape_md(s)}" for s in inst["specialties"])
    deps = "\n".join(f"  \U0001f538 {escape_md(d)}" for d in inst["departments"])

    text = (
        f"{inst['emoji']} *{inst['short']} \\- {escape_md(inst['name'])}*\n"
        f"\n"
        f"\U0001f4cb *Про інститут:*\n"
        f"{escape_md(inst['description'])}\n"
        f"\n"
        f"\U0001f4da *Спеціальності:*\n"
        f"{specs}\n"
        f"\n"
        f"\U0001f3e0 *Кафедри:*\n"
        f"{deps}\n"
        f"\n"
        f"\U0001f4cd *Деканат:* {escape_md(inst['dean'])}\n"
        f"\U0001f4de *Телефон:* {escape_md(inst['phone'])}\n"
        f"\U0001f310 *Сайт:* {escape_md(inst['website'])}\n"
        f"\U0001f4e8 *Подача документів:* {escape_md(inst['admission_info'])}\n"
        f"\n"
        f"\U0001f517 [Перейти на сайт інституту]({escape_md(inst['website'])})"
    )
    return text


def build_back_to_institutes_keyboard():
    """Кнопка назад до списку інститутів."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до списку інститутів", callback_data="menu_institutes")]
    ])


async def handle_institutes_menu(query):
    """Показує список інститутів."""
    text = get_institutes_list_text()
    keyboard = build_institutes_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


async def handle_institute_detail(query, inst_key):
    """Показує деталі конкретного інституту."""
    if inst_key not in INSTITUTES:
        await query.edit_message_text("Інститут не знайдено\\.")
        return
    text = get_institute_detail(inst_key)
    keyboard = build_back_to_institutes_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
