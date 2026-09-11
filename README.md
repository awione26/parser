# Парсер мастеров Яндекс Услуг

## Требования

Рекомендуемый способ установки — Docker Compose.

- Linux или macOS;
- Git;
- Docker Engine 24+;
- Docker Compose v2;
- не менее 4 ГБ оперативной памяти;
- свободный локальный порт для админки (по умолчанию `8080`).

Для установки без Docker потребуются:

- Python 3.11+;
- MySQL 8+;
- PHP 8.3+;
- Composer 2;
- Chromium и Playwright — только для одиночного получения телефона.

Перед сетевым запуском необходимо иметь законное основание и требуемые разрешения на
автоматизированный сбор данных с `uslugi.yandex.ru`. Получение телефона и отключение
проверки `robots.txt` допускаются только тогда, когда это прямо разрешено владельцем
ресурса.

## Установка

### 1. Получение проекта

```bash
git clone https://github.com/awione26/parser.git uslugi-parser
cd uslugi-parser
cp .env.example .env
```

### 2. Настройка окружения

Откройте `.env` и обязательно задайте разные пароли MySQL:

```ini
MYSQL_ROOT_PASSWORD=replace_with_random_root_password
MYSQL_MIGRATOR_PASSWORD=replace_with_random_migrator_password
MYSQL_PARSER_PASSWORD=replace_with_random_parser_password
MYSQL_ADMIN_PASSWORD=replace_with_random_admin_password

MYSQL_USER=uslugi_migrator
MYSQL_PASSWORD=replace_with_random_migrator_password
```

Сгенерировать случайный пароль можно командой:

```bash
openssl rand -hex 32
```

Сгенерируйте ключ Laravel:

```bash
php -r "echo 'base64:'.base64_encode(random_bytes(32)).PHP_EOL;"
```

Добавьте полученное значение и параметры первого администратора в `.env`:

```ini
ADMIN_APP_KEY=base64:generated_value
ADMIN_APP_URL=http://127.0.0.1:8080
ADMIN_HOST_PORT=8080
ADMIN_SESSION_SECURE_COOKIE=false

ADMIN_INITIAL_LOGIN=admin
ADMIN_INITIAL_PASSWORD=replace_with_password_of_at_least_12_characters
ADMIN_INITIAL_NAME="Главный администратор"
ADMIN_ALLOW_WEAK_INITIAL_PASSWORD=false
```

Для HTTPS укажите публичный адрес и включите защищённые cookie:

```ini
ADMIN_APP_URL=https://parser.example.com
ADMIN_SESSION_SECURE_COOKIE=true
```

Замените контакт владельца парсера в User-Agent:

```ini
SCRAPER_USER_AGENT=CompanyName-UslugiParser/0.1 (+mailto:parser-owner@example.com)
```

Остальные `SCRAPER_*` параметры можно оставить со значениями из `.env.example`.

### 3. Запуск через Docker Compose

Соберите образы и запустите MySQL и админку:

```bash
docker compose up -d --build mysql admin admin-web
```

Compose автоматически выполнит миграции Alembic и Laravel и создаст runtime-роли
MySQL. Затем создайте первого администратора:

```bash
docker compose exec admin php artisan db:seed --force
```

Проверьте состояние контейнеров:

```bash
docker compose ps
```

Админка будет доступна по адресу:

```text
http://127.0.0.1:8080/cp
```

Проверьте установку парсера без записи данных:

```bash
docker compose run --rm parser categories
docker compose run --rm parser crawl \
  --category all \
  --max-pages 1 \
  --max-profiles 5 \
  --dry-run \
  --progress
```

### 4. Непрерывный запуск на Linux

Готовый systemd-сервис рассчитан на размещение проекта в `/opt/uslugi-parser` и
production-файл `compose.production.yaml`:

```bash
sudo install -m 0555 docker/parser/continuous-crawl.sh \
  /opt/uslugi-parser/docker/parser/continuous-crawl.sh
sudo install -m 0644 deploy/uslugi-parser-worker.service \
  /etc/systemd/system/uslugi-parser-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now uslugi-parser-worker
```

Проверка состояния и журнала:

```bash
sudo systemctl status uslugi-parser-worker
sudo journalctl -u uslugi-parser-worker -f
```

Сервис выполняет полный проход, ждёт 10 минут и запускает следующий. В поставляемом
worker используется `--no-respect-robots`, поэтому включайте его только при наличии
письменного разрешения, которое прямо допускает такой режим.

### 5. Установка Python без Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,phone]'
playwright install chromium
cp .env.example .env
alembic upgrade head
```

После заполнения `.env` проверьте установку:

```bash
uslugi-parser categories
```

### 6. Установка админки без Docker

Сначала подготовьте MySQL-схему парсера командой `alembic upgrade head`, затем:

```bash
cd admin
cp .env.example .env
composer install
php artisan key:generate
php artisan migrate
php artisan db:seed
php artisan serve
```

Перед `db:seed` заполните `ADMIN_INITIAL_LOGIN` и `ADMIN_INITIAL_PASSWORD` в
`admin/.env`, а также настройте подключения `DB_*` и `PARSER_DB_*` к MySQL.
