import io
import os
import re
import shutil
import cv2
import numpy as np
import pytesseract
from datetime import datetime
from typing import Optional, Dict
import logging

from utils.parsers import normalize_date

logger = logging.getLogger(__name__)

# Auto-detect Tesseract path on Windows
if os.name == 'nt' and not shutil.which('tesseract'):
    _win_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.isfile(_win_path):
        pytesseract.pytesseract.tesseract_cmd = _win_path


def preprocess_for_ocr(img: np.ndarray, sharpen: bool = True) -> np.ndarray:
    """Standard OCR preprocessing"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    if sharpen:
        blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
        gray = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)

    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 10
    )


def normalize_digits(text: str) -> str:
    """Fix common OCR digit mistakes"""
    trans = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5", "B": "8"})
    return text.translate(trans)


class OCRService:
    """Unified OCR extraction service"""

    @staticmethod
    def extract_id_front(image_buffer: io.BytesIO) -> Dict[str, Optional[str]]:
        """Extract gender, DOB, record number from ID front (Robust Gender)"""
        from utils.helpers import bytes_to_image
        import pytesseract

        img = bytes_to_image(image_buffer)

        # Спробуємо кілька варіантів обробки
        images_to_try = [
            preprocess_for_ocr(img, sharpen=True),
            preprocess_for_ocr(img, sharpen=False),
            cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # <--- ВИПРАВЛЕНО TYPO
        ]

        cfg = r'--oem 1 --psm 6'
        gender, dob, record = None, None, None

        for processed in images_to_try:
            raw_text = pytesseract.image_to_string(processed, config=cfg, lang='eng+ukr')
            txt_norm = normalize_digits(raw_text).upper()
            logger.debug(f"OCR Raw Text (ID Front): \n{txt_norm}")

            # --- Стать (більш гнучкий regex) ---
            if not gender:
                if re.search(r'Ч\s*[/І|l1\\]?\s*М', txt_norm):
                    gender = "Чоловіча"
                    logger.info("Gender found: Чоловіча")
                elif re.search(r'Ж\s*[/І|l1\\]?\s*F', txt_norm):
                    gender = "Жіноча"
                    logger.info("Gender found: Жіноча")
            # --- Кінець оновлення ---

            if not dob:
                dob_match = re.search(r'\b(\d{2})[ ./-](\d{2})[ ./-](\d{4})\b', raw_text)
                if dob_match: dob = f"{dob_match.group(1)}.{dob_match.group(2)}.{dob_match.group(3)}"

            if not record:
                rec_match = re.search(r'\b(\d{8}-\d{5})\b', raw_text)
                if rec_match: record = rec_match.group(1)

            if gender and dob and record:
                logger.info("Extracted all fields from ID front.")
                break  # Всі дані знайдено

        logger.info(f"ID Front OCR Result: Gender={gender}, DOB={dob}, Record={record}")
        return {"gender": gender, "date_of_birth": dob, "record_no": record}

    @staticmethod
    def extract_id_back(image_buffer: io.BytesIO) -> Dict[str, Optional[str]]:
        """Extract authority code, issue date, tax ID from ID back (Improved Tax ID OCR)"""
        from utils.helpers import bytes_to_image
        import pytesseract

        img = bytes_to_image(image_buffer)
        # Спробуємо різні методи перед обробки для кращого розпізнавання цифр
        results = {}
        processed_images = [
            preprocess_for_ocr(img, sharpen=False),  # Стандартний
            cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),  # Просто сірий
            cv2.adaptiveThreshold(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 11, 2)  # Інший adaptive threshold
        ]

        tax_id = None
        date_of_issue = None
        authority_code = None

        cfg = r'--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789-./ eng+ukr'  # Додамо whitelist

        for processed in processed_images:
            raw_text = pytesseract.image_to_string(processed, config=cfg, lang='ukr+eng')
            logger.debug(f"OCR Raw Text (ID Back, attempt): \n{raw_text}")

            # РНОКПП (шукаємо 10 цифр біля ключових слів або просто підряд)
            if not tax_id:
                tax_id_match = re.search(r'(?:РНОКПП|RNT?RC)\s*[: ]*(\d{10})', raw_text)
                if tax_id_match:
                    tax_id = tax_id_match.group(1)
                    logger.info(f"Tax ID found on ID back (with keyword): {tax_id}")
                else:
                    # Шукаємо блок з 10 цифр, який НЕ є датою народження чи частиною УНЗР
                    # (УНЗР зазвичай формату РРРРММДД-ХХХХХ)
                    potential_ids = re.findall(r'(?<!\d)(\d{10})(?!\d)', raw_text)
                    for pid in potential_ids:
                        # Проста перевірка, щоб це не було схоже на дату
                        if not re.match(r'(?:19|20)\d{2}\d{2}\d{2}', pid):
                            tax_id = pid
                            logger.info(f"Tax ID found on ID back (10 digits): {tax_id}")
                            break  # Беремо перший знайдений

            # Дата видачі (шукаємо ДД ММ РРРР або ДД.ММ.РРРР)
            if not date_of_issue:
                date_match = re.search(r'(\d{2})[\s.]+(\d{2})[\s.]+(\d{4})', raw_text)
                if date_match:
                    potential_date = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}"
                    # Перевіряємо, чи дата валідна і не майбутня
                    try:
                        dt = datetime.strptime(potential_date, "%d.%m.%Y")
                        if dt <= datetime.now():
                            date_of_issue = potential_date
                            logger.info(f"Issue date found on ID back: {date_of_issue}")
                    except ValueError:
                        pass

            # Орган, що видав (шукаємо 4 цифри окремо)
            if not authority_code:
                # Шукаємо 4 цифри, які НЕ є роком у даті видачі
                auth_matches = re.findall(r'\b(\d{4})\b', raw_text)
                for code in auth_matches:
                    if not date_of_issue or code not in date_of_issue:
                        authority_code = code
                        logger.info(f"Authority code found on ID back: {authority_code}")
                        break

            # Якщо все знайдено, виходимо з циклу
            if tax_id and date_of_issue and authority_code:
                break

        # Якщо РНОКПП так і не знайшли після всіх спроб
        if not tax_id:
            logger.warning("Tax ID was NOT found on ID back after multiple OCR attempts.")

        return {
            "passport_date": date_of_issue,
            "passport_issued_by": authority_code,
            "tax_id": tax_id  # Повертаємо те, що знайшли (може бути None)
        }

    @staticmethod
    def extract_student_valid_until(image_buffer: io.BytesIO, expected_surname: Optional[str] = None) -> Dict[str, Optional[object]]:
        """
        Extract 'Valid Until' date from student card and optionally verify surname.
        Returns: {"date": "DD.MM.YYYY" or None, "surname_matched": bool or None}
        """
        import difflib
        from utils.helpers import bytes_to_image
        from utils.parsers import normalize_date

        img = bytes_to_image(image_buffer)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)

        images_to_try = [
            preprocess_for_ocr(img, sharpen=True),
            gray_resized,
            cv2.threshold(gray_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        ]

        uk_months = {
            "січня": "01", "лютого": "02", "березня": "03", "квітня": "04",
            "травня": "05", "червня": "06", "липня": "07", "серпня": "08",
            "вересня": "09", "жовтня": "10", "листопада": "11", "грудня": "12",
            "черв": "06", "лип": "07", "серп": "08", "верес": "09", "жовт": "10"
        }

        cfg = r'--oem 1 --psm 6'
        found_date = None
        all_text = ""

        for processed_img in images_to_try:
            text = pytesseract.image_to_string(processed_img, lang='ukr+eng', config=cfg)
            all_text += " " + text

            text_lower = text.lower()
            for wrong, right in uk_months.items():
                if wrong in text_lower:
                    text_lower = text_lower.replace(wrong, f".{right}.")

            dates = re.findall(r"(\d{1,2})[.\-/ ]+(\d{1,2})[.\-/ ]+(\d{2,4})", text_lower)

            today = datetime.today().date()
            future_dates = []

            for d, m, y in dates:
                if len(y) == 2: y = "20" + y
                candidate_str = f"{d}.{m}.{y}"
                norm_date = normalize_date(candidate_str)

                if norm_date:
                    try:
                        dt = datetime.strptime(norm_date, "%d.%m.%Y").date()
                        if dt >= today and dt.year < today.year + 10:
                            future_dates.append(dt)
                    except ValueError:
                        pass

            if future_dates:
                found_date = max(future_dates).strftime("%d.%m.%Y")
                break

        if found_date:
            logger.info(f"Extracted student card valid until: {found_date}")
        else:
            logger.warning("No *future* date found on student card.")

        # Surname matching
        surname_matched = None
        if expected_surname:
            surname_upper = expected_surname.upper()
            text_upper = all_text.upper()
            if surname_upper in text_upper:
                surname_matched = True
            else:
                words = text_upper.split()
                best_ratio = max(
                    (difflib.SequenceMatcher(None, surname_upper, word).ratio() for word in words),
                    default=0.0
                )
                surname_matched = best_ratio >= 0.75
            logger.info(f"Surname check '{expected_surname}': matched={surname_matched}")

        return {"date": found_date, "surname_matched": surname_matched}