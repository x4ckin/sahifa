import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.domain.lifecycle import DomainError, MuseumState
from sahifa.domain.pricing import TRANSFER_TTL_DAYS
from sahifa.models import Museum, Transfer, User
from sahifa.services import audit


def _ensure_owner(museum: Museum, user: User) -> None:
    if museum.owner_id != user.id or museum.status == MuseumState.DELETED:
        raise DomainError("not_found")


async def create_transfer(s: AsyncSession, museum: Museum, from_user: User, now: datetime) -> Transfer:
    _ensure_owner(museum, from_user)
    await s.execute(
        update(Transfer)
        .where(Transfer.museum_id == museum.id, Transfer.status == "pending")
        .values(status="cancelled")
    )
    transfer = Transfer(
        token=secrets.token_urlsafe(16), museum_id=museum.id, from_user_id=from_user.id,
        expires_at=now + timedelta(days=TRANSFER_TTL_DAYS), created_at=now,
    )
    s.add(transfer)
    await s.flush()
    return transfer


async def pending_transfer(s: AsyncSession, museum: Museum) -> Transfer | None:
    return await s.scalar(
        select(Transfer).where(Transfer.museum_id == museum.id, Transfer.status == "pending")
    )


async def get_pending(s: AsyncSession, token: str, now: datetime) -> tuple[Transfer, Museum]:
    transfer = await s.scalar(select(Transfer).where(Transfer.token == token))
    if transfer is None or transfer.status != "pending":
        raise DomainError("transfer_invalid")
    museum = await s.get(Museum, transfer.museum_id)
    # the giver must still own a live museum, otherwise the link is stale
    if museum is None or museum.status == MuseumState.DELETED or museum.owner_id != transfer.from_user_id:
        raise DomainError("transfer_invalid")
    if transfer.expires_at < now:
        raise DomainError("transfer_expired")
    return transfer, museum


async def cancel_transfer(s: AsyncSession, transfer: Transfer, user: User) -> None:
    if transfer.from_user_id != user.id:
        raise DomainError("not_found")
    transfer.status = "cancelled"
    await s.flush()


async def accept_transfer(s: AsyncSession, token: str, user: User, now: datetime) -> Museum:
    transfer, museum = await get_pending(s, token, now)
    if transfer.from_user_id == user.id:
        raise DomainError("transfer_self")
    claimed = await s.execute(
        update(Transfer)
        .where(Transfer.id == transfer.id, Transfer.status == "pending")
        .values(status="accepted", to_user_id=user.id)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:  # someone else accepted it a moment ago
        raise DomainError("transfer_invalid")
    await s.refresh(transfer)
    museum.owner_id = user.id
    museum.updated_at = now
    await audit.log(s, user.id, "transfer_accepted", museum_id=museum.id, from_user=transfer.from_user_id)
    return museum
