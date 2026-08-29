# Використовуємо легкий образ Python
FROM python:3.11-slim

# Встановлюємо системні залежності для Tesseract та OpenCV
# libgl1-mesa-glx замінено на libgl1, який є актуальним для нових версій Debian
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ukr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо файли залежностей
COPY requirements.txt .

# Встановлюємо Python-бібліотеки
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код бота
COPY . .

# Команда запуску
CMD ["python", "main.py"]