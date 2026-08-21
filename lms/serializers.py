from rest_framework import serializers

from .models import Course, Lesson


class LessonSerializer(serializers.ModelSerializer):
    """Сериализатор для урока."""

    class Meta:
        model = Lesson
        fields = '__all__'


class CourseSerializer(serializers.ModelSerializer):
    """Сериализатор для курса.

    lessons_count — количество уроков курса (задание 1),
    lessons — полная информация по всем урокам курса (задание 3).
    Оба поля отдаются одним сериализатором одновременно.
    """

    lessons_count = serializers.SerializerMethodField(read_only=True)
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = (
            'id',
            'name',
            'preview',
            'description',
            'lessons_count',
            'lessons',
        )

    def get_lessons_count(self, obj: Course) -> int:
        """Считает уроки курса через related_name='lessons'."""
        return obj.lessons.count()
