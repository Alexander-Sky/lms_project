from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsModer, IsOwner

from .models import Course, Lesson, Subscription
from .paginators import CoursePaginator, LessonPaginator
from .serializers import (
    CourseSerializer,
    LessonSerializer,
    SubscriptionRequestSerializer,
    SubscriptionResponseSerializer,
)


class OwnerQuerysetMixin:
    """Модератор видит всё, остальные — только свои объекты."""

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if IsModer().has_permission(self.request, self):
            return queryset
        return queryset.filter(owner=user)


@extend_schema(tags=['courses'])
@extend_schema_view(
    list=extend_schema(
        summary='Список курсов',
        description='Модератор видит все курсы, остальные — только свои. Ответ постраничный.',
    ),
    create=extend_schema(
        summary='Создать курс',
        description='Владельцем становится автор запроса. Модератору создавать курсы нельзя.',
    ),
    retrieve=extend_schema(
        summary='Курс целиком',
        description=(
            'Возвращает курс вместе с количеством уроков, полным списком уроков '
            'и признаком подписки текущего пользователя.'
        ),
    ),
    update=extend_schema(summary='Заменить курс', description='Доступно владельцу и модератору.'),
    partial_update=extend_schema(summary='Изменить курс', description='Доступно владельцу и модератору.'),
    destroy=extend_schema(
        summary='Удалить курс',
        description='Доступно только владельцу. Модератору удалять запрещено.',
    ),
)
class CourseViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    """CRUD курсов. Права разделены по action.

    create   — любой авторизованный, кроме модератора
    list     — любой авторизованный (выборка ограничена своими курсами)
    retrieve — модератор или владелец
    update   — модератор или владелец
    destroy  — только владелец, модератору удалять нельзя
    """

    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    pagination_class = CoursePaginator

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [IsAuthenticated, ~IsModer]
        elif self.action in ('update', 'partial_update', 'retrieve'):
            self.permission_classes = [IsAuthenticated, IsModer | IsOwner]
        elif self.action == 'destroy':
            self.permission_classes = [IsAuthenticated, ~IsModer, IsOwner]
        else:
            self.permission_classes = [IsAuthenticated]
        return [permission() for permission in self.permission_classes]

    def perform_create(self, serializer):
        """Владельцем курса становится тот, кто его создал."""
        serializer.save(owner=self.request.user)


@extend_schema(
    tags=['lessons'],
    summary='Создать урок',
    description=(
        'Владельцем становится автор запроса. Модератору создавать уроки нельзя.\n\n'
        'Ссылки в `video_url` и `description` проверяются: допускается только youtube.com.'
    ),
    responses={
        201: LessonSerializer,
        400: OpenApiResponse(description='В материалах есть ссылка на сторонний ресурс'),
        403: OpenApiResponse(description='Модератор не может создавать уроки'),
    },
)
class LessonCreateAPIView(generics.CreateAPIView):
    """Создание урока. Модератору запрещено."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, ~IsModer)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(
    tags=['lessons'],
    summary='Список уроков',
    description='Модератор видит все уроки, остальные — только свои. Ответ постраничный.',
)
class LessonListAPIView(OwnerQuerysetMixin, generics.ListAPIView):
    """Список уроков: модератору — все, остальным — только свои."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = LessonPaginator


@extend_schema(
    tags=['lessons'],
    summary='Урок',
    description='Доступно владельцу и модератору.',
    responses={200: LessonSerializer, 403: OpenApiResponse(description='Чужой урок')},
)
class LessonRetrieveAPIView(generics.RetrieveAPIView):
    """Просмотр урока: модератор или владелец."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, IsModer | IsOwner)


@extend_schema(
    tags=['lessons'],
    summary='Изменить урок',
    description='Доступно владельцу и модератору. Ссылки проверяются валидатором.',
    responses={
        200: LessonSerializer,
        400: OpenApiResponse(description='В материалах есть ссылка на сторонний ресурс'),
        403: OpenApiResponse(description='Чужой урок'),
    },
)
class LessonUpdateAPIView(generics.UpdateAPIView):
    """Редактирование урока: модератор или владелец."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, IsModer | IsOwner)


@extend_schema(
    tags=['lessons'],
    summary='Удалить урок',
    description='Доступно только владельцу. Модератору удалять запрещено.',
    responses={204: None, 403: OpenApiResponse(description='Чужой урок или запрос от модератора')},
)
class LessonDestroyAPIView(generics.DestroyAPIView):
    """Удаление урока: только владелец. Модератору запрещено."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, ~IsModer, IsOwner)


@extend_schema(
    tags=['subscriptions'],
    summary='Переключить подписку на курс',
    description=(
        'Один эндпоинт работает переключателем: если подписки нет — она создаётся, '
        'если есть — удаляется. Отдельного метода на отписку не требуется.\n\n'
        'Тело запроса нестандартное — это не сериализатор модели, поэтому схема описана вручную.'
    ),
    request=SubscriptionRequestSerializer,
    responses={
        200: SubscriptionResponseSerializer,
        400: OpenApiResponse(description='Не передан course_id'),
        404: OpenApiResponse(description='Курс с таким id не найден'),
    },
    examples=[
        OpenApiExample('Запрос', value={'course_id': 1}, request_only=True),
        OpenApiExample('Подписка создана', value={'message': 'подписка добавлена'}, response_only=True),
        OpenApiExample('Подписка снята', value={'message': 'подписка удалена'}, response_only=True),
    ],
)
class SubscriptionAPIView(APIView):
    """Подписка на обновления курса — переключатель.

    POST /api/subscription/ с телом {"course_id": 1}
    Подписки нет — создаём, подписка есть — удаляем.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = SubscriptionRequestSerializer

    def post(self, request, *args, **kwargs):
        user = request.user
        course_id = request.data.get('course_id')

        if not course_id:
            return Response(
                {'course_id': 'Обязательное поле.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course_item = get_object_or_404(Course, pk=course_id)
        subs_item = Subscription.objects.filter(user=user, course=course_item)

        if subs_item.exists():
            subs_item.delete()
            message = 'подписка удалена'
        else:
            Subscription.objects.create(user=user, course=course_item)
            message = 'подписка добавлена'

        return Response({'message': message})
