import io

from PIL import Image
from sqlalchemy import update

from sahifa.models import Museum


def jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (1, 2, 3)).save(buf, "JPEG")
    return buf.getvalue()


async def _create(client, headers) -> dict:
    r = await client.post("/api/museums", json={"template": "birthday"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_create_list_get_museum(client, auth):
    h = auth(1)
    created = await _create(client, h)
    assert created["status"] == "draft" and created["template"] == "birthday"
    listed = (await client.get("/api/museums", headers=h)).json()
    assert [m["id"] for m in listed] == [created["id"]]
    full = (await client.get(f"/api/museums/{created['id']}", headers=h)).json()
    assert full["limits"] == {"rooms": 3, "images": 30, "videos": 5}
    assert full["locked"] is False and full["media"] == []
    assert len(full["slug"]) >= 12


async def test_other_users_museum_is_404(client, auth):
    m = await _create(client, auth(1))
    assert (await client.get(f"/api/museums/{m['id']}", headers=auth(2))).status_code == 404
    assert (await client.delete(f"/api/museums/{m['id']}", headers=auth(2))).status_code == 404


async def test_patch_settings_and_locked_returns_409(client, auth, sessionmaker, now):
    h = auth(1)
    m = await _create(client, h)
    r = await client.patch(
        f"/api/museums/{m['id']}",
        json={"title": "Bizning yo'l", "open_at": (now.replace(day=20)).isoformat()},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["title"] == "Bizning yo'l"
    bad = await client.patch(f"/api/museums/{m['id']}", json={"slug": "x"}, headers=h)
    assert (bad.status_code, bad.json()) == (400, {"error": "bad_field"})

    async with sessionmaker() as s:
        await s.execute(update(Museum).values(paid_at=now, status="active"))
        await s.commit()
    r = await client.patch(f"/api/museums/{m['id']}", json={"title": "Boshqa"}, headers=h)
    assert (r.status_code, r.json()) == (409, {"error": "locked"})


async def test_upload_edit_remove_media(client, auth, settings):
    h = auth(1)
    m = await _create(client, h)
    r = await client.post(
        f"/api/museums/{m['id']}/media",
        files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
        data={"caption": "Samarqand", "taken_on": "2021"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["kind"] == "image" and item["caption"] == "Samarqand"
    assert item["url"].startswith("https://api.test/media/")
    served = await client.get(item["url"].removeprefix("https://api.test"))
    assert served.status_code == 200

    r = await client.patch(f"/api/museums/{m['id']}/media/{item['id']}", json={"position": 9}, headers=h)
    assert r.json()["position"] == 9
    assert (await client.delete(f"/api/museums/{m['id']}/media/{item['id']}", headers=h)).status_code == 200
    assert (await client.get(f"/api/museums/{m['id']}", headers=h)).json()["media"] == []


async def test_upload_rejects_unknown_type(client, auth):
    h = auth(1)
    m = await _create(client, h)
    r = await client.post(
        f"/api/museums/{m['id']}/media", files={"file": ("a.pdf", b"%PDF", "application/pdf")}, headers=h
    )
    assert (r.status_code, r.json()) == (400, {"error": "bad_format"})


async def test_upload_over_limit_returns_409(client, auth, sessionmaker):
    h = auth(1)
    m = await _create(client, h)
    from sahifa.models import MediaItem

    async with sessionmaker() as s:
        s.add_all(
            MediaItem(museum_id=m["id"], kind="image", path=f"x{i}.webp", thumb_path=f"t{i}.webp")
            for i in range(30)
        )
        await s.commit()
    r = await client.post(
        f"/api/museums/{m['id']}/media", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")}, headers=h
    )
    assert (r.status_code, r.json()) == (409, {"error": "media_full"})


async def test_slots_full_returns_409(client, auth):
    h = auth(1)
    for _ in range(10):
        await _create(client, h)
    r = await client.post("/api/museums", json={}, headers=h)
    assert (r.status_code, r.json()) == (409, {"error": "slots_full"})


async def test_receipts_are_not_public(client, settings):
    receipts = settings.media_dir.parent / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "r.webp").write_bytes(b"secret")
    assert (await client.get("/media/../receipts/r.webp")).status_code == 404
    assert (await client.get("/receipts/r.webp")).status_code == 404
