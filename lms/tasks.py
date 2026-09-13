from celery import shared_task
from django.conf import settings
from django.core.mail import send_mass_mail

from .models import Course, Subscription


@shared_task
def send_course_update_email(course_id: int) -> int:
    """Рассылает подписчикам письмо об обновлении курса.

    Возвращает количество отправленных писем — так в логе воркера сразу
    видно, сработала задача вхолостую или нет.

    Каждому подписчику уходит отдельное письмо: если сложить всех в один
    recipient_list, адреса попадут в поле To и станут видны друг другу.
    send_mass_mail при этом открывает одно соединение с SMTP на всю рассылку.
    """
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        # Курс успели удалить, пока задача ждала в очереди
        return 0

    emails = list(
        Subscription.objects
        .filter(course=course)
        .exclude(user__email='')
        .values_list('user__email', flat=True)
    )
    if not emails:
        return 0

    subject = f'Обновление курса «{course.name}»'
    body = (
        f'Здравствуйте!\n\n'
        f'Материалы курса «{course.name}», на который вы подписаны, обновились.\n'
        f'Загляните в личный кабинет, чтобы посмотреть, что нового.\n\n'
        f'Если вы больше не хотите получать эти письма, отключите подписку на курс.'
    )

    messages = [(subject, body, settings.DEFAULT_FROM_EMAIL, [email]) for email in emails]
    send_mass_mail(messages, fail_silently=False)

    return len(messages)
