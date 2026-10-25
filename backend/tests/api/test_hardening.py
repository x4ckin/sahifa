"""Regression tests for the Task 7 checkpoint review (API input handling)."""

from httpx import ASGITransport, AsyncClient

from sahifa.api.app import create_app
from tests.api.test_museums_api import jpeg_bytes


async def _museum(client, h) -> dict:
    return (await client.post("/api/museums", json={}, headers=h)).json()


async def test_oversized_body_rejected_before_parsing(settings, sessionmaker, hooks, now, auth):
    app = create_app(
        settings, sessionmaker, invoice_link_factory=hooks.invoice_link,
        receipt_notifier=hooks.notify_receipt, clock=lambda: now, max_body_bytes=1000,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://api.test") as c:
        r = await c.post("/api/museums/1/media", files={"file": ("a.jpg", b"x" * 5000, "image/jpeg")})
        assert (r.status_code, r.json()) == (413, {"error": "too_large"})
        ok = await c.post("/api/museums", json={}, headers=auth(1))
        assert ok.status_code == 200


async def test_settings_values_are_validated(client, auth):
    h = auth(1)
    m = await _museum(client, h)
    url = f"/api/museums/{m['id']}"
    for bad in (
        {"title": "x" * 81},
        {"letter_text": "x" * 3001},
        {"title": {"a": 1}},
        {"theme": "<script>"},
        {"mascot": "../../etc"},
        {"open_at": "tomorrow"},
    ):
        r = await client.patch(url, json=bad, headers=h)
        assert (r.status_code, r.json()) == (400, {"error": "bad_field"}), bad
    ok = await client.patch(url, json={"theme": "oriental_palace", "mascot": "penguin"}, headers=h)
    assert ok.status_code == 200


async def test_media_fields_are_validated(client, auth):
    h = auth(1)
    m = await _museum(client, h)
    r = await client.post(
        f"/api/museums/{m['id']}/media", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
        data={"caption": "x" * 201}, headers=h,
    )
    assert (r.status_code, r.json()) == (400, {"error": "bad_field"})
    item = (await client.post(
        f"/api/museums/{m['id']}/media", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")}, headers=h,
    )).json()
    r = await client.patch(f"/api/museums/{m['id']}/media/{item['id']}", json={"position": -1}, headers=h)
    assert r.status_code == 400


async def test_media_of_other_users_is_unreachable(client, auth):
    a, b = auth(1), auth(2)
    ma, mb = await _museum(client, a), await _museum(client, b)
    item = (await client.post(
        f"/api/museums/{ma['id']}/media", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")}, headers=a,
    )).json()
    assert (await client.delete(f"/api/museums/{ma['id']}/media/{item['id']}", headers=b)).status_code == 404
    # b's own museum id with a's media id
    assert (await client.delete(f"/api/museums/{mb['id']}/media/{item['id']}", headers=b)).status_code == 404
    assert (await client.patch(f"/api/museums/{mb['id']}/media/{item['id']}", json={"caption": "x"}, headers=b)).status_code == 404


async def test_receipts_unreachable_with_encoded_traversal(client, settings):
    receipts = settings.receipts_dir
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "r.webp").write_bytes(b"secret")
    assert not receipts.resolve().is_relative_to(settings.media_dir.resolve())
    for path in ("/media/%2e%2e/receipts/r.webp", "/media/..%2freceipts/r.webp", "/media/..%5creceipts/r.webp"):
        r = await client.get(path)
        assert r.status_code == 404 and b"secret" not in r.content, path
