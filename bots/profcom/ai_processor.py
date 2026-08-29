from google import genai
import json
import os
import re
from config import GEMINI_API_KEY

MODELS = ['gemini-2.5-flash', 'gemini-2.0-flash-001']

client = genai.Client(api_key=GEMINI_API_KEY)

# Mapping of NULP institute abbreviations to their group prefixes
INSTITUTE_GROUPS = {
    "ІАДУ": ["УА", "УАПА", "МЕУП", "УААМ", "УАРА"],
    "ІАРД": ["АР", "ВД", "ІП", "РМ", "ДС", "АРМ", "ДЗМ", "АРБС", "АРДФ", "АРМБ", "АРРП", "ДЗЗВ"],
    "ІБІБ": ["БД", "ГБ", "ПБ"],
    "ІГДГ": ["ГД", "ІГ", "ЦЗ", "ГК", "НЗ"],
    "ІППО": ["ПВ", "ПС", "ЖР", "ПЦ"],
    "ІГСН": ["МВ", "СК", "СР", "СЛ", "СЗ", "СТ"],
    "ІЕСК": ["АВ", "АЕ", "ЕЕ", "СЕ", "ТЕ"],
    "ІКНІ": ["ОІ", "ПП", "ВР", "ШІ", "СА", "УП", "РІ", "ВП", "ФЛ", "ПЗ"],
    "ІКТА": ["ІВ", "КБ", "КІ", "ІР"],
    "ІКТЕ": ["АН", "АП", "БІ", "ЕЛ", "ІК", "ІХ", "МН"],
    "ІМІТ": ["АТ", "ЛА", "ЛГ", "МБ", "МЗ", "РП", "ТТ", "УЗ", "ФТ"],
    "ІМФН": ["ПМ", "ФІ", "ПФ", "МІ", "ОМ", "КМ"],
    "ІНЕМ": ["АМ", "МЕ", "МК", "ЕВ", "ФБ", "ЕК", "ОП"],
    "ІППТ": ["КНМС", "КН", "МГ", "ФЗ"],
    "ІПМТ": ["ВС", "ГР", "ІО", "КР", "КС", "ММ", "РГ", "РК", "СП", "ГМ", "ЕРМ", "ДЗ"],
    "ІСТР": ["ГО", "ЕО", "ПІ", "ПТ", "ТУ", "ЦБ"],
    "ІХХТ": ["ХЕ", "ХТ", "БТ", "ТО", "ХР", "НГ"],
}

# Institute info: full name, director (nominative), director in dative for document header
INSTITUTE_INFO = {
    "ІАДУ": {
        "name": "адміністрування, державного управління та професійного розвитку",
        "director_form": "Директору",
        "director_info": "Любомиру ПИЛИПЕНКУ",
    },
    "ІАРД": {
        "name": "архітектури та дизайну",
        "director_form": "Директору",
        "director_info": "Юрію ДИБІ",
    },
    "ІБІБ": {
        "name": "будівництва інфраструктури та безпеки життєдіяльності",
        "director_form": "Директору",
        "director_info": "Зіновію БЛІХАРСЬКОМУ",
    },
    "ІГДГ": {
        "name": "геодезії",
        "director_form": "Директору",
        "director_info": "Ігорю САВЧИНУ",
    },
    "ІППО": {
        "name": "права, психології та інноваційної освіти",
        "director_form": "Директору",
        "director_info": "Володимиру ОРТИНСЬКОМУ",
    },
    "ІГСН": {
        "name": "гуманітарних та соціальних наук",
        "director_form": "Директорці",
        "director_info": "Зоряні КУНЬЧ",
    },
    "ІЕСК": {
        "name": "енергетики та систем керування",
        "director_form": "Директору",
        "director_info": "Андрію МАЛЯРУ",
    },
    "ІКНІ": {
        "name": "комп'ютерних наук та інформаційних технологій",
        "director_form": "Директору",
        "director_info": "Олегу МАТВІЙКІВУ",
    },
    "ІКТА": {
        "name": "комп'ютерних технологій, автоматики та метрології",
        "director_form": "Директору",
        "director_info": "Юрію КОСТІВУ",
    },
    "ІКТЕ": {
        "name": "телекомунікацій, радіоелектроніки та електронної техніки",
        "director_form": "Директору",
        "director_info": "Леоніду ОЗІРКОВСЬКОМУ",
    },
    "ІМІТ": {
        "name": "механічної інженерії та транспорту",
        "director_form": "Директору",
        "director_info": "Юрію РОЙКУ",
    },
    "ІМФН": {
        "name": "прикладної математики та фундаментальних наук",
        "director_form": "Директору",
        "director_info": "Петру ПУКАЧУ",
    },
    "ІНЕМ": {
        "name": "економіки і менеджменту",
        "director_form": "Директору",
        "director_info": "Михайлу ГОНЧАРУ",
    },
    "ІППТ": {
        "name": "просторового планування та перспективних технологій",
        "director_form": "Директору",
        "director_info": "Йосипу ХРОМ'ЯКУ",
    },
    "ІПМТ": {
        "name": "поліграфії та медійних технологій",
        "director_form": "Директорці",
        "director_info": "Лесі СТЕЦІВ",
    },
    "ІСТР": {
        "name": "сталого розвитку ім. В'ячеслава Чорновола",
        "director_form": "Директору",
        "director_info": "Святославу КНЯЗЮ",
    },
    "ІХХТ": {
        "name": "хімії та хімічних технологій",
        "director_form": "Директору",
        "director_info": "Богдану ДЗІНЯКУ",
    },
}

# Reverse mapping: group prefix -> institute
GROUP_TO_INSTITUTE = {}
for inst, groups in INSTITUTE_GROUPS.items():
    for g in groups:
        GROUP_TO_INSTITUTE[g] = inst


def detect_institute_from_groups(students_text: str) -> str | None:
    """Try to detect institute abbreviation from student group codes in text."""
    # Case-insensitive: match both БД-21 and Бд-21 or бд-21
    group_matches = re.findall(r'([А-ЯІЇЄҐа-яіїєґ]{2,4})-\d', students_text)
    for prefix in group_matches:
        upper_prefix = prefix.upper()
        if upper_prefix in GROUP_TO_INSTITUTE:
            return GROUP_TO_INSTITUTE[upper_prefix]
    return None


def fill_institute_and_director(data: dict) -> dict:
    """Auto-fill institute_name, director_form, director_info from student groups."""
    students = data.get("students", [])
    if not students:
        return data

    # Collect all group codes from students
    all_groups_text = " ".join(s.get("group", "") for s in students)
    institute_abbr = detect_institute_from_groups(all_groups_text)

    if institute_abbr and institute_abbr in INSTITUTE_INFO:
        info = INSTITUTE_INFO[institute_abbr]
        data["institute_name"] = info["name"]
        data["director_form"] = info["director_form"]
        data["director_info"] = info["director_info"]

    return data


def read_example_from_file(example_filename: str) -> str:
    try:
        example_path = os.path.join("examples", example_filename)
        with open(example_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Помилка читання файлу-прикладу {example_filename}: {e}")
        return ""


def get_onetime_prompt(user_text: str, example_text: str) -> str:
    return f"""Ти — помічник для створення клопотань на одноразове використання аудиторії.
Проаналізуй запит користувача та витягни дані у форматі JSON.

ІДЕАЛЬНИЙ ПРИКЛАД ГОТОВОГО КЛОПОТАННЯ:
---
{example_text}
---

Запит користувача: "{user_text}"

Витягни з запиту наступні поля та поверни ТІЛЬКИ JSON (без пояснень, без markdown):
{{
    "auditorium_number": "номер аудиторії (тільки цифри, наприклад 215)",
    "building_info": "номер корпусу цифрою (наприклад 4, 18) або 'головний' якщо головний навчальний корпус",
    "event_name": "назва заходу у родовому відмінку (для проведення ЧОГО). Без слів 'проведення' на початку. Наприклад: 'репетиції акустичного вечора', 'засідання Колегії студентів ІКТА'",
    "event_date": "дата у форматі '25 вересня 2025 року'. Завжди додавай рік якщо його немає. Завжди закінчуй словом 'року'",
    "start_time": "час початку у форматі HH:MM (наприклад 14:50)",
    "end_time": "час закінчення у форматі HH:MM (наприклад 18:00)",
    "responsible_persons": "рядок з відповідальними ТОЧНО як потрібно вставити у документ. Формат: 'Посада - Ім'я Прізвище'. Якщо кілька осіб з однаковою посадою: 'члени проєктного відділу Колегії та профкому студентів - Шкіль Анастасія та Лось Анастасія'. Якщо різні посади: 'Голова Колегії та профбюро студентів ІКТА - Ірина Грицай, член проєктного відділу - Андрій Коваль'",
    "institute": "абревіатура інституту (ІАДУ, ІАРД, ІБІБ, ІГДГ, ІППО, ІГСН, ІЕСК, ІКНІ, ІКТА, ІКТЕ, ІМІТ, ІМФН, ІНЕМ, ІППТ, ІПМТ, ІСТР, ІХХТ) або null якщо не вказано"
}}

ВАЖЛИВІ ПРАВИЛА:
1. event_name - у родовому відмінку (для проведення ЧОГО?). НЕ починай зі слова "проведення".
2. event_date - ЗАВЖДИ повний формат з роком: "25 вересня 2025 року". Додай поточний рік якщо не вказано.
3. responsible_persons - поверни як РЯДОК (string), не масив. Це готовий текст для вставки в документ.
4. building_info - тільки цифра корпусу або слово "головний".
5. Не дублюй слова (не "року року", не "проведення проведення").
6. Відповідь - ТІЛЬКИ валідний JSON, без зайвого тексту."""


def get_longterm_prompt(user_text: str, example_text: str) -> str:
    return f"""Ти — помічник для створення клопотань на використання аудиторії протягом семестру.
Проаналізуй запит користувача та витягни дані у форматі JSON.

ІДЕАЛЬНИЙ ПРИКЛАД ГОТОВОГО КЛОПОТАННЯ:
---
{example_text}
---

Запит користувача: "{user_text}"

Витягни з запиту наступні поля та поверни ТІЛЬКИ JSON (без пояснень, без markdown):
{{
    "auditorium_number": "номер аудиторії (тільки цифри, наприклад 321)",
    "building_info": "номер корпусу цифрою (наприклад 4, 18) або 'головний' якщо головний навчальний корпус",
    "event_name": "назва заходу у родовому відмінку (для проведення ЧОГО). Без слів 'проведення' на початку. Наприклад: 'засідань Колегії та профбюро студентів ІКТА', 'репетицій хору'",
    "period_and_time_description": "повний опис періоду та часу. Формат: 'щовівторка протягом осіннього семестру 2025/2026 навчального року з 16:25 год до 20:50 год'. Включає: день тижня, семестр, навчальний рік, час початку та закінчення з 'год'.",
    "responsible_persons": "рядок з відповідальними ТОЧНО як потрібно вставити у документ. Формат: 'Посада - Ім'я Прізвище'. Наприклад: 'Голова Колегії та профбюро студентів ІКТА - Ірина Грицай'",
    "institute": "абревіатура інституту (ІАДУ, ІАРД, ІБІБ, ІГДГ, ІППО, ІГСН, ІЕСК, ІКНІ, ІКТА, ІКТЕ, ІМІТ, ІМФН, ІНЕМ, ІППТ, ІПМТ, ІСТР, ІХХТ) або null якщо не вказано"
}}

ВАЖЛИВІ ПРАВИЛА:
1. event_name - у родовому відмінку (для проведення ЧОГО?). НЕ починай зі слова "проведення".
2. period_and_time_description - повний опис: день тижня + "протягом" + семестр + навч.рік + час. Час у форматі "з HH:MM год до HH:MM год".
3. responsible_persons - поверни як РЯДОК (string), не масив. Це готовий текст для вставки в документ.
4. building_info - тільки цифра корпусу або слово "головний".
5. Семестр: визнач осінній (вересень-січень) чи весняний (лютий-червень) з контексту.
6. Навчальний рік у форматі: 2025/2026.
7. Не дублюй слова.
8. Відповідь - ТІЛЬКИ валідний JSON, без зайвого тексту."""


def get_exemption_prompt(user_text: str, example_text: str) -> str:
    return f"""Ти — помічник для створення клопотань на звільнення студентів від занять.
Проаналізуй запит користувача та витягни дані у форматі JSON.

ІДЕАЛЬНИЙ ПРИКЛАД ГОТОВОГО КЛОПОТАННЯ:
---
{example_text}
---

Запит користувача: "{user_text}"

УВАГА: Інститут та директора НЕ потрібно витягувати — вони визначаються автоматично за групою студента.

Витягни з запиту наступні поля та поверни ТІЛЬКИ JSON (без пояснень, без markdown):
{{
    "event_date": "дата у форматі '10 жовтня 2025'. Завжди додавай рік якщо його немає",
    "event_name": "назва заходу у формі для 'участю у [ЦЕ]' (місцевий відмінок). Наприклад: 'фестивалі «Весна Політехніки 2025»', 'заході «День студента 2025»', 'конференції «Наука і молодь»'",
    "students": [
        {{"name": "Прізвище Ім'я (називний відмінок)", "group": "XX-XX"}}
    ],
    "students_inline": "рядок для вставки у документ (для 1-2 студентів). Родовий відмінок з 'студента/студентки'. Наприклад: 'студентки Лось Анастасії МВ-44', 'студента Коваленка Андрія КН-21 та студентки Петренко Марії КН-22'"
}}

ВАЖЛИВІ ПРАВИЛА:
1. event_name - місцевий відмінок для "участю у [ЦЕ]". Наприклад: "фестивалі", "заході", "конференції".
2. students - масив об'єктів з name (Прізвище Ім'я у НАЗИВНОМУ відмінку) та group. Приклад: {{"name": "Копійка Дар'я", "group": "ПС-210"}}.
3. students_inline - РОДОВИЙ відмінок (КОГО?) з "студента/студентки" + прізвище ім'я + група. Для 2 студентів через "та". Приклад: "студентки Лось Анастасії МВ-44".
4. event_date - НЕ додавай слово "року".
5. Відповідь - ТІЛЬКИ валідний JSON, без зайвого тексту."""


def get_structured_data_from_ai(user_text: str, petition_type: str) -> dict:
    example_filenames = {
        "longterm": "longterm_example.txt",
        "exemption": "exemption_example.txt",
        "onetime": "onetime_example.txt",
    }
    example_filename = example_filenames.get(petition_type, "onetime_example.txt")
    example_text = read_example_from_file(example_filename)

    if not example_text:
        print("Попередження: не вдалося завантажити приклад. Робота без нього може бути неточною.")

    if petition_type == "longterm":
        prompt = get_longterm_prompt(user_text, example_text)
    elif petition_type == "exemption":
        prompt = get_exemption_prompt(user_text, example_text)
    else:
        prompt = get_onetime_prompt(user_text, example_text)

    try:
        response = None
        for model_name in MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                print(f"Використано модель: {model_name}")
                break
            except Exception as model_err:
                if '429' in str(model_err) or 'quota' in str(model_err).lower():
                    print(f"Квота вичерпана для {model_name}, пробую наступну модель...")
                    continue
                raise

        if response is None:
            print("Помилка: всі моделі недоступні (квота вичерпана).")
            return {}

        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        print(f"Відповідь від AI перед парсингом: '{cleaned_response}'")
        if not cleaned_response:
            print("Помилка: AI повернув порожню відповідь.")
            return {}

        data = json.loads(cleaned_response)

        # Auto-fill institute and director for exemption petitions
        if petition_type == "exemption":
            data = fill_institute_and_director(data)

        # Normalize responsible_persons: ensure it's always a usable format
        rp = data.get('responsible_persons')
        if isinstance(rp, list):
            # If AI returned a list despite instructions, convert to string
            parts = []
            for item in rp:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    role = item.get('role', item.get('position', ''))
                    name = item.get('name', '')
                    if role and name:
                        parts.append(f"{role} - {name}")
                    elif name:
                        parts.append(name)
            data['responsible_persons'] = ", ".join(parts) if parts else rp

        return data
    except json.JSONDecodeError as e:
        print(f"Помилка парсингу JSON від AI: {e}")
        return {}
    except Exception as e:
        print(f"Помилка при обробці відповіді від AI: {e}")
        return {}
