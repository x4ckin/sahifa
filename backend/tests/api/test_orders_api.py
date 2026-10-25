from sqlalchemy import update

from sahifa.models import User
from sahifa.services.settings_store import set_cards
from tests.api.test_museums_api import jpeg_bytes


async def _museum(client, h) -> dict:
    return (await client.post("/api/museums", json={}, headers=h)).json()


async def test_card_order_flow(client, auth, hooks, sessionmaker):
    async with sessionmaker() as s:
        await set_cards(s, [{"number": "8600 0000 0000 0001", "holder": "Ali V."}])
        await s.commit()
    h = auth(1)
    m = await _museum(client, h)
    r = await client.post("/api/orders", json={"product": "museum", "museum_id": m["id"], "method": "card"}, headers=h)
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["status"] == "pending" and order["amount_uzs"] == 15000
    assert order["cards"] == [{"number": "8600 0000 0000 0001", "holder": "Ali V."}]
    assert order["comment"] == order["code"]

    r = await client.post(
        f"/api/orders/{order['code']}/receipt", files={"file": ("r.jpg", jpeg_bytes(), "image/jpeg")}, headers=h
    )
    assert r.json()["status"] == "awaiting_review"
    assert hooks.receipts == [order["code"]]
    got = (await client.get(f"/api/orders/{order['code']}", headers=h)).json()
    assert got["status"] == "awaiting_review"


async def test_orders_are_private(client, auth):
    h = auth(1)
    m = await _museum(client, h)
    order = (await client.post("/api/orders", json={"product": "museum", "museum_id": m["id"], "method": "card"}, headers=h)).json()
    other = auth(2)
    assert (await client.get(f"/api/orders/{order['code']}", headers=other)).status_code == 404
    r = await client.post(
        f"/api/orders/{order['code']}/receipt", files={"file": ("r.jpg", jpeg_bytes(), "image/jpeg")}, headers=other
    )
    assert r.status_code == 404


async def test_stars_order_returns_invoice_link(client, auth):
    h = auth(1)
    r = await client.post("/api/orders", json={"product": "slots", "method": "stars"}, headers=h)
    body = r.json()
    assert body["invoice_link"] == f"https://t.me/$invoice-{body['code']}"
    assert body["amount_stars"] == 25


async def test_free_user_order_paid(client, auth, sessionmaker):
    h = auth(1)
    m = await _museum(client, h)
    async with sessionmaker() as s:
        await s.execute(update(User).where(User.id == 1).values(is_free=True))
        await s.commit()
    r = await client.post("/api/orders", json={"product": "museum", "museum_id": m["id"], "method": "stars"}, headers=h)
    assert (r.json()["status"], r.json()["method"]) == ("paid", "free")
    assert "invoice_link" not in r.json()


async def test_bad_product_is_400(client, auth):
    r = await client.post("/api/orders", json={"product": "gold", "method": "card"}, headers=auth(1))
    assert r.status_code == 400
