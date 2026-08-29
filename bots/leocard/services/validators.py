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
        """Validate payment receipt contains user surname"""
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
                    text = pytesseract.image_to_string(img, lang='ukr+eng')
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

            # Check if surname is in payment text (case-insensitive)
            text_lower = text.lower()
            if surname in text_lower:
                logger.info(f"Payment receipt validated: surname '{surname}' found")
                return True

            logger.warning(f"Surname '{surname}' not found in receipt text")
            return False

        except Exception as e:
            logger.error(f"Receipt validation error: {e}", exc_info=True)
            return False