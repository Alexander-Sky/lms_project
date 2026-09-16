from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    PaymentCreateAPIView,
    PaymentListAPIView,
    PaymentStatusAPIView,
    UserDestroyAPIView,
    UserListAPIView,
    UserRegisterAPIView,
    UserRetrieveAPIView,
    UserUpdateAPIView,
)

app_name = 'users'

LoginView = extend_schema(
    tags=['auth'],
    summary='Получить пару токенов',
    description='Принимает email и пароль, возвращает access и refresh. Доступен без авторизации.',
)(TokenObtainPairView)

RefreshView = extend_schema(
    tags=['auth'],
    summary='Обновить access-токен',
    description='Принимает refresh-токен, возвращает новый access. Доступен без авторизации.',
)(TokenRefreshView)

urlpatterns = [
    # Авторизация и регистрация — открыты для неавторизованных
    path('register/', UserRegisterAPIView.as_view(), name='register'),
    path('login/', LoginView.as_view(permission_classes=(AllowAny,)), name='login'),
    path('token/refresh/', RefreshView.as_view(permission_classes=(AllowAny,)), name='token-refresh'),

    # CRUD пользователей — только с токеном
    path('users/', UserListAPIView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserRetrieveAPIView.as_view(), name='user-detail'),
    path('users/<int:pk>/update/', UserUpdateAPIView.as_view(), name='user-update'),
    path('users/<int:pk>/delete/', UserDestroyAPIView.as_view(), name='user-delete'),

    # Платежи
    path('payments/', PaymentListAPIView.as_view(), name='payment-list'),
    path('payments/create/', PaymentCreateAPIView.as_view(), name='payment-create'),
    path('payments/<int:pk>/status/', PaymentStatusAPIView.as_view(), name='payment-status'),
]
