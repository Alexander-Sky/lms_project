"""Логика уведомлений об обновлении курса.

Вынесена из вьюх, чтобы одно и то же правило работало и при правке курса,
и при правке отдельного урока.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Course
from .tasks import send_course_update_email

logger = logging.getLogger(__name__)


def is_stale(previous_updated_at) -> bool:
    """Прошло ли достаточно времени с прошлого обновления курса.

    None означает, что курс ни разу не обновлялся после добавления поля —
    в этом случае уведомляем.
    """
    if previous_updated_at is None:
        return True

    limit = timedelta(hours=settings.COURSE_UPDATE_NOTIFY_HOURS)
    return timezone.now() - previous_updated_at >= limit


def notify_course_subscribers(course: Course, previous_updated_at) -> bool:
    """Ставит задачу на рассылку, если курс не обновлялся дольше лимита.

    Пользователь может править уроки курса один за другим — без этой
    проверки подписчик получил бы письмо на каждую правку.

    Возвращает True, если задача поставлена в очередь.
    """
    if not is_stale(previous_updated_at):
        return False

    try:
        send_course_update_email.delay(course.pk)
    except Exception as error:
        # Redis недоступен или очередь не отвечает. Курс уже успешно обновлён,
        # и ронять запрос из-за рассылки нельзя: пользователь не виноват,
        # что почтовая очередь легла. Пишем в лог и отдаём ответ как обычно.
        logger.warning('Не удалось поставить рассылку по курсу %s: %s', course.pk, error)
        return False

    return True


def touch_course(course: Course) -> None:
    """Обновляет updated_at курса, не трогая остальные поля.

    Нужно при правке урока: сам курс при этом не сохраняется,
    а материалы курса всё-таки изменились.
    """
    course.save(update_fields=['updated_at'])
