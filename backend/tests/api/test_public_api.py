from datetime import timedelta

from sqlalchemy import update

from sahifa.models import Museum
from tests.api.test_museums_api import jpeg_bytes


async def _museum_with_photo(client, h) -> dict:
    m = (await client.post("/api/museums", json={}, headers=h)).json()
    await client.post(
        f"/api/museums/{m['id']}/media", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
        data={"caption": "Birinchi kun"}, headers=h,
    )
    await client.patch(f"/api/museums/{m['id']}", json={"recipient_name": "Aziza"}, headers=h)
    return m


async def _set(sessionmaker, museum_id, **values):
    async with sessionmaker() as s:
        await s.execute(update(Museum).where(Museum.id == museum_id).values(**values))
        await s.commit()


async def test_public_view_hides_unopened_and_drafts(client, auth, sessionmaker, now):
    h = auth(1)
    m = await _museum_with_photo(client, h)
    url = f"/api/public/m/{m['slug']}"

    assert (await client.get(url)).status_code == 404  # draft, stranger
    assert (await client.get(url, headers=auth(2))).status_code == 404
    own = (await client.get(url, headers=h)).json()
    assert own["state"] == "draft" and len(own["media"]) == 1  # owner previews for free

    await _set(sessionmaker, m["id"], status="active", paid_at=now, open_at=now + timedelta(days=2),
               expires_at=now + timedelta(days=122))
    locked = (await client.get(url)).json()
    assert locked["state"] == "locked" and locked["recipient_name"] == "Aziza"
    assert "media" not in locked and "voice_url" not in locked

    await _set(sessionmaker, m["id"], open_at=now - timedelta(minutes=1))
    opened = (await client.get(url)).json()
    assert opened["state"] == "open"
    assert opened["media"][0]["caption"] == "Birinchi kun"
    assert "owner_id" not in opened and "id" not in opened

    await _set(sessionmaker, m["id"], expires_at=now - timedelta(seconds=1))
    assert (await client.get(url)).json() == {"state": "expired"}

    await _set(sessionmaker, m["id"], status="deleted")
    assert (await client.get(url)).status_code == 404
    assert (await client.get("/api/public/m/doesnotexist")).status_code == 404


async def test_transfer_accept_via_api(client, auth, settings):
    giver, taker = auth(1), auth(2, "Malika")
    m = (await client.post("/api/museums", json={}, headers=giver)).json()
    r = await client.post(f"/api/museums/{m['id']}/transfer", headers=giver)
    link = r.json()["link"]
    assert link.startswith(f"https://t.me/{settings.bot_username}?start=tr_")
    token = link.split("tr_", 1)[1]

    r = await client.post(f"/api/transfers/{token}/accept", headers=taker)
    assert r.status_code == 200 and r.json()["id"] == m["id"]
    assert (await client.get(f"/api/museums/{m['id']}", headers=giver)).status_code == 404
    assert (await client.get(f"/api/museums/{m['id']}", headers=taker)).status_code == 200


async def test_transfer_cancel_via_api(client, auth):
    giver = auth(1)
    m = (await client.post("/api/museums", json={}, headers=giver)).json()
    token = (await client.post(f"/api/museums/{m['id']}/transfer", headers=giver)).json()["link"].split("tr_", 1)[1]
    assert (await client.delete(f"/api/museums/{m['id']}/transfer", headers=giver)).status_code == 200
    r = await client.post(f"/api/transfers/{token}/accept", headers=auth(2))
    assert (r.status_code, r.json()) == (400, {"error": "transfer_invalid"})
