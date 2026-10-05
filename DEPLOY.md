# Запуск ГрафЗакуп через Docker Compose

Стек объединяет PostgreSQL 17, Redis, однократные миграции, Django/Gunicorn, Celery worker и один beat. Автоматический сбор данных выключен по умолчанию. Реальные токены не нужны для запуска пустой базы и проверки интерфейса.

## Подготовка

Нужны Docker с Linux containers и Docker Compose v2. Для существующих данных сначала проверь резервную копию и восстановление по [docs/RECOVERY.md](docs/RECOVERY.md).

Из корня проекта в PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Скопируй сгенерированное значение в SECRET_KEY, задай собственный DB_PASSWORD. Если `.env` уже существует, сохрани его и обнови необходимые ключи вручную. Не заменяй имеющиеся реквизиты примером.
Сайт по умолчанию слушает `127.0.0.1:8000`, DEBUG выключен. Compose передаёт только перечисленные переменные; внутренний маршрут PostgreSQL всегда `db:5432`, PGHOST локального `.env` его не переопределяет.

## Один запуск для всего стека

```powershell
docker compose up --build -d
```

PostgreSQL и Redis проходят healthchecks. Сервис migrate применяет миграции и завершается; web и worker ждут успешное завершение migrate. Beat также ждёт готовый worker. Не масштабируй beat: для одного окружения нужен один планировщик.

```powershell
docker compose ps -a
docker compose logs --tail=100 migrate web worker beat
Invoke-RestMethod http://127.0.0.1:8000/health/live/
Invoke-RestMethod http://127.0.0.1:8000/health/ready/
```

`/health/live/` проверяет HTTP процесс без обращений к зависимостям. `/health/ready/` выполняет SELECT 1 и Redis PING; недоступная зависимость даёт HTTP 503 без реквизитов и traceback в ответе. Эти маршруты только читают состояние. Healthcheck worker использует адресованный Celery inspect ping.
Сайт: http://127.0.0.1:8000/ . Администратор создаётся отдельной ручной командой:

```powershell
docker compose exec web python manage.py createsuperuser
```

Пустая база не содержит компаний и графов. Compose не заполняет её live-парсингом.

## Настройки и состояние

| Переменная | Назначение |
|---|---|
| SECRET_KEY | Обязательный runtime секрет; placeholder запрещён |
| DB_NAME, DB_USER, DB_PASSWORD | БД контейнера и согласованные реквизиты Django |
| WEB_PORT, WEB_BIND_ADDRESS | Порт и адрес компьютера; внутри Gunicorn использует 8000 |
| ALLOWED_HOSTS | Явные hosts без протокола; wildcard при DEBUG=false запрещён |
| CSRF_TRUSTED_ORIGINS | Дополнительные origins с протоколом |
| ENABLE_SCHEDULED_IMPORT | false: задача update_all_data выключена; true: явное разрешение live pipeline |
| GPG_LOG_TO_FILES | true для локального Python; Compose принудительно false, пишет stdout/stderr |
| OPENROUTER_API_KEY, OPENROUTER_MODEL, GOSZAKUP_TOKEN | Внешние интеграции; ключи могут быть пустыми при проверке инфраструктуры |

БД сохраняется в новом volume postgres17_data, Redis использует redis_data и AOF. Старый postgres_data от PostgreSQL 16 не подключается к 17: перенос выполняется через проверенный dump/restore в отдельную БД. Конфигурация не меняет и не удаляет прежний volume.
Остановка сохраняет volumes:

```powershell
docker compose down
```

Повторный `docker compose up -d` использует сохранённую БД. Не добавляй `--volumes` к остановке окружения с нужными данными.
Docker устанавливает зависимости через `uv sync --frozen --no-dev` из uv.lock, сохраняя пользовательские pyproject/lock. Статика собирается с build-only фиктивным ключом; runtime SECRET_KEY он не заменяет. Образ запускается от непривилегированного пользователя. Только migrate собирает общий backend image; web/worker/beat используют тот же локальный образ с pull_policy=never. Для первого запуска используется команда с `--build` выше.
Контейнеры пишут логи только в stdout/stderr, доступные через `docker compose logs`. Общая файловая ротация между Gunicorn workers не используется. Для локального запуска Python файловые логи включены по умолчанию через GPG_LOG_TO_FILES=true.

## Проверка в отдельном окружении

Создай smoke.env в игнорируемом artifacts/ с временными реквизитами, свободным WEB_PORT и уникальным project name. Не копируй рабочие пароли/API ключи. Compose не импортирует локальный `.env` как env_file контейнера. Переменные процесса имеют приоритет над `--env-file`: при изолированной проверке они также должны содержать временные значения.

```powershell
docker compose --env-file artifacts/phase1/smoke.env -p gpg_phase1_smoke up --build -d
docker compose --env-file artifacts/phase1/smoke.env -p gpg_phase1_smoke ps -a
```

В smoke.env задай собственные SECRET_KEY/DB_PASSWORD, ENABLE_SCHEDULED_IMPORT=false, пустые API ключи и отдельный WEB_PORT. Проектный префикс отделяет контейнеры и volumes от обычного запуска.
Офлайн тесты приложения используют SQLite в памяти, не читают `.env`, не подключаются к рабочим PostgreSQL/Redis и не открывают log файлы:

```powershell
.\.venv\Scripts\python.exe -B manage.py test --settings=config.test_settings
```

## Публичное HTTPS окружение

Поставь reverse proxy с TLS и задай домен в ALLOWED_HOSTS. Включи SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE и CSRF_COOKIE_SECURE. TRUST_PROXY_SSL_HEADER=true разрешается только когда proxy заменяет входящий X-Forwarded-Proto. HSTS включается через SECURE_HSTS_SECONDS после проверки HTTPS; subdomains/preload требуют готовности соответствующих доменов.
Health маршруты исключены из SSL redirect для внутреннего HTTP healthcheck; Compose добавляет localhost/127.0.0.1 в hosts. При необходимости отдельный origin frontend добавляется в CSRF_TRUSTED_ORIGINS.
Автосбор включается намеренно после проверки источников, данных и токенов: ENABLE_SCHEDULED_IMPORT=true. Task guard также блокирует ранее сохранённые расписания beat, пока флаг false; сами записи расписания не удаляются. Расписания доступны в Django admin.

Официальные справочники: [uv в Docker](https://docs.astral.sh/uv/guides/integration/docker/), [порядок запуска Compose](https://docs.docker.com/compose/how-tos/startup-order/), [Django deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).
