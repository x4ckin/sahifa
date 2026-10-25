"""Pure museum lifecycle rules. Every function takes `now` explicitly."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from sahifa.domain.pricing import (
    ACTIVE_DAYS,
    BASE_IMAGES,
    BASE_ROOMS,
    BASE_VIDEOS,
    ROOM_IMAGES,
    ROOM_VIDEOS,
)


class DomainError(Exception):
    """A business-rule violation; `code` is turned into user-facing text by API/bot."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class MuseumState(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    DELETED = "deleted"


@dataclass(frozen=True)
class Limits:
    rooms: int
    images: int
    videos: int


LOCKED_AFTER_PAYMENT = frozenset(
    {
        "recipient_name",
        "title",
        "opening_style",
        "letter_text",
        "voice",
        "theme",
        "mascot",
        "music",
        "open_at",
    }
)

ACTIVE_PERIOD = timedelta(days=ACTIVE_DAYS)


def limits_for(extra_rooms: int) -> Limits:
    return Limits(
        rooms=BASE_ROOMS + extra_rooms,
        images=BASE_IMAGES + ROOM_IMAGES * extra_rooms,
        videos=BASE_VIDEOS + ROOM_VIDEOS * extra_rooms,
    )


MAX_EXTRA_ROOMS = 10


def rooms_needed(images: int, videos: int) -> int:
    """Extra rooms a museum needs for this much media (free museums may grow up to 10 rooms)."""
    rooms = max(-(-(images - BASE_IMAGES) // ROOM_IMAGES), -(-(videos - BASE_VIDEOS) // ROOM_VIDEOS), 0)
    if rooms > MAX_EXTRA_ROOMS:
        raise DomainError("media_full")
    return rooms


def locked_fields(changed: set[str], paid: bool) -> set[str]:
    return set(changed & LOCKED_AFTER_PAYMENT) if paid else set()


def activation_window(now: datetime, open_at: datetime | None) -> tuple[datetime, datetime]:
    active_from = open_at if open_at is not None else now
    return active_from, active_from + ACTIVE_PERIOD


def reactivated_expiry(now: datetime, expires_at: datetime | None) -> datetime:
    base = expires_at if expires_at is not None and expires_at > now else now
    return base + ACTIVE_PERIOD


def validate_open_at(now: datetime, open_at: datetime) -> None:
    if not isinstance(open_at, datetime) or open_at.tzinfo is None:
        raise DomainError("open_at")
    if open_at <= now or open_at > now + ACTIVE_PERIOD:
        raise DomainError("open_at")


def public_state(
    status: str,
    open_at: datetime | None,
    expires_at: datetime | None,
    now: datetime,
) -> Literal["draft", "locked", "open", "expired", "deleted"]:
    if status == MuseumState.DELETED:
        return "deleted"
    if status == MuseumState.DRAFT:
        return "draft"
    if status == MuseumState.EXPIRED or (expires_at is not None and expires_at <= now):
        return "expired"
    if open_at is not None and open_at > now:
        return "locked"
    return "open"
