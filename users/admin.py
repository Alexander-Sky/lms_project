from django.contrib import admin

from .models import Payment, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'first_name', 'last_name', 'city', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'groups')
    search_fields = ('email', 'first_name', 'last_name', 'city')
    filter_horizontal = ('groups', 'user_permissions')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'payment_date', 'paid_course', 'paid_lesson',
        'amount', 'payment_method', 'status',
    )
    list_filter = ('status', 'payment_method', 'payment_date', 'paid_course', 'paid_lesson')
    search_fields = ('user__email', 'session_id')
    readonly_fields = ('stripe_product_id', 'stripe_price_id', 'session_id', 'payment_link')
