# Используем официальный образ Python
FROM python:3.13-slim

# Устанавливаем зависимости для psql
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /code

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Указываем команду для запуска Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]