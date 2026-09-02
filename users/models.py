from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

NULLABLE = {'blank': True, 'null': True}


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email ist erforderlich')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name='Email')
    first_name = models.CharField(max_length=100, verbose_name='Имя', **NULLABLE)
    last_name = models.CharField(max_length=100, verbose_name='Фамилия', **NULLABLE)
    phone = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Payment(models.Model):
    """Платёж пользователя за курс или за отдельный урок."""

    CASH = 'cash'
    TRANSFER = 'transfer'

    PAYMENT_METHOD_CHOICES = [
        (CASH, 'Наличные'),
        (TRANSFER, 'Перевод на счет'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Пользователь',
    )
    payment_date = models.DateField(verbose_name='Дата оплаты')
    paid_course = models.ForeignKey(
        'lms.Course',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Оплаченный курс',
        **NULLABLE,
    )
    paid_lesson = models.ForeignKey(
        'lms.Lesson',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Оплаченный урок',
        **NULLABLE,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма оплаты',
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=TRANSFER,
        verbose_name='Способ оплаты',
    )

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ('-payment_date',)
        constraints = [
            # Платёж относится либо к курсу, либо к уроку — ровно к одному из двух.
            models.CheckConstraint(
                condition=(
                    models.Q(paid_course__isnull=False, paid_lesson__isnull=True)
                    | models.Q(paid_course__isnull=True, paid_lesson__isnull=False)
                ),
                name='payment_has_exactly_one_target',
            ),
        ]

    def __str__(self):
        paid_for = self.paid_course or self.paid_lesson or 'без привязки'
        return f'{self.user} — {paid_for} — {self.amount}'
