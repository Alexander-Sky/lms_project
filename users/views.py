import stripe
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment, User
from .permissions import IsProfileOwner
from .serializers import (
    PaymentCreateSerializer,
    PaymentSerializer,
    PaymentStatusSerializer,
    UserPublicSerializer,
    UserRegisterSerializer,
    UserSerializer,
)
from .services import (
    create_stripe_price,
    create_stripe_product,
    create_stripe_session,
    retrieve_stripe_session,
)


class PaymentServiceError(APIException):
    """Stripe ответил ошибкой — это не вина клиента, отдаём 502."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = 'Платёжный сервис недоступен. Попробуйте позже.'
    default_code = 'payment_service_error'


@extend_schema(
    tags=['auth'],
    summary='Регистрация пользователя',
    description=(
        'Создаёт пользователя. Единственный эндпоинт, кроме получения токена, '
        'доступный без авторизации. Пароль сохраняется хешем и в ответе не возвращается.'
    ),
    responses={
        201: UserRegisterSerializer,
        400: OpenApiResponse(description='Email уже занят или пароль не прошёл валидацию'),
    },
)
class UserRegisterAPIView(generics.CreateAPIView):
    """Регистрация. Единственный эндпоинт users, открытый без токена."""

    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = (AllowAny,)


@extend_schema(
    tags=['users'],
    summary='Список пользователей',
    description='Общая информация о пользователях, без фамилий и истории платежей.',
)
class UserListAPIView(generics.ListAPIView):
    """Список пользователей — только общая информация."""

    queryset = User.objects.all()
    serializer_class = UserPublicSerializer
    permission_classes = (IsAuthenticated,)


@extend_schema(
    tags=['users'],
    summary='Профиль пользователя',
    description=(
        'Свой профиль отдаётся целиком: с фамилией, суммой платежей и полной историей. '
        'Чужой — только общая информация.'
    ),
    responses={200: UserSerializer},
)
class UserRetrieveAPIView(generics.RetrieveAPIView):
    """Профиль пользователя: свой — целиком, чужой — в урезанном виде."""

    queryset = User.objects.all()
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.get_object() == self.request.user:
            return UserSerializer
        return UserPublicSerializer

    def get_queryset(self):
        return User.objects.prefetch_related('payments__paid_course__lessons', 'payments__paid_lesson')


@extend_schema(
    tags=['users'],
    summary='Редактирование профиля',
    description='Редактировать можно только свой профиль, чужой вернёт 403.',
    responses={200: UserSerializer, 403: OpenApiResponse(description='Это не ваш профиль')},
)
class UserUpdateAPIView(generics.UpdateAPIView):
    """Редактирование профиля — только своего."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated, IsProfileOwner)


@extend_schema(
    tags=['users'],
    summary='Удаление профиля',
    description='Удалить можно только свой профиль.',
    responses={204: None, 403: OpenApiResponse(description='Это не ваш профиль')},
)
class UserDestroyAPIView(generics.DestroyAPIView):
    """Удаление профиля — только своего."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated, IsProfileOwner)


@extend_schema(
    tags=['payments'],
    summary='Список платежей',
    description=(
        'Поддерживает сортировку по дате и сумме (`ordering`) и фильтрацию '
        'по курсу, уроку, способу оплаты и пользователю.'
    ),
)
class PaymentListAPIView(generics.ListAPIView):
    """Список платежей с фильтрацией и сортировкой.

    Примеры запросов:
        /api/payments/?ordering=payment_date      — по возрастанию даты
        /api/payments/?ordering=-payment_date     — по убыванию даты
        /api/payments/?paid_course=1              — только по курсу 1
        /api/payments/?payment_method=cash        — только наличные
    """

    queryset = Payment.objects.select_related('user', 'paid_course', 'paid_lesson')
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)

    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ('paid_course', 'paid_lesson', 'payment_method', 'user')
    ordering_fields = ('payment_date', 'amount')
    ordering = ('-payment_date',)


@extend_schema(
    tags=['payments'],
    summary='Создать платёж и получить ссылку на оплату',
    description=(
        'Принимает курс **или** урок — ровно одно из двух. Сумма берётся из стоимости '
        'объекта, а не из запроса.\n\n'
        'Под капотом последовательно создаются продукт, цена и сессия оплаты в Stripe. '
        'Цена уходит в Stripe в копейках. Полученные идентификаторы и ссылка на оплату '
        'сохраняются в платеже и возвращаются в ответе.'
    ),
    request=PaymentCreateSerializer,
    responses={
        201: PaymentCreateSerializer,
        400: OpenApiResponse(description='Указаны оба объекта сразу, ни одного, или у объекта нулевая цена'),
        502: OpenApiResponse(description='Stripe вернул ошибку'),
    },
    examples=[
        OpenApiExample(
            'Оплата курса',
            value={'paid_course': 1, 'payment_method': 'transfer'},
            request_only=True,
        ),
        OpenApiExample(
            'Оплата отдельного урока',
            value={'paid_lesson': 3, 'payment_method': 'transfer'},
            request_only=True,
        ),
    ],
)
class PaymentCreateAPIView(generics.CreateAPIView):
    """Создание платежа с оплатой через Stripe."""

    queryset = Payment.objects.all()
    serializer_class = PaymentCreateSerializer
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        item = serializer.validated_data.get('paid_course') or serializer.validated_data.get('paid_lesson')

        try:
            product_id = create_stripe_product(name=str(item), description=item.description)
            price_id = create_stripe_price(product_id=product_id, amount=item.price)
            session_id, payment_link = create_stripe_session(price_id=price_id)
        except stripe.StripeError as error:
            raise PaymentServiceError(f'Stripe вернул ошибку: {error}')

        serializer.save(
            user=self.request.user,
            amount=item.price,
            payment_date=timezone.now().date(),
            stripe_product_id=product_id,
            stripe_price_id=price_id,
            session_id=session_id,
            payment_link=payment_link,
        )


@extend_schema(
    tags=['payments'],
    summary='Статус оплаты',
    description=(
        'Запрашивает у Stripe данные сессии по сохранённому `session_id` и заодно '
        'обновляет статус платежа в базе: `paid`, если оплата прошла, `canceled`, '
        'если сессия истекла.\n\n'
        'Доступен только владельцу платежа.'
    ),
    responses={
        200: PaymentStatusSerializer,
        404: OpenApiResponse(description='Платёж не найден или принадлежит другому пользователю'),
        400: OpenApiResponse(description='У платежа нет сессии Stripe'),
        502: OpenApiResponse(description='Stripe вернул ошибку'),
    },
)
class PaymentStatusAPIView(APIView):
    """Проверка статуса платежа через Stripe Session Retrieve."""

    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentStatusSerializer

    def get(self, request, pk, *args, **kwargs):
        payment = Payment.objects.filter(pk=pk, user=request.user).first()

        if payment is None:
            return Response({'detail': 'Платёж не найден.'}, status=status.HTTP_404_NOT_FOUND)

        if not payment.session_id:
            return Response(
                {'detail': 'У этого платежа нет сессии Stripe — он не оплачивался онлайн.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = retrieve_stripe_session(payment.session_id)
        except stripe.StripeError as error:
            raise PaymentServiceError(f'Stripe вернул ошибку: {error}')

        if session.get('payment_status') == 'paid':
            payment.status = Payment.PAID
            payment.save(update_fields=['status'])
        elif session.get('status') == 'expired':
            payment.status = Payment.CANCELED
            payment.save(update_fields=['status'])

        return Response(session)
