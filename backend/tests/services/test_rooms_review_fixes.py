"""Regression tests for the plan-2 Task 2 checkpoint review."""

from datetime import timedelta

import pytest

from sahifa.domain.lifecycle import DomainError
from sahifa.domain.pricing import Product
from sahifa.models import Order
from sahifa.services.museums import create_museum
from sahifa.services.orders import create_order, fulfil
from tests.factories import make_user


async def test_rooms_cannot_be_bought_separately_on_a_draft(session, now):
    user = await make_user(session)
    draft = await create_museum(session, user, now)
    draft.extra_rooms = 2  # imported with rooms: they are paid inside the museum order
    with pytest.raises(DomainError) as err:
        await create_order(session, user, Product.ROOM, draft.id, "card", now)
    assert err.value.code == "bad_order"
    order = await create_order(session, user, Product.MUSEUM, draft.id, "card", now)
    assert order.amount_uzs == 21000


async def test_second_museum_payment_is_refused_not_turned_into_an_extension(session, now):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    first = await create_order(session, user, Product.MUSEUM, m.id, "stars", now)
    await fulfil(session, first, now, charge_id="c1")
    late = Order(code="LATE33", user_id=user.id, product="museum", museum_id=m.id, method="card",
                 status="awaiting_review", amount_uzs=21000)
    session.add(late)
    await session.flush()
    with pytest.raises(DomainError) as err:
        await fulfil(session, late, now, admin_id=999)
    assert err.value.code == "duplicate_payment"
    assert m.expires_at == now + timedelta(days=120)  # not extended


async def test_stars_invoice_label_mentions_rooms(session, now):
    from tests.bot.conftest import FakeBot

    from sahifa.bot.payments import make_stars_invoice_link

    user = await make_user(session)
    m = await create_museum(session, user, now)
    m.extra_rooms = 2
    order = await create_order(session, user, Product.MUSEUM, m.id, "stars", now)
    bot = FakeBot()
    await make_stars_invoice_link(bot, order, rooms=2)
    assert "+2 xona" in bot.invoices[0]["title"]
