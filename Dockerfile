FROM python:3.13-slim-bookworm

# Pin uv; project dependency versions come exclusively from uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    DJANGO_LOAD_DOTENV=false

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev --no-editable
# Build-only nonproduction key: no ENV/ARG secret persists in the image.
RUN GPG_DISABLE_LOGGING_INIT=true SECRET_KEY=build-only-static-collection-key python manage.py collectstatic --noinput
RUN useradd --create-home --uid 10001 app && mkdir -p logs && chown app:app logs
USER app

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
