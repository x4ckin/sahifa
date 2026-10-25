from datetime import timedelta
from urllib.parse import parse_qsl, urlencode

import pytest

from sahifa.api.auth import AuthError, verify_init_data
from tests.api.conftest import sign_init_data

TOKEN = "123456:TEST-TOKEN"


def test_accepts_valid_init_data(now):
    data = sign_init_data({"id": 42, "first_name": "Ali"}, TOKEN, int(now.timestamp()))
    assert verify_init_data(data, TOKEN, now)["id"] == 42


def test_rejects_tampered_and_stale_init_data(now):
    good = sign_init_data({"id": 42, "first_name": "Ali"}, TOKEN, int(now.timestamp()))
    fields = dict(parse_qsl(good))
    fields["user"] = fields["user"].replace("42", "43")
    with pytest.raises(AuthError):
        verify_init_data(urlencode(fields), TOKEN, now)
    with pytest.raises(AuthError):
        verify_init_data(good, "999:OTHER", now)
    stale = sign_init_data({"id": 42}, TOKEN, int((now - timedelta(hours=25)).timestamp()))
    with pytest.raises(AuthError):
        verify_init_data(stale, TOKEN, now)
    for broken in ("", "hash=abc", "user=%7B%7D&auth_date=1"):
        with pytest.raises(AuthError):
            verify_init_data(broken, TOKEN, now)


async def test_api_requires_valid_header(client, auth, settings, now):
    assert (await client.get("/api/me")).status_code == 401
    bad = {"X-Telegram-Init-Data": sign_init_data({"id": 1}, "1:WRONG", int(now.timestamp()))}
    assert (await client.get("/api/me", headers=bad)).status_code == 401
    r = await client.get("/api/me", headers=auth(1, "Ali", language_code="ru"))
    assert r.status_code == 200
    assert r.json() == {
        "id": 1, "first_name": "Ali", "lang": "ru", "is_free": False, "slots": {"used": 0, "total": 10},
        "bot_username": "SahifaTestBot",
    }
