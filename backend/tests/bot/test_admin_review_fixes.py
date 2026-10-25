"""Regression tests for the Task 10 checkpoint review."""

from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import MessageOriginHiddenUser, MessageOriginUser, User as TgUser
from sqlalchemy import select

from sahifa.bot.admin import cmd_broadcast, cmd_cards, cmd_free, cmd_refund
from sahifa.bot.review import on_review
from sahifa.domain.pricing import Product
from sahifa.models import Order, User
from sahifa.services.museums import create_museum
from sahifa.services.orders import attach_receipt, create_order, fulfil
from sahifa.services.settings_store import get_cards
from tests.bot.conftest import fake_callback
from tests.bot.test_admin import ADMIN, admin_msg, cmd
from tests.factories import make_user, tiny_jpeg


async def _receipt(sessionmaker, settings, now, tmp_path, product=Product.SLOTS):
    async with sessionmaker() as s:
        user = await make_user(s, 1)
        museum_id = None
        if product != Product.SLOTS:
            m = await create_museum(s, user, now)
            museum_id = m.id
        order = await create_order(s, user, product, museum_id, "card", now)
        await attach_receipt(s, order, tiny_jpeg(tmp_path / "r.jpg"), now, receipts_dir=settings.receipts_dir)
        await s.commit()
        return order.code, museum_id


async def test_double_tap_and_approve_reject_race_grant_once(bot, sessionmaker, settings, clock, now, tmp_path):
    code, _ = await _receipt(sessionmaker, settings, now, tmp_path)
    async with sessionmaker() as a, sessionmaker() as b:
        await a.scalar(select(Order).where(Order.code == code))
        await b.scalar(select(Order).where(Order.code == code))  # both handlers loaded it as awaiting_review
        await on_review(fake_callback(ADMIN, f"rv:ok:{code}"), a, bot, settings, clock)
        late = fake_callback(ADMIN, f"rv:no:{code}:amount")
        await on_review(late, b, bot, settings, clock)
        assert late.answer.call_args.kwargs.get("show_alert") is True
    async with sessionmaker() as c:
        order = await c.scalar(select(Order).where(Order.code == code))
        assert order.status == "paid"
        assert (await c.get(User, 1)).extra_slots == 5
    assert len([t for chat, t, _ in bot.sent if chat == 1]) == 1


async def test_pending_card_order_without_receipt_cannot_be_approved(bot, session, settings, clock, now):
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "card", now)
    await session.commit()
    cb = fake_callback(ADMIN, f"rv:ok:{order.code}")
    await on_review(cb, session, bot, settings, clock)
    await session.refresh(order)
    assert order.status == "pending"


async def test_blocked_user_does_not_break_review(bot, sessionmaker, settings, clock, now, tmp_path):
    code, _ = await _receipt(sessionmaker, settings, now, tmp_path)

    async def blocked(*_, **__):
        raise TelegramForbiddenError(method=None, message="Forbidden: bot was blocked by the user")

    bot.send_message = blocked
    cb = fake_callback(ADMIN, f"rv:ok:{code}")
    async with sessionmaker() as s:
        await on_review(cb, s, bot, settings, clock)
    cb.answer.assert_awaited()
    cb.message.edit_caption.assert_awaited()


async def test_user_told_when_museum_gone(bot, sessionmaker, settings, clock, now, tmp_path):
    code, museum_id = await _receipt(sessionmaker, settings, now, tmp_path, Product.MUSEUM)
    async with sessionmaker() as s:
        from sahifa.models import Museum

        (await s.get(Museum, museum_id)).status = "deleted"
        await s.commit()
        await on_review(fake_callback(ADMIN, f"rv:ok:{code}"), s, bot, settings, clock)
    assert any(chat == 1 and "qaytariladi" in text for chat, text, _ in bot.sent)


async def test_malformed_or_unknown_review_data_is_answered(bot, session, settings, clock):
    for data in ("rv:ok", "rv:ok:NOPE22"):
        cb = fake_callback(ADMIN, data)
        await on_review(cb, session, bot, settings, clock)
        cb.answer.assert_awaited()


async def test_free_by_reply_to_forward_uses_forward_origin(bot, session, clock):
    await make_user(session, 5)
    await make_user(session, ADMIN)
    await session.commit()
    origin = MessageOriginUser(date=0, sender_user=TgUser(id=5, is_bot=False, first_name="Aziza"))
    forwarded = SimpleNamespace(from_user=SimpleNamespace(id=ADMIN), forward_origin=origin)
    await cmd_free(admin_msg("/bepul", reply_to=forwarded), cmd(None), session, bot, clock)
    assert (await session.get(User, 5)).is_free
    assert not (await session.get(User, ADMIN)).is_free

    hidden = SimpleNamespace(
        from_user=SimpleNamespace(id=ADMIN), forward_origin=MessageOriginHiddenUser(date=0, sender_user_name="X")
    )
    msg = admin_msg("/bepul", reply_to=hidden)
    await cmd_free(msg, cmd(None), session, bot, clock)
    assert "yashirgan" in msg.answer.call_args.args[0]
    assert not (await session.get(User, ADMIN)).is_free


async def test_free_days_parsing_is_strict(bot, session, clock):
    await make_user(session, 5, username="aziza")
    await session.commit()
    for args in ("@aziza 30d", "@aziza abc", "@aziza 0", "@aziza 99999999", "@aziza 30 kun"):
        msg = admin_msg(f"/bepul {args}")
        await cmd_free(msg, cmd(args), session, bot, clock)
        assert "Foydalanish" in msg.answer.call_args.args[0], args
        assert not (await session.get(User, 5)).is_free


async def test_broadcast_retries_after_flood_and_survives_network_errors(bot, session):
    for uid in (1, 2, 3):
        await make_user(session, uid)
    await session.commit()
    calls = {1: 0}

    async def copy_message(chat_id, from_chat_id, message_id):
        if chat_id == 1:
            calls[1] += 1
            if calls[1] == 1:
                raise TelegramRetryAfter(method=None, message="Too Many Requests", retry_after=0)
        if chat_id == 2:
            raise TelegramNetworkError(method=None, message="timeout")
        bot.copied.append(chat_id)

    bot.copied = []
    bot.copy_message = copy_message
    msg = admin_msg("/xabar", reply_to=SimpleNamespace(chat=SimpleNamespace(id=ADMIN), message_id=1))
    await cmd_broadcast(msg, session, bot, delay=0)
    assert sorted(bot.copied) == [1, 3]
    assert "Xato: 1" in msg.answer.call_args.args[0]


async def test_refund_errors_are_reported(bot, session, clock, now):
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    await fulfil(session, order, now, charge_id="ch-1")
    await session.commit()

    async def already(**_):
        raise TelegramBadRequest(method=None, message="Bad Request: CHARGE_ALREADY_REFUNDED")

    bot.refund_star_payment = already
    msg = admin_msg(f"/qaytar {order.code}")
    await cmd_refund(msg, cmd(order.code), session, bot, clock)
    await session.refresh(order)
    assert order.status == "refunded"
    assert "saqlanib qoldi" in msg.answer.call_args.args[0]


async def test_card_needs_16_digits(session):
    msg = admin_msg("/karta 1 2 3 4 5 6 7 Ali")
    await cmd_cards(msg, cmd("1 2 3 4 5 6 7 Ali"), session)
    assert await get_cards(session) == []
