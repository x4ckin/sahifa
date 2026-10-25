import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient

from sahifa.api.app import create_app


def sign_init_data(user: dict, bot_token: str, auth_date: int) -> str:
    """Build initData exactly the way Telegram signs it."""
    fields = {"auth_date": str(auth_date), "query_id": "AAE", "user": json.dumps(user, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class FakeHooks:
    def __init__(self):
        self.receipts: list[str] = []

    async def invoice_link(self, order) -> str:
        return f"https://t.me/$invoice-{order.code}"

    async def notify_receipt(self, order) -> None:
        self.receipts.append(order.code)


@pytest.fixture
def hooks() -> FakeHooks:
    return FakeHooks()


@pytest.fixture
def app(settings, sessionmaker, now, hooks):
    return create_app(
        settings,
        sessionmaker,
        invoice_link_factory=hooks.invoice_link,
        receipt_notifier=hooks.notify_receipt,
        clock=lambda: now,
    )


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://api.test") as c:
        yield c


@pytest.fixture
def auth(settings, now):
    def make(uid: int = 1, first_name: str = "Ali", **extra) -> dict:
        user = {"id": uid, "first_name": first_name, **extra}
        return {"X-Telegram-Init-Data": sign_init_data(user, settings.bot_token, int(now.timestamp()))}

    return make
