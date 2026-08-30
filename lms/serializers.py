from rest_framework import serializers

from .models import Course, Lesson


class LessonSerializer(serializers.ModelSerializer):
    """Сериализатор для урока."""

    class Meta:
        model = Lesson
        fields = ('id', 'name', 'description', 'preview', 'video_url', 'course', 'owner')
        read_only_fields = ('owner',)


class CourseSerializer(serializers.ModelSerializer):
    """Сериализатор для курса.

    lessons_count — количество уроков курса,
    lessons — полная информация по всем урокам курса.
    Владелец проставляется во вьюхе и на запись не принимается.
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
            'owner',
            'lessons_count',
            'lessons',
        )
        read_only_fields = ('owner',)

    def get_lessons_count(self, obj: Course) -> int:
        """Считает уроки курса через related_name='lessons'."""
        return obj.lessons.count()
