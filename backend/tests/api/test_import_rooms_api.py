import pytest

from sahifa.domain.lifecycle import DomainError, rooms_needed
from tests.api.test_tgmedia_api import _upload


@pytest.mark.parametrize(
    ("images", "videos", "rooms"),
    [(30, 5, 0), (0, 0, 0), (31, 5, 1), (40, 7, 1), (41, 5, 2), (30, 8, 2), (130, 25, 10)],
)
def test_rooms_needed_formula(images, videos, rooms):
    assert rooms_needed(images, videos) == rooms


@pytest.mark.parametrize(("images", "videos"), [(131, 0), (0, 26)])
def test_rooms_over_ten_rejected(images, videos):
    with pytest.raises(DomainError) as err:
        rooms_needed(images, videos)
    assert err.value.code == "media_full"


async def test_import_45_photos_creates_two_rooms(client, auth):
    token = (await _upload(client, auth(7))).json()["token"]
    r = await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": token}] * 45}, headers=auth(7))
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["limits"]["images"] == 50 and m["rooms"] == 5
    assert len(m["media"]) == 45


async def test_bundled_museum_order_amount(client, auth):
    token = (await _upload(client, auth(7))).json()["token"]
    m = (await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": token}] * 45}, headers=auth(7))).json()
    order = (await client.post("/api/orders", json={"product": "museum", "museum_id": m["id"], "method": "card"}, headers=auth(7))).json()
    assert (order["amount_uzs"], order["amount_stars"]) == (21000, 105)


async def test_import_over_10_rooms_rejected_before_fetch(client, auth, hooks):
    token = (await _upload(client, auth(7))).json()["token"]
    hooks.fetches = 0
    r = await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": token}] * 131}, headers=auth(7))
    assert (r.status_code, r.json()) == (409, {"error": "media_full"})
    assert hooks.fetches == 0
