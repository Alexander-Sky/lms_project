# LMS Project

Учебная LMS-система на Django REST Framework: курсы, уроки, пользователи, платежи и разграничение прав доступа.

## Стек

- Python 3.14
- Django 6.1
- Django REST Framework
- djangorestframework-simplejwt — JWT-авторизация
- django-filter
- SQLite
- Poetry

## Установка и запуск

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

Реализовано через `ModelViewSet` + `DefaultRouter`. Ответ содержит вычисляемое поле `lessons_count` и вложенный список `lessons`.

### Уроки

У каждой операции свой контроллер — так у каждой свои права.

| Метод | Эндпоинт | Контроллер |
|---|---|---|
| GET | `/api/lessons/` | `ListAPIView` |
| POST | `/api/lessons/create/` | `CreateAPIView` |
| GET | `/api/lessons/<id>/` | `RetrieveAPIView` |
| PUT / PATCH | `/api/lessons/<id>/update/` | `UpdateAPIView` |
| DELETE | `/api/lessons/<id>/delete/` | `DestroyAPIView` |

### Платежи

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/payments/` | Список платежей с фильтрацией и сортировкой |

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

**Course** — название, превью, описание, владелец (FK на пользователя).

**Lesson** — название, описание, превью, ссылка на видео, курс (FK, `related_name='lessons'`), владелец (FK на пользователя).

**User** — кастомная модель, `USERNAME_FIELD = 'email'`, плюс имя, фамилия, телефон, город, аватар.

**Payment** — пользователь (FK), дата оплаты, оплаченный курс (FK, nullable), оплаченный урок (FK, nullable), сумма, способ оплаты (`cash` — наличные, `transfer` — перевод на счет).

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
