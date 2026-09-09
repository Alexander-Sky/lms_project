"""Взаимодействие со Stripe.

Все обращения к платёжному сервису собраны здесь. Вьюхи вызывают эти
функции и не знают, как устроен Stripe — если завтра эквайринг сменится,
переписывать придётся только этот файл.

Документация: https://docs.stripe.com/api
"""

from decimal import Decimal

import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_API_KEY


def create_stripe_product(name: str, description: str = '') -> str:
    """Создаёт продукт в Stripe и возвращает его id.

    https://docs.stripe.com/api/products/create
    """
    product = stripe.Product.create(name=name, description=description or None)
    return product['id']


def create_stripe_price(product_id: str, amount: Decimal, currency: str = 'rub') -> str:
    """Создаёт цену для продукта и возвращает её id.

    Stripe принимает сумму в минимальных единицах валюты — в копейках,
    поэтому рубли умножаются на 100 и округляются до целого.

    https://docs.stripe.com/api/prices/create
    """
    price = stripe.Price.create(
        product=product_id,
        currency=currency,
        unit_amount=int(Decimal(amount) * 100),
    )
    return price['id']


def create_stripe_session(price_id: str) -> tuple[str, str]:
    """Создаёт сессию оплаты и возвращает пару (id сессии, ссылка на оплату).

    https://docs.stripe.com/api/checkout/sessions/create
    """
    session = stripe.checkout.Session.create(
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='payment',
    )
    return session['id'], session['url']


def retrieve_stripe_session(session_id: str) -> dict:
    """Забирает данные сессии по её id — для проверки статуса оплаты.

    https://docs.stripe.com/api/checkout/sessions/retrieve
    """
    session = stripe.checkout.Session.retrieve(session_id)

    # Stripe отдаёт не словарь, а объект StripeObject: у него нет метода .get(),
    # хотя обращение по ключу работает. Приводим к словарю явно.
    data = session.to_dict() if hasattr(session, 'to_dict') else dict(session)

    return {
        'id': data.get('id'),
        'status': data.get('status'),
        'payment_status': data.get('payment_status'),
        'amount_total': data.get('amount_total'),
        'currency': data.get('currency'),
        'url': data.get('url'),
    }
