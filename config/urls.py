"""
URL configuration for config project.
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def home(request):
    return JsonResponse({
        "message": "LMS API is running!",
        "endpoints": {
            "register": "POST /api/register/",
            "login": "POST /api/login/",
            "refresh token": "POST /api/token/refresh/",
            "users": "/api/users/",
            "user profile": "/api/users/<id>/",
            "courses": "/api/courses/",
            "lessons": "/api/lessons/",
            "payments": "/api/payments/",
        },
    })


urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('lms.urls')),
    path('api/', include('users.urls')),
]
