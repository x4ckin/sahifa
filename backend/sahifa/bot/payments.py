"""Telegram Stars: invoice links, pre-checkout validation, and fulfilment on payment."""

import logging

from aiogram import F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.bot import texts
from sahifa.config import Settings
from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import PRODUCT_TITLES_UZ, Product
from sahifa.models import Order
from sahifa.services import orders

log = logging.getLogger(__name__)
router = Router(name="payments")


async def make_stars_invoice_link(bot, order: Order) -> str:
    title = PRODUCT_TITLES_UZ[Product(order.product)]
    return await bot.create_invoice_link(
        title=title,
        description=f"Sahifa — {title}. Buyurtma {order.code}",
        payload=order.code,
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=order.amount_stars)],
    )


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery, session: AsyncSession) -> None:
    try:
        order = await orders.get_by_code(session, query.invoice_payload)
    except DomainError:
        order = None
    ok = (
        order is not None
        and order.status == "pending"
        and order.method == "stars"
        and order.user_id == query.from_user.id
        and query.currency == "XTR"
        and query.total_amount == order.amount_stars
    )
    if ok:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message=texts.PRECHECKOUT_FAIL)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: AsyncSession, bot, settings: Settings, clock) -> None:
    payment = message.successful_payment
    charge_id = payment.telegram_payment_charge_id
    try:
        order = await orders.get_by_code(session, payment.invoice_payload)
        await orders.fulfil(session, order, clock(), charge_id=charge_id)
    except DomainError as e:
        # money arrived but nothing can be granted: keep the rejection/audit, give the Stars back
        await session.commit()
        log.warning("refunding stars charge %s: %s", charge_id, e.code)
        await bot.refund_star_payment(user_id=message.from_user.id, telegram_payment_charge_id=charge_id)
        await message.answer(texts.PAYMENT_REFUNDED)
        return
    await session.commit()
    await message.answer(texts.PAID.format(product=PRODUCT_TITLES_UZ[Product(order.product)]))
