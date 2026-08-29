from datetime import datetime, date
import re


def get_current_academic_info():
    today = date.today()
    current_year = today.year
    if today.month >= 9:
        return f"{current_year}/{current_year + 1}"
    else:
        return f"{current_year - 1}/{current_year}"


def get_current_semester():
    """Return 'осіннього' or 'весняного' based on current month."""
    month = date.today().month
    if 9 <= month <= 12 or month == 1:
        return "осіннього"
    return "весняного"


def parse_time(time_str: str):
    if not time_str:
        return None
    # Handle various time formats: "14:50", "14.50", "1450"
    cleaned = time_str.strip().replace('.', ':')
    try:
        return datetime.strptime(cleaned, '%H:%M').time()
    except (ValueError, TypeError):
        return None


def validate_petition_data(data: dict, petition_type: str) -> (bool, str):
    if not data:
        return False, "Не вдалося розпізнати запит. Спробуй перефразувати, будь ласка."

    required_fields = {
        "onetime": [
            "auditorium_number", "building_info", "event_name",
            "event_date", "start_time", "end_time", "responsible_persons"
        ],
        "longterm": [
            "auditorium_number", "building_info", "event_name",
            "period_and_time_description", "responsible_persons"
        ],
        "exemption": [
            "students", "event_date", "event_name"
        ]
    }

    missing_fields = [
        field for field in required_fields.get(petition_type, [])
        if not data.get(field)
    ]

    if missing_fields:
        error_map = {
            "auditorium_number": "номер аудиторії",
            "building_info": "корпус",
            "event_name": "назву заходу",
            "event_date": "дату проведення",
            "start_time": "час початку",
            "end_time": "час закінчення",
            "responsible_persons": "відповідальних осіб (з посадою)",
            "period_and_time_description": "період та час проведення (день тижня, семестр, час)",
            "students": "список студентів (ПІБ та група)",
            "director_info": "директора інституту (посада та ПІБ)",
            "institute_name": "повну назву інституту"
        }
        missing_friendly = [error_map.get(f, f) for f in missing_fields]
        return False, f"Не вистачає: **{', '.join(missing_friendly)}**. Спробуй додати цю інформацію."

    # Auto-add year to date if missing (onetime and exemption)
    if petition_type in ("onetime", "exemption"):
        date_str = data.get("event_date", "")
        if date_str and not re.search(r'\b(20\d{2})\b', date_str):
            current_year = datetime.now().year
            # If date already ends with "року", insert year before it
            if 'року' in date_str:
                date_str = date_str.replace('року', f'{current_year} року')
            else:
                date_str = f"{date_str.strip()} {current_year} року"
            data["event_date"] = date_str
            print(f"Автоматично додано рік: {data['event_date']}")

        # Ensure date ends with "року"
        date_str = data.get("event_date", "")
        if date_str and not date_str.strip().endswith("року"):
            data["event_date"] = f"{date_str.strip()} року"

    # Validate time format for onetime
    if petition_type == "onetime":
        start = data.get("start_time", "")
        end = data.get("end_time", "")
        # Normalize time: remove "год", spaces, replace . with :
        for field in ("start_time", "end_time"):
            t = data.get(field, "")
            t = t.replace("год", "").replace(".", ":").strip()
            # Ensure HH:MM format
            if re.match(r'^\d{1,2}:\d{2}$', t):
                data[field] = t
            elif re.match(r'^\d{3,4}$', t):
                # Handle "1450" -> "14:50"
                t = t.zfill(4)
                data[field] = f"{t[:2]}:{t[2:]}"

    return True, None
