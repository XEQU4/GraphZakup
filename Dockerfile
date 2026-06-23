FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Сначала копируем только зависимости — слой закэшируется
COPY pyproject.toml ./

# Устанавливаем все зависимости из pyproject.toml в системный Python
RUN uv pip install --system --no-cache -e .

# Копируем весь проект
COPY . .

# Собираем статику (whitenoise)
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Миграции + запуск gunicorn
CMD ["sh", "-c", \
    "python manage.py migrate --noinput && \
     gunicorn config.wsgi:application \
       --bind 0.0.0.0:8000 \
       --workers 2 \
       --timeout 120 \
       --log-level info"]
