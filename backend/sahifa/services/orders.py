import secrets
from datetime import datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.domain.lifecycle import DomainError, MuseumState, activation_window, reactivated_expiry
from sahifa.domain.pricing import SLOT_PACK, Product
from sahifa.models import Museum, Order, User
from sahifa.services import audit
from sahifa.services.media import process_image
from sahifa.services.settings_store import get_price
from sahifa.services.users import is_free_now

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I — read aloud from a receipt
OPEN_STATUSES = ("pending", "awaiting_review")

# which museum states each product may be bought for
_MUSEUM_STATES: dict[Product, set[str]] = {
    Product.MUSEUM: {MuseumState.DRAFT},
    Product.ROOM: {MuseumState.DRAFT, MuseumState.ACTIVE},
    Product.REACTIVATE: {MuseumState.ACTIVE, MuseumState.EXPIRED},
}


async def _new_code(s: AsyncSession) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if await s.scalar(select(Order.id).where(Order.code == code)) is None:
            return code


async def _check_target(s: AsyncSession, user: User, product: Product, museum_id: int | None) -> None:
    if product == Product.SLOTS:
        if museum_id is not None:
            raise DomainError("bad_order")
        return
    if museum_id is None:
        raise DomainError("bad_order")
    museum = await s.get(Museum, museum_id)
    if museum is None or museum.owner_id != user.id or museum.status == MuseumState.DELETED:
        raise DomainError("not_found")
    if museum.status not in _MUSEUM_STATES[product]:
        raise DomainError("bad_order")
    if product == Product.REACTIVATE and museum.paid_at is None:
        raise DomainError("bad_order")


async def create_order(
    s: AsyncSession,
    user: User,
    product: Product,
    museum_id: int | None,
    method: Literal["stars", "card"],
    now: datetime,
) -> Order:
    product = Product(product)
    if method not in ("stars", "card"):
        raise DomainError("bad_order")
    await _check_target(s, user, product, museum_id)

    open_orders = (
        await s.scalars(
            select(Order).where(
                Order.user_id == user.id,
                Order.product == product,
                Order.museum_id.is_(None) if museum_id is None else Order.museum_id == museum_id,
                Order.status.in_(OPEN_STATUSES),
            )
        )
    ).all()
    for order in open_orders:
        # a receipt under review, or the same method again: never open a second payment
        if order.status == "awaiting_review" or order.method == method:
            return order
    for order in open_orders:
        order.status = "cancelled"

    order = Order(
        code=await _new_code(s), user_id=user.id, product=product, museum_id=museum_id,
        method=method, created_at=now,
    )
    if is_free_now(user, now):
        order.method = "free"
        s.add(order)
        await s.flush()
        return await fulfil(s, order, now)

    order.amount_uzs = await get_price(s, product, "uzs")
    order.amount_stars = await get_price(s, product, "stars")
    s.add(order)
    await s.flush()
    return order


async def get_by_code(s: AsyncSession, code: str) -> Order:
    order = await s.scalar(select(Order).where(Order.code == code.strip().upper()))
    if order is None:
        raise DomainError("not_found")
    return order


async def fulfil(
    s: AsyncSession,
    order: Order,
    now: datetime,
    charge_id: str | None = None,
    admin_id: int | None = None,
) -> Order:
    """Grant what the order bought. Safe to call again: a paid order is returned unchanged.

    If the museum is gone the order is marked rejected (flushed) and DomainError("museum_gone")
    is raised — callers commit before reporting it.
    """
    if order.status == "paid":
        return order
    product = Product(order.product)

    if product == Product.SLOTS:
        user = await s.get(User, order.user_id)
        user.extra_slots += SLOT_PACK
    else:
        museum = await s.get(Museum, order.museum_id)
        if museum is None or museum.status == MuseumState.DELETED:
            order.status, order.reject_reason, order.admin_id = "rejected", "museum_gone", admin_id
            await s.flush()
            raise DomainError("museum_gone")
        if product == Product.ROOM:
            museum.extra_rooms += 1
        elif product == Product.MUSEUM and museum.paid_at is None:
            open_at = museum.open_at if museum.open_at and museum.open_at > now else None
            museum.active_from, museum.expires_at = activation_window(now, open_at)
            museum.paid_at, museum.status = now, MuseumState.ACTIVE
        else:  # REACTIVATE, or a museum payment that raced an earlier one: extend
            museum.expires_at = reactivated_expiry(now, museum.expires_at)
            museum.status = MuseumState.ACTIVE
        museum.updated_at = now

    order.status, order.paid_at = "paid", now
    order.charge_id = charge_id or order.charge_id
    order.admin_id = admin_id or order.admin_id
    await audit.log(s, admin_id or order.user_id, "order_paid", code=order.code, product=product)
    return order


async def attach_receipt(
    s: AsyncSession, order: Order, src: Path, now: datetime, media_dir: Path
) -> Order:
    if order.method != "card" or order.status not in ("pending", "rejected"):
        raise DomainError("bad_order")
    if order.reject_reason == "museum_gone":
        raise DomainError("museum_gone")
    main, thumb = process_image(src, media_dir / "receipts")
    thumb.unlink(missing_ok=True)
    if order.receipt_path:
        (media_dir / order.receipt_path).unlink(missing_ok=True)
    order.receipt_path = main.relative_to(media_dir).as_posix()
    order.status, order.reject_reason = "awaiting_review", None
    await s.flush()
    return order


async def reject(s: AsyncSession, order: Order, admin_id: int, reason: str, now: datetime) -> Order:
    if order.status not in OPEN_STATUSES:
        raise DomainError("bad_order")
    order.status, order.reject_reason, order.admin_id = "rejected", reason, admin_id
    await audit.log(s, admin_id, "order_rejected", code=order.code, reason=reason)
    return order


async def mark_refunded(s: AsyncSession, order: Order, admin_id: int, now: datetime) -> Order:
    if order.status != "paid" or order.method != "stars":
        raise DomainError("bad_order")
    order.status, order.admin_id = "refunded", admin_id
    await audit.log(s, admin_id, "order_refunded", code=order.code)
    return order
