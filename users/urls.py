from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    PaymentListAPIView,
    UserDestroyAPIView,
    UserListAPIView,
    UserRegisterAPIView,
    UserRetrieveAPIView,
    UserUpdateAPIView,
)

app_name = 'users'

urlpatterns = [
    # Авторизация и регистрация — открыты для неавторизованных
    path('register/', UserRegisterAPIView.as_view(), name='register'),
    path(
        'login/',
        TokenObtainPairView.as_view(permission_classes=(AllowAny,)),
        name='login',
    ),
    path(
        'token/refresh/',
        TokenRefreshView.as_view(permission_classes=(AllowAny,)),
        name='token-refresh',
    ),

    # CRUD пользователей — только с токеном
    path('users/', UserListAPIView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserRetrieveAPIView.as_view(), name='user-detail'),
    path('users/<int:pk>/update/', UserUpdateAPIView.as_view(), name='user-update'),
    path('users/<int:pk>/delete/', UserDestroyAPIView.as_view(), name='user-delete'),

    # Платежи
    path('payments/', PaymentListAPIView.as_view(), name='payment-list'),
]
