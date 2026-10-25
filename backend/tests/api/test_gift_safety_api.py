"""Regression tests for the plan-2 Task 10 review: the gift flow must never delete paid or in-review drafts."""

from sqlalchemy import update

from sahifa.models import Museum, Order
from sahifa.services.settings_store import set_cards
from tests.api.test_museums_api import jpeg_bytes


async def _draft(client, h):
    return (await client.post("/api/museums", json={}, headers=h)).json()


async def test_only_draft_delete_refuses_a_paid_museum(client, auth, sessionmaker, now):
    h = auth(1)
    m = await _draft(client, h)
    async with sessionmaker() as s:
        await s.execute(update(Museum).values(paid_at=now, status="active"))
        await s.commit()
    r = await client.delete(f"/api/museums/{m['id']}?only_draft=1", headers=h)
    assert (r.status_code, r.json()) == (409, {"error": "already_paid"})
    assert (await client.get(f"/api/museums/{m['id']}", headers=h)).status_code == 200


async def test_only_draft_delete_refuses_while_a_receipt_is_in_review(client, auth):
    h = auth(1)
    m = await _draft(client, h)
    order = (await client.post("/api/orders", json={"product": "museum", "museum_id": m["id"], "method": "card"}, headers=h)).json()
    await client.post(f"/api/orders/{order['code']}/receipt", files={"file": ("r.jpg", jpeg_bytes(), "image/jpeg")}, headers=h)
    r = await client.delete(f"/api/museums/{m['id']}?only_draft=1", headers=h)
    assert (r.status_code, r.json()) == (409, {"error": "payment_in_review"})


async def test_only_draft_delete_removes_an_unpaid_draft(client, auth):
    h = auth(1)
    m = await _draft(client, h)
    assert (await client.delete(f"/api/museums/{m['id']}?only_draft=1", headers=h)).status_code == 200


async def test_get_order_includes_cards_for_open_card_orders(client, auth, sessionmaker):
    async with sessionmaker() as s:
        await set_cards(s, [{"number": "8600 0000 0000 0001", "holder": "Ali"}])
        await s.commit()
    h = auth(1)
    m = await _draft(client, h)
    order = (await client.post("/api/orders", json={"product": "museum", "museum_id": m["id"], "method": "card"}, headers=h)).json()
    got = (await client.get(f"/api/orders/{order['code']}", headers=h)).json()
    assert got["cards"] == [{"number": "8600 0000 0000 0001", "holder": "Ali"}]
    assert got["comment"] == order["code"]
    async with sessionmaker() as s:
        await s.execute(update(Order).values(status="paid"))
        await s.commit()
    assert "cards" not in (await client.get(f"/api/orders/{order['code']}", headers=h)).json()
