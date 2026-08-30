from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Payment, User
from .permissions import IsProfileOwner
from .serializers import (
    PaymentSerializer,
    UserPublicSerializer,
    UserRegisterSerializer,
    UserSerializer,
)


class UserRegisterAPIView(generics.CreateAPIView):
    """Регистрация. Единственный эндпоинт users, открытый без токена."""

    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = (AllowAny,)


class UserListAPIView(generics.ListAPIView):
    """Список пользователей — только общая информация."""

    queryset = User.objects.all()
    serializer_class = UserPublicSerializer
    permission_classes = (IsAuthenticated,)


class UserRetrieveAPIView(generics.RetrieveAPIView):
    """Профиль пользователя.

    Свой профиль отдаётся целиком, вместе с историей платежей.
    Чужой — в урезанном виде: без фамилии и без платежей.
    """

    queryset = User.objects.all()
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.get_object() == self.request.user:
            return UserSerializer
        return UserPublicSerializer

    def get_queryset(self):
        return User.objects.prefetch_related('payments__paid_course__lessons', 'payments__paid_lesson')


class UserUpdateAPIView(generics.UpdateAPIView):
    """Редактирование профиля — только своего."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated, IsProfileOwner)


class UserDestroyAPIView(generics.DestroyAPIView):
    """Удаление профиля — только своего."""

    queryset = User.objects.all()
    permission_classes = (IsAuthenticated, IsProfileOwner)


class PaymentListAPIView(generics.ListAPIView):
    """Список платежей с фильтрацией и сортировкой.

    Примеры запросов:
        /api/payments/?ordering=payment_date      — по возрастанию даты
        /api/payments/?ordering=-payment_date     — по убыванию даты
        /api/payments/?paid_course=1              — только по курсу 1
        /api/payments/?paid_lesson=3              — только по уроку 3
        /api/payments/?payment_method=cash        — только наличные
    """

    queryset = Payment.objects.select_related('user', 'paid_course', 'paid_lesson')
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)

    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ('paid_course', 'paid_lesson', 'payment_method', 'user')
    ordering_fields = ('payment_date', 'amount')
    ordering = ('-payment_date',)
