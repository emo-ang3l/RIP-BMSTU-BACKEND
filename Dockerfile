# Dockerfile
# Используем официальный образ Python
FROM python:3.9-slim

RUN apt-get update && apt-get install -y redis-tools

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем директории для Django
RUN mkdir -p /app/media /app/static

# Указываем порт
EXPOSE 8000

# Собираем статические файлы
RUN python manage.py collectstatic --noinput || true

# Команда по умолчанию
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]