# Sahifa — 1b-reja: Akkaunt-muzeylar (backend) (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bepul muzey media'si foydalanuvchining Telegram chatida yashaydi; server uni faqat uzatadi (diskka yozmaydi); to'lov paytida akkaunt-muzey oddiy server muzeyiga import qilinadi.

**Architecture:** Mini App faylni `POST /api/tg-media`ga yuboradi → server uni qayta ishlaydi (WebP/720p), bot foydalanuvchi chatiga hujjat sifatida yuboradi, vaqtinchalik faylni o'chiradi va imzolangan token qaytaradi. `GET /api/tg-media/{token}` Telegram'dan xotiraga olib uzatadi. `POST /api/museums/import` tokenlar ro'yxatidan server qoralamasini yaratadi — keyin mavjud buyurtma oqimi ishlaydi. Telegram bilan aloqa `app.state.tg_uploader` / `tg_fetcher` orqali (testda soxta).

**Tech Stack:** mavjud (FastAPI, aiogram 3, SQLAlchemy, Pillow, ffmpeg).

**Spec:** `docs/superpowers/specs/2026-10-25-sahifa-design.md` §4.12

## Global Constraints

- Bepul muzey media'si serverda **saqlanmaydi**: vaqtinchalik fayllar so'rov tugashi bilan o'chadi; uzatish xotirada (≤ 20 MB).
- Bot API `getFile` chegarasi: **20 MB** — chatga yuboriladigan har bir fayl ≤ 20 MB (qayta ishlangandan keyin); oshsa `too_large`.
- Token = foydalanuvchiga bog'langan HMAC imzo; boshqa foydalanuvchi tokenini import qilib bo'lmaydi.
- Bot tokeni hech qachon klientga berilmaydi.
- Import qilingan qoralama mavjud qoidalarga bo'ysunadi (limitlar, 7 kunlik to'lanmagan qoralama tozalash).

## Review Focus

1. **Boshqaning tokenini import qilish** — 403/400, muzeyga qo'shilmaydi. → Task 4 `test_import_rejects_foreign_tokens`.
2. **Soxta yoki buzilgan token bilan proxy** — 404, Telegram'ga so'rov ketmaydi. → Task 1/3.
3. **Diskda iz qolishi** (yuklash yoki uzatishdan keyin) — vaqtinchalik fayl qolmaydi. → Task 2 `test_upload_leaves_no_files`.
4. **Foydalanuvchi botni bloklagan** — aniq xato `start_bot`, 500 emas. → Task 2.
5. **Importda Telegram fayli yo'qolgan** (chat o'chirilgan) — aniq xato `media_gone`, yarim muzey qolmaydi. → Task 4.

---

### Task 1: Imzolangan media tokenlari

**Files:** Create `backend/sahifa/services/tgmedia.py`; Test `backend/tests/services/test_tgmedia.py`

**Interfaces — Produces:**
- `KINDS = ("image", "video", "audio")`
- `sign_media(secret: bytes, user_id: int, file_id: str, kind: str) -> str` — `base64url(json{"u","f","k"}) + "." + base64url(hmac_sha256[:16])`.
- `verify_media(secret: bytes, token: str) -> tuple[int, str, str]` → `(user_id, file_id, kind)`; har qanday buzilish → `DomainError("bad_token")`.
- `media_secret(bot_token: str) -> bytes` = `sha256(b"sahifa-tg-media:" + token)`.

- [ ] Tests: `test_roundtrip`, `test_tampered_payload_or_signature_rejected`, `test_other_secret_rejected`, `test_garbage_rejected` → FAIL → implement → PASS → commit `feat(tgmedia): signed media tokens`.

### Task 2: `POST /api/tg-media` — chatga yuklash

**Files:** Create `backend/sahifa/api/routes_tgmedia.py`; Modify `app.py` (`tg_uploader`, `tg_fetcher` kwargs, router); Test `backend/tests/api/test_tgmedia_api.py`

**Interfaces:**
- `TgUploader = Callable[[int, Path, str], Awaitable[str]]` — `(user_id, path, kind) -> file_id`; foydalanuvchi botni bloklagan bo'lsa `DomainError("start_bot")`.
- Endpoint (auth): multipart `file`; `kind` MIME'dan (`image|video|audio`). Qayta ishlash: rasm → `process_image` (faqat main; thumb o'chiriladi), video → `process_video` (poster o'chiriladi), audio → `process_audio(max MAX_VOICE_SECONDS... musiqa uchun MAX_MUSIC_SECONDS: forma maydoni `purpose=voice|music`)`. Natija > 20 MB → `too_large`. `tg_uploader` chaqiriladi; **barcha** vaqtinchalik fayllar `finally` da o'chiriladi. Javob: `{"token", "kind"}`.

- [ ] Tests: `test_upload_returns_signed_token` (soxta uploader `file_id` qaytaradi; token verify bo'yicha shu foydalanuvchi), `test_upload_leaves_no_files` (media_dir va temp bo'sh), `test_blocked_bot_is_409_start_bot`, `test_over_20mb_after_processing_rejected` (monkeypatch limit) → FAIL → implement → PASS → commit.

### Task 3: `GET /api/tg-media/{token}` — saqlamasdan uzatish

**Files:** Modify `routes_tgmedia.py`; Test same file.

**Interfaces:**
- `TgFetcher = Callable[[str], Awaitable[bytes]]` — `file_id -> bytes` (≤ 20 MB); fayl yo'q bo'lsa `DomainError("media_gone")`.
- Endpoint (loginsiz; token — ruxsat): `verify_media` → `tg_fetcher` → `Response(content, media_type={"image": "image/webp", "video": "video/mp4", "audio": "audio/mp4"}[kind], headers={"Cache-Control": "private, max-age=86400"})`. Bir vaqtda ≤ 4 ta fetch (semafor). `bad_token` → 404, `media_gone` → 410.

- [ ] Tests: `test_proxy_streams_bytes_without_disk`, `test_bad_token_never_calls_telegram`, `test_gone_media_is_410` → FAIL → implement → PASS → commit.

### Task 4: `POST /api/museums/import` — to'lov uchun server qoralamasi

**Files:** Modify `routes_museums.py`, `services/museums.py`; Test `backend/tests/api/test_import_api.py`

**Interfaces:**
- `async import_account_museum(s, user, settings_in: dict, items: list[dict], fetch: TgFetcher, secret: bytes, now, media_dir) -> Museum` — `items[i] = {"token", "caption"?, "taken_on"?}`; har token `verify_media` bilan, `user_id == user.id` bo'lmasa `DomainError("bad_token")`; `create_museum` + `update_settings` + har biri uchun fetch → temp fayl → `add_media` (rasm/video; audio `kind` → `set_voice`/`set_music_file` yo'q — ovoz/musiqa alohida maydonlar `voice_token`, `music_token`). Istalgan xato → yaratilgan qoralama `delete_museum` bilan tozalanadi va xato qayta ko'tariladi.
- Endpoint body: `{"settings": SettingsIn, "media": [{token, caption?, taken_on?}], "voice_token"?, "music_token"?}` (≤ 60 ta media) → to'liq muzey JSON (keyin klient `POST /api/orders` qiladi).

- [ ] Tests: `test_import_creates_draft_with_media_in_order`, `test_import_rejects_foreign_tokens`, `test_import_cleans_up_when_media_gone`, `test_import_respects_limits` → FAIL → implement → PASS → commit.

### Task 5: Ulash va hujjatlar

**Files:** Modify `backend/sahifa/main.py`, `backend/sahifa/bot/` (yangi `tgfiles.py`: haqiqiy uploader/fetcher), `backend/README.md`, spec §4.12 (qoralama satri).

**Interfaces — Produces:** `make_tg_uploader(bot) -> TgUploader` (`bot.send_document(user_id, FSInputFile(path), disable_notification=True, caption="🗂 Sahifa: muzeyingiz fayli — o'chirmang")`, `TelegramForbiddenError/BadRequest(chat not found)` → `start_bot`); `make_tg_fetcher(bot) -> TgFetcher` (`get_file` + `download_file` → `BytesIO`; `file is too big`/not found → `media_gone`).

- [ ] Tests: `test_runtime_wires_tg_media` (main.build: `app.state.tg_uploader`/`tg_fetcher` mavjud); fake-bot bilan `test_uploader_maps_forbidden_to_start_bot`, `test_fetcher_maps_missing_to_media_gone` → FAIL → implement → PASS → commit.
