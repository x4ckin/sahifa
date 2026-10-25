"""Regression tests for the Task 5 checkpoint review findings."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import Product
from sahifa.models import Museum, Order
from sahifa.services.museums import create_museum, delete_museum, update_settings
from sahifa.services.orders import attach_receipt, create_order, fulfil, mark_refunded
from sahifa.services.users import grant_free
from tests.factories import make_user, tiny_jpeg


async def test_receipt_for_deleted_museum_is_refused(session, now, tmp_path):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await delete_museum(session, m, now, media_dir=tmp_path)
    with pytest.raises(DomainError) as err:
        await attach_receipt(session, order, tiny_jpeg(tmp_path / "r.jpg"), now, receipts_dir=tmp_path / "rc")
    assert err.value.code == "museum_gone"


async def test_delete_keeps_receipts_under_review_for_admin(session, now, tmp_path):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await attach_receipt(session, order, tiny_jpeg(tmp_path / "r.jpg"), now, receipts_dir=tmp_path / "rc")
    await delete_museum(session, m, now, media_dir=tmp_path)
    assert order.status == "awaiting_review"  # money was sent: the admin must see it and refund


async def test_free_user_cannot_stack_reactivations_or_slots(session, now):
    user = await make_user(session)
    await grant_free(session, user.id, admin_id=999, days=1, now=now)
    m = await create_museum(session, user, now)
    await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    for _ in range(5):
        await create_order(session, user, Product.REACTIVATE, m.id, "card", now)
    assert m.expires_at == now + timedelta(days=120)
    with pytest.raises(DomainError) as err:
        await create_order(session, user, Product.SLOTS, None, "card", now)
    assert err.value.code == "not_needed"
    assert user.extra_slots == 0


async def test_free_status_wins_over_an_old_open_order(session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    old = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await grant_free(session, user.id, admin_id=999, days=None, now=now)
    new = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    assert (new.method, new.status, old.status) == ("free", "paid", "cancelled")
    assert m.status == "active"


async def test_second_charge_on_paid_order_is_reported(session, now):
    user = await make_user(session)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    await fulfil(session, order, now, charge_id="c1")
    await fulfil(session, order, now, charge_id="c1")  # same update delivered twice: fine
    with pytest.raises(DomainError) as err:
        await fulfil(session, order, now, charge_id="c2")
    assert err.value.code == "duplicate_payment"
    assert user.extra_slots == 5


async def test_payment_on_refunded_order_grants_nothing(session, now):
    user = await make_user(session)
    order = await create_order(session, user, Product.SLOTS, None, "stars", now)
    await fulfil(session, order, now, charge_id="c1")
    await mark_refunded(session, order, admin_id=999, now=now)
    with pytest.raises(DomainError) as err:
        await fulfil(session, order, now, charge_id="c9")
    assert err.value.code == "duplicate_payment"
    assert user.extra_slots == 5


async def test_unchanged_locked_values_can_be_resent(session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    await update_settings(session, m, {"title": "Biz", "recipient_name": "Aziza"}, now)
    m.paid_at, m.status = now, "active"
    await update_settings(session, m, {"title": "Biz", "recipient_name": "Aziza"}, now)
    with pytest.raises(DomainError):
        await update_settings(session, m, {"title": "Biz", "recipient_name": "Malika"}, now)


async def test_naive_open_at_is_a_domain_error(session, now):
    m = await create_museum(session, await make_user(session), now)
    with pytest.raises(DomainError) as err:
        await update_settings(session, m, {"open_at": now.replace(tzinfo=None) + timedelta(days=3)}, now)
    assert err.value.code == "open_at"


async def test_activation_survives_commit_and_reload(sessionmaker, session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    await update_settings(session, m, {"open_at": now + timedelta(days=5)}, now)
    order = await create_order(session, user, Product.MUSEUM, m.id, "card", now)
    await session.commit()
    async with sessionmaker() as fresh:
        order = await fresh.scalar(select(Order).where(Order.id == order.id))
        await fulfil(fresh, order, now)
        await fresh.commit()
    async with sessionmaker() as again:
        m = await again.get(Museum, m.id)
        assert m.expires_at == now + timedelta(days=125)
        assert m.open_at.tzinfo is not None
