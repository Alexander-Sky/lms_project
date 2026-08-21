from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter

from .models import Payment, User
from .serializers import PaymentSerializer, UserSerializer


class PaymentListAPIView(generics.ListAPIView):
    """Список платежей с фильтрацией и сортировкой (задание 4).

    Примеры запросов:
        /api/payments/?ordering=payment_date      — по возрастанию даты
        /api/payments/?ordering=-payment_date     — по убыванию даты
        /api/payments/?paid_course=1              — только по курсу 1
        /api/payments/?paid_lesson=3              — только по уроку 3
        /api/payments/?payment_method=cash        — только наличные
        /api/payments/?paid_course=1&payment_method=transfer&ordering=amount
    """

    queryset = Payment.objects.select_related('user', 'paid_course', 'paid_lesson')
    serializer_class = PaymentSerializer

    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ('paid_course', 'paid_lesson', 'payment_method', 'user')
    ordering_fields = ('payment_date', 'amount')
    ordering = ('-payment_date',)


class UserRetrieveAPIView(generics.RetrieveAPIView):
    """Профиль пользователя вместе с историей платежей (задание со звёздочкой)."""

    queryset = User.objects.prefetch_related('payments__paid_course__lessons', 'payments__paid_lesson')
    serializer_class = UserSerializer
