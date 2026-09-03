# LMS Project

Учебная LMS-система на Django REST Framework: курсы, уроки, пользователи, платежи и разграничение прав доступа.

## Стек

- Python 3.14
- Django 6.1
- Django REST Framework
- djangorestframework-simplejwt — JWT-авторизация
- drf-spectacular — OpenAPI-документация
- stripe — приём оплаты
- django-filter
- python-dotenv — переменные окружения
- coverage — покрытие тестами
- SQLite
- Poetry

## Установка и запуск

Скопируйте `.env.sample` в `.env` и заполните значения:

```bash
cp .env.sample .env
```

| Переменная | Зачем |
|---|---|
| `SECRET_KEY` | Ключ Django. Без него используется небезопасное значение по умолчанию |
| `DEBUG` | `True` для разработки, `False` для боевого запуска |
| `STRIPE_API_KEY` | Тестовый ключ из [дашборда Stripe](https://dashboard.stripe.com/test/apikeys), начинается на `sk_test_` |
| `STRIPE_SUCCESS_URL` | Куда Stripe вернёт пользователя после успешной оплаты |
| `STRIPE_CANCEL_URL` | Куда вернёт при отмене |

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

```bash
poetry run python manage.py test
```

90 тестов: CRUD уроков и курсов для всех групп пользователей, валидатор ссылок, подписки, регистрация, JWT, профили, платежи, оплата через Stripe и доступность документации.

Обращения к Stripe в тестах замоканы — реальный ключ и сеть не нужны, тесты проходят где угодно.

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

**Course** — название, превью, описание, стоимость, владелец (FK на пользователя).

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
