from datetime import date
from decimal import Decimal
from unittest.mock import patch

import stripe
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from lms.models import Course, Lesson
from users.models import Payment, User
from users.services import (
    create_stripe_price,
    create_stripe_product,
    create_stripe_session,
    retrieve_stripe_session,
)

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


class DocumentationTestCase(APITestCase):
    """Документация доступна и отдаётся без токена."""

    def test_schema_is_public(self):
        response = self.client.get('/api/schema/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_swagger_is_public(self):
        response = self.client.get('/api/docs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_redoc_is_public(self):
        response = self.client.get('/api/redoc/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_schema_contains_all_endpoints(self):
        schema = self.client.get('/api/schema/', {'format': 'json'}).json()
        paths = schema['paths']

        for path in (
            '/api/register/',
            '/api/login/',
            '/api/token/refresh/',
            '/api/users/',
            '/api/courses/',
            '/api/lessons/',
            '/api/subscription/',
            '/api/payments/',
            '/api/payments/create/',
            '/api/payments/{id}/status/',
        ):
            self.assertIn(path, paths, f'В схеме нет {path}')

    def test_subscription_body_is_documented(self):
        """У нестандартного эндпоинта описано тело запроса."""
        schema = self.client.get('/api/schema/', {'format': 'json'}).json()
        post = schema['paths']['/api/subscription/']['post']

        self.assertIn('requestBody', post)
        self.assertIn('200', post['responses'])
        self.assertIn('404', post['responses'])


class PaymentCreateTestCase(APITestCase):
    """Создание платежа и оплата через Stripe. Stripe замокан."""

    def setUp(self):
        self.user = User.objects.create(email='payer@test.ru')
        self.course = Course.objects.create(name='Платный курс', price=Decimal('1000.00'), owner=self.user)
        self.free_course = Course.objects.create(name='Бесплатный курс', price=0, owner=self.user)
        self.lesson = Lesson.objects.create(
            name='Платный урок', course=self.course, price=Decimal('150.00'), owner=self.user,
        )
        self.url = reverse('users:payment-create')
        self.client.force_authenticate(user=self.user)

    def _mock_stripe(self):
        """Подменяет три сервисные функции разом."""
        return (
            patch('users.views.create_stripe_product', return_value='prod_TEST'),
            patch('users.views.create_stripe_price', return_value='price_TEST'),
            patch('users.views.create_stripe_session', return_value=('cs_test_123', 'https://checkout.stripe.com/pay/cs_test_123')),
        )

    def test_anonymous_cannot_create_payment(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {'paid_course': self.course.pk})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_payment_for_course_returns_link(self):
        product, price, session = self._mock_stripe()
        with product, price, session:
            response = self.client.post(self.url, {'paid_course': self.course.pk})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['payment_link'], 'https://checkout.stripe.com/pay/cs_test_123')
        self.assertEqual(data['session_id'], 'cs_test_123')
        self.assertEqual(data['status'], Payment.PENDING)

    def test_payment_saves_stripe_ids_and_owner(self):
        product, price, session = self._mock_stripe()
        with product, price, session:
            self.client.post(self.url, {'paid_course': self.course.pk})

        payment = Payment.objects.get()
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.stripe_product_id, 'prod_TEST')
        self.assertEqual(payment.stripe_price_id, 'price_TEST')
        self.assertEqual(payment.amount, self.course.price)

    def test_price_is_sent_to_stripe_in_kopecks(self):
        product, price, session = self._mock_stripe()
        with product, price as price_mock, session:
            self.client.post(self.url, {'paid_course': self.course.pk})

        self.assertEqual(price_mock.call_args.kwargs['amount'], Decimal('1000.00'))

    def test_payment_for_lesson(self):
        product, price, session = self._mock_stripe()
        with product, price, session:
            response = self.client.post(self.url, {'paid_lesson': self.lesson.pk})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.get().paid_lesson, self.lesson)

    def test_both_course_and_lesson_is_rejected(self):
        response = self.client.post(
            self.url, {'paid_course': self.course.pk, 'paid_lesson': self.lesson.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nothing_to_pay_for_is_rejected(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_price_is_rejected(self):
        response = self.client.post(self.url, {'paid_course': self.free_course.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', response.json())

    def test_stripe_error_returns_502(self):
        with patch('users.views.create_stripe_product', side_effect=stripe.StripeError('нет ключа')):
            response = self.client.post(self.url, {'paid_course': self.course.pk})

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(Payment.objects.count(), 0)


class PaymentStatusTestCase(APITestCase):
    """Проверка статуса оплаты через Session Retrieve."""

    def setUp(self):
        self.user = User.objects.create(email='payer@test.ru')
        self.other = User.objects.create(email='other@test.ru')
        self.course = Course.objects.create(name='Курс', price=Decimal('100.00'), owner=self.user)

        self.payment = Payment.objects.create(
            user=self.user, payment_date=date(2026, 9, 1), paid_course=self.course,
            amount=Decimal('100.00'), session_id='cs_test_123',
        )
        self.offline_payment = Payment.objects.create(
            user=self.user, payment_date=date(2026, 9, 1), paid_course=self.course,
            amount=Decimal('100.00'), payment_method=Payment.CASH,
        )
        self.url = reverse('users:payment-status', args=(self.payment.pk,))
        self.client.force_authenticate(user=self.user)

    def test_paid_session_updates_status(self):
        session = {'id': 'cs_test_123', 'status': 'complete', 'payment_status': 'paid',
                   'amount_total': 10000, 'currency': 'rub', 'url': None}

        with patch('users.views.retrieve_stripe_session', return_value=session):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['payment_status'], 'paid')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PAID)

    def test_expired_session_cancels_payment(self):
        session = {'id': 'cs_test_123', 'status': 'expired', 'payment_status': 'unpaid',
                   'amount_total': 10000, 'currency': 'rub', 'url': None}

        with patch('users.views.retrieve_stripe_session', return_value=session):
            self.client.get(self.url)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.CANCELED)

    def test_open_session_keeps_pending(self):
        session = {'id': 'cs_test_123', 'status': 'open', 'payment_status': 'unpaid',
                   'amount_total': 10000, 'currency': 'rub', 'url': 'https://checkout.stripe.com/x'}

        with patch('users.views.retrieve_stripe_session', return_value=session):
            self.client.get(self.url)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PENDING)

    def test_other_user_gets_404(self):
        self.client.force_authenticate(user=self.other)
        with patch('users.views.retrieve_stripe_session') as mocked:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mocked.assert_not_called()

    def test_payment_without_session_returns_400(self):
        url = reverse('users:payment-status', args=(self.offline_payment.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stripe_error_returns_502(self):
        with patch('users.views.retrieve_stripe_session', side_effect=stripe.StripeError('boom')):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)


class StripeServiceTestCase(APITestCase):
    """Сервисные функции: что именно уходит в Stripe."""

    def test_product_is_created_with_name(self):
        with patch('stripe.Product.create', return_value={'id': 'prod_1'}) as mocked:
            product_id = create_stripe_product('Курс по Django', 'Описание')

        self.assertEqual(product_id, 'prod_1')
        self.assertEqual(mocked.call_args.kwargs['name'], 'Курс по Django')

    def test_price_is_converted_to_kopecks(self):
        with patch('stripe.Price.create', return_value={'id': 'price_1'}) as mocked:
            price_id = create_stripe_price('prod_1', Decimal('1234.56'))

        self.assertEqual(price_id, 'price_1')
        self.assertEqual(mocked.call_args.kwargs['unit_amount'], 123456)
        self.assertEqual(mocked.call_args.kwargs['product'], 'prod_1')
        self.assertEqual(mocked.call_args.kwargs['currency'], 'rub')

    def test_session_gets_price_id_and_returns_link(self):
        stripe_session = {'id': 'cs_1', 'url': 'https://checkout.stripe.com/pay/cs_1'}

        with patch('stripe.checkout.Session.create', return_value=stripe_session) as mocked:
            session_id, link = create_stripe_session('price_1')

        self.assertEqual(session_id, 'cs_1')
        self.assertEqual(link, 'https://checkout.stripe.com/pay/cs_1')
        self.assertEqual(mocked.call_args.kwargs['line_items'], [{'price': 'price_1', 'quantity': 1}])
        self.assertEqual(mocked.call_args.kwargs['mode'], 'payment')

    def test_retrieve_returns_status_fields(self):
        """Stripe отдаёт StripeObject, а не словарь: у него нет метода .get().

        Раньше здесь стоял обычный dict — тест был зелёный, а живой запрос падал
        с AttributeError. Подделка ведёт себя как настоящий объект Stripe.
        """
        class FakeStripeObject:
            _data = {
                'id': 'cs_1', 'status': 'complete', 'payment_status': 'paid',
                'amount_total': 123456, 'currency': 'rub', 'url': None,
            }

            def to_dict(self):
                return dict(self._data)

            def __getattr__(self, item):
                if item in self._DICT_METHODS:
                    raise AttributeError(
                        f"'{item}' is a dict method, but a Session is not a dict."
                    )
                return self._data[item]

            _DICT_METHODS = ('get', 'keys', 'values', 'items')

        with patch('stripe.checkout.Session.retrieve', return_value=FakeStripeObject()):
            data = retrieve_stripe_session('cs_1')

        self.assertEqual(data['payment_status'], 'paid')
        self.assertEqual(data['amount_total'], 123456)
        self.assertEqual(data['id'], 'cs_1')
