# LMS Project

Учебная LMS-система на Django REST Framework: курсы, уроки, пользователи и платежи.

## Стек

- Python 3.14
- Django 6.1
- Django REST Framework
- django-filter
- SQLite
- Poetry

## Установка и запуск

```bash
poetry install --no-root
poetry run python manage.py migrate
poetry run python manage.py loaddata users.json courses.json lessons.json payments.json
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
| `users` | Кастомная модель `User` (вход по email) и модель `Payment` |

## Модели

**Course** — название, превью, описание.

**Lesson** — название, описание, превью, ссылка на видео, курс (FK, `related_name='lessons'`).

**User** — кастомная модель, `USERNAME_FIELD = 'email'`, плюс телефон, город, аватар.

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

## API

### Курсы

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/courses/` | Список курсов |
| POST | `/api/courses/` | Создать курс |
| GET | `/api/courses/<id>/` | Курс с количеством и списком уроков |
| PUT | `/api/courses/<id>/` | Обновить курс |
| DELETE | `/api/courses/<id>/` | Удалить курс |

Реализовано через `ModelViewSet` + `DefaultRouter`.

Ответ содержит вычисляемое поле `lessons_count` и вложенный список `lessons`:

```json
{
  "id": 1,
  "name": "Django REST Framework с нуля",
  "description": "...",
  "lessons_count": 3,
  "lessons": [
    { "id": 1, "name": "Что такое сериализатор", "course": 1 }
  ]
}
```

### Уроки

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/lessons/` | Список уроков |
| POST | `/api/lessons/` | Создать урок |
| GET | `/api/lessons/<id>/` | Один урок |
| PUT | `/api/lessons/<id>/` | Обновить урок |
| DELETE | `/api/lessons/<id>/` | Удалить урок |

Реализовано через дженерики `ListCreateAPIView` и `RetrieveUpdateDestroyAPIView`.

### Платежи

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/payments/` | Список платежей с фильтрацией и сортировкой |

Фильтрация — `DjangoFilterBackend`, сортировка — `OrderingFilter`.

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

### Профиль пользователя

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/users/<id>/` | Профиль с полной историей платежей |

История платежей отдаётся расширенным сериализатором: вместо id курса и урока — вложенные объекты. Дополнительно считается `payments_total` — сумма всех платежей пользователя, через `aggregate(Sum('amount'))` на стороне базы.

## Фикстуры

| Файл | Что заливает |
|---|---|
| `users/fixtures/users.json` | 2 пользователя |
| `lms/fixtures/courses.json` | 2 курса |
| `lms/fixtures/lessons.json` | 4 урока |
| `users/fixtures/payments.json` | 6 платежей |

В каждом платеже заполнено ровно одно из полей `paid_course` / `paid_lesson` — иначе загрузка упадёт на констрейнте.

Загружать в этом порядке — платежи ссылаются на пользователей, курсы и уроки:

```bash
poetry run python manage.py loaddata users.json courses.json lessons.json payments.json
```

Пароль тестовых пользователей — `test1234`.
