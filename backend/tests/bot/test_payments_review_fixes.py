"""Regression tests for the Task 9 checkpoint review."""

from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from sahifa.bot.payments import on_successful_payment
from sahifa.bot.start import cmd_start, on_transfer_answer
from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import Product
from sahifa.models import AuditLog, Museum, Order, User
from sahifa.services.museums import create_museum
from sahifa.services.orders import create_order, fulfil
from sahifa.services.transfers import accept_transfer, create_transfer
from tests.bot.conftest import fake_callback, fake_message
from tests.bot.test_payments import paid_message
from tests.factories import make_user


async def test_concurrent_charges_grant_once_and_flag_the_second(sessionmaker, session, now):
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    await session.commit()
    async with sessionmaker() as a, sessionmaker() as b:
        oa = await a.scalar(select(Order).where(Order.id == order.id))
        ob = await b.scalar(select(Order).where(Order.id == order.id))  # both see "pending"
        await fulfil(a, oa, now, charge_id="c1")
        await a.commit()
        with pytest.raises(DomainError) as err:
            await fulfil(b, ob, now, charge_id="c2")
        assert err.value.code == "duplicate_payment"
        await b.commit()
    async with sessionmaker() as c:
        assert (await c.get(User, 1)).extra_slots == 5
        assert (await c.scalar(select(Order).where(Order.id == order.id))).charge_id == "c1"


async def test_same_charge_redelivered_after_refund_is_ignored(session, now):
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    await fulfil(session, order, now, charge_id="c1")
    order.status = "refunded"
    await fulfil(session, order, now, charge_id="c1")  # no exception, nothing granted
    assert user.extra_slots == 5


async def test_stars_on_cancelled_order_is_refunded(bot, session, settings, clock, now):
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    order.status = "cancelled"
    await session.commit()
    await on_successful_payment(paid_message(1, order.code, "c5"), session, bot, settings, clock)
    assert bot.refunds == [(1, "c5")]
    assert (await session.get(User, 1)).extra_slots == 0


async def test_refund_is_recorded_once_and_failures_reach_admins(bot, session, settings, clock, now):
    user = await make_user(session, 1)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "stars", now)
    m.status = "deleted"
    await session.commit()
    for _ in range(2):  # Telegram re-delivers the same update
        await on_successful_payment(paid_message(1, order.code, "c7"), session, bot, settings, clock)
    assert bot.refunds == [(1, "c7")]
    actions = (await session.scalars(select(AuditLog.action).where(AuditLog.action.like("stars_refund%")))).all()
    assert actions == ["stars_refund"]

    async def failing_refund(**_):
        raise TelegramBadRequest(method=None, message="Bad Request: CHARGE_NOT_FOUND")

    bot.refund_star_payment = failing_refund
    await on_successful_payment(paid_message(1, "NOPE22", "c8"), session, bot, settings, clock)
    assert any(chat == settings.admin_chat_id and "c8" in text for chat, text, _ in bot.sent)
    assert "stars_refund_failed" in (await session.scalars(select(AuditLog.action))).all()


async def test_transfer_accepted_by_only_one_of_two(sessionmaker, session, now):
    giver = await make_user(session, 1)
    await make_user(session, 2)
    await make_user(session, 3)
    m = await create_museum(session, giver, now)
    t = await create_transfer(session, m, giver, now)
    await session.commit()
    async with sessionmaker() as a, sessionmaker() as b:
        ua, ub = await a.get(User, 2), await b.get(User, 3)
        from sahifa.models import Transfer

        await b.scalar(select(Transfer).where(Transfer.token == t.token))  # b has it loaded as pending
        await accept_transfer(a, t.token, ua, now)
        await a.commit()
        with pytest.raises(DomainError):
            await accept_transfer(b, t.token, ub, now)
    async with sessionmaker() as c:
        assert (await c.get(Museum, m.id)).owner_id == 2


async def test_user_text_is_html_escaped(bot, session, settings, clock, now):
    giver = await make_user(session, 1)
    giver.first_name = "<b>Ali</b>"
    m = await create_museum(session, giver, now)
    m.title = '<a href="https://evil">x</a>'
    t = await create_transfer(session, m, giver, now)
    await session.commit()

    msg = fake_message(2)
    msg.from_user.first_name = "<i>Vali</i>"
    await cmd_start(msg, SimpleNamespace(args=None), session, settings, clock)
    assert "&lt;i&gt;Vali&lt;/i&gt;" in msg.answer.call_args.args[0]

    offer = fake_message(2)
    await cmd_start(offer, SimpleNamespace(args=f"tr_{t.token}"), session, settings, clock)
    text = offer.answer.call_args.args[0]
    assert "<a href" not in text and "&lt;b&gt;Ali" in text


async def test_giver_notified_and_blocked_giver_does_not_break_accept(bot, session, settings, clock, now):
    giver = await make_user(session, 1)
    t = await create_transfer(session, await create_museum(session, giver, now), giver, now)
    await session.commit()

    async def blocked(*_, **__):
        from aiogram.exceptions import TelegramForbiddenError

        raise TelegramForbiddenError(method=None, message="Forbidden: bot was blocked by the user")

    bot.send_message = blocked
    cb = fake_callback(2, f"tr:ok:{t.token}")
    await on_transfer_answer(cb, session, bot, settings, clock)
    cb.answer.assert_awaited()


async def test_bad_deeplinks_fall_back_to_welcome(session, settings, clock):
    for arg in ("ref_99999999999999999999", "m_" + "ж" * 10, "x" * 300):
        msg = fake_message(9)
        await cmd_start(msg, SimpleNamespace(args=arg), session, settings, clock)
        assert "Sahifa" in msg.answer.call_args.args[0]
    assert (await session.get(User, 9)).referrer_id is None
