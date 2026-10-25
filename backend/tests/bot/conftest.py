from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str, object]] = []
        self.refunds: list[tuple[int, str]] = []
        self.invoices: list[dict] = []
        self.photos: list[tuple] = []

    async def send_photo(self, chat_id, photo, caption=None, reply_markup=None, **_):
        self.photos.append((chat_id, photo, caption, reply_markup))

    async def send_message(self, chat_id, text, reply_markup=None, **_):
        self.sent.append((chat_id, text, reply_markup))

    async def refund_star_payment(self, user_id, telegram_payment_charge_id):
        self.refunds.append((user_id, telegram_payment_charge_id))
        return True

    async def create_invoice_link(self, **kwargs):
        self.invoices.append(kwargs)
        return f"https://t.me/$inv-{kwargs['payload']}"


def tg_user(uid=1, first_name="Ali", username=None):
    return SimpleNamespace(
        id=uid, first_name=first_name, username=username, language_code="uz",
        model_dump=lambda **_: {"id": uid, "first_name": first_name, "username": username, "language_code": "uz"},
    )


def fake_message(uid=1, text="/start", **extra):
    msg = SimpleNamespace(from_user=tg_user(uid), text=text, chat=SimpleNamespace(id=uid), **extra)
    msg.answer = AsyncMock()
    msg.reply = AsyncMock()
    return msg


def fake_callback(uid, data):
    cb = SimpleNamespace(from_user=tg_user(uid), data=data, message=fake_message(uid))
    cb.answer = AsyncMock()
    cb.message.html_text = "🧾 chek"
    cb.message.edit_text = AsyncMock()
    cb.message.edit_caption = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    return cb


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def clock(now):
    return lambda: now


def buttons(markup) -> list:
    return [b for row in markup.inline_keyboard for b in row]
