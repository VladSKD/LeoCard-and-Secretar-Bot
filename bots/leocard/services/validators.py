import io
import re
import logging
from services.pdf import PDFService
from services.ocr import OCRService

logger = logging.getLogger(__name__)


class Validators:
    """Document and data validation"""

    @staticmethod
    def validate_payment_receipt(receipt_buffer: io.BytesIO, user_data: dict, mimetype: str) -> bool:
        """Validate payment receipt contains user surname with robust matching"""
        try:
            # Extract text
            text = ""
            if "pdf" in mimetype:
                try:
                    text = PDFService.extract_text(receipt_buffer)
                except Exception as e:
                    logger.error(f"PDF text extraction failed in receipt validation: {e}")
                    return False
            else:
                receipt_buffer.seek(0)
                try:
                    import pytesseract
                    from utils.helpers import bytes_to_image
                    img = bytes_to_image(receipt_buffer)
                    if img is None:
                        logger.error("Receipt image decode failed")
                        return False
                    # Змінено мову тільки на українську, щоб уникнути плутанини з латиницею
                    text = pytesseract.image_to_string(img, lang='ukr') 
                except Exception as e:
                    logger.error(f"OCR failed in receipt validation: {e}")
                    return False

            # Get surname
            full_name = user_data.get("passport_data", {}).get("full_name", "")
            if not full_name:
                logger.error("No full name in user data for receipt validation")
                return False

            parts = full_name.split()
            if not parts:
                return False
            surname = parts[0].lower()

            # ДЕБАГ: Виводимо в консоль, що саме ми шукаємо і де
            logger.info(f"--- РЕЗУЛЬТАТ OCR --- \n{text}\n--------------------")
            logger.info(f"Шукаємо прізвище: '{surname}'")

            text_lower = text.lower()

            # 1. Прямий пошук
            if surname in text_lower:
                logger.info(f"Payment receipt validated: surname '{surname}' found (Direct match)")
                return True

            # 2. Нечіткий пошук (fuzzy search)
            import difflib
            words_in_text = text_lower.split()
            matches = difflib.get_close_matches(surname, words_in_text, n=1, cutoff=0.75)
            if matches:
                logger.info(f"Payment receipt validated: surname '{surname}' found (Fuzzy match as {matches})")
                return True

            # 3. Агресивне очищення (видаляємо всі пробіли та спецсимволи)
            import re
            clean_text = re.sub(r'[\W_]+', '', text_lower)
            clean_surname = re.sub(r'[\W_]+', '', surname)
            
            # Замінюємо візуально схожі латинські букви на кириличні
            latin_to_cyrillic = {'a':'а', 'b':'в', 'c':'с', 'e':'е', 'h':'н', 'i':'і', 'm':'м', 'o':'о', 'p':'р', 't':'т', 'x':'х', 'y':'у'}
            trans_text = ''.join(latin_to_cyrillic.get(c, c) for c in clean_text)
            
            if clean_surname in trans_text:
                logger.info(f"Payment receipt validated: surname '{surname}' found (Cleaned/Transliterated match)")
                return True

            logger.warning(f"Surname '{surname}' not found in receipt text even after robust checks.")
            return False

        except Exception as e:
            logger.error(f"Receipt validation error: {e}", exc_info=True)
            return False