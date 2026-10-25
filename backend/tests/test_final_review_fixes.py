"""Regression tests for the final whole-branch review."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from sahifa.bot import payments
from sahifa.config import Settings
from sahifa.domain.pricing import Product
from sahifa.models import AuditLog
from sahifa.services.jobs import run_daily
from sahifa.services.orders import attach_receipt, create_order
from tests.api.test_museums_api import jpeg_bytes
from tests.bot.conftest import FakeBot
from tests.bot.test_payments import paid_message
from tests.factories import make_user, tiny_jpeg


async def test_unexpected_payment_error_is_recorded_and_reported(session, settings, clock, now, monkeypatch):
    bot = FakeBot()
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    await session.commit()

    async def locked(*_, **__):
        raise OperationalError("UPDATE", {}, Exception("database is locked"))

    monkeypatch.setattr(payments.orders, "fulfil", locked)
    msg = paid_message(1, order.code, "ch-x")
    await payments.on_successful_payment(msg, session, bot, settings, clock)
    rows = (await session.scalars(select(AuditLog).where(AuditLog.action == "payment_unhandled"))).all()
    assert len(rows) == 1 and rows[0].payload["charge_id"] == "ch-x"
    assert any(chat == settings.admin_chat_id and "ch-x" in text for chat, text, _ in bot.sent)
    assert "admin" in msg.answer.call_args.args[0].lower()


async def test_reminder_title_is_escaped_and_sent_after_commit(session, now, tmp_path):
    from datetime import timedelta

    from sahifa.models import Museum

    user = await make_user(session, 1)
    session.add(Museum(owner_id=user.id, created_by_id=user.id, status="active", title="Onam <3",
                       paid_at=now, expires_at=now + timedelta(days=3)))
    await session.commit()
    sent = []

    async def notify(chat_id, text):
        assert not session.in_transaction(), "Telegram must not be called while holding the DB write lock"
        sent.append(text)

    await run_daily(session, now, notify, media_dir=tmp_path)
    assert "Onam &lt;3" in sent[0]


async def test_receipt_upload_survives_notifier_failure(settings, sessionmaker, now, auth):
    from httpx import ASGITransport, AsyncClient

    from sahifa.api.app import create_app

    async def broken_notifier(order):
        raise RuntimeError("chat not found")

    async def link(order):
        return "x"

    app = create_app(settings, sessionmaker, invoice_link_factory=link, receipt_notifier=broken_notifier,
                     clock=lambda: now)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://api.test") as c:
        h = auth(1)
        order = (await c.post("/api/orders", json={"product": "slots", "method": "card"}, headers=h)).json()
        r = await c.post(f"/api/orders/{order['code']}/receipt",
                         files={"file": ("r.jpg", jpeg_bytes(), "image/jpeg")}, headers=h)
        assert (r.status_code, r.json()["status"]) == (200, "awaiting_review")


async def test_admin_can_list_and_resend_waiting_receipts(session, settings, now, tmp_path):
    from sahifa.bot.admin import cmd_pending_receipts

    bot = FakeBot()
    user = await make_user(session, 1)
    order = await create_order(session, user, Product.SLOTS, None, "card", now)
    await attach_receipt(session, order, tiny_jpeg(tmp_path / "r.jpg"), now, receipts_dir=settings.receipts_dir)
    await session.commit()
    msg = SimpleNamespace(from_user=SimpleNamespace(id=999), chat=SimpleNamespace(id=999))
    from unittest.mock import AsyncMock

    msg.answer = AsyncMock()
    await cmd_pending_receipts(msg, session, bot, settings)
    assert [p[0] for p in bot.photos] == [settings.admin_chat_id]
    assert order.code in bot.photos[0][2]


async def test_card_money_sent_before_switching_to_stars_can_still_be_attached(session, now, tmp_path):
    user = await make_user(session, 1)
    card = await create_order(session, user, Product.SLOTS, None, "card", now)
    await create_order(session, user, Product.SLOTS, None, "stars", now)  # cancels the card order
    assert card.status == "cancelled"
    await attach_receipt(session, card, tiny_jpeg(tmp_path / "r.jpg"), now, receipts_dir=tmp_path / "rc")
    assert card.status == "awaiting_review"


def test_admin_settings_are_required(monkeypatch):
    for key in ("SAHIFA_ADMIN_IDS", "SAHIFA_ADMIN_CHAT_ID"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError):
        Settings(_env_file=None, bot_token="1:x")


@pytest.fixture
def clock(now):
    return lambda: now


@pytest.fixture
def auth(settings, now):
    from tests.api.conftest import sign_init_data

    def make(uid: int = 1) -> dict:
        return {"X-Telegram-Init-Data": sign_init_data({"id": uid, "first_name": "A"}, settings.bot_token, int(now.timestamp()))}

    return make
