"""Regression tests for the plan-1b final review."""

from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

from sahifa.bot.tgfiles import make_tg_fetcher, make_tg_uploader
from sahifa.domain.lifecycle import DomainError
from sahifa.services.tgmedia import sign_media
from tests.api.test_tgmedia_api import _upload


class Bot:
    def __init__(self, fail=()):
        self.fail = list(fail)
        self.kwargs = None

    async def send_document(self, chat_id, document, **kwargs):
        self.kwargs = kwargs
        if self.fail:
            raise self.fail.pop(0)
        return SimpleNamespace(document=None, video=SimpleNamespace(file_id="VID"), animation=None,
                               audio=None, voice=None, sticker=None)

    async def get_file(self, file_id):
        raise TelegramNetworkError(method=None, message="timeout")


async def test_uploader_keeps_file_as_document_and_reads_any_media_field(tmp_path):
    path = tmp_path / "v.mp4"
    path.write_bytes(b"x")
    bot = Bot()
    assert await make_tg_uploader(bot)(7, path, "video") == "VID"
    assert bot.kwargs["disable_content_type_detection"] is True


async def test_uploader_waits_out_flood_control(tmp_path):
    path = tmp_path / "a.webp"
    path.write_bytes(b"x")
    bot = Bot(fail=[TelegramRetryAfter(method=None, message="Too Many Requests", retry_after=0)])
    assert await make_tg_uploader(bot)(7, path, "image") == "VID"


async def test_network_errors_are_temporary_not_500(tmp_path):
    path = tmp_path / "a.webp"
    path.write_bytes(b"x")
    with pytest.raises(DomainError) as err:
        await make_tg_uploader(Bot(fail=[TelegramNetworkError(method=None, message="x")]))(7, path, "image")
    assert err.value.code == "telegram_unavailable"
    with pytest.raises(DomainError) as err:
        await make_tg_fetcher(Bot())("F")
    assert err.value.code == "telegram_unavailable"


async def test_video_range_requests_get_206(client, auth):
    token = (await _upload(client, auth(7))).json()["token"]
    full = (await client.get(f"/api/tg-media/{token}")).content
    r = await client.get(f"/api/tg-media/{token}", headers={"Range": "bytes=0-3"})
    assert r.status_code == 206
    assert r.content == full[:4]
    assert r.headers["content-range"] == f"bytes 0-3/{len(full)}"
    assert r.headers["accept-ranges"] == "bytes"
    tail = await client.get(f"/api/tg-media/{token}", headers={"Range": "bytes=4-"})
    assert tail.content == full[4:]
    bad = await client.get(f"/api/tg-media/{token}", headers={"Range": f"bytes={len(full) + 5}-"})
    assert bad.status_code == 416


async def test_proxy_is_rate_limited_per_ip(client, auth, monkeypatch):
    from sahifa.api import routes_tgmedia

    monkeypatch.setattr(routes_tgmedia, "_limiter", routes_tgmedia.RateLimiter(per_minute=2))
    token = (await _upload(client, auth(7))).json()["token"]
    codes = [(await client.get(f"/api/tg-media/{token}")).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_media_key_survives_bot_token_rotation(settings):
    from sahifa.services.tgmedia import media_key

    a = settings.model_copy(update={"media_secret": "long-random-secret"})
    b = a.model_copy(update={"bot_token": "123456:ROTATED"})
    assert media_key(a) == media_key(b)
    token = sign_media(media_key(a), 1, "F", "image")
    assert token  # still verifiable after rotation (same key)


async def test_import_counts_limits_before_fetching(client, auth, hooks):
    token = (await _upload(client, auth(7))).json()["token"]
    hooks.fetches = 0
    r = await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": token}] * 31}, headers=auth(7))
    assert (r.status_code, r.json()) == (409, {"error": "media_full"})
    assert hooks.fetches == 0


async def test_import_does_not_re_encode(client, auth, hooks, settings):
    token = (await _upload(client, auth(7))).json()["token"]
    sent = next(iter(hooks.chat_files.values()))
    m = (await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": token}]}, headers=auth(7))).json()
    stored = settings.media_dir / m["media"][0]["url"].split("/media/", 1)[1]
    assert stored.read_bytes() == sent


@pytest.fixture
def auth(settings, now):
    from tests.api.conftest import sign_init_data

    def make(uid: int = 1) -> dict:
        return {"X-Telegram-Init-Data": sign_init_data({"id": uid, "first_name": "A"}, settings.bot_token, int(now.timestamp()))}

    return make


@pytest.fixture
def hooks():
    from tests.api.conftest import FakeHooks

    return FakeHooks()


@pytest.fixture
async def client(settings, sessionmaker, now, hooks):
    from httpx import ASGITransport, AsyncClient

    from sahifa.api.app import create_app

    app = create_app(settings, sessionmaker, invoice_link_factory=hooks.invoice_link,
                     receipt_notifier=hooks.notify_receipt, tg_uploader=hooks.tg_upload,
                     tg_fetcher=hooks.tg_fetch, clock=lambda: now)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://api.test") as c:
        yield c
