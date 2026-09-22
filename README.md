# LMS Project

Учебная LMS-система на Django REST Framework: курсы, уроки, пользователи, платежи и разграничение прав доступа.

## Стек

- Python 3.14
- Django 6.1
- Django REST Framework
- djangorestframework-simplejwt — JWT-авторизация
- drf-spectacular — OpenAPI-документация
- stripe — приём оплаты
- Celery + Redis — фоновые и периодические задачи
- django-filter
- python-dotenv — переменные окружения
- coverage — покрытие тестами
- PostgreSQL
- Poetry
- Docker и Docker Compose — запуск всего проекта одной командой
- Gunicorn + Nginx — боевой сервер приложения
- GitHub Actions — линт, тесты, сборка образа и деплой на каждый push
- flake8 — проверка стиля кода

## Запуск в Docker

Рекомендуемый способ: поднимает сразу всё — приложение, базу, Redis, воркер и расписание.

### Что нужно

Установленный [Docker Desktop](https://www.docker.com/products/docker-desktop) (на Windows — с включённым WSL 2). Больше ничего: ни Python, ни Poetry, ни PostgreSQL на компьютере не требуются.

### Первый запуск

```bash
cp .env.template .env
```

Откройте `.env` и задайте `SECRET_KEY`. Остальные значения уже рассчитаны на Docker — менять их не нужно.

```bash
docker compose up -d --build
```

Первая сборка занимает несколько минут: скачиваются образы и ставятся зависимости. Дальше запуск будет почти мгновенным.

Приложение поднимется на **http://localhost:8000/**, документация — на **http://localhost:8000/api/docs/**

Миграции и сборка статики выполняются автоматически при старте контейнера `web`. Суперпользователь создаётся вручную:

```bash
docker compose exec web python manage.py createsuperuser
```

### Из чего состоит стек

| Сервис | Что делает | Доступ снаружи |
|---|---|---|
| `web` | Django, отдаёт API | порт **8000** |
| `db` | PostgreSQL | только `expose` — изнутри сети |
| `redis` | брокер очереди для Celery | только `expose` — изнутри сети |
| `celery` | выполняет фоновые задачи | нет |
| `celery-beat` | ставит задачи по расписанию | нет |

Порт наружу пробрасывает только `web`: к нему обращается браузер. База и Redis объявлены через `expose` — они видны другим контейнерам по имени сервиса (`db`, `redis`), но с компьютера к ним не подключиться. Так база не торчит в сеть.

### Сохранность данных

Контейнер одноразовый: всё, что записано внутрь него, исчезает при пересоздании. Поэтому данные вынесены в тома:

| Том | Что хранит |
|---|---|
| `postgres_data` | база |
| `redis_data` | очередь задач |
| `static_data` | собранная статика |
| `media_data` | загруженные файлы |

```bash
docker compose down     # остановить, данные сохранятся
docker compose down -v  # остановить и стереть тома вместе с базой
```

Разница между этими командами — единственное, что стоит запомнить твёрдо. Флаг `-v` удаляет тома, то есть базу.

### Повседневные команды

```bash
docker compose ps                    # что запущено и в каком состоянии
docker compose logs -f web           # логи приложения
docker compose logs -f celery        # логи воркера
docker compose restart web           # перезапустить один сервис
docker compose exec web bash         # консоль внутри контейнера
docker compose up -d --build         # пересобрать после правок кода
```

### Переменные окружения

Все настройки берутся из `.env`. Файл в репозиторий не попадает — образец лежит в `.env.template`.

Внутри Docker сервисы обращаются друг к другу по именам из `docker-compose.yaml`, поэтому в `.env` указано `POSTGRES_HOST=db` и `CELERY_BROKER_URL=redis://redis:6379/0`. Если запускаете проект без Docker, замените оба значения на `localhost`.

---

## CI/CD и деплой на сервер

Каждый push проходит через конвейер GitHub Actions — `.github/workflows/ci.yml`:

```
  lint  ──►  test  ──►  build  ──►  deploy
 flake8    114 тестов   Docker-     на сервер
           на Postgres  образ       по SSH
```

Каждый этап стартует, только если предыдущий прошёл. Упал flake8 — тесты не запускаются. Упал хоть один тест — образ не собирается, и на сервер ничего не уезжает.

### Когда что запускается

| Событие | lint | test | build | deploy |
|---|---|---|---|---|
| push в рабочую ветку | ✅ | ✅ | только сборка | — |
| pull request в `main` | ✅ | ✅ | только сборка | — |
| push в `main` | ✅ | ✅ | сборка + публикация | ✅ |
| ручной запуск из `main` | ✅ | ✅ | сборка + публикация | ✅ |

На боевой сервер попадает только ветка `main`. Push в рабочую или экспериментальную ветку проходит линт, тесты и пробную сборку — ошибка видна сразу, — но сервер не трогает. Код доходит до сервера только через pull request.

Ручной запуск: **Actions** → **CI/CD** → **Run workflow**.

### Что проверяет каждый этап

**lint** — `flake8 .` с правилами из `setup.cfg`: длина строки 119, миграции исключены.

**test** — поднимает настоящие PostgreSQL и Redis рядом с раннером и прогоняет:

- `manage.py check` — конфигурация Django корректна;
- `makemigrations --check` — никто не забыл создать миграцию после правки модели;
- все тесты под `coverage`;
- `coverage report --fail-under=80` — покрытие ниже 80% тоже останавливает конвейер.

**build** — собирает Docker-образ. На push в `main` публикует его в GitHub Container Registry с двумя тегами: хэш коммита и `latest`.

**deploy** — по SSH копирует на сервер `docker-compose.prod.yaml` и конфиг Nginx, собирает `.env` из секретов репозитория, скачивает новый образ и перезапускает контейнеры. В конце проверяет, что приложение действительно отвечает по HTTP; если нет — деплой помечается проваленным, а в лог выводятся последние строки контейнера `web`.

### Как устроен сервер

```
Интернет ──► :80 Nginx ──► web:8000 Gunicorn (Django)
                 │                  │
                 └ /static/, /media/ │
                                     ├──► db:5432     PostgreSQL
                                     └──► redis:6379  Redis ◄── celery, celery-beat
```

Наружу открыт только порт 80 у Nginx. Gunicorn, PostgreSQL и Redis объявлены через `expose` и доступны только внутри сети Docker. Статику Nginx отдаёт сам, не нагружая Python.

Все сервисы запущены с `restart: always`, а Docker включён в автозагрузку системы. Упал процесс — Docker поднимет контейнер заново; перезагрузился сервер — всё стартует само.

### Подготовка сервера

Нужен VPS с Ubuntu 22.04 или 24.04 и публичным IP. Подойдёт самый маленький тариф: 1–2 ядра, 2 ГБ памяти.

**1. Ключи.** Понадобится два SSH-ключа. На своём компьютере:

```bash
# Личный — чтобы заходить на сервер самому (если ещё нет)
ssh-keygen -t ed25519

# Отдельный для GitHub Actions. На вопрос о пароле — дважды Enter:
# CI не умеет вводить пароль от ключа
ssh-keygen -t ed25519 -f ~/.ssh/lms_deploy -C github-actions
```

Два ключа, а не один, — чтобы при утечке секретов GitHub можно было отозвать доступ деплоя, не теряя собственного.

**2. Сервер.** При создании VPS добавьте публичный личный ключ (`~/.ssh/id_ed25519.pub`). Машина нужна с процессором **x86** — образ собирается под эту архитектуру и на ARM не запустится. Если провайдер выдаёт динамический IP (Yandex Cloud), сделайте его статическим: иначе после перезагрузки машины адрес сменится, и деплой перестанет находить сервер.

Зайдите на сервер, скачайте скрипт настройки и запустите, передав ему публичный ключ деплоя:

```bash
curl -fsSLO https://raw.githubusercontent.com/Alexander-Sky/lms_project/main/deploy/server-setup.sh

# Hetzner и другие, где входите сразу под root:
bash server-setup.sh "ssh-ed25519 AAAA... github-actions"

# Yandex Cloud, AWS и другие, где входите под своим пользователем:
sudo bash server-setup.sh "ssh-ed25519 AAAA... github-actions"
```

В кавычках — целиком содержимое `~/.ssh/lms_deploy.pub`, одной строкой.

Скрипт `deploy/server-setup.sh`:

- ставит Docker из официального репозитория и включает его автозапуск;
- создаёт пользователя `deploy` в группе `docker` — под ним работает деплой;
- отключает вход по паролю — только ключи;
- включает firewall `ufw`: снаружи открыты только 22 (SSH) и 80 (HTTP).

Ваш личный ключ скрипт копирует пользователю `deploy`, чтобы вы тоже могли под ним входить. Если ключа не найдёт — откажется работать: иначе после отключения паролей на сервер было бы не зайти. Повторный запуск безопасен.

После него проверьте в **новом** окне, не закрывая старое: `ssh deploy@<IP>`.

**3. Секреты.** В репозитории: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

| Секрет | Обязателен | Что туда положить |
|---|---|---|
| `SSH_HOST` | да | IP сервера |
| `SSH_USER` | да | `deploy` |
| `SSH_PRIVATE_KEY` | да | содержимое `~/.ssh/lms_deploy` — **приватного**, без `.pub` |
| `SECRET_KEY` | да | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `POSTGRES_PASSWORD` | да | длинный случайный пароль, той же командой |
| `STRIPE_API_KEY` | нет | тестовый ключ Stripe; без него не работает оплата |
| `EMAIL_HOST_USER` | нет | почта для рассылки |
| `EMAIL_HOST_PASSWORD` | нет | пароль приложения от почты |

Реестру образов отдельный пароль не нужен: GitHub Actions использует встроенный `GITHUB_TOKEN`, который выдаётся на один запуск и сам истекает.

**4. Первый деплой.** Слейте изменения в `main` или запустите workflow вручную: **Actions** → **CI/CD** → **Run workflow**. Через пару минут приложение откроется на `http://<IP>/api/docs/`.

Суперпользователь создаётся один раз вручную:

```bash
ssh deploy@<IP>
cd ~/lms_project
docker compose -f docker-compose.prod.yaml exec web python manage.py createsuperuser
```

### Где что хранится

На сервере в `~/lms_project` лежат три файла, и все их кладёт туда деплой:

| Файл | Откуда |
|---|---|
| `docker-compose.prod.yaml` | копируется из репозитория |
| `nginx/default.conf` | копируется из репозитория |
| `.env` | собирается из секретов GitHub, права `600` |

Руками на сервере ничего не правится. Поменять настройку — значит поменять файл в репозитории или секрет в GitHub и запустить деплой. Так конфигурация сервера всегда совпадает с тем, что видно в git.

### Работа с сервером

```bash
cd ~/lms_project
docker compose -f docker-compose.prod.yaml ps              # состояние сервисов
docker compose -f docker-compose.prod.yaml logs -f web     # логи Gunicorn
docker compose -f docker-compose.prod.yaml logs -f nginx   # логи Nginx
grep WEB_IMAGE .env                                        # какая версия запущена
```

### Откат

Каждый образ помечен хэшем коммита, поэтому вернуться на прошлую версию — значит перезапустить workflow на нужном коммите: **Actions** → выбрать успешный запуск → **Re-run all jobs**.

### Безопасность

- Вход на сервер только по ключам, пароли отключены.
- Firewall пропускает только 22 и 80.
- PostgreSQL и Redis не опубликованы наружу. Это важно не только из-за firewall: порты, опубликованные через `ports:`, Docker пробрасывает **в обход** `ufw`, и firewall их не закрыл бы.
- `DEBUG=False`, `ALLOWED_HOSTS` — только IP сервера: запросы с чужим заголовком `Host` отклоняются.
- Секреты живут в GitHub Secrets и попадают в `.env` на сервере при деплое. В репозитории их нет, в логах GitHub они маскируются.

---

## Установка без Docker

Понадобится Python 3.14, Poetry, запущенные PostgreSQL и Redis.

Скопируйте `.env.template` в `.env` и заполните значения:

```bash
cp .env.template .env
```

| Переменная | Зачем |
|---|---|
| `SECRET_KEY` | Ключ Django. Без него используется небезопасное значение по умолчанию |
| `DEBUG` | `True` для разработки, `False` для боевого запуска |
| `STRIPE_API_KEY` | Тестовый ключ из [дашборда Stripe](https://dashboard.stripe.com/test/apikeys), начинается на `sk_test_` |
| `STRIPE_SUCCESS_URL` | Куда Stripe вернёт пользователя после успешной оплаты |
| `STRIPE_CANCEL_URL` | Куда вернёт при отмене |
| `CELERY_BROKER_URL` | Адрес Redis для очереди задач |
| `CELERY_RESULT_BACKEND` | Адрес Redis для результатов задач |
| `EMAIL_BACKEND` | По умолчанию письма печатаются в консоль. Для реальной отправки — `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Доступы к SMTP |
| `INACTIVITY_DAYS_LIMIT` | Через сколько дней без входа блокировать пользователя (по умолчанию 30) |
| `COURSE_UPDATE_NOTIFY_HOURS` | Не чаще раза в сколько часов уведомлять подписчиков об обновлении курса (по умолчанию 4) |

Файл `.env` в репозиторий не попадает — он в `.gitignore`.

```bash
poetry install --no-root
poetry run python manage.py migrate
poetry run python manage.py loaddata groups.json users.json courses.json lessons.json payments.json
poetry run python manage.py runserver
```

Сервер поднимется на http://127.0.0.1:8000/

Создать суперпользователя для админки:

```bash
poetry run python manage.py createsuperuser
```

## Фоновые задачи (Celery)

Отправка писем и блокировка пользователей вынесены из цикла запрос-ответ: клиент не должен ждать, пока ответит почтовый сервер.

Для работы нужен **Redis** — он выступает брокером очереди.

### Запуск

В Docker воркер и расписание поднимаются сами — сервисы `celery` и `celery-beat` описаны в `docker-compose.yaml`, отдельно запускать ничего не нужно.

Без Docker нужны три процесса в трёх окнах терминала, и Redis должен быть запущен.

```bash
# 1. Django
poetry run python manage.py runserver

# 2. Воркер — выполняет задачи
poetry run celery -A config worker -l info

# 3. Beat — ставит задачи по расписанию
poetry run celery -A config beat -l info
```

На **Windows** воркер запускается только в режиме `solo` — стандартный пул процессов там не поддерживается:

```powershell
poetry run celery -A config worker -l info -P solo
```

Проверить, что воркер жив:

```bash
poetry run celery -A config inspect ping
```

### Задача 1: письма подписчикам об обновлении курса

Живёт в `lms/tasks.py`, вызывается из контроллеров обновления курса и урока.

| Что произошло | Что делает система |
|---|---|
| Обновлён курс | Ставит задачу на рассылку подписчикам этого курса |
| Обновлён урок | Обновляет `updated_at` курса и ставит ту же задачу |
| Добавлен урок | То же самое — новый урок это тоже обновление материалов |

Каждому подписчику уходит **отдельное письмо**: если сложить всех в один `recipient_list`, адреса окажутся в поле To и станут видны друг другу. `send_mass_mail` при этом открывает одно соединение с SMTP на всю рассылку.

**Защита от спама.** Курс можно править по одному уроку, и без ограничения подписчик получил бы письмо на каждую правку. Поэтому уведомление уходит, только если курс не обновлялся дольше `COURSE_UPDATE_NOTIFY_HOURS` (по умолчанию 4 часа):

```python
previous_updated_at = serializer.instance.updated_at   # читаем ДО save()
course = serializer.save()                              # auto_now перезапишет поле
notify_course_subscribers(course, previous_updated_at)
```

Прошлое значение `updated_at` берётся до сохранения — после `save()` поле уже показывает текущий момент, и сравнивать было бы не с чем.

**Если Redis недоступен**, постановка задачи не роняет запрос: курс всё равно обновляется, а неудача пишется в лог. Пользователь не виноват, что легла почтовая очередь.

### Задача 2: блокировка неактивных пользователей

Живёт в `users/tasks.py`, запускается по расписанию celery-beat каждый день в 03:00.

Пользователи, которые не заходили дольше `INACTIVITY_DAYS_LIMIT` дней, получают `is_active = False`. Обновление идёт **одним UPDATE** на всю выборку, а не циклом с `save()` по каждому — на большой базе разница принципиальная.

Пользователи с `last_login = NULL` под фильтр не попадают: блокировать того, кто только зарегистрировался и ещё не логинился, было бы неверно.

Расписание задаётся в `settings.py`:

```python
CELERY_BEAT_SCHEDULE = {
    'block-inactive-users-every-night': {
        'task': 'users.tasks.block_inactive_users',
        'schedule': crontab(hour=3, minute=0),
    },
}
```

**Таймзона Celery привязана к таймзоне Django** — `CELERY_TIMEZONE = TIME_ZONE`. Если их развести, периодические задачи будут запускаться не в то время, которое написано в расписании.

Запустить задачу вручную, не дожидаясь трёх ночи:

```bash
poetry run python manage.py shell
>>> from users.tasks import block_inactive_users
>>> block_inactive_users.delay()      # через очередь
>>> block_inactive_users()            # прямо здесь, синхронно
```

## Документация API

Схема генерируется автоматически из кода библиотекой **drf-spectacular**. Все три адреса открыты без токена — документацию можно читать до логина.

| Адрес | Что это |
|---|---|
| `/api/docs/` | Swagger UI — интерактивная документация, запросы можно отправлять прямо из браузера |
| `/api/redoc/` | ReDoc — та же схема в виде читаемого справочника |
| `/api/schema/` | Сырая схема OpenAPI 3 в формате YAML |

Эндпоинты со стандартным поведением документируются автоматически. Нестандартные — подписка, создание платежа, проверка статуса — описаны вручную через `@extend_schema`: у них указаны тело запроса, коды ответов и примеры, потому что вывести это из сериализатора модели нельзя.

Выгрузить схему в файл:

```bash
poetry run python manage.py spectacular --file schema.yml
```

## Структура проекта

| Приложение | Что внутри |
|---|---|
| `config` | Настройки проекта и корневая маршрутизация |
| `lms` | Модели `Course` и `Lesson`, их сериализаторы и вьюхи |
| `users` | Кастомная модель `User`, модель `Payment`, классы прав доступа |

| Инфраструктура | Зачем |
|---|---|
| `Dockerfile` | Образ приложения |
| `docker-compose.yaml` | Локальная разработка: `runserver`, порт 8000 |
| `docker-compose.prod.yaml` | Сервер: Gunicorn, Nginx, образ из реестра |
| `nginx/default.conf` | Прокси на Gunicorn и раздача статики |
| `.github/workflows/ci.yml` | Конвейер: линт, тесты, сборка, деплой |
| `deploy/server-setup.sh` | Первичная настройка сервера: Docker, пользователь, SSH, firewall |
| `setup.cfg` | Правила flake8 |
| `.env.template` | Все переменные окружения с пояснениями |

## Авторизация

Проект закрыт по умолчанию: в настройках DRF стоит `IsAuthenticated`, аутентификация — по JWT. Без токена доступны только два эндпоинта: регистрация и получение пары токенов.

```bash
# 1. Регистрация
POST /api/register/
{ "email": "user@example.com", "password": "Str0ngPass!42" }

# 2. Получение пары токенов
POST /api/login/
{ "email": "user@example.com", "password": "Str0ngPass!42" }
→ { "access": "...", "refresh": "..." }

# 3. Все остальные запросы — с заголовком
Authorization: Bearer <access>

# 4. Когда access протух (60 минут)
POST /api/token/refresh/
{ "refresh": "..." }
→ { "access": "..." }
```

Пароль при регистрации проходит штатные валидаторы Django и сохраняется хешем. Email проверяется на уникальность без учёта регистра.

## Роли и права

| Роль | Кто это |
|---|---|
| **Модератор** | Пользователь в группе `Модераторы` (назначается в админке) |
| **Владелец** | Тот, кто создал курс или урок — поле `owner` заполняется автоматически |

Права по операциям:

| Операция | Модератор | Владелец | Остальные |
|---|---|---|---|
| Список курсов / уроков | видит все | видит только свои | видит только свои |
| Просмотр объекта | ✅ | ✅ | ❌ |
| Создание | ❌ | ✅ | ✅ |
| Редактирование | ✅ | ✅ | ❌ |
| Удаление | ❌ | ✅ | ❌ |

Классы прав лежат в `users/permissions.py`:

- `IsModer` — пользователь состоит в группе `Модераторы`
- `IsOwner` — пользователь является владельцем объекта
- `IsProfileOwner` — пользователь работает со своим профилем

Во вьюсете курсов права разделены по action через `get_permissions()`, у уроков каждая операция вынесена в отдельный контроллер со своим `permission_classes`.

## API

### Аутентификация и регистрация

| Метод | Эндпоинт | Доступ |
|---|---|---|
| POST | `/api/register/` | без токена |
| POST | `/api/login/` | без токена |
| POST | `/api/token/refresh/` | без токена |

### Пользователи

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/users/` | Список пользователей, общая информация |
| GET | `/api/users/<id>/` | Профиль |
| PATCH / PUT | `/api/users/<id>/update/` | Редактирование — только своего |
| DELETE | `/api/users/<id>/delete/` | Удаление — только своего |

Свой профиль отдаётся целиком: с фамилией, суммой платежей `payments_total` и полной историей платежей с вложенными данными курса и урока. Чужой профиль — только общая информация: id, email, имя, телефон, город, аватар. Пароль не отдаётся никогда.

### Курсы

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/courses/` | Список |
| POST | `/api/courses/` | Создать |
| GET | `/api/courses/<id>/` | Курс с количеством и списком уроков |
| PUT / PATCH | `/api/courses/<id>/` | Обновить |
| DELETE | `/api/courses/<id>/` | Удалить |

Реализовано через `ModelViewSet` + `DefaultRouter`. Ответ содержит вычисляемое поле `lessons_count`, вложенный список `lessons` и признак `is_subscribed` — подписан ли текущий пользователь на обновления курса.

### Подписка на обновления курса

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/api/subscription/` | Переключатель подписки |

Тело запроса — `{"course_id": 1}`. Один эндпоинт работает как переключатель: подписки нет — создаётся, есть — удаляется.

```json
{ "message": "подписка добавлена" }
{ "message": "подписка удалена" }
```

Пара «пользователь + курс» уникальна на уровне базы (`UniqueConstraint`), так что дубль подписки создать нельзя даже в обход API.

### Уроки

У каждой операции свой контроллер — так у каждой свои права.

| Метод | Эндпоинт | Контроллер |
|---|---|---|
| GET | `/api/lessons/` | `ListAPIView` |
| POST | `/api/lessons/create/` | `CreateAPIView` |
| GET | `/api/lessons/<id>/` | `RetrieveAPIView` |
| PUT / PATCH | `/api/lessons/<id>/update/` | `UpdateAPIView` |
| DELETE | `/api/lessons/<id>/delete/` | `DestroyAPIView` |

## Оплата через Stripe

Курс или урок можно оплатить картой. Работа с платёжным сервисом вынесена в `users/services.py` — вьюхи не знают, как устроен Stripe, и при смене эквайринга переписывать придётся только этот файл.

### Как проходит платёж

```
POST /api/payments/create/  {"paid_course": 1}
        │
        ├─ 1. Product.create           → prod_xxx   название курса
        ├─ 2. Price.create             → price_xxx  цена в копейках
        └─ 3. checkout.Session.create  → cs_xxx + ссылка на оплату
        │
        ▼
   Платёж сохранён: amount, stripe_product_id, stripe_price_id,
   session_id, payment_link, status = pending
        │
        ▼
   Пользователь открывает payment_link и платит
        │
        ▼
GET /api/payments/<id>/status/  → Session.retrieve → status = paid
```

Ответ на создание платежа:

```json
{
  "id": 7,
  "paid_course": 1,
  "amount": "12000.00",
  "status": "pending",
  "session_id": "cs_test_a1b2c3",
  "payment_link": "https://checkout.stripe.com/c/pay/cs_test_a1b2c3"
}
```

### Важные детали

**Сумма не принимается от клиента.** Она берётся из поля `price` курса или урока — иначе цену можно было бы подделать в запросе.

**Stripe считает в копейках.** `Price.create` получает `unit_amount = int(price * 100)`: 1234.56 ₽ уходит как 123456.

**Ровно один объект.** В запросе указывается либо `paid_course`, либо `paid_lesson`. Оба сразу или ни одного — 400.

**Ошибки Stripe отдаются как 502.** Недоступный сервис или неверный ключ — это не вина клиента, поэтому `502 Bad Gateway`, а не 400. Платёж при этом не создаётся.

### Тестовые карты

Аккаунт Stripe в тестовом режиме подтверждать не нужно. Для оплаты на странице Checkout подойдёт карта `4242 4242 4242 4242`, любая будущая дата и любой CVC. Остальные варианты — в [документации Stripe](https://docs.stripe.com/testing).

## Валидация ссылок

В материалах курсов и уроков допускаются ссылки только на `youtube.com` и `youtu.be`. Проверяются поля `video_url` и `description`.

Валидатор лежит в `lms/validators.py` и подключается в `Meta` сериализатора:

```python
validators = [
    LinksValidator(field='video_url'),
    LinksValidator(field='description'),
]
```

Он вытаскивает из текста все http/https-ссылки и сверяет хост. Поддомены YouTube проходят, а похожие на вид домены вроде `youtube.com.evil.ru` — нет: сравнивается именно хост, а не подстрока.

При нарушении возвращается 400 с понятным текстом:

```json
{
  "video_url": [
    "В материалах можно размещать ссылки только на youtube.com. Запрещённые ссылки: https://vimeo.com/123456"
  ]
}
```

## Пагинация

Классы пагинации в `lms/paginators.py`:

| Класс | `page_size` | `max_page_size` |
|---|---|---|
| `CoursePaginator` | 3 | 10 |
| `LessonPaginator` | 5 | 20 |

Размер страницы переопределяется параметром запроса: `?page_size=10`. Списки курсов и уроков отдаются в формате `{count, next, previous, results}`.

## Тесты

В Docker:

```bash
docker compose exec web python manage.py test
```

Без Docker (нужна запущенная база):

```bash
poetry run python manage.py test
```

114 тестов: CRUD уроков и курсов для всех групп пользователей, валидатор ссылок, подписки, регистрация, JWT, профили, платежи, оплата через Stripe, доступность документации, рассылка подписчикам и блокировка неактивных пользователей.

Обращения к Stripe замоканы, вызов Celery-задач подменяется, сами задачи вызываются напрямую — ни ключа, ни Redis, ни воркера для прогона тестов не нужно.

Покрытие:

```bash
poetry run coverage run manage.py test
poetry run coverage report > coverage.txt
poetry run coverage html          # HTML-отчёт в htmlcov/
```

Текущий результат — **99%**, отчёт сохранён в `coverage.txt`. Настройки покрытия в `.coveragerc`: миграции, сами тесты и служебные файлы Django из подсчёта исключены.

### Платежи

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/payments/` | Список платежей с фильтрацией и сортировкой |
| POST | `/api/payments/create/` | Создать платёж и получить ссылку на оплату |
| GET | `/api/payments/<id>/status/` | Статус оплаты по данным Stripe |

| Что нужно | Запрос |
|---|---|
| Сортировка по дате, по возрастанию | `/api/payments/?ordering=payment_date` |
| Сортировка по дате, по убыванию | `/api/payments/?ordering=-payment_date` |
| Сортировка по сумме | `/api/payments/?ordering=amount` |
| Фильтр по курсу | `/api/payments/?paid_course=1` |
| Фильтр по уроку | `/api/payments/?paid_lesson=3` |
| Фильтр по способу оплаты | `/api/payments/?payment_method=cash` |
| Фильтр по пользователю | `/api/payments/?user=1` |
| Комбинация | `/api/payments/?paid_course=2&payment_method=cash&ordering=amount` |

## Модели

**Course** — название, превью, описание, стоимость, владелец (FK на пользователя), дата последнего обновления (`updated_at`, `auto_now`).

**Subscription** — подписка: пользователь (FK), курс (FK), дата подписки. Пара «пользователь + курс» уникальна.

**Lesson** — название, описание, превью, ссылка на видео, стоимость, курс (FK, `related_name='lessons'`), владелец (FK на пользователя).

**User** — кастомная модель, `USERNAME_FIELD = 'email'`, плюс имя, фамилия, телефон, город, аватар.

**Payment** — пользователь (FK), дата оплаты, оплаченный курс (FK, nullable), оплаченный урок (FK, nullable), сумма, способ оплаты (`cash` — наличные, `transfer` — перевод на счет).

Плюс данные Stripe: `stripe_product_id`, `stripe_price_id`, `session_id`, `payment_link` и `status` (`pending` / `paid` / `canceled`).

### Целостность данных платежа

Платёж относится либо к курсу, либо к уроку — ровно к одному из двух. Правило закреплено на уровне базы:

```python
models.CheckConstraint(
    condition=(
        models.Q(paid_course__isnull=False, paid_lesson__isnull=True)
        | models.Q(paid_course__isnull=True, paid_lesson__isnull=False)
    ),
    name='payment_has_exactly_one_target',
)
```

Оба FK стоят с `on_delete=PROTECT`: курс или урок нельзя удалить, пока за него есть платежи — попытка вернёт `ProtectedError`. `SET_NULL` здесь не подходит: при удалении курса поле обнулилось бы и запись нарушила бы констрейнт.

Поле `owner` у курса и урока, наоборот, стоит с `SET_NULL` — удаление пользователя не должно утаскивать за собой учебные материалы.

## Фикстуры

| Файл | Что заливает |
|---|---|
| `users/fixtures/groups.json` | группа `Модераторы` |
| `users/fixtures/users.json` | 3 пользователя, один из них модератор |
| `lms/fixtures/courses.json` | 2 курса |
| `lms/fixtures/lessons.json` | 4 урока |
| `users/fixtures/payments.json` | 6 платежей |

Загружать в этом порядке — пользователи ссылаются на группу, курсы и уроки на пользователей, платежи на всё сразу:

```bash
poetry run python manage.py loaddata groups.json users.json courses.json lessons.json payments.json
```

Тестовые учётные записи, пароль у всех `test1234`:

| Email | Роль |
|---|---|
| `anna@example.com` | владелец курса 1 и уроков 1–3 |
| `boris@example.com` | владелец курса 2 и урока 4 |
| `moder@example.com` | модератор |

Снять фикстуру групп заново можно так:

```bash
poetry run python manage.py dumpdata auth.group --indent 2 > users/fixtures/groups.json
```
