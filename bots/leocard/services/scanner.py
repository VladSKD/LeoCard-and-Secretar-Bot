import cv2
import numpy as np
import io
import logging

logger = logging.getLogger(__name__)


class DocumentScanner:
    @staticmethod
    def order_points(pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    @staticmethod
    def four_point_transform(image, pts):
        rect = DocumentScanner.order_points(pts)
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    @staticmethod
    def scan_and_deskew(image_buffer: io.BytesIO) -> io.BytesIO:
        try:
            file_bytes = np.asarray(bytearray(image_buffer.read()), dtype=np.uint8)
            image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            image_buffer.seek(0)

            if image is None: return image_buffer

            orig = image.copy()
            ratio = image.shape[0] / 500.0
            image_resized = cv2.resize(image, (int(image.shape[1] / ratio), 500))

            gray = cv2.cvtColor(image_resized, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(gray, 75, 200)

            cnts = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]

            screenCnt = None
            for c in cnts:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    screenCnt = approx
                    break

            if screenCnt is not None:
                logger.info("Контур документа знайдено. Обрізаю.")
                warped = DocumentScanner.four_point_transform(orig, screenCnt.reshape(4, 2) * ratio)
                is_success, buffer = cv2.imencode(".jpg", warped)
                if is_success: return io.BytesIO(buffer)

            return image_buffer  # Якщо контур не знайдено, повертаємо оригінал
        except Exception as e:
            logger.error(f"Scanner error: {e}")
            image_buffer.seek(0)
            return image_buffer