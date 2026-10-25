from sqlalchemy import func, select

from sahifa.models import MediaItem, Museum
from tests.api.test_tgmedia_api import _upload


async def _tokens(client, h, n):
    return [(await _upload(client, h)).json()["token"] for _ in range(n)]


async def test_import_creates_draft_with_media_in_order(client, auth):
    h = auth(7)
    tokens = await _tokens(client, h, 3)
    body = {
        "settings": {"title": "Bizning yo'l", "recipient_name": "Aziza", "theme": "oriental_palace"},
        "media": [{"token": t, "caption": f"#{i}", "taken_on": "2021"} for i, t in enumerate(tokens)],
    }
    r = await client.post("/api/museums/import", json=body, headers=h)
    assert r.status_code == 200, r.text
    m = r.json()
    assert (m["status"], m["title"], m["recipient_name"], m["theme"]) == ("draft", "Bizning yo'l", "Aziza", "oriental_palace")
    assert [x["caption"] for x in m["media"]] == ["#0", "#1", "#2"]
    order = await client.post("/api/orders", json={"product": "museum", "museum_id": m["id"], "method": "card"}, headers=h)
    assert order.status_code == 200


async def test_import_rejects_foreign_tokens(client, auth, sessionmaker):
    theirs = await _tokens(client, auth(8), 1)
    r = await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": theirs[0]}]}, headers=auth(7))
    assert (r.status_code, r.json()) == (404, {"error": "bad_token"})
    async with sessionmaker() as s:
        assert await s.scalar(select(func.count()).select_from(Museum).where(Museum.status != "deleted")) == 0


async def test_import_cleans_up_when_media_gone(client, auth, hooks, sessionmaker, settings):
    h = auth(7)
    tokens = await _tokens(client, h, 2)
    hooks.chat_files.pop(list(hooks.chat_files)[1])  # the user deleted that message from the chat
    r = await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": t} for t in tokens]}, headers=h)
    assert (r.status_code, r.json()) == (410, {"error": "media_gone"})
    async with sessionmaker() as s:
        assert await s.scalar(select(func.count()).select_from(Museum).where(Museum.status != "deleted")) == 0
        assert await s.scalar(select(func.count()).select_from(MediaItem)) == 0
    assert not [p for p in settings.media_dir.rglob("*") if p.is_file()]


async def test_import_respects_limits(client, auth):
    h = auth(7)
    token = (await _tokens(client, h, 1))[0]
    r = await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": token}] * 131}, headers=h)
    assert (r.status_code, r.json()) == (409, {"error": "media_full"})
    r = await client.post("/api/museums/import", json={"settings": {}, "media": [{"token": token}] * 156}, headers=h)
    assert (r.status_code, r.json()) == (400, {"error": "bad_field"})


async def test_import_voice_and_music(client, auth, monkeypatch):
    async def fake_audio(src, out_dir, max_seconds):
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{src.stem}-a.m4a"
        out.write_bytes(src.read_bytes())
        return out

    monkeypatch.setattr("sahifa.api.routes_tgmedia.process_audio", fake_audio)
    monkeypatch.setattr("sahifa.services.museums.process_audio", fake_audio)
    h = auth(7)
    voice = (await _upload(client, h, content=b"OggS", mime="audio/ogg", name="v.ogg", purpose="voice")).json()["token"]
    music = (await _upload(client, h, content=b"ID3", mime="audio/mpeg", name="m.mp3", purpose="music")).json()["token"]
    image = (await _tokens(client, h, 1))[0]
    r = await client.post(
        "/api/museums/import",
        json={"settings": {}, "media": [{"token": image}], "voice_token": voice, "music_token": music},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["voice_url"] and r.json()["music_url"]

    bad = await client.post(
        "/api/museums/import", json={"settings": {}, "media": [{"token": voice}]}, headers=h
    )
    assert (bad.status_code, bad.json()) == (400, {"error": "bad_format"})  # audio is not a wall item
