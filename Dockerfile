FROM node:24.21.0-bookworm-slim AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --include=dev --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

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
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable
# Vite outputs browser assets only; Node and npm dependencies stay in the build stage.
COPY --from=frontend-build /build/static/frontend /app/static/frontend
# Build-only nonproduction key: no ENV/ARG secret persists in the image.
RUN GPG_DISABLE_LOGGING_INIT=true SECRET_KEY=build-only-static-collection-key python manage.py collectstatic --noinput
RUN useradd --create-home --uid 10001 app && mkdir -p logs && chown app:app logs
USER app

EXPOSE 8000
CMD ["gunicorn", "--config", "python:config.gunicorn", "config.wsgi:application"]
