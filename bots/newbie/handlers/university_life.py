"""Обробник кнопки 'Що є цікавого в університеті'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from institutes import INSTITUTES
from utils import escape_md

INSTITUTES_PER_ROW = 2

# Посилання на Linktree університету — замініть на актуальне
LINKTREE_URL = "https://linktr.ee/"

UNI_LIFE_TEXT = (
    "\U0001f3d3 *Що є цікавого в університеті*\n\n"
    "Тут зібрана інформація від студентів про життя в університеті: "
    "гуртки, клуби, заходи, можливості та багато іншого\\!\n\n"
    "\U0001f517 *Більше інформації:*\n"
    f"{escape_md(LINKTREE_URL)}\n\n"
    "\U0001f3e2 *Студентське самоврядування інститутів*\n\n"
    "Оберіть інститут, щоб дізнатися про його "
    "студентське самоврядування:"
)

# Посилання на самоврядування кожного інституту — заповніть актуальними
SELF_GOV_LINKS = {
    "iadu": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "iard": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ibib": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "igdg": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "igsn": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "inem": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "iesk": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ikte": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ikni": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ikta": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "imit": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ipmt": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ippt": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ippo": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "imfn": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "istr": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
    "ihht": {"telegram": "https://t.me/", "instagram": "https://instagram.com/"},
}


def build_uni_life_keyboard():
    """Клавіатура зі списком інститутів для самоврядування."""
    keyboard = []
    row = []
    for key, inst in INSTITUTES.items():
        btn = InlineKeyboardButton(
            f"{inst['emoji']} {inst['short']}",
            callback_data=f"selfgov_{key}",
        )
        row.append(btn)
        if len(row) == INSTITUTES_PER_ROW:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def get_self_gov_detail(key):
    """Формує текст із посиланнями на самоврядування інституту."""
    inst = INSTITUTES[key]
    links = SELF_GOV_LINKS.get(key, {})

    tg = links.get("telegram", "https://t.me/")
    ig = links.get("instagram", "https://instagram.com/")

    text = (
        f"{inst['emoji']} *Самоврядування {inst['short']}*\n"
        f"{escape_md(inst['name'])}\n\n"
        f"\U0001f4e2 *Соціальні мережі:*\n\n"
        f"\u2708\ufe0f Telegram: {escape_md(tg)}\n"
        f"\U0001f4f7 Instagram: {escape_md(ig)}\n"
    )
    return text


def build_back_to_uni_life_keyboard():
    """Кнопка назад до вибору самоврядування."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад", callback_data="menu_uni_life")]
    ])


async def handle_uni_life_menu(query):
    """Показує інформацію про університетське життя та вибір самоврядування."""
    keyboard = build_uni_life_keyboard()
    await query.edit_message_text(
        UNI_LIFE_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


async def handle_self_gov_detail(query, inst_key):
    """Показує соцмережі самоврядування обраного інституту."""
    if inst_key not in INSTITUTES:
        await query.edit_message_text("Інститут не знайдено\\.")
        return
    text = get_self_gov_detail(inst_key)
    keyboard = build_back_to_uni_life_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
