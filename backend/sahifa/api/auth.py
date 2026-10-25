"""Telegram Mini App identity: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.models import User
from sahifa.services.users import upsert_user

HEADER = "X-Telegram-Init-Data"


class AuthError(Exception):
    pass


def verify_init_data(
    init_data: str, bot_token: str, now: datetime, max_age: timedelta = timedelta(hours=24)
) -> dict:
    """Return the Telegram user dict if `init_data` is signed by our bot and fresh."""
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as e:
        raise AuthError("malformed") from e
    received = fields.pop("hash", None)
    if not received:
        raise AuthError("no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("bad hash")
    try:
        auth_date = datetime.fromtimestamp(int(fields["auth_date"]), tz=now.tzinfo)
        user = json.loads(fields["user"])
        int(user["id"])
    except (KeyError, ValueError, TypeError) as e:
        raise AuthError("bad fields") from e
    if now - auth_date > max_age or auth_date - now > timedelta(minutes=5):
        raise AuthError("stale")
    return user


async def get_session(request: Request):
    async with request.app.state.sessionmaker() as s:
        yield s


async def optional_user(request: Request, s: AsyncSession = Depends(get_session)) -> User | None:
    raw = request.headers.get(HEADER)
    if not raw:
        return None
    try:
        tg = verify_init_data(raw, request.app.state.settings.bot_token, request.app.state.clock())
    except AuthError:
        return None
    user = await upsert_user(s, tg)
    await s.commit()
    return user


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise AuthError("unauthorized")
    return user
