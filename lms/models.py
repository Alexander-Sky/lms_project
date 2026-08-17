from django.db import models
from users.models import User

class Course(models.Model):
    """Модель курса"""
    name = models.CharField(max_length=255, verbose_name="Название")
    preview = models.ImageField(upload_to='courses/', blank=True, null=True, verbose_name="Превью")
    description = models.TextField(blank=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"

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

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"

    def __str__(self):
        return self.name