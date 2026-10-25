# Sahifa — 1-reja: Backend asosi (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram bot + HTTP API: muzeylar, limitlar, qulflar, media, buyurtmalar (Stars + karta cheki), bepul foydalanuvchilar, topshirish, admin buyruqlari va kundalik vazifalar — Mini App (2-reja) va 3D ko'rinish (3-reja) shu API ustiga quriladi.

**Architecture:** Bitta Python jarayon: FastAPI (uvicorn) va aiogram 3 polling bitta asyncio loop'da. Biznes qoidalari `sahifa/domain/` (sof funksiyalar) va `sahifa/services/` (DB bilan) ichida; API va bot faqat servislarni chaqiradi. SQLite (WAL) + SQLAlchemy 2 async. Media server diskida, `/media` orqali beriladi.

**Tech Stack:** Python ≥3.12, aiogram 3.x, FastAPI, uvicorn, SQLAlchemy 2 (async) + aiosqlite, pydantic-settings, Pillow, ffmpeg/ffprobe (tizimda), segno (QR), pytest + pytest-asyncio + httpx.

**Spec:** `docs/superpowers/specs/2026-10-25-sahifa-design.md`

## Global Constraints

- Muzey: 30 rasm + 5 video, **3 xona**; har qo'shimcha xona +10 rasm +2 video.
- Narxlar (so'm, standart, admin o'zgartiradi): muzey 15 000; qayta faollashtirish 15 000; xona 3 000; +5 muzey limiti 5 000.
- Stars narxlari admin sozlamasida; standart (mening qarorim): muzey 75, qayta faollashtirish 75, xona 15, limit 25.
- Faol muddat **120 kun**: to'lovdan, ochilish sanasi bo'lsa undan. Ochilish sanasi ≤ to'lov + 120 kun.
- Qayta faollashtirish: qolgan muddat ustiga +120 kun (tugagan bo'lsa — hozirdan).
- Qoralama 7 kun o'zgarishsiz → o'chiriladi. Tugagan muzey kontenti 30 kun saqlanadi → o'chiriladi. Eslatmalar tugashdan 7 va 1 kun oldin.
- Muzey limiti: 10 (o'zi yaratgan, o'chirilmagan muzeylar). +5 har paket. Topshirib olingan muzeylar sanalmaydi.
- To'lovdan keyin qulflanadigan maydonlar: `recipient_name, title, opening_style, letter_text, voice, theme, mascot, music, open_at`. Ochiq: media qo'shish/olib tashlash, izoh, sana, tartib, xona sotib olish.
- Bepul foydalanuvchi (`is_free`, ixtiyoriy `free_until`): barcha mahsulotlar to'lovsiz, muzey limiti yo'q.
- Topshirish havolasi 7 kun amal qiladi; muzey slug'i o'zgarmaydi.
- Fayl limitlari: rasm ≤ 15 MB → WebP, uzun tomoni ≤ 2048 + 480 kichik nusxa; video ≤ 50 MB, ≤ 60 s → 720p H.264 mp4 + poster; MP3 ≤ 10 MB; ovozli tabrik ≤ 120 s.
- Ko'rish bepul va loginsiz. Qoralama va ochilish sanasi kelmagan muzey media'si ommaga berilmaydi.
- Shaxs faqat Telegram `initData` orqali (HMAC tekshiruvi). Muzeycha'ning matn/nom/asset'laridan foydalanilmaydi.
- Foydalanuvchiga ko'rinadigan matnlar o'zbekcha (lotin) — ruscha tarjima 2-rejada.

## Review Focus

1. **Bir buyurtma ikki marta bajarilishi** (Stars `successful_payment` qayta kelishi, admin "Tasdiqlash"ni ikki marta bosishi) — huquq bir marta beriladi. → Task 5 testi `test_fulfil_is_idempotent`, Task 10 testi `test_approve_twice_fulfils_once`.
2. **Buyurtma kutilayotganda muzey o'chirilsa yoki topshirilsa** — tasdiqlash xato bermasdan rad etiladi va admin sababini ko'radi; topshirilgan muzeyda xona yangi egaga qo'shiladi. → Task 5 `test_fulfil_on_deleted_museum_fails_cleanly`.
3. **Limitdan oshiq yuklash** (parallel so'rovlar, yoki olib tashlab qayta qo'shish) — server yuklash paytida sanaydi; olib tashlash joyni bo'shatadi. → Task 4 `test_media_limit_enforced_and_freed`.
4. **Soxta yoki eskirgan initData** — 401. → Task 7 `test_rejects_tampered_and_stale_init_data`.
5. **Ommaviy ko'rishda qoralama yoki ochilmagan muzey media'si chiqib qolishi** — chiqmaydi. → Task 8 `test_public_view_hides_unopened_and_drafts`.

---

## Fayl tuzilmasi

```
backend/
  pyproject.toml
  sahifa/
    __init__.py
    config.py            # Settings (env)
    db.py                # engine, session factory, init_db
    models.py            # ORM jadvallari
    domain/
      pricing.py         # Product, limitlar, standart narxlar
      lifecycle.py       # sof funksiyalar: limitlar, faollashtirish, qulf, holat
    services/
      users.py           # upsert, bepul maqom, slotlar
      settings_store.py  # narxlar, karta raqami
      museums.py         # yaratish, sozlash, o'chirish, media qo'shish/olib tashlash
      media.py           # rasm/video/audio qayta ishlash
      orders.py          # buyurtma, bajarish, chek, rad etish
      transfers.py       # topshirish
      audit.py           # log yozish
      jobs.py            # kundalik vazifalar
    api/
      auth.py            # initData tekshiruvi, current_user dependency
      app.py             # create_app()
      routes_me.py, routes_museums.py, routes_orders.py, routes_transfers.py, routes_public.py
    bot/
      setup.py           # Dispatcher, routerlar
      start.py           # /start va deep link'lar
      payments.py        # Stars invoice, pre_checkout, successful_payment
      review.py          # chek tasdiqlash callback'lari
      admin.py           # admin buyruqlari
    main.py              # API + bot + jobs birga
  tests/ ...
deploy/
  docker-compose.yml, Dockerfile, .env.example
```

---

### Task 0: Loyiha skeleti va test muhiti

**Files:**
- Create: `.gitignore`, `backend/pyproject.toml`, `backend/sahifa/__init__.py`, `backend/sahifa/config.py`, `backend/tests/conftest.py`, `backend/tests/test_config.py`

**Interfaces:**
- Produces: `class Settings(BaseSettings)` maydonlari: `bot_token: str`, `admin_ids: list[int]`, `admin_chat_id: int`, `database_url: str = "sqlite+aiosqlite:///./data/sahifa.db"`, `media_dir: Path = Path("./data/media")`, `public_api_url: str` (Tailscale manzil), `webapp_url: str` (GitHub Pages), `bot_username: str`. `get_settings() -> Settings` (lru_cache). Env prefiksi `SAHIFA_`.
- Produces (conftest): `settings` fixture (tmp media_dir, in-memory DB), `session` fixture (`AsyncSession`, jadvallar yaratilgan), `now` fixture = `datetime(2026, 11, 1, 12, 0, tzinfo=UTC)`.

- [ ] **Step 1:** `git init` (D:\claude\pul), `.gitignore`: `.venv/`, `out/`, `userbot_session*`, `.superpowers/`, `backend/data/`, `__pycache__/`, `.env`.
- [ ] **Step 2:** `pyproject.toml` — bog'liqliklar Tech Stack'dagidek; `[tool.pytest.ini_options] asyncio_mode = "auto"`, `testpaths = ["tests"]`.
- [ ] **Step 3: Failing test** `test_settings_reads_env(monkeypatch)`: `SAHIFA_BOT_TOKEN=x`, `SAHIFA_ADMIN_IDS=[1,2]` → `Settings().admin_ids == [1, 2]`.
- [ ] **Step 4:** Run `cd backend && ..\.venv\Scripts\python -m pytest tests/test_config.py -v` → FAIL (import).
- [ ] **Step 5:** `config.py` ni yozing → PASS.
- [ ] **Step 6:** Commit `chore: scaffold sahifa backend`.

### Task 1: Narx va hayot sikli qoidalari (sof funksiyalar)

**Files:**
- Create: `backend/sahifa/domain/pricing.py`, `backend/sahifa/domain/lifecycle.py`
- Test: `backend/tests/domain/test_lifecycle.py`

**Interfaces:**
- Produces (`pricing.py`):
  - `class Product(StrEnum): MUSEUM="museum"; REACTIVATE="reactivate"; ROOM="room"; SLOTS="slots"`
  - Konstantalar: `BASE_ROOMS=3, BASE_IMAGES=30, BASE_VIDEOS=5, ROOM_IMAGES=10, ROOM_VIDEOS=2, ACTIVE_DAYS=120, DRAFT_TTL_DAYS=7, EXPIRED_RETENTION_DAYS=30, BASE_SLOTS=10, SLOT_PACK=5, TRANSFER_TTL_DAYS=7, REMINDER_DAYS=(7, 1)`
  - `DEFAULT_PRICES_UZS: dict[Product,int]`, `DEFAULT_PRICES_STARS: dict[Product,int]` (Global Constraints qiymatlari).
- Produces (`lifecycle.py`) — barcha funksiyalar `now: datetime` ni parametr sifatida oladi:
  - `@dataclass(frozen=True) class Limits: rooms:int; images:int; videos:int`
  - `limits_for(extra_rooms: int) -> Limits`
  - `LOCKED_AFTER_PAYMENT: frozenset[str]` (Global Constraints ro'yxati)
  - `locked_fields(changed: set[str], paid: bool) -> set[str]` — to'lanmagan bo'lsa bo'sh to'plam.
  - `activation_window(now, open_at: datetime|None) -> tuple[datetime, datetime]` → `(active_from, expires_at)`; `open_at` bo'lsa `active_from=open_at`.
  - `reactivated_expiry(now, expires_at: datetime|None) -> datetime`
  - `validate_open_at(now, open_at) -> None` — `open_at <= now` yoki `> now + 120d` bo'lsa `DomainError("open_at")`.
  - `class MuseumState(StrEnum): DRAFT, ACTIVE, EXPIRED, DELETED`
  - `public_state(status, open_at, expires_at, now) -> Literal["draft","locked","open","expired","deleted"]`
  - `class DomainError(Exception)` — `code: str` atributi bilan (API va bot shu kodni foydalanuvchi matniga aylantiradi).

- [ ] **Step 1: Failing tests:**
```python
def test_limits_grow_per_room():
    assert limits_for(0) == Limits(rooms=3, images=30, videos=5)
    assert limits_for(2) == Limits(rooms=5, images=50, videos=9)

def test_activation_starts_at_open_at(now):
    open_at = now + timedelta(days=40)
    assert activation_window(now, open_at) == (open_at, open_at + timedelta(days=120))
    assert activation_window(now, None) == (now, now + timedelta(days=120))

def test_reactivation_adds_to_remaining_or_now(now):
    assert reactivated_expiry(now, now + timedelta(days=10)) == now + timedelta(days=130)
    assert reactivated_expiry(now, now - timedelta(days=3)) == now + timedelta(days=120)

def test_open_at_bounds(now):
    validate_open_at(now, now + timedelta(days=120))
    for bad in (now, now + timedelta(days=120, seconds=1)):
        with pytest.raises(DomainError): validate_open_at(now, bad)

def test_locks_only_after_payment():
    assert locked_fields({"title", "media"}, paid=False) == set()
    assert locked_fields({"title", "caption"}, paid=True) == {"title"}

def test_public_state(now):
    assert public_state("active", now + timedelta(hours=1), now + timedelta(days=9), now) == "locked"
    assert public_state("active", None, now - timedelta(seconds=1), now) == "expired"
    assert public_state("draft", None, None, now) == "draft"
```
- [ ] **Step 2:** Run `pytest tests/domain -v` → FAIL.
- [ ] **Step 3:** Ikkala modulni yozing.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(domain): pricing and lifecycle rules`.

### Task 2: Ma'lumotlar bazasi modellari, foydalanuvchilar, sozlamalar

**Files:**
- Create: `backend/sahifa/db.py`, `backend/sahifa/models.py`, `backend/sahifa/services/users.py`, `backend/sahifa/services/settings_store.py`, `backend/sahifa/services/audit.py`
- Test: `backend/tests/services/test_users.py`, `backend/tests/services/test_settings_store.py`

**Interfaces:**
- Produces (`db.py`): `make_engine(url) -> AsyncEngine` (SQLite'da `PRAGMA journal_mode=WAL`, `foreign_keys=ON`), `make_sessionmaker(engine)`, `async init_db(engine)`.
- Produces (`models.py`, barcha vaqtlar UTC `DateTime(timezone=True)`):
  - `User`: `id` (Telegram ID, PK), `username`, `first_name`, `lang="uz"`, `extra_slots:int=0`, `is_free:bool=False`, `free_until`, `referrer_id` (nullable, 4-reja uchun), `created_at`.
  - `Museum`: `id`, `slug` (unique, `secrets.token_urlsafe(9)`), `owner_id`, `created_by_id`, `status` (`MuseumState`), `title="Bizning muzeyimiz"`, `recipient_name`, `theme="gallery_light"`, `mascot="boy"`, `opening_style="gift_box"`, `letter_text`, `voice_path`, `music_id`, `music_path`, `open_at`, `extra_rooms:int=0`, `paid_at`, `active_from`, `expires_at`, `reminded_days: str = ""` (masalan `"7,1"`), `created_at`, `updated_at`.
  - `MediaItem`: `id`, `museum_id`, `kind` (`image|video`), `path`, `thumb_path`, `caption`, `taken_on` (str, ixtiyoriy), `position:int`, `created_at`.
  - `Order`: `id`, `code` (unique, 6 belgi, `A-Z2-9`), `user_id`, `product`, `museum_id` (nullable), `method` (`stars|card|free`), `amount_uzs`, `amount_stars`, `status` (`pending|awaiting_review|paid|rejected|refunded`), `receipt_path`, `charge_id`, `admin_id`, `reject_reason`, `created_at`, `paid_at`.
  - `Transfer`: `id`, `token` (unique), `museum_id`, `from_user_id`, `to_user_id`, `status` (`pending|accepted|cancelled`), `expires_at`, `created_at`.
  - `Setting`: `key` (PK), `value` (JSON).
  - `AuditLog`: `id`, `actor_id`, `action`, `payload` (JSON), `at`.
- Produces (`users.py`): `async upsert_user(s, tg: dict) -> User` (`tg` — initData/aiogram'dagi `id, username, first_name, language_code`); `is_free_now(user, now) -> bool`; `async grant_free(s, user_id, admin_id, days: int|None, now)`; `async revoke_free(s, user_id, admin_id)`; `async list_free(s) -> list[User]`; `async slots_status(s, user, now) -> tuple[int, int|None]` → `(used, total)`, bepulda `total=None`. `used` = `created_by_id == owner_id == user.id` va `status != deleted`.
- Produces (`settings_store.py`): `async get_price(s, product, currency: Literal["uzs","stars"]) -> int`, `async set_price(...)`, `async get_cards(s) -> list[dict]` (`{"number","holder"}`), `async set_cards(s, cards)`.
- Produces (`audit.py`): `async log(s, actor_id, action, **payload)`.

- [ ] **Step 1: Failing tests:**
  - `test_upsert_creates_then_updates_username` — ikkinchi chaqiruvda `username` yangilanadi, qator bitta.
  - `test_free_status_with_expiry(now)` — `grant_free(days=30)` → `is_free_now(u, now+29d)` True, `now+31d` False; `days=None` → muddatsiz; `revoke_free` → False; ikkala amal `AuditLog`ga yoziladi.
  - `test_slots_ignore_transferred_and_deleted` — 2 ta o'zi yaratgan + 1 o'chirilgan + 1 topshirib olingan (`created_by_id` boshqa) → `(2, 10)`; `extra_slots=5` → `(2, 15)`; bepul → `(2, None)`.
  - `test_prices_default_then_override` — `get_price(MUSEUM,"uzs") == 15000`; `set_price(..., 17000)` → 17000.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Modullarni yozing.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(db): models, users, settings, audit`.

### Task 3: Media qayta ishlash

**Files:**
- Create: `backend/sahifa/services/media.py`
- Test: `backend/tests/services/test_media.py`

**Interfaces:**
- Produces:
  - `MAX_IMAGE_BYTES=15*2**20, MAX_VIDEO_BYTES=50*2**20, MAX_VIDEO_SECONDS=60, MAX_AUDIO_BYTES=10*2**20, MAX_VOICE_SECONDS=120`
  - `class MediaError(DomainError)` kodlari: `too_large`, `too_long`, `bad_format`.
  - `def process_image(src: Path, out_dir: Path) -> tuple[Path, Path]` → `(main.webp, thumb.webp)`; EXIF bo'yicha aylantiriladi, metadata olib tashlanadi.
  - `async def process_video(src: Path, out_dir: Path) -> tuple[Path, Path]` → `(video.mp4, poster.jpg)`; `ffprobe` bilan davomiylik, `ffmpeg -vf scale=-2:'min(720,ih)' -c:v libx264 -crf 26 -preset veryfast -c:a aac -movflags +faststart`.
  - `async def process_audio(src: Path, out_dir: Path, max_seconds: int) -> Path` → `.m4a` (ovoz ham, musiqa ham; Telegram voice `.ogg` ham qabul qilinadi).
  - Fayl nomlari `uuid4().hex` — foydalanuvchi bergan nom ishlatilmaydi.

- [ ] **Step 1: Failing tests:**
  - `test_image_resized_to_webp(tmp_path)` — Pillow bilan 4000×3000 JPEG yarating → main `.webp`, `max(size) == 2048`; thumb `max(size) == 480`.
  - `test_image_rejects_non_image(tmp_path)` — matn faylini `.jpg` deb bering → `MediaError("bad_format")`.
  - `test_video_too_long_rejected` va `test_video_transcoded_720p` — `@pytest.mark.skipif(shutil.which("ffmpeg") is None)`; ffmpeg bilan 61 s va 3 s 1080p test video yarating; birinchisi `too_long`, ikkinchisida chiqish balandligi 720.
- [ ] **Step 2:** Run → FAIL. **Step 3:** yozing. **Step 4:** Run → PASS (ffmpeg yo'q bo'lsa video testlari SKIP — Windows'da `winget install ffmpeg` bilan o'rnatib, PASS ekanini ko'ring).
- [ ] **Step 5:** Commit `feat(media): image/video/audio processing`.

### Task 4: Muzey servisi

**Files:**
- Create: `backend/sahifa/services/museums.py`
- Test: `backend/tests/services/test_museums.py`

**Interfaces:**
- Consumes: Task 1 (`limits_for`, `locked_fields`, `validate_open_at`, `DomainError`), Task 2 (`slots_status`, `is_free_now`), Task 3 (`process_image`, `process_video`, `process_audio`).
- Produces:
  - `SETTINGS_FIELDS = {"title","recipient_name","theme","mascot","opening_style","letter_text","music_id","open_at"}`
  - `async create_museum(s, user, now, template: str|None = None) -> Museum` — limit to'lsa `DomainError("slots_full")`. Shablon qiymatlari 3-rejada to'ldiriladi; hozir `template` faqat saqlanadi (`Museum.template` maydonini qo'shing).
  - `async get_owned(s, user, museum_id) -> Museum` — boshqa egada yoki o'chirilgan bo'lsa `DomainError("not_found")`.
  - `async update_settings(s, museum, changes: dict, now) -> Museum` — noma'lum maydon → `DomainError("bad_field")`; `locked_fields(...)` bo'sh bo'lmasa `DomainError("locked")`; `open_at` bo'lsa `validate_open_at`.
  - `async set_voice(s, museum, src: Path, now)`, `async set_music_file(s, museum, src: Path, now)` — to'langan bo'lsa `locked`.
  - `async add_media(s, museum, src: Path, kind, caption, taken_on, now) -> MediaItem` — sanash va saqlash bitta tranzaksiyada (`BEGIN IMMEDIATE`), limit to'lsa `DomainError("media_full")`; holat `deleted`/`expired` bo'lsa `DomainError("not_editable")`.
  - `async update_media(s, museum, media_id, caption=None, taken_on=None, position=None)`, `async remove_media(s, museum, media_id)` (fayllarini ham o'chiradi).
  - `async delete_museum(s, museum, now)` — `status=deleted`, fayllar o'chiriladi, kutilayotgan buyurtmalar `rejected` (`reject_reason="museum_deleted"`).
  - Har o'zgarish `updated_at=now` qiladi.

- [ ] **Step 1: Failing tests:**
  - `test_create_respects_slots(now)` — 10 ta yaratilgach 11-chisi `slots_full`; bepul foydalanuvchi 11-chini yarata oladi.
  - `test_settings_locked_after_payment(now)` — `paid_at=None`: `title` o'zgaradi; `paid_at=now`: `title` → `locked`, lekin media qo'shish ishlaydi.
  - `test_media_limit_enforced_and_freed(now, tmp_path)` — 30 rasm qo'shilgach 31-chisi `media_full`; bittasini olib tashlagach qo'shiladi; `extra_rooms=1` → 40 tagacha; videolar alohida sanaladi (5, keyin `media_full`). (Tezlik uchun `process_image`ni kichik rasm bilan ishlating.)
  - `test_open_at_validation(now)` — 121 kun keyingi sana → `DomainError("open_at")`.
  - `test_delete_rejects_pending_orders(now)` — kutilayotgan `Order` `rejected` bo'ladi.
- [ ] **Step 2:** FAIL → **Step 3:** yozing → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(museums): create, settings locks, media limits`.

### Task 5: Buyurtmalar va bajarish

**Files:**
- Create: `backend/sahifa/services/orders.py`
- Test: `backend/tests/services/test_orders.py`

**Interfaces:**
- Consumes: Task 1, 2, 4.
- Produces:
  - `async create_order(s, user, product: Product, museum_id: int|None, method: Literal["stars","card"], now) -> Order` — qoidalar: `MUSEUM` → egasining `draft` muzeyi; `ROOM` → `active` muzey; `REACTIVATE` → `active` yoki `expired`; `SLOTS` → `museum_id=None`. Noto'g'ri kombinatsiya → `DomainError("bad_order")`. Summalar `settings_store`dan olinadi va buyurtmada qotiriladi. Agar `is_free_now(user)` → `method="free"`, darhol `fulfil` va `paid` qaytariladi. Bitta muzey+mahsulot uchun ochiq `pending/awaiting_review` buyurtma bo'lsa — o'shani qaytaradi (yangisini yaratmaydi).
  - `async fulfil(s, order, now, charge_id: str|None = None, admin_id: int|None = None) -> Order` — **idempotent** (`paid` bo'lsa o'zgarishsiz qaytadi). Ta'sir: `MUSEUM` → `paid_at=now`, `activation_window(now, open_at)` (`open_at` o'tib ketgan bo'lsa `None` deb olinadi), `status=active`; `ROOM` → `extra_rooms += 1`; `REACTIVATE` → `expires_at = reactivated_expiry(...)`, `status=active`; `SLOTS` → `user.extra_slots += SLOT_PACK`. Muzey o'chirilgan bo'lsa → `DomainError("museum_gone")`, buyurtma `rejected`. Muzey topshirilgan bo'lsa ham ta'sir muzeyga beriladi (egasidan qat'i nazar). `audit.log` yoziladi.
  - `async attach_receipt(s, order, src: Path, now) -> Order` — faqat `method=card` va `pending`/`rejected` holatida; `awaiting_review`.
  - `async reject(s, order, admin_id, reason: str, now) -> Order`
  - `async get_by_code(s, code) -> Order`
  - `async mark_refunded(s, order, admin_id, now)` — huquq qaytarib olinmaydi (spec: admin qaror qiladi), faqat holat.

- [ ] **Step 1: Failing tests:**
  - `test_museum_order_activates(now)` — `fulfil` → `status=active`, `expires_at == now+120d`; `open_at=now+10d` bo'lsa `expires_at == now+130d`.
  - `test_fulfil_is_idempotent(now)` — ikki marta `fulfil` → `extra_rooms == 1`, audit yozuvi bitta.
  - `test_room_and_slots_effects(now)`, `test_reactivate_extends(now)`.
  - `test_free_user_order_is_paid_immediately(now)` — `method == "free"`, `amount_uzs == 0`, muzey faol.
  - `test_reuses_open_order(now)` — ikki marta `create_order(ROOM, card)` → bir xil `code`.
  - `test_fulfil_on_deleted_museum_fails_cleanly(now)` — `DomainError("museum_gone")`, `order.status == "rejected"`.
  - `test_price_snapshot(now)` — buyurtmadan keyin narx o'zgarsa ham `order.amount_uzs` eski.
- [ ] **Step 2:** FAIL → **Step 3:** yozing → **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(orders): orders, idempotent fulfilment, free users`.

### Task 6: Topshirish

**Files:**
- Create: `backend/sahifa/services/transfers.py`
- Test: `backend/tests/services/test_transfers.py`

**Interfaces:**
- Produces: `async create_transfer(s, museum, from_user, now) -> Transfer` (avvalgi `pending` topshirish bekor qilinadi; token `secrets.token_urlsafe(16)`, `expires_at = now+7d`); `async cancel_transfer(s, transfer, user)`; `async accept_transfer(s, token, user, now) -> Museum` — xatolar: `transfer_invalid` (topilmadi/bekor/qabul qilingan), `transfer_expired`, `transfer_self`. Qabulda `owner_id = user.id`, `created_by_id` o'zgarmaydi, `slug` o'zgarmaydi, ochiq buyurtmalar yangi egaga o'tkazilmaydi (eski ega to'lasa ham ta'sir muzeyga — Task 5).

- [ ] **Step 1: Failing tests:** `test_accept_moves_owner_and_keeps_slug`, `test_expired_and_self_rejected`, `test_new_transfer_cancels_previous`, `test_transferred_museum_not_counted_in_new_owner_slots` (Task 2 `slots_status` bilan).
- [ ] **Step 2–4:** FAIL → yozing → PASS.
- [ ] **Step 5:** Commit `feat(transfers): hand a museum to another user`.

### Task 7: initData tekshiruvi va API: men / muzeylar / media

**Files:**
- Create: `backend/sahifa/api/auth.py`, `backend/sahifa/api/app.py`, `backend/sahifa/api/routes_me.py`, `backend/sahifa/api/routes_museums.py`
- Test: `backend/tests/api/test_auth.py`, `backend/tests/api/test_museums_api.py`, `backend/tests/api/conftest.py`

**Interfaces:**
- Produces (`auth.py`): `verify_init_data(init_data: str, bot_token: str, now: datetime, max_age: timedelta = timedelta(hours=24)) -> dict` (Telegram algoritmi: `secret = HMAC_SHA256(key=b"WebAppData", msg=bot_token)`, `hash == HMAC_SHA256(secret, data_check_string).hex()`; `auth_date` eskirgan bo'lsa ham rad) — `AuthError`; `current_user` FastAPI dependency — sarlavha `X-Telegram-Init-Data`, `upsert_user` qiladi; `optional_user`.
- Produces (`app.py`): `create_app(settings, sessionmaker, bot) -> FastAPI` — CORS faqat `settings.webapp_url` uchun; `/media` → `StaticFiles(settings.media_dir)`; `DomainError` → HTTP 400 `{"error": code}` (`not_found` → 404, `locked`/`slots_full`/`media_full` → 409); upload hajmi `Content-Length` bo'yicha oldindan tekshiriladi.
- Produces (routes; barchasi `current_user` bilan; javoblar JSON):
  - `GET /api/me` → `{id, first_name, lang, is_free, slots:{used,total}}`
  - `GET /api/museums` → egasining o'chirilmagan muzeylari (`id, slug, title, status, expires_at, cover_thumb, counts:{images,videos}, limits`)
  - `POST /api/museums {template?}` → muzey
  - `GET /api/museums/{id}` → to'liq (sozlamalar + media ro'yxati + `limits` + `locked: bool`)
  - `PATCH /api/museums/{id}` → `update_settings`
  - `DELETE /api/museums/{id}`
  - `POST /api/museums/{id}/media` (multipart: `file`, `caption?`, `taken_on?`) — `kind` MIME'dan
  - `PATCH /api/museums/{id}/media/{mid}`, `DELETE /api/museums/{id}/media/{mid}`
  - `PUT /api/museums/{id}/voice`, `PUT /api/museums/{id}/music` (multipart)
  - Media URL'lari `f"{settings.public_api_url}/media/{relpath}"`.

- [ ] **Step 1: Failing tests:**
  - `test_accepts_valid_init_data` — testda haqiqiy algoritm bilan imzolangan initData (yordamchi `sign_init_data(user, token, auth_date)` `tests/api/conftest.py`da).
  - `test_rejects_tampered_and_stale_init_data` — `user` o'zgartirilgan → 401; `auth_date` 25 soat oldin → 401; sarlavhasiz → 401.
  - `test_create_list_get_museum`, `test_other_users_museum_is_404`, `test_patch_locked_returns_409`, `test_upload_over_limit_returns_409` (limit uchun `extra_rooms`/mavjud media'ni DB orqali tayyorlang).
- [ ] **Step 2–4:** FAIL → yozing → PASS (`httpx.AsyncClient(transport=ASGITransport(app))`).
- [ ] **Step 5:** Commit `feat(api): auth, museums and media endpoints`.

### Task 8: API: buyurtmalar, topshirish, ommaviy ko'rish

**Files:**
- Create: `backend/sahifa/api/routes_orders.py`, `backend/sahifa/api/routes_transfers.py`, `backend/sahifa/api/routes_public.py`
- Test: `backend/tests/api/test_orders_api.py`, `backend/tests/api/test_public_api.py`

**Interfaces:**
- Consumes: Task 5, 6; `bot.create_invoice_link` (Task 9 dagi `make_stars_invoice_link`).
- Produces:
  - `POST /api/orders {product, museum_id?, method}` → `stars`: `{code, status, invoice_link}`; `card`: `{code, status, amount_uzs, cards:[{number, holder}], comment: code}`; `free`: `{code, status:"paid"}`.
  - `POST /api/orders/{code}/receipt` (multipart rasm) → `awaiting_review`; so'ng `notify_admins_new_receipt(order)` chaqiriladi (Task 10 da yoziladi; bu yerda dependency orqali uzatiladi, testda soxta).
  - `GET /api/orders/{code}` → holat (Mini App so'rab turadi).
  - `POST /api/museums/{id}/transfer` → `{link: f"https://t.me/{bot_username}?start=tr_{token}", expires_at}`; `DELETE /api/museums/{id}/transfer`.
  - `POST /api/transfers/{token}/accept` → muzey.
  - `GET /api/public/m/{slug}` (loginsiz; `optional_user`): `public_state` bo'yicha — `draft`: faqat egasiga to'liq, boshqalarga 404; `locked`: `{state, open_at, opening_style, recipient_name, title}` (media yo'q); `open`: to'liq ko'rish ma'lumoti (sozlamalar, xonalar soni, media URL/izoh/sana, ovoz/musiqa URL); `expired`: `{state:"expired"}`; `deleted` → 404.

- [ ] **Step 1: Failing tests:**
  - `test_card_order_flow` — buyurtma → chek yuklash → `awaiting_review`, soxta notifier bir marta chaqirilgan.
  - `test_stars_order_returns_invoice_link` (soxta bot).
  - `test_free_user_order_paid`.
  - `test_public_view_hides_unopened_and_drafts` — begona uchun qoralama 404; `open_at` kelajakda → javobda `media` kaliti yo'q; ochiq → media bor; egasi qoralamasini ko'radi.
  - `test_transfer_accept_via_api`.
- [ ] **Step 2–4:** FAIL → yozing → PASS.
- [ ] **Step 5:** Commit `feat(api): orders, transfers, public view`.

### Task 9: Bot: /start, deep link'lar, Telegram Stars

**Files:**
- Create: `backend/sahifa/bot/setup.py`, `backend/sahifa/bot/start.py`, `backend/sahifa/bot/payments.py`
- Test: `backend/tests/bot/test_start.py`, `backend/tests/bot/test_payments.py`

**Interfaces:**
- Produces:
  - `build_dispatcher(sessionmaker, settings) -> Dispatcher` — routerlarni ulaydi, `session`ni middleware orqali beradi.
  - `/start` — salom matni (o'zimizniki; "Sahifa" nomi bilan) + `WebAppInfo` tugmalar: "🎁 Sovg'a-muzey yaratish" → `webapp_url`, "📂 Muzeylarim" → `webapp_url + "#/my"`; `set_chat_menu_button` ham shu manzil.
  - Deep link: `tr_<token>` → muzey nomi bilan "Qabul qilish / Rad etish" inline tugmalar (`tr:ok:<token>`, `tr:no:<token>`) → `accept_transfer`; `m_<slug>` → muzeyni ochuvchi WebApp tugma; `ref_<id>` → hozircha faqat `referrer_id` yoziladi (bonus 4-rejada).
  - `async make_stars_invoice_link(bot, order) -> str` — `currency="XTR"`, `provider_token=""`, `payload=order.code`, `prices=[LabeledPrice(label=<mahsulot nomi>, amount=order.amount_stars)]`.
  - `pre_checkout_query` — buyurtma `pending` va summa mos bo'lsa `ok=True`, aks holda `ok=False` + sabab.
  - `successful_payment` — `fulfil(order, charge_id=telegram_payment_charge_id)`; foydalanuvchiga "To'lov qabul qilindi" + muzeyni ochish tugmasi. Qayta kelsa — idempotent.
- Testlar aiogram handlerlarini to'g'ridan-to'g'ri soxta `Message`/`PreCheckoutQuery` obyektlari (`AsyncMock` bilan `answer`) bilan chaqiradi.

- [ ] **Step 1: Failing tests:** `test_start_shows_webapp_buttons`, `test_transfer_deeplink_accept`, `test_precheckout_rejects_wrong_amount`, `test_successful_payment_fulfils_once` (ikki marta yuboring → `extra_rooms == 1`).
- [ ] **Step 2–4:** FAIL → yozing → PASS.
- [ ] **Step 5:** Commit `feat(bot): start, deep links, Stars payments`.

### Task 10: Bot: chek tasdiqlash va admin buyruqlari

**Files:**
- Create: `backend/sahifa/bot/review.py`, `backend/sahifa/bot/admin.py`
- Test: `backend/tests/bot/test_review.py`, `backend/tests/bot/test_admin.py`

**Interfaces:**
- Produces:
  - `async notify_admins_new_receipt(bot, settings, order, user, museum)` — `admin_chat_id`ga chek rasmi + matn (kod, foydalanuvchi, mahsulot, summa, muzey nomi) + tugmalar: `rv:ok:<code>`, `rv:no:<code>:amount|unreadable|notfound`.
  - Callback `rv:ok` — faqat `admin_ids` dagilar; `fulfil(admin_id=...)`; xabar matni "✅ Tasdiqlandi — <admin>" ga o'zgaradi, tugmalar olinadi; foydalanuvchiga xabar. `rv:no` — `reject` + foydalanuvchiga sabab matni va "Chekni qayta yuborish" WebApp tugmasi.
  - Admin buyruqlari (faqat `admin_ids`, boshqalarga javob yo'q):
    - `/stats` — foydalanuvchilar, muzeylar holat bo'yicha, bugungi/jami to'langan buyurtmalar va so'm/Stars summasi.
    - `/narx <museum|reactivate|room|slots> <uzs|stars> <son>`; argumentsiz — joriy narxlar.
    - `/karta <raqam> <egasi ismi>` (bir nechta karta — har biri alohida qator; `/karta tozalash`).
    - `/bepul <id|@username> [kun]` yoki foydalanuvchi xabariga reply qilib `/bepul [kun]`; `/bepul_ochir <id|@username>`; `/bepullar`.
    - `/xabar` — reply qilingan xabarni barcha foydalanuvchilarga nusxalaydi (soniyasiga ≤ 25 ta, bloklaganlarni o'tkazib yuboradi, oxirida hisobot).
    - `/qaytar <code>` — Stars buyurtmasi uchun `refund_star_payment` + `mark_refunded`.
- `@username` faqat bazada bor foydalanuvchilar orasidan qidiriladi; topilmasa aniq xabar.

- [ ] **Step 1: Failing tests:** `test_approve_twice_fulfils_once`, `test_non_admin_cannot_approve`, `test_reject_notifies_user_with_reason`, `test_grant_free_by_username_and_reply`, `test_set_price_command`, `test_broadcast_skips_blocked` (soxta bot `TelegramForbiddenError` tashlaydi).
- [ ] **Step 2–4:** FAIL → yozing → PASS.
- [ ] **Step 5:** Commit `feat(bot): receipt review and admin commands`.

### Task 11: Kundalik vazifalar, ishga tushirish, Docker

**Files:**
- Create: `backend/sahifa/services/jobs.py`, `backend/sahifa/main.py`, `deploy/Dockerfile`, `deploy/docker-compose.yml`, `deploy/.env.example`, `backend/README.md`
- Test: `backend/tests/services/test_jobs.py`

**Interfaces:**
- Produces (`jobs.py`): `async run_daily(s, now, notify: Callable[[int, str], Awaitable[None]]) -> dict` — qaytaradi `{"drafts_deleted", "expired", "reminded", "purged"}`:
  - `draft` va `updated_at < now-7d` → `delete_museum`.
  - `active` va `expires_at <= now` → `expired`.
  - `active` va `expires_at - now` ≤ 7 yoki ≤ 1 kun, `reminded_days`da yo'q → eslatma (`notify(owner_id, matn)`), qayd qilinadi.
  - `expired` va `expires_at < now-30d` → `delete_museum`.
- Produces (`main.py`): `async main()` — sozlamalar, `init_db`, bot, dispatcher, `create_app`; `asyncio.gather(uvicorn.Server(...).serve(), dp.start_polling(bot), daily_loop())`; `daily_loop` har soatda tekshirib, kuniga bir marta (03:00 Asia/Tashkent) `run_daily` ni chaqiradi. Ishga tushish: `python -m sahifa.main`.
- Docker: `python:3.12-slim` + `ffmpeg`; `data/` volume; `.env` dan `SAHIFA_*`. README: lokal ishga tushirish, `.env` maydonlari, BotFather'da Mini App/menyu sozlash, Tailscale Funnel `tailscale funnel --bg 8000` (to'liq deploy 4-rejada).

- [ ] **Step 1: Failing tests:** `test_daily_deletes_stale_drafts`, `test_daily_expires_and_reminds_once` (7 kun qolganda bir marta, ikkinchi chaqiruvda yo'q; 1 kun qolganda yana bir marta), `test_daily_purges_after_retention`.
- [ ] **Step 2–4:** FAIL → yozing → PASS.
- [ ] **Step 5: To'liq tekshiruv:** `pytest -q` → hammasi PASS. So'ng haqiqiy token bilan `.env` to'ldirib `python -m sahifa.main` → botda `/start` WebApp tugmalarini ko'rsatadi; `curl localhost:8000/api/public/m/x` → 404.
- [ ] **Step 6:** Commit `feat: daily jobs, entrypoint, docker`.

---

## Keyingi rejalar (alohida hujjatlar)
- **2-reja — Mini App:** shablon tanlash, yuklash, sozlash, to'lov ekranlari (Stars/karta+chek), "Muzeylarim", topshirish, o'zbek/rus tillari.
- **3-reja — 3D va ochilish:** 6 mavzu, 10 qahramon, 4 ochilish uslubi, ovoz/musiqa, izohlar, orqaga sanoq, "rahmat" javobi, shablon to'plamlari, QR.
- **4-reja — O'sish va deploy:** referal bonusi, bayram eslatmalari, Stories, preview havolasi `/g/<slug>`, GitHub Pages CI, Ubuntu + Docker + Tailscale Funnel, zaxira.
