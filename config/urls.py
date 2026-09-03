"""
URL configuration for config project.
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny


def home(request):
    return JsonResponse({
        "message": "LMS API is running!",
        "docs": {
            "swagger": "/api/docs/",
            "redoc": "/api/redoc/",
            "schema": "/api/schema/",
        },
        "endpoints": {
            "register": "POST /api/register/",
            "login": "POST /api/login/",
            "refresh token": "POST /api/token/refresh/",
            "users": "/api/users/",
            "courses": "/api/courses/",
            "lessons": "/api/lessons/",
            "subscription": "POST /api/subscription/",
            "payments": "/api/payments/",
            "create payment": "POST /api/payments/create/",
            "payment status": "/api/payments/<id>/status/",
        },
    })


urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),

    # Документация. Открыта без токена, чтобы её можно было читать до логина.
    path('api/schema/', SpectacularAPIView.as_view(permission_classes=[AllowAny]), name='schema'),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[AllowAny]),
        name='swagger-ui',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema', permission_classes=[AllowAny]),
        name='redoc',
    ),

    path('api/', include('lms.urls')),
    path('api/', include('users.urls')),
]
