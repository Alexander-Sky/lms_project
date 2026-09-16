# Slim-образ: полноценный Python без лишних системных пакетов.
# Версия совпадает с requires-python в pyproject.toml.
FROM python:3.14-slim

# PYTHONDONTWRITEBYTECODE — не засорять образ .pyc, они всё равно одноразовые.
# PYTHONUNBUFFERED — иначе логи Django копятся в буфере и docker logs пустой.
# POETRY_VIRTUALENVS_CREATE — внутри контейнера окружение уже изолировано,
# второе виртуальное окружение поверх него только мешает.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.4.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Зависимости ставятся отдельным слоем, до копирования кода.
# Пока pyproject.toml и poetry.lock не менялись, Docker берёт этот слой
# из кэша, и пересборка после правки кода занимает секунды, а не минуты.
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# Код копируется последним — он меняется чаще всего.
COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
