from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from sahifa.domain.lifecycle import DomainError
from sahifa.models import Order
from sahifa.services.museums import (
    add_media,
    create_museum,
    delete_museum,
    get_owned,
    remove_media,
    update_media,
    update_settings,
)
from sahifa.services.users import grant_free
from tests.factories import make_user, tiny_jpeg


@pytest.fixture
def img(tmp_path) -> Path:
    return tiny_jpeg(tmp_path / "p.jpg")


async def test_create_respects_slots(session, now):
    user = await make_user(session, 1)
    for _ in range(10):
        await create_museum(session, user, now)
    with pytest.raises(DomainError) as err:
        await create_museum(session, user, now)
    assert err.value.code == "slots_full"

    free = await make_user(session, 2)
    await grant_free(session, 2, admin_id=999, days=None, now=now)
    for _ in range(11):
        await create_museum(session, free, now)


async def test_get_owned_hides_foreign_and_deleted(session, now, tmp_path):
    a, b = await make_user(session, 1), await make_user(session, 2)
    m = await create_museum(session, a, now)
    with pytest.raises(DomainError) as err:
        await get_owned(session, b, m.id)
    assert err.value.code == "not_found"
    await delete_museum(session, m, now, media_dir=tmp_path)
    with pytest.raises(DomainError):
        await get_owned(session, a, m.id)


async def test_settings_locked_after_payment(session, now, img, tmp_path):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    await update_settings(session, m, {"title": "Biz", "recipient_name": "Aziza"}, now)
    assert (m.title, m.recipient_name) == ("Biz", "Aziza")

    m.paid_at, m.status = now, "active"
    with pytest.raises(DomainError) as err:
        await update_settings(session, m, {"title": "Boshqa"}, now)
    assert err.value.code == "locked"
    await add_media(session, m, img, "image", "Samarqand", "2021", now, media_dir=tmp_path)


async def test_unknown_setting_rejected(session, now):
    m = await create_museum(session, await make_user(session), now)
    with pytest.raises(DomainError) as err:
        await update_settings(session, m, {"owner_id": 5}, now)
    assert err.value.code == "bad_field"


async def test_media_limit_enforced_and_freed(session, now, tmp_path):
    m = await create_museum(session, await make_user(session), now)
    items = [
        await add_media(session, m, tiny_jpeg(tmp_path / f"{i}.jpg"), "image", None, None, now, media_dir=tmp_path)
        for i in range(30)
    ]
    with pytest.raises(DomainError) as err:
        await add_media(session, m, tiny_jpeg(tmp_path / "x.jpg"), "image", None, None, now, media_dir=tmp_path)
    assert err.value.code == "media_full"

    await remove_media(session, m, items[0].id, media_dir=tmp_path)
    assert not (tmp_path / items[0].path).exists()
    await add_media(session, m, tiny_jpeg(tmp_path / "y.jpg"), "image", None, None, now, media_dir=tmp_path)

    m.extra_rooms = 1
    for i in range(10):
        await add_media(session, m, tiny_jpeg(tmp_path / f"r{i}.jpg"), "image", None, None, now, media_dir=tmp_path)
    with pytest.raises(DomainError):
        await add_media(session, m, tiny_jpeg(tmp_path / "z.jpg"), "image", None, None, now, media_dir=tmp_path)


async def test_video_limit_counted_separately(session, now, tmp_path, monkeypatch):
    async def fake_video(src, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        v, p = out_dir / f"{src.stem}.mp4", out_dir / f"{src.stem}.jpg"
        v.write_bytes(b"v"), p.write_bytes(b"p")
        return v, p

    monkeypatch.setattr("sahifa.services.museums.process_video", fake_video)
    m = await create_museum(session, await make_user(session), now)
    for i in range(5):
        await add_media(session, m, tmp_path / f"v{i}.mp4", "video", None, None, now, media_dir=tmp_path)
    with pytest.raises(DomainError) as err:
        await add_media(session, m, tmp_path / "v9.mp4", "video", None, None, now, media_dir=tmp_path)
    assert err.value.code == "media_full"
    await add_media(session, m, tiny_jpeg(tmp_path / "ok.jpg"), "image", None, None, now, media_dir=tmp_path)


async def test_update_media_fields(session, now, img, tmp_path):
    m = await create_museum(session, await make_user(session), now)
    item = await add_media(session, m, img, "image", None, None, now, media_dir=tmp_path)
    await update_media(session, m, item.id, caption="Toshkent", taken_on="2020-05", position=4)
    assert (item.caption, item.taken_on, item.position) == ("Toshkent", "2020-05", 4)


async def test_open_at_validation(session, now):
    m = await create_museum(session, await make_user(session), now)
    with pytest.raises(DomainError) as err:
        await update_settings(session, m, {"open_at": now + timedelta(days=121)}, now)
    assert err.value.code == "open_at"
    await update_settings(session, m, {"open_at": now + timedelta(days=30)}, now)


async def test_delete_rejects_pending_orders(session, now, tmp_path):
    user = await make_user(session)
    m = await create_museum(session, user, now)
    order = Order(code="ABC234", user_id=user.id, product="museum", museum_id=m.id, method="card")
    session.add(order)
    await session.flush()
    await delete_museum(session, m, now, media_dir=tmp_path)
    assert m.status == "deleted"
    order = await session.scalar(select(Order).where(Order.code == "ABC234"))
    assert (order.status, order.reject_reason) == ("rejected", "museum_deleted")


async def test_expired_museum_not_editable(session, now, img, tmp_path):
    m = await create_museum(session, await make_user(session), now)
    m.status = "expired"
    with pytest.raises(DomainError) as err:
        await add_media(session, m, img, "image", None, None, now, media_dir=tmp_path)
    assert err.value.code == "not_editable"
