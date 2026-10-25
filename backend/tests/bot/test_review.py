from sahifa.bot.review import notify_admins_new_receipt, on_review
from sahifa.domain.pricing import Product
from sahifa.services.museums import create_museum
from sahifa.services.orders import attach_receipt, create_order
from tests.bot.conftest import buttons, fake_callback
from tests.factories import make_user, tiny_jpeg

ADMIN = 999


async def _receipt_order(session, settings, now, tmp_path, uid=1):
    user = await make_user(session, uid)
    m = await create_museum(session, user, now)
    m.title = "Onam <3"
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await attach_receipt(session, order, tiny_jpeg(tmp_path / "r.jpg"), now, receipts_dir=settings.receipts_dir)
    await session.commit()
    return order, m


async def test_admins_get_receipt_with_buttons(bot, session, settings, now, tmp_path):
    order, _ = await _receipt_order(session, settings, now, tmp_path)
    await notify_admins_new_receipt(bot, settings, session, order)
    (chat_id, photo, caption, markup) = bot.photos[0]
    assert chat_id == settings.admin_chat_id
    assert order.code in caption and "15 000" in caption
    assert "Onam &lt;3" in caption  # user text is escaped for HTML
    datas = [b.callback_data for b in buttons(markup)]
    assert datas[0] == f"rv:ok:{order.code}"
    assert {d.rsplit(":", 1)[1] for d in datas[1:]} == {"amount", "unreadable", "notfound"}


async def test_approve_twice_fulfils_once(bot, session, settings, clock, now, tmp_path):
    order, m = await _receipt_order(session, settings, now, tmp_path)
    for _ in range(2):
        cb = fake_callback(ADMIN, f"rv:ok:{order.code}")
        await on_review(cb, session, bot, settings, clock)
    await session.refresh(m)
    await session.refresh(order)
    assert (order.status, order.admin_id, m.status) == ("paid", ADMIN, "active")
    user_msgs = [t for chat, t, _ in bot.sent if chat == 1]
    assert len(user_msgs) == 1 and "tasdiqlandi" in user_msgs[0]


async def test_non_admin_cannot_approve(bot, session, settings, clock, now, tmp_path):
    order, m = await _receipt_order(session, settings, now, tmp_path)
    cb = fake_callback(1, f"rv:ok:{order.code}")
    await on_review(cb, session, bot, settings, clock)
    await session.refresh(order)
    assert order.status == "awaiting_review"
    assert cb.answer.call_args.kwargs.get("show_alert") is True


async def test_reject_notifies_user_with_reason(bot, session, settings, clock, now, tmp_path):
    order, _ = await _receipt_order(session, settings, now, tmp_path)
    cb = fake_callback(ADMIN, f"rv:no:{order.code}:amount")
    await on_review(cb, session, bot, settings, clock)
    await session.refresh(order)
    assert (order.status, order.reject_reason) == ("rejected", "amount")
    (chat, text, markup) = bot.sent[0]
    assert chat == 1 and "summa" in text.lower()
    assert buttons(markup)[0].web_app.url.startswith(settings.webapp_url)


async def test_approve_for_deleted_museum_tells_admin_to_refund(bot, session, settings, clock, now, tmp_path):
    order, m = await _receipt_order(session, settings, now, tmp_path)
    m.status = "deleted"
    await session.commit()
    cb = fake_callback(ADMIN, f"rv:ok:{order.code}")
    await on_review(cb, session, bot, settings, clock)
    await session.refresh(order)
    assert order.status == "rejected"
    assert "qaytaring" in cb.message.edit_caption.call_args.kwargs["caption"]
