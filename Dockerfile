FROM python:3.10-slim

# Установка системных зависимостей включая SQLite
RUN apt-get update && apt-get install -y \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Установка порта
ENV PORT=8080

# Запуск приложения
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app