"""Обробник кнопки 'Вступ до Бакалаврату'."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import escape_md


# Розділи меню бакалаврату: (callback_data, назва кнопки, опис, посилання)
BACHELOR_SECTIONS = {
    "bach_rules": {
        "button": "Правила прийому до НУЛП",
        "text": (
            "Правила прийому визначають умови та порядок зарахування "
            "на навчання до Львівської політехніки. Ознайомтесь із повним "
            "текстом правил прийому за посиланням нижче."
        ),
        "link": "https://lpnu.ua/",
    },
    "bach_enrollment": {
        "button": "Зарахування на навчання",
        "text": (
            "Інформація про порядок зарахування, необхідні документи "
            "та терміни подання заяв на навчання за освітнім ступенем бакалавра."
        ),
        "link": "https://lpnu.ua/",
    },
    "bach_cost": {
        "button": "Вартість навчання",
        "text": (
            "Вартість навчання на контрактній формі для різних спеціальностей. "
            "Детальна інформація за посиланням нижче."
        ),
        "link": "https://lpnu.ua/",
    },
    "bach_subjects": {
        "button": "Перелік конкурсних предметів, коефіцієнтів оцінок та творчих конкурсів",
        "text": (
            "Перелік вагових коефіцієнтів оцінок предметів національного "
            "мультипредметного тесту та творчих конкурсів. "
            "Детальна інформація за посиланням."
        ),
        "link": "https://lpnu.ua/",
    },
    "bach_specialties": {
        "button": "Перелік освітніх ступенів та спеціальностей, ліцензійні обсяги, нормативні терміни навчання",
        "text": (
            "Повний перелік спеціальностей, ліцензійні обсяги набору "
            "та нормативні терміни навчання за кожною спеціальністю."
        ),
        "link": "https://lpnu.ua/",
    },
    "bach_stages": {
        "button": "Етапи вступної кампанії",
        "text": (
            "Основні дати та етапи вступної кампанії: реєстрація, подання документів, "
            "конкурсний відбір та зарахування."
        ),
        "link": "https://lpnu.ua/",
    },
    "bach_motivation": {
        "button": "Мотиваційні листи",
        "text": (
            "Вимоги до мотиваційного листа, приклади та рекомендації "
            "щодо його написання для вступу на бакалаврат."
        ),
        "link": "https://lpnu.ua/",
    },
    "bach_creative": {
        "button": "Творчі конкурси",
        "text": (
            "Інформація про творчі конкурси для вступу на окремі спеціальності: "
            "розклад, вимоги та порядок проведення."
        ),
        "link": "https://lpnu.ua/",
    },
}


def build_bachelor_keyboard():
    """Клавіатура розділів бакалаврату."""
    keyboard = []
    keys = list(BACHELOR_SECTIONS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for k in keys[i:i+2]:
            section = BACHELOR_SECTIONS[k]
            row.append(InlineKeyboardButton(section["button"], callback_data=k))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("\U0001f519 Назад до головного меню", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def build_back_to_bachelor_keyboard():
    """Кнопка назад до меню бакалаврату."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Назад до меню бакалаврату", callback_data="menu_bachelor")]
    ])


async def handle_bachelor_menu(query):
    """Показує меню вступу до бакалаврату."""
    text = "\U0001f33f *Вступ до Бакалаврату*\n\nОберіть розділ, щоб отримати детальну інформацію:"
    keyboard = build_bachelor_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def handle_bachelor_section(query, section_key):
    """Показує деталі обраного розділу бакалаврату."""
    section = BACHELOR_SECTIONS.get(section_key)
    if not section:
        await query.edit_message_text("Розділ не знайдено\\.")
        return

    text = (
        f"\U0001f4d6 *{escape_md(section['button'])}*\n\n"
        f"{escape_md(section['text'])}\n\n"
        f"\U0001f517 {escape_md(section['link'])}"
    )
    keyboard = build_back_to_bachelor_keyboard()
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
