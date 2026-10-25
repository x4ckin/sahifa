"""Tokens for media that lives in the user's Telegram chat with the bot (free, account-held museums).

A token names one Telegram file and the user it belongs to. It is signed with a key derived from the
bot token, so only our server can mint it and nobody can swap in someone else's file.
"""

import base64
import binascii
import hashlib
import hmac
import json

from sahifa.domain.lifecycle import DomainError

KINDS = ("image", "video", "audio")
_SIG_BYTES = 16


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def media_secret(bot_token: str) -> bytes:
    return hashlib.sha256(b"sahifa-tg-media:" + bot_token.encode()).digest()


def _sign(secret: bytes, payload: str) -> str:
    return _b64(hmac.new(secret, payload.encode(), hashlib.sha256).digest()[:_SIG_BYTES])


def sign_media(secret: bytes, user_id: int, file_id: str, kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown media kind {kind!r}")
    payload = _b64(json.dumps({"u": user_id, "f": file_id, "k": kind}, separators=(",", ":")).encode())
    return f"{payload}.{_sign(secret, payload)}"


def verify_media(secret: bytes, token: str) -> tuple[int, str, str]:
    try:
        payload, sig = token.split(".")
        if not hmac.compare_digest(_sign(secret, payload).encode(), sig.encode()):
            raise ValueError("signature")
        data = json.loads(_unb64(payload))
        user_id, file_id, kind = int(data["u"]), str(data["f"]), data["k"]
    except (ValueError, KeyError, TypeError, binascii.Error, UnicodeDecodeError) as e:
        raise DomainError("bad_token") from e
    if kind not in KINDS or not file_id:
        raise DomainError("bad_token")
    return user_id, file_id, kind
