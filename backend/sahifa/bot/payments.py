"""Telegram Stars: invoice links, pre-checkout validation, and fulfilment on payment."""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.bot import texts
from sahifa.config import Settings
from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import PRODUCT_TITLES_UZ, Product
from sahifa.models import AuditLog, Order
from sahifa.services import audit, orders

log = logging.getLogger(__name__)
router = Router(name="payments")


async def make_stars_invoice_link(bot, order: Order, rooms: int = 0) -> str:
    title = PRODUCT_TITLES_UZ[Product(order.product)] + (f" +{rooms} xona" if rooms else "")
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
        await refund_once(bot, session, settings, message.from_user.id, charge_id, e.code)
        await message.answer(texts.PAYMENT_REFUNDED)
        return
    except Exception:
        # e.g. "database is locked": the money is with us but nothing was granted — leave a trace
        log.exception("payment %s could not be processed", charge_id)
        await session.rollback()
        await audit.log(session, message.from_user.id, "payment_unhandled",
                        code=payment.invoice_payload, charge_id=charge_id)
        await session.commit()
        await bot.send_message(
            settings.admin_chat_id,
            f"🚨 To'lov qayta ishlanmadi — buyurtma <code>{payment.invoice_payload}</code>, "
            f"foydalanuvchi <code>{message.from_user.id}</code>, charge <code>{charge_id}</code>. Qo'lda tekshiring.",
        )
        await message.answer(texts.PAYMENT_PENDING_ADMIN)
        return
    await session.commit()
    await message.answer(texts.PAID.format(product=PRODUCT_TITLES_UZ[Product(order.product)]))


async def refund_once(bot, session: AsyncSession, settings: Settings, user_id: int, charge_id: str, reason: str) -> None:
    """Refund a Stars charge at most once; if Telegram refuses, record it and tell the admins."""
    done = await session.scalar(
        select(AuditLog.id).where(
            AuditLog.action == "stars_refund", func.json_extract(AuditLog.payload, "$.charge_id") == charge_id
        )
    )
    if done is not None:
        return
    try:
        await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)
    except TelegramAPIError as err:
        log.error("stars refund failed for %s: %s", charge_id, err)
        await audit.log(session, user_id, "stars_refund_failed", charge_id=charge_id, reason=reason, error=str(err))
        await session.commit()
        await bot.send_message(
            settings.admin_chat_id,
            f"⚠️ Stars qaytarilmadi — foydalanuvchi <code>{user_id}</code>, charge <code>{charge_id}</code> ({reason}). "
            "Qo'lda tekshiring.",
        )
        return
    await audit.log(session, user_id, "stars_refund", charge_id=charge_id, reason=reason)
    await session.commit()
