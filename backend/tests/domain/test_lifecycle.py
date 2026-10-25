from datetime import timedelta

import pytest

from sahifa.domain.lifecycle import (
    DomainError,
    Limits,
    activation_window,
    limits_for,
    locked_fields,
    public_state,
    reactivated_expiry,
    validate_open_at,
)
from sahifa.domain.pricing import DEFAULT_PRICES_STARS, DEFAULT_PRICES_UZS, Product


def test_default_prices_match_spec():
    assert DEFAULT_PRICES_UZS == {
        Product.MUSEUM: 15000,
        Product.REACTIVATE: 15000,
        Product.ROOM: 3000,
        Product.SLOTS: 5000,
    }
    assert set(DEFAULT_PRICES_STARS) == set(Product)


def test_limits_grow_per_room():
    assert limits_for(0) == Limits(rooms=3, images=30, videos=5)
    assert limits_for(2) == Limits(rooms=5, images=50, videos=9)


def test_activation_starts_at_open_at(now):
    open_at = now + timedelta(days=40)
    assert activation_window(now, open_at) == (open_at, open_at + timedelta(days=120))
    assert activation_window(now, None) == (now, now + timedelta(days=120))


def test_reactivation_adds_to_remaining_or_now(now):
    assert reactivated_expiry(now, now + timedelta(days=10)) == now + timedelta(days=130)
    assert reactivated_expiry(now, now - timedelta(days=3)) == now + timedelta(days=120)
    assert reactivated_expiry(now, None) == now + timedelta(days=120)


def test_open_at_bounds(now):
    validate_open_at(now, now + timedelta(days=120))
    for bad in (now, now - timedelta(days=1), now + timedelta(days=120, seconds=1)):
        with pytest.raises(DomainError) as err:
            validate_open_at(now, bad)
        assert err.value.code == "open_at"


def test_locks_only_after_payment():
    assert locked_fields({"title", "media"}, paid=False) == set()
    assert locked_fields({"title", "caption"}, paid=True) == {"title"}
    assert locked_fields({"recipient_name", "voice", "open_at", "music"}, paid=True) == {
        "recipient_name",
        "voice",
        "open_at",
        "music",
    }


def test_public_state(now):
    later = now + timedelta(days=9)
    assert public_state("active", now + timedelta(hours=1), later, now) == "locked"
    assert public_state("active", now - timedelta(hours=1), later, now) == "open"
    assert public_state("active", None, now - timedelta(seconds=1), now) == "expired"
    assert public_state("expired", None, now - timedelta(days=1), now) == "expired"
    assert public_state("draft", None, None, now) == "draft"
    assert public_state("deleted", None, None, now) == "deleted"
