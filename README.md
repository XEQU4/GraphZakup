# ГрафЗакуп

ГрафЗакуп — дипломный проект для анализа связей компаний в государственных закупках Казахстана. Система собирает сведения о договорах и компаниях, показывает совпадения и объясняет основания для дальнейшей проверки аналитиком.

Текущая версия — Django-прототип с PostgreSQL, Celery, Redis, HTML-шаблонами и D3.js. Переход на DRF и React, интеграция КГД, сохранение версий анализа и обновление интерфейса запланированы по фазам. Наблюдаемые совпадения и текущий эвристический скор не устанавливают факт нарушения.

## Документация проекта

| Документ | Содержание |
|---|---|
| [Аудит](docs/AUDIT.md) | Подтверждённые дефекты, риски качества данных и ограничения проверки |
| [План по фазам](docs/ROADMAP.md) | Объём работ, зависимости и критерии завершения |
| [Архитектура](docs/ARCHITECTURE.md) | Текущее устройство и предлагаемые решения |
| [Исходное состояние](docs/BASELINE.md) | Результаты фазы 0 и воспроизводимые проверки |
| [Резервное копирование](docs/RECOVERY.md) | Экспорт базы, проверка восстановления и хранение локальных артефактов |
| [Результат фазы 1](docs/PHASE1.md) | Исправления, проверки и оставшиеся ограничения |
| [Запуск и обновление](DEPLOY.md) | Docker Compose, переменные окружения и healthchecks |
| [Инструкции для Codex](AGENTS.md) | Правила работы, сохранения данных и проверки изменений |

## Запуск через Docker

Нужны Docker Desktop с Linux containers и Docker Compose v2. Существующий `.env` с подключением к локальной БД сохрани. Для отдельного Docker окружения создай `.env.docker` из `.env.example`, задай сгенерированный `SECRET_KEY` и свой `DB_PASSWORD`:

```powershell
if (-not (Test-Path .env.docker)) { Copy-Item .env.example .env.docker }
python -c "import secrets; print(secrets.token_urlsafe(50))"
docker compose --env-file .env.docker up --build -d --wait
```

Сайт: http://127.0.0.1:8000/ . Стек запускает PostgreSQL 17, Redis, миграции, Gunicorn, Celery worker и один beat. Worker/web ждут миграции; зависимости ставятся по `uv.lock`, статика использует manifest WhiteNoise. База и Redis сохраняются в отдельных volumes. Автоматический сбор выключен (`ENABLE_SCHEDULED_IMPORT=false`); пустая база сама не заполняется.

Проверка готовности:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready/
docker compose --env-file .env.docker ps -a
```

Подробности запуска, остановки без удаления данных, HTTPS и переноса существующей БД — в [DEPLOY.md](DEPLOY.md) и [RECOVERY.md](docs/RECOVERY.md). Не подключай старый PostgreSQL 16 volume напрямую к 17.

## Локальная разработка и проверки

Python проекта — 3.13 или новее. Зависимости описаны в `pyproject.toml` и `uv.lock`. Локальные реквизиты задаются в `.env`, реальный `SECRET_KEY` обязателен. Для запуска Django с существующей БД сначала проверь резервную копию, затем примени миграции:

```powershell
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py runserver
```

Офлайн-тесты используют SQLite в памяти и mock HTTP; они не читают `.env` и не подключаются к рабочей БД, Redis или сайтам. Проверки текущего JavaScript используют только стандартные модули Node.js:

```powershell
.\.venv\Scripts\python.exe -B manage.py test --settings=config.test_settings
node tests/frontend_regressions.cjs
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=config.test_settings
```

`test.py` содержит учебные функции пользователя и не является тестовым набором проекта. Детали проверенного обновления PostgreSQL и границы проверки находятся в [PHASE1.md](docs/PHASE1.md).

Для сохранения исходников и проверки текущего окружения в PowerShell:

```powershell
.\.venv\Scripts\python.exe -B scripts/capture_baseline.py --label 2026-10-05
```

Для резервной копии и проверки восстановления следуй [docs/RECOVERY.md](docs/RECOVERY.md). Артефакты внутри `artifacts/` исключены из Git и Docker image. Они содержат данные проекта и хранятся локально.

## Работа по фазам

Следующая реализация начинается после проверки критериев текущей фазы. В фазе 4 изменятся алгоритм, хранение и визуальное представление графа. Общий UI/UX React-сайта будет разработан по референсам пользователя в фазе 7.

Git-команды выполняет пользователь. Для отдельного чата Codex указывай фазу, границы задачи и критерии проверки; архитектурные решения и актуальный статус бери из документов репозитория.
