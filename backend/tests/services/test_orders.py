from datetime import timedelta

import pytest
from sqlalchemy import func, select

from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import Product
from sahifa.models import AuditLog
from sahifa.services.museums import create_museum, delete_museum, update_settings
from sahifa.services.orders import (
    attach_receipt,
    create_order,
    fulfil,
    get_by_code,
    mark_refunded,
    reject,
)
from sahifa.services.settings_store import set_price
from sahifa.services.users import grant_free
from tests.factories import make_user, tiny_jpeg


async def _paid_museum(session, user, now):
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await fulfil(session, order, now)
    return m


async def test_museum_order_activates(session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    assert (order.status, order.amount_uzs, order.amount_stars) == ("pending", 15000, 75)
    assert len(order.code) == 6
    await fulfil(session, order, now)
    assert (order.status, order.paid_at) == ("paid", now)
    assert (m.status, m.paid_at, m.expires_at) == ("active", now, now + timedelta(days=120))


async def test_museum_with_open_at_runs_from_opening(session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    await update_settings(session, m, {"open_at": now + timedelta(days=10)}, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "stars", now)
    await fulfil(session, order, now, charge_id="tg-1")
    assert m.active_from == now + timedelta(days=10)
    assert m.expires_at == now + timedelta(days=130)
    assert order.charge_id == "tg-1"


async def test_fulfil_is_idempotent(session, now):
    user = await make_user(session)
    m = await _paid_museum(session, user, now)
    order = await create_order(session, user, Product.ROOM, m.id, "stars", now)
    await fulfil(session, order, now)
    await fulfil(session, order, now)
    assert m.extra_rooms == 1
    paid_logs = await session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "order_paid")
    )
    assert paid_logs == 2  # museum order + room order, the repeat is not logged


async def test_room_and_slots_effects(session, now):
    user = await make_user(session)
    m = await _paid_museum(session, user, now)
    room = await create_order(session, user, Product.ROOM, m.id, "card", now)
    assert room.amount_uzs == 3000
    await fulfil(session, room, now)
    slots = await create_order(session, user, Product.SLOTS, None, "card", now)
    assert slots.amount_uzs == 5000
    await fulfil(session, slots, now)
    assert m.extra_rooms == 1
    assert user.extra_slots == 5


async def test_reactivate_extends(session, now):
    user = await make_user(session)
    m = await _paid_museum(session, user, now)
    later = now + timedelta(days=150)
    m.status = "expired"
    order = await create_order(session, user, Product.REACTIVATE, m.id, "card", later)
    await fulfil(session, order, later)
    assert (m.status, m.expires_at) == ("active", later + timedelta(days=120))


async def test_bad_combinations_rejected(session, now):
    user = await make_user(session)
    draft = await create_museum(session, user, now)
    other = await make_user(session, 2)
    cases = [
        (user, Product.REACTIVATE, draft.id),  # never paid
        (user, Product.SLOTS, draft.id),  # slots are not per museum
        (user, Product.MUSEUM, None),
        (other, Product.MUSEUM, draft.id),  # not the owner
    ]
    for who, product, museum_id in cases:
        with pytest.raises(DomainError) as err:
            await create_order(session, who, product, museum_id, "card", now)
        assert err.value.code in ("bad_order", "not_found")


async def test_free_user_order_is_paid_immediately(session, now):
    user = await make_user(session)
    await grant_free(session, user.id, admin_id=999, days=None, now=now)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    assert (order.method, order.status, order.amount_uzs, order.amount_stars) == ("free", "paid", 0, 0)
    assert m.status == "active"


async def test_reuses_open_order(session, now):
    user = await make_user(session)
    m = await _paid_museum(session, user, now)
    first = await create_order(session, user, Product.ROOM, m.id, "card", now)
    again = await create_order(session, user, Product.ROOM, m.id, "card", now)
    assert again.code == first.code


async def test_switching_method_cancels_pending_but_keeps_receipt_under_review(session, now, tmp_path):
    user = await make_user(session)
    m = await _paid_museum(session, user, now)
    card = await create_order(session, user, Product.ROOM, m.id, "card", now)
    stars = await create_order(session, user, Product.ROOM, m.id, "stars", now)
    assert (card.status, stars.status) == ("cancelled", "pending")

    card2 = await create_order(session, user, Product.ROOM, m.id, "card", now)
    await attach_receipt(session, card2, tiny_jpeg(tmp_path / "r.jpg"), now, media_dir=tmp_path)
    again = await create_order(session, user, Product.ROOM, m.id, "stars", now)
    assert again.code == card2.code  # a receipt is being checked: never take a second payment


async def test_fulfil_on_deleted_museum_fails_cleanly(session, now, tmp_path):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await attach_receipt(session, order, tiny_jpeg(tmp_path / "r.jpg"), now, media_dir=tmp_path)
    m.status = "deleted"  # deleted after the receipt was sent
    with pytest.raises(DomainError) as err:
        await fulfil(session, order, now, admin_id=999)
    assert err.value.code == "museum_gone"
    assert (order.status, order.reject_reason) == ("rejected", "museum_gone")


async def test_open_museum_order_is_reused_across_methods(session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    a = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    a.status = "awaiting_review"
    stars = await create_order(session, user, Product.MUSEUM, m.id, "stars", now)
    assert stars.code == a.code


async def test_second_museum_payment_extends_instead_of_wasting(session, now):
    from sahifa.models import Order

    user = await make_user(session)
    m = await _paid_museum(session, user, now)
    # a payment that raced the first one (e.g. Stars paid while the card receipt was approved)
    late = Order(code="LATE22", user_id=user.id, product="museum", museum_id=m.id, method="stars")
    session.add(late)
    await session.flush()
    await fulfil(session, late, now)
    assert m.expires_at == now + timedelta(days=240)


async def test_price_snapshot(session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await set_price(session, Product.MUSEUM, "uzs", 20000)
    assert (await get_by_code(session, order.code)).amount_uzs == 15000


async def test_receipt_reject_and_refund(session, now, tmp_path):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await attach_receipt(session, order, tiny_jpeg(tmp_path / "r.jpg"), now, media_dir=tmp_path)
    assert order.status == "awaiting_review" and (tmp_path / order.receipt_path).exists()
    await reject(session, order, admin_id=999, reason="amount", now=now)
    assert (order.status, order.reject_reason, order.admin_id) == ("rejected", "amount", 999)
    await attach_receipt(session, order, tiny_jpeg(tmp_path / "r2.jpg"), now, media_dir=tmp_path)
    assert order.status == "awaiting_review"

    stars = await create_order(session, user, Product.SLOTS, None, "stars", now)
    with pytest.raises(DomainError):
        await attach_receipt(session, stars, tiny_jpeg(tmp_path / "r3.jpg"), now, media_dir=tmp_path)
    await fulfil(session, stars, now, charge_id="c1")
    await mark_refunded(session, stars, admin_id=999, now=now)
    assert stars.status == "refunded"


async def test_unknown_code(session):
    with pytest.raises(DomainError) as err:
        await get_by_code(session, "NOPE22")
    assert err.value.code == "not_found"


async def test_deleted_museum_rejects_waiting_order(session, now, tmp_path):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await delete_museum(session, m, now, media_dir=tmp_path)
    await session.refresh(order)
    assert order.status == "rejected"
