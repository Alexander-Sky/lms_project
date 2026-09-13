"""Инстанс Celery для проекта.

Импортируется в config/__init__.py, чтобы приложение поднималось вместе
с Django — иначе задачи не зарегистрируются.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Все настройки Celery живут в settings.py с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Ищет tasks.py во всех приложениях из INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Проверка, что воркер жив: celery -A config call config.debug_task"""
    print(f'Request: {self.request!r}')
