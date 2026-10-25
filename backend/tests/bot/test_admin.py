from types import SimpleNamespace

from aiogram.exceptions import TelegramForbiddenError

from sahifa.bot.admin import (
    IsAdmin,
    cmd_broadcast,
    cmd_cards,
    cmd_free,
    cmd_free_list,
    cmd_price,
    cmd_refund,
    cmd_stats,
    cmd_unfree,
)
from sahifa.domain.pricing import Product
from sahifa.models import User
from sahifa.services.orders import create_order, fulfil
from sahifa.services.settings_store import get_cards, get_price
from tests.bot.conftest import fake_message
from tests.factories import make_user

ADMIN = 999


def admin_msg(text, reply_to=None):
    msg = fake_message(ADMIN, text=text)
    msg.reply_to_message = reply_to
    return msg


def cmd(args):
    return SimpleNamespace(args=args)


async def test_is_admin_filter(settings):
    f = IsAdmin()
    assert await f(fake_message(ADMIN), settings) is True
    assert await f(fake_message(1), settings) is False


async def test_set_price_command(session):
    msg = admin_msg("/narx room uzs 4000")
    await cmd_price(msg, cmd("room uzs 4000"), session)
    assert await get_price(session, Product.ROOM, "uzs") == 4000
    shown = admin_msg("/narx")
    await cmd_price(shown, cmd(None), session)
    assert "4 000" in shown.answer.call_args.args[0]
    bad = admin_msg("/narx gold uzs 1")
    await cmd_price(bad, cmd("gold uzs 1"), session)
    assert "Foydalanish" in bad.answer.call_args.args[0]


async def test_cards_command(session):
    msg = admin_msg("/karta 8600 1234 5678 9012 Ali Valiyev\n9860 0000 1111 2222 Vali Aliyev")
    await cmd_cards(msg, cmd("8600 1234 5678 9012 Ali Valiyev\n9860 0000 1111 2222 Vali Aliyev"), session)
    assert await get_cards(session) == [
        {"number": "8600 1234 5678 9012", "holder": "Ali Valiyev"},
        {"number": "9860 0000 1111 2222", "holder": "Vali Aliyev"},
    ]
    await cmd_cards(admin_msg("/karta tozalash"), cmd("tozalash"), session)
    assert await get_cards(session) == []


async def test_grant_free_by_username_and_reply(bot, session, clock, now):
    await make_user(session, 5, username="Aziza_01")
    await make_user(session, 6)
    await session.commit()
    msg = admin_msg("/bepul @aziza_01 30")
    await cmd_free(msg, cmd("@aziza_01 30"), session, bot, clock)
    u5 = await session.get(User, 5)
    assert u5.is_free and u5.free_until == now.replace() + (u5.free_until - now)
    assert (u5.free_until - now).days == 30
    assert any(chat == 5 for chat, _, _ in bot.sent)

    forwarded = SimpleNamespace(from_user=SimpleNamespace(id=6), forward_from=None)
    await cmd_free(admin_msg("/bepul", reply_to=forwarded), cmd(None), session, bot, clock)
    assert (await session.get(User, 6)).free_until is None and (await session.get(User, 6)).is_free

    listing = admin_msg("/bepullar")
    await cmd_free_list(listing, session)
    assert "5" in listing.answer.call_args.args[0] and "6" in listing.answer.call_args.args[0]

    await cmd_unfree(admin_msg("/bepul_ochir 6"), cmd("6"), session)
    assert not (await session.get(User, 6)).is_free

    unknown = admin_msg("/bepul @nobody")
    await cmd_free(unknown, cmd("@nobody"), session, bot, clock)
    assert "topilmadi" in unknown.answer.call_args.args[0]


async def test_stats_counts(session, clock, now):
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "card", now)
    await fulfil(session, order, now)
    await session.commit()
    msg = admin_msg("/stats")
    await cmd_stats(msg, session, clock)
    text = msg.answer.call_args.args[0]
    assert "Foydalanuvchilar: 1" in text and "5 000" in text


async def test_broadcast_skips_blocked(bot, session):
    for uid in (1, 2, 3):
        await make_user(session, uid)
    await session.commit()

    async def copy_message(chat_id, from_chat_id, message_id):
        if chat_id == 2:
            raise TelegramForbiddenError(method=None, message="Forbidden: bot was blocked by the user")
        bot.copied.append(chat_id)

    bot.copied = []
    bot.copy_message = copy_message
    source = SimpleNamespace(chat=SimpleNamespace(id=ADMIN), message_id=77)
    msg = admin_msg("/xabar", reply_to=source)
    await cmd_broadcast(msg, session, bot, delay=0)
    assert sorted(bot.copied) == [1, 3]
    assert (await session.get(User, 2)).blocked_bot is True
    assert "2" in msg.answer.call_args.args[-1] or "2" in str(msg.answer.call_args_list[-1])


async def test_refund_stars_order(bot, session, clock, now):
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    await fulfil(session, order, now, charge_id="ch-7")
    await session.commit()
    msg = admin_msg(f"/qaytar {order.code}")
    await cmd_refund(msg, cmd(order.code), session, bot, clock)
    assert bot.refunds == [(1, "ch-7")]
    await session.refresh(order)
    assert order.status == "refunded"
