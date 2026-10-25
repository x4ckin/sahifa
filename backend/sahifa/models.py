import secrets
from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sahifa.domain.lifecycle import MuseumState


class UTCDateTime(TypeDecorator):
    """Stores UTC, always returns timezone-aware datetimes (SQLite drops tzinfo)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("naive datetime")
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_slug() -> str:
    return secrets.token_urlsafe(9)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UTCDateTime, int: BigInteger().with_variant(Integer, "sqlite")}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    lang: Mapped[str] = mapped_column(String(8), default="uz")
    extra_slots: Mapped[int] = mapped_column(default=0)
    is_free: Mapped[bool] = mapped_column(default=False)
    free_until: Mapped[datetime | None]
    referrer_id: Mapped[int | None]
    blocked_bot: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Museum(Base):
    __tablename__ = "museums"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, default=new_slug)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default=MuseumState.DRAFT, index=True)
    template: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(80), default="Bizning muzeyimiz")
    recipient_name: Mapped[str | None] = mapped_column(String(60))
    theme: Mapped[str] = mapped_column(String(32), default="gallery_light")
    mascot: Mapped[str] = mapped_column(String(32), default="boy")
    opening_style: Mapped[str] = mapped_column(String(32), default="gift_box")
    letter_text: Mapped[str | None] = mapped_column(Text)
    voice_path: Mapped[str | None] = mapped_column(String(255))
    music_id: Mapped[str | None] = mapped_column(String(64))
    music_path: Mapped[str | None] = mapped_column(String(255))
    open_at: Mapped[datetime | None]
    extra_rooms: Mapped[int] = mapped_column(default=0)
    paid_at: Mapped[datetime | None]
    active_from: Mapped[datetime | None]
    expires_at: Mapped[datetime | None] = mapped_column(index=True)
    reminded_days: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class MediaItem(Base):
    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    museum_id: Mapped[int] = mapped_column(ForeignKey("museums.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # image | video
    path: Mapped[str] = mapped_column(String(255))
    thumb_path: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(String(200))
    taken_on: Mapped[str | None] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product: Mapped[str] = mapped_column(String(16))
    museum_id: Mapped[int | None] = mapped_column(ForeignKey("museums.id"))
    method: Mapped[str] = mapped_column(String(8))  # stars | card | free
    amount_uzs: Mapped[int] = mapped_column(default=0)
    amount_stars: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    receipt_path: Mapped[str | None] = mapped_column(String(255))
    charge_id: Mapped[str | None] = mapped_column(String(128))
    admin_id: Mapped[int | None]
    reject_reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    paid_at: Mapped[datetime | None]


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True)
    museum_id: Mapped[int] = mapped_column(ForeignKey("museums.id"), index=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | int | str] = mapped_column(JSON)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None]
    action: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(default=utcnow)
