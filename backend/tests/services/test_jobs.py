from datetime import timedelta

from sahifa.domain.pricing import Product
from sahifa.models import Museum, Order
from sahifa.services.jobs import run_daily
from sahifa.services.museums import add_media, create_museum
from sahifa.services.orders import attach_receipt, create_order
from tests.factories import make_user, tiny_jpeg


class Inbox:
    def __init__(self, fail_for: set[int] = frozenset()):
        self.messages: list[tuple[int, str]] = []
        self.fail_for = fail_for

    async def __call__(self, chat_id: int, text: str) -> None:
        if chat_id in self.fail_for:
            raise RuntimeError("blocked")
        self.messages.append((chat_id, text))


async def test_daily_deletes_stale_drafts_but_keeps_paid_or_reviewed(session, now, tmp_path):
    user = await make_user(session, 1)
    stale = await create_museum(session, user, now - timedelta(days=8))
    await add_media(session, stale, tiny_jpeg(tmp_path / "a.jpg"), "image", None, None, now - timedelta(days=8), media_dir=tmp_path)
    fresh = await create_museum(session, user, now - timedelta(days=2))
    with_receipt = await create_museum(session, user, now - timedelta(days=9))
    order = await create_order(session, user, Product.MUSEUM, with_receipt.id, "card", now - timedelta(days=9))
    await attach_receipt(session, order, tiny_jpeg(tmp_path / "r.jpg"), now - timedelta(days=9), receipts_dir=tmp_path / "rc")
    with_room = await create_museum(session, user, now - timedelta(days=9))
    session.add(Order(code="ROOM22", user_id=user.id, product="room", museum_id=with_room.id,
                      method="card", status="paid"))  # e.g. a room paid before drafts lost room sales
    for m in (stale, with_receipt, with_room):
        m.updated_at = now - timedelta(days=8)

    report = await run_daily(session, now, Inbox(), media_dir=tmp_path)
    assert report["drafts_deleted"] == 1
    assert (stale.status, fresh.status, with_receipt.status, with_room.status) == ("deleted", "draft", "draft", "draft")
    assert not any((tmp_path / str(stale.id)).glob("*"))


def _active(user, now, days_left) -> Museum:
    return Museum(
        owner_id=user.id, created_by_id=user.id, status="active", title="Onam",
        paid_at=now - timedelta(days=100), expires_at=now + timedelta(days=days_left),
    )


async def test_daily_expires_and_reminds_once(session, now, tmp_path):
    user = await make_user(session, 1)
    m = _active(user, now, 6.5)
    gone = _active(user, now, -0.1)
    session.add_all([m, gone])
    await session.flush()
    inbox = Inbox()

    first = await run_daily(session, now, inbox, media_dir=tmp_path)
    assert (first["reminded"], first["expired"]) == (1, 1)
    assert gone.status == "expired"
    assert "7 kun" in inbox.messages[0][1] and "Onam" in inbox.messages[0][1]

    again = await run_daily(session, now + timedelta(hours=12), inbox, media_dir=tmp_path)
    assert again["reminded"] == 0

    last_day = await run_daily(session, now + timedelta(days=5.8), inbox, media_dir=tmp_path)
    assert last_day["reminded"] == 1 and "1 kun" in inbox.messages[-1][1]
    assert len(inbox.messages) == 2


async def test_late_first_reminder_sends_only_the_closest(session, now, tmp_path):
    user = await make_user(session, 1)
    session.add(_active(user, now, 0.5))
    await session.flush()
    inbox = Inbox()
    await run_daily(session, now, inbox, media_dir=tmp_path)
    await run_daily(session, now + timedelta(hours=1), inbox, media_dir=tmp_path)
    assert [t for _, t in inbox.messages] == [inbox.messages[0][1]] and "1 kun" in inbox.messages[0][1]


async def test_blocked_owner_does_not_stop_the_job(session, now, tmp_path):
    a, b = await make_user(session, 1), await make_user(session, 2)
    session.add_all([_active(a, now, 3), _active(b, now, 3)])
    await session.flush()
    inbox = Inbox(fail_for={1})
    report = await run_daily(session, now, inbox, media_dir=tmp_path)
    assert report["reminded"] == 1 and inbox.messages[0][0] == 2


async def test_daily_purges_after_retention(session, now, tmp_path):
    user = await make_user(session, 1)
    old = _active(user, now, -31)
    old.status = "expired"
    recent = _active(user, now, -29)
    recent.status = "expired"
    session.add_all([old, recent])
    await session.flush()
    report = await run_daily(session, now, Inbox(), media_dir=tmp_path)
    assert report["purged"] == 1
    assert (old.status, recent.status) == ("deleted", "expired")
