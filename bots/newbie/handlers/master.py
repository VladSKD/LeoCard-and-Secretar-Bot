"""Обробник кнопки 'Вступ до Магістратури'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import escape_md


# Розділи меню магістратури: (callback_data, назва кнопки, опис, посилання)
MASTER_SECTIONS = {
    "mast_programs": {
        "button": "Програми фахових випробувань",
        "text": (
            "Програми фахових випробувань для вступу на магістратуру "
            "за різними спеціальностями. Детальна інформація за посиланням."
        ),
        "link": "https://lpnu.ua/",
    },
    "mast_enrollment": {
        "button": "Зарахування на навчання",
        "text": (
            "Порядок зарахування на навчання за освітнім ступенем магістра: "
            "необхідні документи, терміни та умови."
        ),
        "link": "https://lpnu.ua/",
    },
    "mast_cost": {
        "button": "Вартість навчання",
        "text": (
            "Вартість навчання на контрактній формі для магістерських програм. "
            "Детальна інформація за посиланням."
        ),
        "link": "https://lpnu.ua/",
    },
    "mast_exams": {
        "button": "Іспити для вступу",
        "text": (
            "Перелік іспитів для вступу на магістратуру, "
            "розклад та вимоги до складання."
        ),
        "link": "https://lpnu.ua/",
    },
    "mast_stages": {
        "button": "Основні етапи вступної кампанії",
        "text": (
            "Ключові дати та етапи вступної кампанії на магістратуру: "
            "реєстрація, подання документів, іспити та зарахування."
        ),
        "link": "https://lpnu.ua/",
    },
    "mast_state": {
        "button": "Державне замовлення",
        "text": (
            "Інформація про державне замовлення на магістратуру: "
            "кількість місць, умови та спеціальності."
        ),
        "link": "https://lpnu.ua/",
    },
    "mast_creative": {
        "button": "Розклад творчих конкурсів",
        "text": (
            "Розклад творчих конкурсів для вступу на магістратуру "
            "за спеціальностями, що потребують творчого іспиту."
        ),
        "link": "https://lpnu.ua/",
    },
}


def build_master_keyboard():
    """Клавіатура розділів магістратури."""
    keyboard = []
    keys = list(MASTER_SECTIONS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for k in keys[i:i+2]:
            section = MASTER_SECTIONS[k]
            row.append(InlineKeyboardButton(section["button"], callback_data=k))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def build_back_to_master_keyboard():
    """Кнопка назад до меню магістратури."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до меню магістратури", callback_data="menu_master")]
    ])


async def handle_master_menu(query):
    """Показує меню вступу до магістратури."""
    text = "\U0001f4da *Вступ до Магістратури*\n\nОберіть розділ, щоб отримати детальну інформацію:"
    keyboard = build_master_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def handle_master_section(query, section_key):
    """Показує деталі обраного розділу магістратури."""
    section = MASTER_SECTIONS.get(section_key)
    if not section:
        await query.edit_message_text("Розділ не знайдено\\.")
        return

    text = (
        f"\U0001f393 *{escape_md(section['button'])}*\n\n"
        f"{escape_md(section['text'])}\n\n"
        f"\U0001f517 {escape_md(section['link'])}"
    )
    keyboard = build_back_to_master_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
