from django.urls import path

from .views import PaymentListAPIView, UserRetrieveAPIView

app_name = 'users'

urlpatterns = [
    path('payments/', PaymentListAPIView.as_view(), name='payment-list'),
    path('users/<int:pk>/', UserRetrieveAPIView.as_view(), name='user-detail'),
]
