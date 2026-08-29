"""Обробник кнопки 'Колегія та профбюро студентів'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from institutes import INSTITUTES
from utils import escape_md

INSTITUTES_PER_ROW = 2

# Шаблон соцмереж для кожного інституту — вставте свої посилання
COUNCIL_LINKS = {
    "iadu": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "iard": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ibib": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "igdg": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "igsn": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "inem": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "iesk": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ikte": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ikni": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ikta": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "imit": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ipmt": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ippt": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ippo": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "imfn": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "istr": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
    "ihht": {"telegram": "https://t.me/", "instagram": "https://instagram.com/", "tiktok": "https://tiktok.com/@"},
}


def build_councils_keyboard():
    """Клавіатура зі списком інститутів для вибору колегії."""
    keyboard = []
    row = []
    for key, inst in INSTITUTES.items():
        btn = InlineKeyboardButton(
            f"{inst['emoji']} {inst['short']}",
            callback_data=f"council_{key}",
        )
        row.append(btn)
        if len(row) == INSTITUTES_PER_ROW:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def get_council_detail(key):
    """Формує текст із посиланнями на соцмережі колегії інституту."""
    inst = INSTITUTES[key]
    links = COUNCIL_LINKS.get(key, {})

    tg = links.get("telegram", "https://t.me/")
    ig = links.get("instagram", "https://instagram.com/")
    tt = links.get("tiktok", "https://tiktok.com/@")

    text = (
        f"{inst['emoji']} *Колегія та профбюро {inst['short']}*\n"
        f"{escape_md(inst['name'])}\n\n"
        f"\U0001f4e2 *Соціальні мережі:*\n\n"
        f"\u2708\ufe0f Telegram: {escape_md(tg)}\n"
        f"\U0001f4f7 Instagram: {escape_md(ig)}\n"
        f"\U0001f3ac TikTok: {escape_md(tt)}\n"
    )
    return text


def build_back_to_councils_keyboard():
    """Кнопка назад до вибору колегії."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до списку колегій", callback_data="menu_councils")]
    ])


async def handle_councils_menu(query):
    """Показує вибір інституту для перегляду колегії."""
    text = "\U0001f3db *Колегія та профбюро студентів*\n\nОберіть колегію та профбюро вашого інституту:"
    keyboard = build_councils_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def handle_council_detail(query, inst_key):
    """Показує соцмережі колегії обраного інституту."""
    if inst_key not in INSTITUTES:
        await query.edit_message_text("Інститут не знайдено\\.")
        return
    text = get_council_detail(inst_key)
    keyboard = build_back_to_councils_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
