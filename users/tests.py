from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from lms.models import Course
from users.models import Payment, User

PASSWORD = 'Str0ngPass!42'


class RegistrationTestCase(APITestCase):
    """Регистрация пользователей."""

    def setUp(self):
        self.url = reverse('users:register')
        self.existing = User.objects.create(email='taken@test.ru')

    def test_registration_without_token(self):
        response = self.client.post(self.url, {'email': 'new@test.ru', 'password': PASSWORD})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='new@test.ru').exists())

    def test_password_is_hashed(self):
        self.client.post(self.url, {'email': 'new@test.ru', 'password': PASSWORD})
        user = User.objects.get(email='new@test.ru')

        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_password_is_not_returned(self):
        response = self.client.post(self.url, {'email': 'new@test.ru', 'password': PASSWORD})
        self.assertNotIn('password', response.json())

    def test_duplicate_email_is_rejected(self):
        response = self.client.post(self.url, {'email': 'taken@test.ru', 'password': PASSWORD})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json())

    def test_duplicate_email_is_case_insensitive(self):
        response = self.client.post(self.url, {'email': 'TAKEN@test.ru', 'password': PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_is_rejected(self):
        response = self.client.post(self.url, {'email': 'new@test.ru', 'password': '12345678'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.json())


class AuthTestCase(APITestCase):
    """Получение и обновление JWT-токенов."""

    def setUp(self):
        self.user = User.objects.create(email='user@test.ru')
        self.user.set_password(PASSWORD)
        self.user.save()

    def test_login_returns_token_pair(self):
        response = self.client.post(
            reverse('users:login'),
            {'email': 'user@test.ru', 'password': PASSWORD},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.json())
        self.assertIn('refresh', response.json())

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse('users:login'),
            {'email': 'user@test.ru', 'password': 'wrong-password'},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access(self):
        refresh = self.client.post(
            reverse('users:login'),
            {'email': 'user@test.ru', 'password': PASSWORD},
        ).json()['refresh']

        response = self.client.post(reverse('users:token-refresh'), {'refresh': refresh})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.json())

    def test_access_token_opens_closed_endpoint(self):
        access = self.client.post(
            reverse('users:login'),
            {'email': 'user@test.ru', 'password': PASSWORD},
        ).json()['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(self.client.get(reverse('lms:course-list')).status_code, status.HTTP_200_OK)

    def test_broken_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not.a.token')
        response = self.client.get(reverse('lms:course-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileTestCase(APITestCase):
    """Профили: свой видно целиком, чужой — в общем виде."""

    def setUp(self):
        self.user = User.objects.create(
            email='user@test.ru',
            first_name='Иван',
            last_name='Петров',
            city='Wien',
        )
        self.other = User.objects.create(email='other@test.ru')
        self.course = Course.objects.create(name='Курс', owner=self.user)
        Payment.objects.create(
            user=self.user,
            payment_date=date(2026, 5, 1),
            paid_course=self.course,
            amount=1000,
        )

    def test_anonymous_cannot_see_profile(self):
        url = reverse('users:user-detail', args=(self.user.pk,))
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_own_profile_is_full(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get(reverse('users:user-detail', args=(self.user.pk,))).json()

        self.assertIn('last_name', data)
        self.assertIn('payments', data)
        self.assertEqual(data['payments_total'], 1000.0)

    def test_other_profile_is_limited(self):
        self.client.force_authenticate(user=self.other)
        data = self.client.get(reverse('users:user-detail', args=(self.user.pk,))).json()

        self.assertNotIn('last_name', data)
        self.assertNotIn('payments', data)
        self.assertNotIn('password', data)

    def test_user_updates_own_profile(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('users:user-update', args=(self.user.pk,))
        response = self.client.patch(url, {'city': 'Salzburg'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.city, 'Salzburg')

    def test_user_cannot_update_other_profile(self):
        self.client.force_authenticate(user=self.other)
        url = reverse('users:user-update', args=(self.user.pk,))
        response = self.client.patch(url, {'city': 'Hacked'})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user.refresh_from_db()
        self.assertEqual(self.user.city, 'Wien')

    def test_user_cannot_delete_other_profile(self):
        self.client.force_authenticate(user=self.other)
        url = reverse('users:user-delete', args=(self.user.pk,))

        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_user_list_requires_auth(self):
        self.assertEqual(
            self.client.get(reverse('users:user-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(reverse('users:user-list')).status_code, status.HTTP_200_OK)


class PaymentTestCase(APITestCase):
    """Список платежей: фильтры и сортировка."""

    def setUp(self):
        self.user = User.objects.create(email='user@test.ru')
        self.course_one = Course.objects.create(name='Курс 1', owner=self.user)
        self.course_two = Course.objects.create(name='Курс 2', owner=self.user)

        Payment.objects.create(
            user=self.user, payment_date=date(2026, 1, 10),
            paid_course=self.course_one, amount=100, payment_method=Payment.CASH,
        )
        Payment.objects.create(
            user=self.user, payment_date=date(2026, 3, 10),
            paid_course=self.course_two, amount=200, payment_method=Payment.TRANSFER,
        )

        self.url = reverse('users:payment-list')

    def test_anonymous_has_no_access(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ordering_by_date(self):
        self.client.force_authenticate(user=self.user)

        asc = self.client.get(self.url, {'ordering': 'payment_date'}).json()
        desc = self.client.get(self.url, {'ordering': '-payment_date'}).json()

        self.assertEqual(asc[0]['payment_date'], '2026-01-10')
        self.assertEqual(desc[0]['payment_date'], '2026-03-10')

    def test_filter_by_course(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url, {'paid_course': self.course_one.pk}).json()

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['paid_course'], self.course_one.pk)

    def test_filter_by_payment_method(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get(self.url, {'payment_method': Payment.CASH}).json()

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['payment_method'], Payment.CASH)


class UserModelTestCase(APITestCase):
    """Менеджер пользователей и строковые представления."""

    def test_create_user_hashes_password(self):
        user = User.objects.create_user(email='manager@test.ru', password=PASSWORD)

        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(email='Manager@TEST.RU', password=PASSWORD)
        self.assertEqual(user.email, 'Manager@test.ru')

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password=PASSWORD)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(email='admin@test.ru', password=PASSWORD)

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_user_str(self):
        user = User.objects.create(email='str@test.ru')
        self.assertEqual(str(user), 'str@test.ru')

    def test_payment_str(self):
        user = User.objects.create(email='pay@test.ru')
        course = Course.objects.create(name='Курс для строки', owner=user)
        payment = Payment.objects.create(
            user=user, payment_date=date(2026, 2, 2), paid_course=course, amount=500,
        )

        self.assertIn('Курс для строки', str(payment))
        self.assertIn('pay@test.ru', str(payment))
