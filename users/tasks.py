from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import User


@shared_task
def block_inactive_users() -> int:
    """Блокирует пользователей, которые давно не заходили.

    Запускается по расписанию celery-beat раз в сутки.
    Возвращает количество заблокированных — попадает в лог воркера.

    Обновление идёт одним UPDATE на всю выборку, а не циклом с save()
    по каждому пользователю: на большой базе разница принципиальная.

    Пользователи с last_login = NULL (ни разу не входили) под фильтр
    не попадают — блокировать того, кто только что зарегистрировался,
    но ещё не логинился, было бы неверно.
    """
    threshold = timezone.now() - timedelta(days=settings.INACTIVITY_DAYS_LIMIT)

    blocked = User.objects.filter(
        is_active=True,
        last_login__lt=threshold,
    ).update(is_active=False)

    return blocked
