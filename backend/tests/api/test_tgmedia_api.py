from sahifa.services import media
from sahifa.services.tgmedia import media_secret, sign_media, verify_media
from tests.api.test_museums_api import jpeg_bytes


async def _upload(client, h, content=None, mime="image/jpeg", name="a.jpg", **data):
    return await client.post(
        "/api/tg-media", files={"file": (name, content or jpeg_bytes(), mime)}, data=data, headers=h
    )


async def test_upload_returns_signed_token(client, auth, settings, hooks):
    r = await _upload(client, auth(7))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "image"
    user_id, file_id, kind = verify_media(media_secret(settings.bot_token), body["token"])
    assert (user_id, kind) == (7, "image") and file_id in hooks.chat_files
    assert hooks.chat_files[file_id][:4] == b"RIFF"  # processed to WebP before it goes to the chat


async def test_upload_leaves_no_files(client, auth, settings, hooks):
    await _upload(client, auth(7))
    assert not any(p.exists() for p in hooks.uploaded_paths)
    assert not [p for p in settings.media_dir.rglob("*") if p.is_file()]


async def test_blocked_bot_is_409_start_bot(client, auth, hooks):
    hooks.blocked.add(7)
    r = await _upload(client, auth(7))
    assert (r.status_code, r.json()) == (409, {"error": "start_bot"})
    assert not any(p.exists() for p in hooks.uploaded_paths)


async def test_over_20mb_after_processing_rejected(client, auth, hooks, monkeypatch):
    monkeypatch.setattr("sahifa.api.routes_tgmedia.MAX_TG_FILE_BYTES", 10)
    r = await _upload(client, auth(7))
    assert (r.status_code, r.json()) == (413, {"error": "too_large"})
    assert hooks.chat_files == {}


async def test_upload_requires_auth_and_known_type(client, auth):
    r = await client.post("/api/tg-media", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 401
    r = await _upload(client, auth(7), content=b"%PDF", mime="application/pdf", name="a.pdf")
    assert (r.status_code, r.json()) == (400, {"error": "bad_format"})


async def test_proxy_streams_bytes_without_disk(client, auth, settings, hooks):
    token = (await _upload(client, auth(7))).json()["token"]
    r = await client.get(f"/api/tg-media/{token}")  # <img src> cannot send headers: the token is the key
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/webp"
    assert "private" in r.headers["cache-control"]
    assert r.content[:4] == b"RIFF"
    assert not [p for p in settings.media_dir.rglob("*") if p.is_file()]


async def test_bad_token_never_calls_telegram(client, hooks):
    for bad in ("x", "e30.AAAA", sign_media(media_secret("1:OTHER"), 7, "F0_7", "image")):
        assert (await client.get(f"/api/tg-media/{bad}")).status_code == 404
    assert hooks.fetches == 0


async def test_gone_media_is_410(client, settings):
    token = sign_media(media_secret(settings.bot_token), 7, "deleted-file", "image")
    r = await client.get(f"/api/tg-media/{token}")
    assert (r.status_code, r.json()) == (410, {"error": "media_gone"})


async def test_voice_upload_is_audio(client, auth, hooks, monkeypatch):
    async def fake_audio(src, out_dir, max_seconds):
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "v.m4a"
        out.write_bytes(b"audio")
        return out

    monkeypatch.setattr(media, "process_audio", fake_audio)
    monkeypatch.setattr("sahifa.api.routes_tgmedia.process_audio", fake_audio)
    r = await _upload(client, auth(7), content=b"OggS", mime="audio/ogg", name="v.ogg", purpose="voice")
    assert r.json()["kind"] == "audio"
