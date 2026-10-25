import pytest

from sahifa.domain.lifecycle import DomainError
from sahifa.services.tgmedia import media_secret, sign_media, verify_media

SECRET = media_secret("123456:TEST-TOKEN")


def test_roundtrip():
    token = sign_media(SECRET, 42, "BQACAgIAAxkBAAIB", "video")
    assert verify_media(SECRET, token) == (42, "BQACAgIAAxkBAAIB", "video")
    assert "/" not in token and "+" not in token  # safe in a URL path


def test_tampered_payload_or_signature_rejected():
    token = sign_media(SECRET, 42, "FILE", "image")
    payload, sig = token.split(".")
    other_payload = sign_media(SECRET, 43, "FILE", "image").split(".")[0]
    for bad in (f"{other_payload}.{sig}", f"{payload}.{sig[:-2]}AA", f"{payload}x.{sig}"):
        with pytest.raises(DomainError) as err:
            verify_media(SECRET, bad)
        assert err.value.code == "bad_token"


def test_other_secret_rejected():
    token = sign_media(media_secret("999:OTHER"), 42, "FILE", "image")
    with pytest.raises(DomainError):
        verify_media(SECRET, token)


def test_garbage_rejected():
    for bad in ("", ".", "abc", "a.b.c", "!!!.???", "e30.AAAA"):
        with pytest.raises(DomainError):
            verify_media(SECRET, bad)


def test_unknown_kind_cannot_be_signed():
    with pytest.raises(ValueError):
        sign_media(SECRET, 1, "F", "pdf")
