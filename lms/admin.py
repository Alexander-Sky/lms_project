from django.contrib import admin

from .models import Course, Lesson, Subscription


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'owner')
    search_fields = ('name', 'description')


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'course', 'price', 'owner')
    list_filter = ('course',)
    search_fields = ('name', 'description')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'course', 'created_at')
    list_filter = ('course',)
    search_fields = ('user__email', 'course__name')
