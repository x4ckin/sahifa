from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.domain.lifecycle import DomainError, MuseumState
from sahifa.domain.pricing import BASE_SLOTS
from sahifa.models import Museum, User
from sahifa.services import audit

SUPPORTED_LANGS = {"uz", "ru"}


async def upsert_user(s: AsyncSession, tg: dict) -> User:
    """Create or refresh a user from Telegram user data (initData or aiogram User.model_dump())."""
    user = await s.get(User, tg["id"])
    if user is None:
        user = User(id=tg["id"])
        s.add(user)
    user.username = tg.get("username")
    user.first_name = tg.get("first_name") or ""
    lang = (tg.get("language_code") or "uz")[:2]
    user.lang = lang if lang in SUPPORTED_LANGS else "uz"
    await s.flush()
    return user


def is_free_now(user: User, now: datetime) -> bool:
    return user.is_free and (user.free_until is None or user.free_until > now)


async def grant_free(
    s: AsyncSession, user_id: int, admin_id: int, days: int | None, now: datetime
) -> User:
    user = await s.get(User, user_id)
    if user is None:
        raise DomainError("user_not_found")
    user.is_free = True
    user.free_until = now + timedelta(days=days) if days else None
    await audit.log(s, admin_id, "grant_free", user_id=user_id, days=days)
    return user


async def revoke_free(s: AsyncSession, user_id: int, admin_id: int) -> User:
    user = await s.get(User, user_id)
    if user is None:
        raise DomainError("user_not_found")
    user.is_free = False
    user.free_until = None
    await audit.log(s, admin_id, "revoke_free", user_id=user_id)
    return user


async def list_free(s: AsyncSession) -> list[User]:
    return list((await s.scalars(select(User).where(User.is_free).order_by(User.id))).all())


async def find_user(s: AsyncSession, ref: str) -> User | None:
    """Look up by numeric id or @username among known users."""
    ref = ref.strip()
    if ref.lstrip("-").isdigit():
        return await s.get(User, int(ref))
    name = ref.lstrip("@").lower()
    return await s.scalar(select(User).where(func.lower(User.username) == name))


async def slots_status(s: AsyncSession, user: User, now: datetime) -> tuple[int, int | None]:
    used = await s.scalar(
        select(func.count())
        .select_from(Museum)
        .where(
            Museum.owner_id == user.id,
            Museum.created_by_id == user.id,
            Museum.status != MuseumState.DELETED,
        )
    )
    total = None if is_free_now(user, now) else BASE_SLOTS + user.extra_slots
    return used or 0, total
