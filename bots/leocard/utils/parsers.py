import re
from datetime import datetime
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# --- існуючі функції залишаю без змін (можеш підставити свої) --- #
def parse_ukrainian_address(full_address: str) -> Dict[str, str]:
    """
    Parse Ukrainian address into components (v5 - Corrected Street Regex)
    """
    result = {"city": "N/A", "street": "N/A", "building_flat": "N/A"}
    if not full_address:
        return result

    # Попередня обробка: видаляємо коми, нормалізуємо пробіли
    address = re.sub(r'[;,]', '', full_address)
    address = re.sub(r'\s+', ' ', address).strip()
    address_lower = address.lower()
    logger.debug(f"Parsing address: {address}")

    # 1. Місто
    if "львів" in address_lower and "місто львів" in address_lower:
        result["city"] = "Львів"
    else:
        city_match = re.search(r'(?:місто|м)\.?\s+([А-Яа-яіїєґІЇЄҐ`\-\']+)', address, re.IGNORECASE)
        if city_match:
            result["city"] = city_match.group(1).strip().title()
        elif "область" in address_lower:
            m = re.search(r'([А-Яа-яіїєґІЇЄҐ`\-\']+)\s+(?:область|обл)', address, re.IGNORECASE)
            if m and "львівська" not in m.group(1).lower():
                result["city"] = m.group(1).strip().title()
            elif "львів" in address_lower:
                result["city"] = "Львів"

    # 2. Вулиця (ВИПРАВЛЕНО: додано (?=...) )
    # Шукаємо "вул." і беремо все до наступного ключового слова ("буд", "кв") АБО до першої окремої цифри
    street_match = re.search(
        r'(вулиця|вул|проспект|просп|площа|пл|бульвар|бул|провулок|пров)\.?\s+([А-Яа-яіїєґІЇЄҐ`\-\'\.\d\s]+?)(?=\s+(?:буд|будинок|б\.?|кв\.?|\d+)|$)',
        address,
        re.IGNORECASE
    )
    if street_match:
        result["street"] = street_match.group(2).strip().rstrip('.').strip().title()

    # 3. Номер будинку та квартири
    building_part = ""
    flat_part = ""

    # Шукаємо "буд X" або "б X"
    b_match = re.search(r'(?:будинок|буд|б)\.?\s*([\d]+[А-Яа-яіїєґІЇЄҐ]?/?\d*[А-Яа-яіїєґІЇЄҐ]?)', address,
                        re.IGNORECASE)
    if b_match:
        building_part = b_match.group(1).strip()
    else:
        # Якщо вулицю було знайдено, шукаємо перше число ПІСЛЯ неї
        if result["street"] != "N/A":
            try:
                # Знаходимо, де закінчилася вулиця
                street_end_index = re.search(re.escape(result["street"]), address, re.IGNORECASE).end()
                # Шукаємо в решті рядка
                search_area = address[street_end_index:]
                num_match = re.search(r'^\s*([\d]+[А-Яа-яіїєґІЇЄҐ]?/?\d*[А-Яа-яіїєґІЇЄҐ]?)', search_area)
                if num_match:
                    building_part = num_match.group(1).strip()
            except AttributeError:
                logger.warning("Could not find street end index, falling back.")

        # Якщо все ще не знайдено, шукаємо число в кінці
        if not building_part:
            num_match_end = re.search(r'([\d]+[А-Яа-яіїєґІЇЄҐ]?/?\d*[А-Яа-яіїєґІЇЄҐ]?)$', address.strip().rstrip(','))
            if num_match_end:
                building_part = num_match_end.group(1).strip()

    # Шукаємо "кв Y"
    f_match = re.search(r'(?:квартира|кв)\.?\s*([\d]+[А-Яа-яіїєґІЇЄҐ]?)', address, re.IGNORECASE)
    if f_match:
        flat_part = f"кв. {f_match.group(1).strip()}"

    # Збираємо результат
    if building_part and flat_part:
        result["building_flat"] = f"{building_part}, {flat_part}"
    elif building_part:
        result["building_flat"] = building_part
    elif flat_part:
        result["building_flat"] = flat_part

    logger.info(
        f"Parsed address '{full_address}' -> City: {result['city']}, Street: {result['street']}, Building/Flat: {result['building_flat']}")
    return result

def normalize_date(date_text: str) -> Optional[str]:
    if not date_text:
        return None
    date_text = date_text.replace('\n', '').replace('\r', '').strip()
    m = re.match(r"^(\d{1,2})[\.\-/](\d{1,2})[\.\-/](\d{4})$", date_text)
    if not m:
        return None
    day, month, year = m.groups()
    try:
        dt = datetime.strptime(f"{int(day):02d}.{int(month):02d}.{year}", "%d.%m.%Y")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return None

def is_valid_full_name(text: str) -> bool:
    """Only Ukrainian/Latin letters, apostrophe, hyphen, space. 2-100 chars, >=2 words, each >=2 chars."""
    if not text or len(text) > 100:
        return False
    words = text.split()
    if len(words) < 2 or any(len(w) < 2 for w in words):
        return False
    return bool(re.match(r"^[А-ЯІЇЄҐа-яіїєґA-Za-z''\-\s]+$", text))


def is_valid_lpnu_email(email: str) -> bool:
    if not email:
        return False
    return bool(re.match(r"^[A-Za-z0-9._%+-]+@lpnu\.ua$", email.strip().lower()))

# --- ОНОВЛЕНА: parse_residency_extract (зберігаємо ім'я функції) --- #
def parse_residency_extract(text: str) -> dict:
    """
    Final robust PDF parser for residency extract (v10)
    — підтримує випадки, коли ключі та значення злиплися або розбиті по рядках.
    — ігнорує "(за наявності)" в ключах.
    """
    result = {}
    text_clean = re.sub(r'\s+', ' ', text.replace('\n', ' ').replace('\r', ' ')).strip()

    # Уніфікуємо лапки/апострофи
    text_clean = text_clean.replace("’", "'")

    # Регулярки для ключів + значень
    patterns = {
        "last_name": r"Прізвище\s+([А-ЯІЇЄҐ][а-яіїєґ'\-]+)",
        "first_name": r"Власне\s+ім['’]я\s+([А-ЯІЇЄҐ][а-яіїєґ'\-]+)",
        "patronymic": r"По\s+батькові\s*(?:\(за наявності\))?\s+([А-ЯІЇЄҐ][а-яіїєґ'\-]+)",
        "date_of_birth": r"Дата\s+народження\s+(\d{2}\.\d{2}\.\d{4})",
        "record_no": r"УНЗР\s*\(за наявності\)\s*([0-9\-]+)",
        "tax_id": r"РНОКПП\s*\(за наявності\)\s*([0-9]{10})",
    }

    for field, pat in patterns.items():
        m = re.search(pat, text_clean)
        if m:
            result[field] = m.group(1).strip()

    # --- Адреса ---
    addr_match = re.search(
        r"Адреса\s+місця\s+проживання.*?(?:\d{2}\.\d{2}\.\d{4}\s+)([А-ЯІЇЄҐа-яіїєґ0-9\s,\.]+?)(?=Витяг\s+сформовано|$)",
        text_clean
    )
    if addr_match:
        address = addr_match.group(1)
        address = re.sub(r'\s+', ' ', address).strip(" ,.")
        result["residency_address"] = address

    # --- Формуємо повне ім’я ---
    if result.get("last_name") and result.get("first_name"):
        pat = result.get("patronymic", "")
        result["full_name"] = f"{result['last_name']} {result['first_name']} {pat}".strip()

    # --- Нормалізація дати ---
    if "date_of_birth" in result:
        norm = normalize_date(result["date_of_birth"])
        if norm:
            result["date_of_birth"] = norm

    # --- Деталізація адреси ---
    if "residency_address" in result:
        result.update(parse_ukrainian_address(result["residency_address"]))

    logger.info(f"Final Residency Extract Parsing Result: {result}")
    return result


