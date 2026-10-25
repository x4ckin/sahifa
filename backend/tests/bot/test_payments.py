from types import SimpleNamespace
from unittest.mock import AsyncMock

from sahifa.bot.payments import make_stars_invoice_link, on_pre_checkout, on_successful_payment
from sahifa.domain.pricing import Product
from sahifa.services.museums import create_museum
from sahifa.services.orders import create_order
from tests.bot.conftest import fake_message, tg_user
from tests.factories import make_user


async def _stars_room_order(session, now, uid=1):
    user = await make_user(session, uid)
    m = await create_museum(session, user, now)
    m.status, m.paid_at = "active", now
    order = await create_order(session, user, Product.ROOM, m.id, "stars", now)
    await session.commit()
    return order, m


def pre_checkout(uid, payload, amount, currency="XTR"):
    q = SimpleNamespace(from_user=tg_user(uid), invoice_payload=payload, total_amount=amount, currency=currency)
    q.answer = AsyncMock()
    return q


def paid_message(uid, payload, charge_id, amount=15):
    return fake_message(uid, text=None, successful_payment=SimpleNamespace(
        invoice_payload=payload, telegram_payment_charge_id=charge_id, total_amount=amount, currency="XTR",
    ))


async def test_invoice_link_uses_stars(bot, session, now):
    order, _ = await _stars_room_order(session, now)
    link = await make_stars_invoice_link(bot, order)
    (inv,) = bot.invoices
    assert link.endswith(order.code)
    assert inv["currency"] == "XTR" and inv["payload"] == order.code
    assert inv["prices"][0].amount == 15


async def test_precheckout_accepts_matching_order(session, now):
    order, _ = await _stars_room_order(session, now)
    q = pre_checkout(1, order.code, 15)
    await on_pre_checkout(q, session)
    q.answer.assert_awaited_once_with(ok=True)


async def test_precheckout_rejects_wrong_amount_user_or_state(session, now):
    order, _ = await _stars_room_order(session, now)
    for q in (pre_checkout(1, order.code, 1), pre_checkout(2, order.code, 15), pre_checkout(1, "ZZZZZZ", 15)):
        await on_pre_checkout(q, session)
        assert q.answer.call_args.kwargs["ok"] is False
    order.status = "cancelled"
    await session.commit()
    q = pre_checkout(1, order.code, 15)
    await on_pre_checkout(q, session)
    assert q.answer.call_args.kwargs["ok"] is False


async def test_successful_payment_fulfils_once(bot, session, settings, clock, now):
    order, m = await _stars_room_order(session, now)
    for _ in range(2):  # Telegram may deliver the same update twice
        msg = paid_message(1, order.code, "ch-1")
        await on_successful_payment(msg, session, bot, settings, clock)
    await session.refresh(m)
    assert m.extra_rooms == 1 and bot.refunds == []
    assert "qabul qilindi" in msg.answer.call_args.args[0]


async def test_second_charge_is_refunded(bot, session, settings, clock, now):
    order, m = await _stars_room_order(session, now)
    await on_successful_payment(paid_message(1, order.code, "ch-1"), session, bot, settings, clock)
    msg = paid_message(1, order.code, "ch-2")
    await on_successful_payment(msg, session, bot, settings, clock)
    await session.refresh(m)
    assert m.extra_rooms == 1
    assert bot.refunds == [(1, "ch-2")]


async def test_payment_for_deleted_museum_is_refunded(bot, session, settings, clock, now):
    order, m = await _stars_room_order(session, now)
    m.status = "deleted"
    await session.commit()
    await on_successful_payment(paid_message(1, order.code, "ch-9"), session, bot, settings, clock)
    assert bot.refunds == [(1, "ch-9")]
    await session.refresh(order)
    assert order.status == "rejected"
