from django.conf import settings
from django.db import models

NULLABLE = {'blank': True, 'null': True}


class Course(models.Model):
    """Модель курса"""
    name = models.CharField(max_length=255, verbose_name="Название")
    preview = models.ImageField(upload_to='courses/', blank=True, null=True, verbose_name="Превью")
    description = models.TextField(blank=True, verbose_name="Описание")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Стоимость",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='courses',
        verbose_name='Владелец',
        **NULLABLE,
    )

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        ordering = ('id',)  # без явного порядка пагинация может тасовать записи

    def __str__(self):
        return self.name

class Lesson(models.Model):
    """Модель урока"""
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name="Курс"
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    preview = models.ImageField(upload_to='lessons/', blank=True, null=True, verbose_name="Превью")
    video_url = models.URLField(blank=True, null=True, verbose_name="Ссылка на видео")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Стоимость",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='lessons',
        verbose_name='Владелец',
        **NULLABLE,
    )

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        ordering = ('id',)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    """Подписка пользователя на обновления курса."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Пользователь',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Курс',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата подписки')

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        ordering = ('-created_at',)
        constraints = [
            # Один пользователь — одна подписка на курс
            models.UniqueConstraint(
                fields=('user', 'course'),
                name='unique_user_course_subscription',
            ),
        ]

    def __str__(self):
        return f'{self.user} → {self.course}'