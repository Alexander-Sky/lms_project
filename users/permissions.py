from rest_framework.permissions import BasePermission

MODERATORS_GROUP = 'Модераторы'


class IsModer(BasePermission):
    """Пользователь состоит в группе модераторов."""

    message = 'Действие доступно только модераторам.'

    def has_permission(self, request, view):
        return request.user.groups.filter(name=MODERATORS_GROUP).exists()

    def has_object_permission(self, request, view, obj):
        # Важно продублировать проверку на уровне объекта.
        # DRF в конструкции ~IsModer инвертирует ОБА метода, а базовый
        # has_object_permission всегда возвращает True — без этой строки
        # ~IsModer запрещал бы доступ вообще всем, включая владельца.
        return self.has_permission(request, view)


class IsOwner(BasePermission):
    """Пользователь — владелец объекта.

    Проверка объектная: DRF вызывает её после получения объекта
    (в generics — внутри get_object).
    """

    message = 'Доступ есть только у владельца объекта.'

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsProfileOwner(BasePermission):
    """Пользователь работает со своим профилем.

    Владелец профиля — сам объект User, поля owner у него нет.
    """

    message = 'Редактировать можно только свой профиль.'

    def has_object_permission(self, request, view, obj):
        return obj == request.user
