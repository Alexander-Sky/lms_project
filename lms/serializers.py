from rest_framework import serializers

from .models import Course, Lesson, Subscription
from .validators import LinksValidator


class LessonSerializer(serializers.ModelSerializer):
    """Сериализатор для урока.

    Ссылки в video_url и в описании проверяются валидатором:
    к записи допускаются только ссылки на youtube.com.
    """

    class Meta:
        model = Lesson
        fields = ('id', 'name', 'description', 'preview', 'video_url', 'course', 'owner')
        read_only_fields = ('owner',)
        validators = [
            LinksValidator(field='video_url'),
            LinksValidator(field='description'),
        ]


class CourseSerializer(serializers.ModelSerializer):
    """Сериализатор для курса.

    lessons_count — количество уроков курса,
    lessons — полная информация по всем урокам курса,
    is_subscribed — подписан ли текущий пользователь на обновления курса.
    Владелец проставляется во вьюхе и на запись не принимается.
    """

    lessons_count = serializers.SerializerMethodField(read_only=True)
    lessons = LessonSerializer(many=True, read_only=True)
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Course
        fields = (
            'id',
            'name',
            'preview',
            'description',
            'owner',
            'is_subscribed',
            'lessons_count',
            'lessons',
        )
        read_only_fields = ('owner',)
        validators = [LinksValidator(field='description')]

    def get_lessons_count(self, obj: Course) -> int:
        """Считает уроки курса через related_name='lessons'."""
        return obj.lessons.count()

    def get_is_subscribed(self, obj: Course) -> bool:
        """Признак подписки текущего пользователя на этот курс."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return Subscription.objects.filter(user=request.user, course=obj).exists()


class SubscriptionSerializer(serializers.ModelSerializer):
    """Подписка — для админки и возможного вывода списком."""

    class Meta:
        model = Subscription
        fields = ('id', 'user', 'course', 'created_at')
        read_only_fields = ('user', 'created_at')


class SubscriptionRequestSerializer(serializers.Serializer):
    """Тело запроса на переключение подписки."""

    course_id = serializers.IntegerField(
        help_text='ID курса, на обновления которого переключается подписка.',
    )


class SubscriptionResponseSerializer(serializers.Serializer):
    """Ответ эндпоинта подписки."""

    message = serializers.CharField(
        help_text='«подписка добавлена» или «подписка удалена».',
    )
