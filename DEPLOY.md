# Полный гайд деплоя ГрафЗакуп на VPS-сервер

---

## ЧТО МЕНЯЕТСЯ В ЭТОМ ПАКЕТЕ (аудит ошибок)

| Файл | Проблема | Исправление |
|---|---|---|
| `pyproject.toml` | Зависимость `"v>=1"` — несуществующий пакет, падал install. Тяжёлые неиспользуемые пакеты (`playwright`, `scikit-learn`, `pandas`, `faker`) раздували образ Docker | Убраны лишние, добавлены `whitenoise`, `django-celery-beat` |
| `config/settings.py` | `django_celery_beat` не был в `INSTALLED_APPS` → beat не мог сохранить расписание в БД | Добавлен |
| `apps/core/tasks.py` | Задача не имела `name=` → имя в `CELERY_BEAT_SCHEDULE` не совпадало → расписание не срабатывало | Добавлен явный `name=` |
| `services/contract_registry_parser.py` | Нет параметра `start_page` → каждый запуск с нуля парсил одни и те же первые 500 контрактов | Добавлен `start_page` |
| `apps/companies/management/commands/import_contracts.py` | Нет сохранения прогресса страниц → повторный запуск не двигался вперёд | Сохраняет `last_import_page` в `SystemSetting` |

---

## ЧАСТЬ 1: ЭКСПОРТ БАЗЫ С ЛОКАЛЬНОГО ПК

> Выполняй на **своём компьютере** (не на сервере)

```bash
# Заменяем suppliergraph на имя твоей базы, postgres на твоего пользователя
pg_dump -U postgres -Fc suppliergraph > goszakup_backup.dump
```

Если `pg_dump` не найден — запусти через полный путь:
- Windows: `"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U postgres -Fc suppliergraph > goszakup_backup.dump`

---

## ЧАСТЬ 2: ПОДГОТОВКА VPS-СЕРВЕРА (Termius)

### Шаг 1 — Обновление системы

```bash
sudo apt update && sudo apt upgrade -y
```

### Шаг 2 — Установка зависимостей

```bash
sudo apt install -y \
    python3.13 python3-pip python3-venv \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    git curl \
    build-essential libpq-dev
```

### Шаг 3 — Установка uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env   # или перелогинься
uv --version              # должна появиться версия
```

### Шаг 4 — Настройка PostgreSQL

```bash
sudo -u postgres psql

-- Внутри psql выполни:
CREATE DATABASE suppliergraph;
CREATE USER goszakup WITH PASSWORD 'ПРИДУМАЙ_ПАРОЛЬ';
GRANT ALL PRIVILEGES ON DATABASE suppliergraph TO goszakup;
\q
```

### Шаг 5 — Загрузка дампа базы с твоего ПК на сервер

```bash
# На ЛОКАЛЬНОМ ПК (в другом окне / Termius local):
scp goszakup_backup.dump user@IP_СЕРВЕРА:/home/user/

# Обратно на сервере — восстанавливаем:
pg_restore -U goszakup -d suppliergraph /home/user/goszakup_backup.dump
```

> Если появляются ошибки "role does not exist" — игнорируй, данные всё равно загрузятся.

---

## ЧАСТЬ 3: ЗАГРУЗКА ПРОЕКТА НА СЕРВЕР

### Вариант А — через Git (рекомендую)

```bash
cd /var/www
sudo mkdir goszakup && sudo chown $USER:$USER goszakup
git clone https://github.com/ТВО_ИМЯ/goszakup.git goszakup
cd goszakup
```

### Вариант Б — через SCP (без Git)

```bash
# На локальном ПК — архивируем и отправляем:
zip -r goszakup_project.zip . -x "*.pyc" -x "__pycache__/*" -x ".venv/*" -x "staticfiles/*"
scp goszakup_project.zip user@IP:/var/www/

# На сервере:
cd /var/www
unzip goszakup_project.zip -d goszakup
cd goszakup
```

---

## ЧАСТЬ 4: НАСТРОЙКА ПРОЕКТА НА СЕРВЕРЕ

```bash
cd /var/www/goszakup

# Создаём .env
cp .env.example .env
nano .env
```

Заполняй `.env` так (Ctrl+O сохранить, Ctrl+X выйти):

```
SECRET_KEY=сгенерируй-50-символов-здесь
DB_NAME=suppliergraph
DB_USER=goszakup
DB_PASSWORD=ПРИДУМАЙ_ПАРОЛЬ
DB_HOST=localhost
DB_PORT=5432
CELERY_BROKER_URL=redis://localhost:6379/0
ALLOWED_HOSTS=IP_СЕРВЕРА,твой_домен.com
DJANGO_DEBUG=false
OPENROUTER_API_KEY=sk-or-v1-...
```

Генерация SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

```bash
# Устанавливаем зависимости
uv pip install --system -e .

# Миграции (структура БД уже есть из дампа, но новые таблицы появятся)
uv run python manage.py migrate --noinput

# Статика
uv run python manage.py collectstatic --noinput

# Создаём суперюзера для /admin
uv run python manage.py createsuperuser
```

---

## ЧАСТЬ 5: SYSTEMD — автозапуск при перезагрузке

### Django (gunicorn)

```bash
sudo nano /etc/systemd/system/goszakup.service
```

```ini
[Unit]
Description=ГрафЗакуп Django
After=network.target postgresql.service redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/goszakup
EnvironmentFile=/var/www/goszakup/.env
ExecStart=/usr/local/bin/gunicorn config.wsgi:application \
    --bind unix:/run/goszakup.sock \
    --workers 2 \
    --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Celery Worker

```bash
sudo nano /etc/systemd/system/goszakup-worker.service
```

```ini
[Unit]
Description=ГрафЗакуп Celery Worker
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/var/www/goszakup
EnvironmentFile=/var/www/goszakup/.env
ExecStart=celery -A config worker --loglevel=info --concurrency=1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Celery Beat (расписание)

```bash
sudo nano /etc/systemd/system/goszakup-beat.service
```

```ini
[Unit]
Description=ГрафЗакуп Celery Beat
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/var/www/goszakup
EnvironmentFile=/var/www/goszakup/.env
ExecStart=celery -A config beat --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Применяем и запускаем

```bash
sudo chown -R www-data:www-data /var/www/goszakup
sudo systemctl daemon-reload
sudo systemctl enable goszakup goszakup-worker goszakup-beat
sudo systemctl start  goszakup goszakup-worker goszakup-beat

# Проверяем статус:
sudo systemctl status goszakup
sudo systemctl status goszakup-worker
sudo systemctl status goszakup-beat
```

---

## ЧАСТЬ 6: NGINX — раздача сайта

```bash
sudo nano /etc/nginx/sites-available/goszakup
```

```nginx
server {
    listen 80;
    server_name IP_СЕРВЕРА;    # потом заменишь на домен

    # Статика (whitenoise справляется и без nginx, но nginx быстрее)
    location /static/ {
        alias /var/www/goszakup/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://unix:/run/goszakup.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/goszakup /etc/nginx/sites-enabled/
sudo nginx -t          # проверка конфига
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Открываешь `http://IP_СЕРВЕРА` в браузере — должен работать сайт.

---

## ЧАСТЬ 7: ДОМЕН (когда купишь)

### Где купить дёшево
- **reg.ru** / **nic.ru** — `.kz` домен от ~3000 тг/год
- **freenom.com** — бесплатные `.tk`, `.ml` домены (для теста)
- **namecheap.com** — `.com` от $10/год

### Настройка DNS
В панели управления доменом добавь A-запись:
```
@    A    IP_ТВОЕГО_СЕРВЕРА
www  A    IP_ТВОЕГО_СЕРВЕРА
```
Подождать 5-30 минут.

### Обновить конфиг Nginx

```bash
sudo nano /etc/nginx/sites-available/goszakup
# Заменить: server_name IP_СЕРВЕРА;
# На:       server_name твой_домен.com www.твой_домен.com;
sudo systemctl reload nginx
```

### HTTPS — бесплатный сертификат Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d твой_домен.com -d www.твой_домен.com
# Следуй инструкциям, certbot сам обновит nginx конфиг
# Автообновление уже настроено через systemd timer
```

### Обновить ALLOWED_HOSTS в .env

```bash
nano /var/www/goszakup/.env
# ALLOWED_HOSTS=IP_СЕРВЕРА,твой_домен.com,www.твой_домен.com
sudo systemctl restart goszakup
```

---

## ЧАСТЬ 8: РУЧНОЙ ЗАПУСК ПЕРВОГО ПАРСИНГА

После деплоя данных из дампа уже достаточно, но если хочешь запустить
парсинг вручную прямо сейчас:

```bash
cd /var/www/goszakup

# Парсинг 500 контрактов + обогащение + кластеры
uv run python manage.py import_contracts --total=500 --mode=new

# Или запустить через Celery (без ожидания расписания):
uv run celery -A config call apps.core.tasks.update_all_data
```

Дальше каждые 12 часов beat автоматически вызывает эту задачу
и парсит следующие 500 контрактов (продолжая с последней страницы).

---

## ЧАСТЬ 9: МОНИТОРИНГ

```bash
# Логи Django
sudo journalctl -u goszakup -f

# Логи Celery Worker
sudo journalctl -u goszakup-worker -f

# Логи Celery Beat (расписание)
sudo journalctl -u goszakup-beat -f

# Проверить что задача сработала по расписанию:
uv run python manage.py shell -c "
from apps.core.models import SystemSetting
s = SystemSetting.objects.filter(key__startswith='last_import')
for x in s: print(x.key, '=', x.value)
"
```

---

## ЧАСТЬ 10: БЕСПЛАТНЫЕ СЕРВЕРЫ (если нет VPS)

### Render.com
1. New → Web Service → GitHub → Docker
2. Добавить PostgreSQL (free, 1 GB) и Redis (free)
3. Заполнить Environment Variables (как в .env)
4. Отдельные Background Workers для worker и beat

### Railway.app
1. New Project → GitHub Repo
2. Add → Database (PostgreSQL) + Redis
3. Переменные окружения — как в .env

> ⚠️ На бесплатных серверах сервис "засыпает" через 15 мин бездействия.
> Для конкурса это OK, для продакшена нужен платный план.
