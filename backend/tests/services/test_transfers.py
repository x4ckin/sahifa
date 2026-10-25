from datetime import timedelta

import pytest

from sahifa.domain.lifecycle import DomainError
from sahifa.services.museums import create_museum
from sahifa.services.transfers import accept_transfer, cancel_transfer, create_transfer
from sahifa.services.users import slots_status
from tests.factories import make_user


async def test_accept_moves_owner_and_keeps_slug(session, now):
    admin, client = await make_user(session, 1), await make_user(session, 2)
    m = await create_museum(session, admin, now)
    slug = m.slug
    t = await create_transfer(session, m, admin, now)
    assert t.expires_at == now + timedelta(days=7)
    moved = await accept_transfer(session, t.token, client, now + timedelta(days=1))
    assert (moved.owner_id, moved.created_by_id, moved.slug) == (2, 1, slug)
    assert t.status == "accepted" and t.to_user_id == 2
    with pytest.raises(DomainError) as err:
        await accept_transfer(session, t.token, await make_user(session, 3), now)
    assert err.value.code == "transfer_invalid"


async def test_expired_and_self_rejected(session, now):
    a, b = await make_user(session, 1), await make_user(session, 2)
    m = await create_museum(session, a, now)
    t = await create_transfer(session, m, a, now)
    with pytest.raises(DomainError) as err:
        await accept_transfer(session, t.token, a, now)
    assert err.value.code == "transfer_self"
    with pytest.raises(DomainError) as err:
        await accept_transfer(session, t.token, b, now + timedelta(days=7, seconds=1))
    assert err.value.code == "transfer_expired"
    with pytest.raises(DomainError) as err:
        await accept_transfer(session, "nope", b, now)
    assert err.value.code == "transfer_invalid"


async def test_new_transfer_cancels_previous(session, now):
    a, b = await make_user(session, 1), await make_user(session, 2)
    m = await create_museum(session, a, now)
    first = await create_transfer(session, m, a, now)
    second = await create_transfer(session, m, a, now)
    assert first.status == "cancelled"
    with pytest.raises(DomainError):
        await accept_transfer(session, first.token, b, now)
    await cancel_transfer(session, second, a)
    with pytest.raises(DomainError):
        await accept_transfer(session, second.token, b, now)


async def test_only_owner_can_cancel(session, now):
    a, b = await make_user(session, 1), await make_user(session, 2)
    t = await create_transfer(session, await create_museum(session, a, now), a, now)
    with pytest.raises(DomainError) as err:
        await cancel_transfer(session, t, b)
    assert err.value.code == "not_found"


async def test_old_owner_link_dies_after_handover(session, now):
    a, b, c = await make_user(session, 1), await make_user(session, 2), await make_user(session, 3)
    m = await create_museum(session, a, now)
    t = await create_transfer(session, m, a, now)
    await accept_transfer(session, t.token, b, now)
    with pytest.raises(DomainError):
        await create_transfer(session, m, a, now)  # a no longer owns it
    t2 = await create_transfer(session, m, b, now)
    assert (await accept_transfer(session, t2.token, c, now)).owner_id == 3


async def test_transferred_museum_not_counted_in_new_owner_slots(session, now):
    a, b = await make_user(session, 1), await make_user(session, 2)
    m = await create_museum(session, a, now)
    await accept_transfer(session, (await create_transfer(session, m, a, now)).token, b, now)
    assert await slots_status(session, b, now) == (0, 10)
    assert await slots_status(session, a, now) == (0, 10)
