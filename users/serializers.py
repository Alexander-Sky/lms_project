from django.db.models import Sum
from rest_framework import serializers

from lms.serializers import CourseSerializer, LessonSerializer

from .models import Payment, User


class PaymentSerializer(serializers.ModelSerializer):
    """Базовый сериализатор платежа — плоский, годится и для записи."""

    payment_method_display = serializers.CharField(
        source='get_payment_method_display',
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = '__all__'


class PaymentDetailSerializer(PaymentSerializer):
    """Расширенный платёж: вместо id курса и урока — вложенные объекты.

    Используется в истории платежей профиля (задание со звёздочкой).
    """

    paid_course = CourseSerializer(read_only=True)
    paid_lesson = LessonSerializer(read_only=True)


class UserSerializer(serializers.ModelSerializer):
    """Профиль пользователя с полной историей платежей."""

    payments = PaymentDetailSerializer(many=True, read_only=True)
    payments_total = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'phone',
            'city',
            'avatar',
            'payments_total',
            'payments',
        )

    def get_payments_total(self, obj: User) -> float:
        """Сумма всех платежей пользователя — считает база одним SELECT SUM()."""
        total = obj.payments.aggregate(total=Sum('amount'))['total']
        return float(total or 0)
