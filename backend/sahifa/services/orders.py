import asyncio
import secrets
from datetime import datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select, update
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
CLAIMABLE = (*OPEN_STATUSES, "reviewing")  # states a payment may complete

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
    free = is_free_now(user, now)
    if free and product == Product.SLOTS:
        raise DomainError("not_needed")  # free users have no museum limit

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
    for order in [] if free else open_orders:
        # a receipt under review, or the same method again: never open a second payment
        if order.status == "awaiting_review" or order.method == method:
            return order
    for order in open_orders:
        order.status = "cancelled"

    order = Order(
        code=await _new_code(s), user_id=user.id, product=product, museum_id=museum_id,
        method=method, created_at=now,
    )
    if free:
        order.method = "free"
        s.add(order)
        await s.flush()
        return await fulfil(s, order, now)

    order.amount_uzs = await get_price(s, product, "uzs")
    order.amount_stars = await get_price(s, product, "stars")
    if product == Product.MUSEUM:  # rooms a big museum was imported with are paid in the same order
        rooms = (await s.get(Museum, museum_id)).extra_rooms
        order.amount_uzs += rooms * await get_price(s, Product.ROOM, "uzs")
        order.amount_stars += rooms * await get_price(s, Product.ROOM, "stars")
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
    if charge_id and charge_id == order.charge_id:
        return order  # Telegram delivered the same payment again
    if order.status not in CLAIMABLE:
        if order.status == "paid" and charge_id is None:
            return order  # e.g. an admin tapping "approve" twice
        return await _duplicate(s, order, charge_id)

    museum = None
    if Product(order.product) != Product.SLOTS:
        museum = await s.get(Museum, order.museum_id)
        if museum is None or museum.status == MuseumState.DELETED:
            order.status, order.reject_reason, order.admin_id = "rejected", "museum_gone", admin_id
            await s.flush()
            raise DomainError("museum_gone")

    # claim the order atomically: of two concurrent payments only one moves it out of CLAIMABLE
    claimed = await s.execute(
        update(Order)
        .where(Order.id == order.id, Order.status.in_(CLAIMABLE))
        .values(status="paid", paid_at=now, charge_id=charge_id, admin_id=admin_id)
        .execution_options(synchronize_session=False)
    )
    await s.refresh(order)
    if claimed.rowcount != 1:
        if (charge_id and order.charge_id == charge_id) or (order.status == "paid" and charge_id is None):
            return order
        return await _duplicate(s, order, charge_id)

    await _grant(s, order, museum, now)
    await audit.log(s, admin_id or order.user_id, "order_paid", code=order.code, product=order.product)
    return order


async def _duplicate(s: AsyncSession, order: Order, charge_id: str | None) -> Order:
    """A second, different charge for one order: grant nothing, the caller refunds it."""
    await audit.log(s, order.user_id, "duplicate_payment", code=order.code, charge_id=charge_id)
    raise DomainError("duplicate_payment")


async def _grant(s: AsyncSession, order: Order, museum: Museum | None, now: datetime) -> None:
    product = Product(order.product)
    if product == Product.SLOTS:
        user = await s.get(User, order.user_id)
        await s.execute(
            update(User).where(User.id == user.id).values(extra_slots=User.extra_slots + SLOT_PACK)
            .execution_options(synchronize_session=False)
        )
        await s.refresh(user)
        return
    await s.refresh(museum)  # we hold the write lock now: read the latest state
    if product == Product.ROOM:
        await s.execute(
            update(Museum).where(Museum.id == museum.id).values(extra_rooms=Museum.extra_rooms + 1)
            .execution_options(synchronize_session=False)
        )
        await s.refresh(museum)
    elif product == Product.MUSEUM and museum.paid_at is None:
        open_at = museum.open_at if museum.open_at and museum.open_at > now else None
        museum.active_from, museum.expires_at = activation_window(now, open_at)
        museum.paid_at, museum.status = now, MuseumState.ACTIVE
    elif order.method == "free":  # free users renew to now+120d, never stack
        museum.expires_at = max(museum.expires_at or now, activation_window(now, None)[1])
        museum.status = MuseumState.ACTIVE
    else:  # REACTIVATE, or a museum payment that raced an earlier one: extend
        museum.expires_at = reactivated_expiry(now, museum.expires_at)
        museum.status = MuseumState.ACTIVE
    museum.updated_at = now
    await s.flush()


async def attach_receipt(
    s: AsyncSession, order: Order, src: Path, now: datetime, receipts_dir: Path
) -> Order:
    """Receipts hold card/bank details: keep them in `receipts_dir`, never under public media."""
    # "cancelled": the user opened Stars after already transferring money — the receipt still counts
    if order.method != "card" or order.status not in ("pending", "rejected", "cancelled"):
        raise DomainError("bad_order")
    if order.museum_id is not None:
        museum = await s.get(Museum, order.museum_id)
        if museum is None or museum.status == MuseumState.DELETED:
            raise DomainError("museum_gone")
    main, thumb = await asyncio.to_thread(process_image, src, receipts_dir)
    thumb.unlink(missing_ok=True)
    if order.receipt_path:
        (receipts_dir / order.receipt_path).unlink(missing_ok=True)
    order.receipt_path = main.name
    order.status, order.reject_reason = "awaiting_review", None
    await s.flush()
    return order


async def claim_for_review(s: AsyncSession, order: Order) -> bool:
    """Atomically take a card receipt for review; False if another tap/admin got it first."""
    claimed = await s.execute(
        update(Order)
        .where(Order.id == order.id, Order.method == "card", Order.status == "awaiting_review")
        .values(status="reviewing")
        .execution_options(synchronize_session=False)
    )
    await s.refresh(order)
    return claimed.rowcount == 1


async def reject(s: AsyncSession, order: Order, admin_id: int, reason: str, now: datetime) -> Order:
    if order.status not in CLAIMABLE:
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
