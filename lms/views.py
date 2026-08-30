from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated

from users.permissions import IsModer, IsOwner

from .models import Course, Lesson
from .serializers import CourseSerializer, LessonSerializer


class OwnerQuerysetMixin:
    """Модератор видит всё, остальные — только свои объекты."""

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if IsModer().has_permission(self.request, self):
            return queryset
        return queryset.filter(owner=user)


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


class LessonCreateAPIView(generics.CreateAPIView):
    """Создание урока. Модератору запрещено."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, ~IsModer)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class LessonListAPIView(OwnerQuerysetMixin, generics.ListAPIView):
    """Список уроков: модератору — все, остальным — только свои."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated,)


class LessonRetrieveAPIView(generics.RetrieveAPIView):
    """Просмотр урока: модератор или владелец."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, IsModer | IsOwner)


class LessonUpdateAPIView(generics.UpdateAPIView):
    """Редактирование урока: модератор или владелец."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, IsModer | IsOwner)


class LessonDestroyAPIView(generics.DestroyAPIView):
    """Удаление урока: только владелец. Модератору запрещено."""

    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated, ~IsModer, IsOwner)
