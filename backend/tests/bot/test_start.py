from types import SimpleNamespace

from sahifa.bot.start import cmd_start, on_transfer_answer
from sahifa.models import Museum, User
from sahifa.services.museums import create_museum
from sahifa.services.transfers import create_transfer
from tests.bot.conftest import buttons, fake_callback, fake_message
from tests.factories import make_user


def command(args=None):
    return SimpleNamespace(args=args)


async def test_start_shows_webapp_buttons(session, settings, clock):
    msg = fake_message(1)
    await cmd_start(msg, command(), session, settings, clock)
    text = msg.answer.call_args.args[0]
    assert "Sahifa" in text
    btns = buttons(msg.answer.call_args.kwargs["reply_markup"])
    assert [b.web_app.url for b in btns] == [settings.webapp_url, f"{settings.webapp_url}#/my"]
    assert await session.get(User, 1) is not None


async def test_museum_deeplink_opens_that_museum(session, settings, clock):
    msg = fake_message(5)
    await cmd_start(msg, command("m_abcDEF123"), session, settings, clock)
    (btn,) = buttons(msg.answer.call_args.kwargs["reply_markup"])
    assert btn.web_app.url == f"{settings.webapp_url}#/m/abcDEF123"


async def test_referral_recorded_once_for_new_users(session, settings, clock):
    for uid in (3, 4):
        await make_user(session, uid)
    await cmd_start(fake_message(6), command("ref_404"), session, settings, clock)
    assert (await session.get(User, 6)).referrer_id is None  # unknown referrer
    await cmd_start(fake_message(7), command("ref_3"), session, settings, clock)
    assert (await session.get(User, 7)).referrer_id == 3
    await cmd_start(fake_message(7), command("ref_4"), session, settings, clock)
    assert (await session.get(User, 7)).referrer_id == 3
    await cmd_start(fake_message(8), command("ref_8"), session, settings, clock)
    assert (await session.get(User, 8)).referrer_id is None  # no self-referral


async def test_transfer_deeplink_accept(bot, session, settings, clock, now):
    giver = await make_user(session, 1)
    m = await create_museum(session, giver, now)
    m.title = "Bizning yo'l"
    t = await create_transfer(session, m, giver, now)
    await session.commit()

    msg = fake_message(2)
    await cmd_start(msg, command(f"tr_{t.token}"), session, settings, clock)
    assert "Bizning yo'l" in msg.answer.call_args.args[0]
    yes, no = buttons(msg.answer.call_args.kwargs["reply_markup"])
    assert yes.callback_data == f"tr:ok:{t.token}" and no.callback_data == f"tr:no:{t.token}"

    cb = fake_callback(2, yes.callback_data)
    await on_transfer_answer(cb, session, bot, settings, clock)
    assert (await session.get(Museum, m.id)).owner_id == 2
    cb.message.edit_text.assert_awaited()


async def test_transfer_deeplink_invalid(session, settings, clock):
    msg = fake_message(2)
    await cmd_start(msg, command("tr_nope"), session, settings, clock)
    assert "yaroqsiz" in msg.answer.call_args.args[0]


async def test_transfer_decline_keeps_owner(bot, session, settings, clock, now):
    giver = await make_user(session, 1)
    m = await create_museum(session, giver, now)
    t = await create_transfer(session, m, giver, now)
    await session.commit()
    cb = fake_callback(2, f"tr:no:{t.token}")
    await on_transfer_answer(cb, session, bot, settings, clock)
    assert (await session.get(Museum, m.id)).owner_id == 1


def test_dispatcher_builds(sessionmaker, settings):
    from sahifa.bot.setup import build_dispatcher

    dp = build_dispatcher(sessionmaker, settings)
    assert {r.name for r in dp.sub_routers} == {"start", "payments", "review", "admin"}
