from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
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
    """Расширенный платёж: вместо id курса и урока — вложенные объекты."""

    paid_course = CourseSerializer(read_only=True)
    paid_lesson = LessonSerializer(read_only=True)


class UserRegisterSerializer(serializers.ModelSerializer):
    """Регистрация нового пользователя.

    Пароль принимается только на запись и сохраняется хешем.
    Уникальность email проверяет валидатор модели, пароль — валидаторы Django.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        label='Пароль',
    )

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name', 'phone', 'city')
        # Штатный UniqueValidator отключён, чтобы отдать своё сообщение
        # и заодно ловить дубли без учёта регистра.
        extra_kwargs = {'email': {'validators': []}}

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return value.lower()

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserPublicSerializer(serializers.ModelSerializer):
    """Чужой профиль: только общая информация.

    Без пароля, без фамилии и без истории платежей.
    """

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'phone', 'city', 'avatar')


class UserSerializer(serializers.ModelSerializer):
    """Свой профиль: полные данные и история платежей."""

    payments = PaymentDetailSerializer(many=True, read_only=True)
    payments_total = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
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
