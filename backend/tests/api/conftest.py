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
        self.chat_files: dict[str, bytes] = {}  # file_id -> content, i.e. the user's Telegram chat
        self.uploaded_paths: list = []
        self.fetches = 0
        self.blocked: set[int] = set()

    async def tg_upload(self, user_id, path, kind) -> str:
        from sahifa.domain.lifecycle import DomainError

        if user_id in self.blocked:
            raise DomainError("start_bot")
        self.uploaded_paths.append(path)
        file_id = f"F{len(self.chat_files)}_{user_id}"
        self.chat_files[file_id] = path.read_bytes()
        return file_id

    async def tg_fetch(self, file_id) -> bytes:
        from sahifa.domain.lifecycle import DomainError

        self.fetches += 1
        if file_id not in self.chat_files:
            raise DomainError("media_gone")
        return self.chat_files[file_id]

    async def invoice_link(self, order, rooms=0) -> str:
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
        tg_uploader=hooks.tg_upload,
        tg_fetcher=hooks.tg_fetch,
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
