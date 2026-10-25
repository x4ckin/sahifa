from datetime import timedelta

from sqlalchemy import func, select

from sahifa.models import AuditLog, Museum, User
from sahifa.services.users import (
    grant_free,
    is_free_now,
    list_free,
    revoke_free,
    slots_status,
    upsert_user,
)


async def test_upsert_creates_then_updates_username(session):
    await upsert_user(session, {"id": 5, "username": "old", "first_name": "Ali"})
    user = await upsert_user(
        session, {"id": 5, "username": "new", "first_name": "Ali", "language_code": "ru"}
    )
    assert user.username == "new"
    assert user.lang == "ru"
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_free_status_with_expiry(session, now):
    user = await upsert_user(session, {"id": 7, "first_name": "Vali"})
    await grant_free(session, 7, admin_id=999, days=30, now=now)
    assert is_free_now(user, now + timedelta(days=29))
    assert not is_free_now(user, now + timedelta(days=31))

    await grant_free(session, 7, admin_id=999, days=None, now=now)
    assert is_free_now(user, now + timedelta(days=3650))
    assert [u.id for u in await list_free(session)] == [7]

    await revoke_free(session, 7, admin_id=999)
    assert not is_free_now(user, now)
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert actions == ["grant_free", "grant_free", "revoke_free"]


def _museum(owner: int, creator: int, status: str = "draft") -> Museum:
    return Museum(owner_id=owner, created_by_id=creator, status=status)


async def test_slots_ignore_transferred_and_deleted(session, now):
    user = await upsert_user(session, {"id": 1, "first_name": "A"})
    await upsert_user(session, {"id": 2, "first_name": "B"})
    session.add_all(
        [
            _museum(1, 1),
            _museum(1, 1, "active"),
            _museum(1, 1, "deleted"),
            _museum(1, 2, "active"),  # handed over by user 2
        ]
    )
    await session.flush()
    assert await slots_status(session, user, now) == (2, 10)

    user.extra_slots = 5
    assert await slots_status(session, user, now) == (2, 15)

    await grant_free(session, 1, admin_id=999, days=None, now=now)
    assert await slots_status(session, user, now) == (2, None)
