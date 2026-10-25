# Sahifa — 2-reja: Mini App (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram Mini App (Vue 3) — bepul akkaunt-muzey yaratish/bezash, sovg'a qilish (Stars/karta), muzeylarni boshqarish, sovg'ani 2D ko'rish; backend'ga kerakli kichik qo'shimchalar.

**Architecture:** `frontend/` — Vite + Vue 3 + TS SPA, hash-router, GitHub Pages uchun statik build. Telegram bilan aloqa faqat `src/telegram.ts` orqali (SDK bo'lmasa zaxira), backend bilan faqat `src/api.ts` orqali. Bepul muzeylar `src/account/store.ts` da Telegram CloudStorage'ga sahifalab yoziladi. Ekranlar `src/views/*`, umumiy bo'laklar `src/components/*`.

**Tech Stack:** Node 22 LTS, Vite 6, Vue 3.5, TypeScript 5, vue-router 4 (hash), Pinia 2, vue-i18n 10, qrcode 1.5, Vitest 3 + @vue/test-utils + happy-dom. Backend: mavjud Python stack.

**Spec:** `docs/superpowers/specs/2026-10-25-sahifa-miniapp-design.md` (+ asosiy `2026-10-25-sahifa-design.md`)

## Global Constraints

- CloudStorage: 1024 kalit, kalit ≤ 128 belgi `[A-Za-z0-9_-]`, qiymat ≤ 4096 belgi; sahifa ≤ 4000 belgi.
- Kalitlar: `idx`, `m_<id>`, `m_<id>_l`, `m_<id>_p<n>`; lokal id 6 belgi `[a-z0-9]`. Yozish: sahifalar → `m_<id>` → `idx`; o'chirish teskari.
- Bepul muzey: ≤ 130 rasm, ≤ 25 video; `rooms = max(ceil((img−30)/10), ceil((vid−5)/2), 0)`, ≤ 10.
- Matn chegaralari: nom ≤ 80 (≥1), kim uchun ≤ 60, maktub ≤ 3000, izoh ≤ 200, sana ≤ 32.
- Kalit ro'yxatlari (3-reja bilan shartnoma) — spec §6a dagidek, aynan shu yozilishda.
- Bir vaqtda ≤ 2 yuklash, ≤ 4 media so'rovi; to'lov holati 3 s da so'raladi.
- Havola: `https://t.me/<bot_username>?start=m_<slug>`.
- Har API so'rovida `X-Telegram-Init-Data`; `#/m/:slug` Telegram'siz ham ishlaydi.
- Tillar: `uz` (standart), `ru`; `language_code` `ru` bo'lsa rus.
- Boshlang'ich yuklama (gzip) ≤ 200 KB JS; `qrcode` faqat kerak bo'lganda (dynamic import).

## Review Focus

1. **CloudStorage yozuvi yarmida uzilsa** (ilova yopildi, tarmoq) — eski muzey buzilmaydi, `idx` faqat to'liq yozilgan muzeyni ko'rsatadi. → Task 6 `saveMuseum keeps the previous version when a page write fails`.
2. **Muzey qisqarganda eski sahifalar qolib ketishi** (rasm o'chirildi) — ortiqcha `_p<n>` kalitlar o'chiriladi, 1024 kalit to'lib qolmaydi. → Task 6 `shrinking a museum removes stale pages`.
3. **Yuklash xatosi bitta faylda** (`start_bot`, `too_large`, tarmoq) — qolgan fayllar davom etadi, xato faylda ko'rinadi, qayta urinish mumkin. → Task 7 `one failed upload does not stop the queue`.
4. **"Sovg'a qilish" ikki marta / eski qoralama** — eski to'lanmagan qoralama o'chiriladi, ikkita to'lov ochilmaydi. → Task 10 `regifting deletes the unpaid draft first`.
5. **Telegram'siz ochilgan sovg'a havolasi** — sahifa ishlaydi, SDK chaqiruvlari xato bermaydi. → Task 12 `viewer works without Telegram SDK`.

---

## Fayl tuzilmasi

```
backend/sahifa/api/routes_prices.py            # GET /api/prices
frontend/
  package.json, vite.config.ts, tsconfig.json, index.html, .env.example
  src/main.ts, App.vue, router.ts, styles.css
  src/telegram.ts            # SDK o'rami + zaxira
  src/api.ts                 # backend mijozi, turlar
  src/i18n/{index.ts,uz.ts,ru.ts}
  src/catalog.ts             # mavzu/ochilish/qahramon/shablon kalitlari
  src/account/store.ts       # CloudStorage sxemasi
  src/account/rooms.ts       # xonalar hisobi
  src/upload/queue.ts        # yuklash navbati
  src/components/*.vue       # MediaGrid, MediaEditor, OptionPicker, QrCard, PriceSummary, StatusBadge
  src/views/{Home,NewMedia,NewDecor,NewReview,Gift,Order,Done,ServerMuseum,LocalMuseum,Viewer}.vue
  tests/*.spec.ts
.github/workflows/pages.yml
```

---

### Task 1: Backend — narxlar, bot nomi, IP limiti

**Files:** Create `backend/sahifa/api/routes_prices.py`; Modify `app.py`, `routes_me.py`, `routes_tgmedia.py`; Test `backend/tests/api/test_prices_api.py`

**Interfaces — Produces:** `GET /api/prices` (loginsiz) → `{"museum":{"uzs":15000,"stars":75},"reactivate":{…},"room":{"uzs":3000,"stars":15},"slots":{"uzs":5000,"stars":25}}` (sozlamalardagi joriy qiymatlar); `GET /api/me` javobida `"bot_username"`; `RateLimiter()` standart `per_minute=300`.

- [ ] Tests: `test_prices_reflect_settings` (`set_price(room, uzs, 4000)` → javobda 4000), `test_me_has_bot_username`, `test_default_rate_limit_is_300` → FAIL → implement → PASS (`bash .superpowers/t.sh -q`) → commit `feat(api): prices endpoint, bot username, higher media rate limit`.

### Task 2: Backend — xonali import va bitta to'lov

**Files:** Modify `services/museums.py` (`import_account_museum`), `routes_museums.py` (`ImportIn.media` ≤ 155), `services/orders.py` (`create_order`); Test `backend/tests/api/test_import_rooms_api.py`

**Interfaces — Produces:**
- `rooms_needed(images: int, videos: int) -> int` (`domain/lifecycle.py`) — `max(ceil((images-30)/10), ceil((videos-5)/2), 0)`; > 10 → `DomainError("media_full")`.
- Import: qoralama `extra_rooms = rooms_needed(...)` bilan yaratiladi; limitlar shu xonalarga nisbatan.
- `create_order(MUSEUM)`: `amount_uzs = price(museum) + extra_rooms × price(room)`, xuddi shunday Stars. `fulfil` o'zgarmaydi (xonalar qoralamada).

- [ ] Tests: `test_rooms_needed_formula` (`(30,5)→0`, `(31,5)→1`, `(40,7)→1`, `(41,5)→2`, `(30,8)→2`, `(130,25)→10`, `(131,0)` → `media_full`), `test_import_45_photos_creates_two_rooms` (`extra_rooms==2`, `limits.images==50`), `test_bundled_museum_order_amount` (2 xona → 21 000 so'm, 105 ⭐), `test_import_over_10_rooms_rejected_before_fetch` → FAIL → implement → PASS → commit `feat: rooms from import and one bundled museum payment`.

### Task 3: Frontend skeleti

**Files:** `frontend/package.json`, `vite.config.ts` (`base: process.env.VITE_BASE ?? "./"`, test env `happy-dom`), `tsconfig.json`, `index.html` (telegram-web-app.js `<script>` + Fraunces/Manrope shriftlari), `src/main.ts`, `App.vue`, `router.ts`, `styles.css` (namunadagi rang tokenlari, `prefers-color-scheme` + Telegram theme o'zgaruvchilari), `.env.example` (`VITE_API_URL=`); Test `frontend/tests/smoke.spec.ts`.

- [ ] Node.js LTS o'rnatish: `winget install OpenJS.NodeJS.LTS` → `node -v` ≥ 22.
- [ ] `npm create vite@latest` ishlatmasdan qo'lda fayllar; `npm i vue vue-router pinia vue-i18n qrcode` va `npm i -D vite @vitejs/plugin-vue typescript vue-tsc vitest @vue/test-utils happy-dom @types/qrcode`.
- [ ] Test `mounts the app with the home route` (`#/` → `App` render bo'ladi) → FAIL → implement → `npx vitest run` PASS; `npm run build` muvaffaqiyatli → commit `chore(frontend): scaffold Vite + Vue app`.

### Task 4: `telegram.ts` va `api.ts`

**Files:** Create `src/telegram.ts`, `src/api.ts`; Test `tests/telegram.spec.ts`, `tests/api.spec.ts`

**Interfaces — Produces:**
- `tg`: `{ available: boolean, initData: string, user: {id, first_name, language_code} | null, startParam: string | null, ready(), haptic(kind: "light"|"success"|"error"), mainButton(text: string, onClick: () => void): () => void /*cleanup*/, backButton(onClick): () => void, openInvoice(url): Promise<"paid"|"cancelled"|"failed"|"pending">, openTelegramLink(url), openLink(url), share(url, text) }`. SDK yo'q bo'lsa: `available=false`, tugma funksiyalari no-op cleanup qaytaradi, `openInvoice` → `"failed"`, `openLink` → `window.open`.
- `cloud`: `{ get(keys: string[]): Promise<Record<string,string>>, set(key, value): Promise<void>, remove(keys: string[]): Promise<void>, keys(): Promise<string[]> }` — SDK yo'q bo'lsa `localStorage` (prefiks `sahifa:`) zaxira.
- `api`: `class ApiError extends Error { code: string; status: number }`; `request<T>(path, init?) => Promise<T>` (`VITE_API_URL` + sarlavha); turlar `Me`, `Prices`, `MuseumFull`, `MuseumSummary`, `MediaOut`, `OrderOut`, `PublicMuseum` (backend `serialize.py`/`routes_*` maydonlari bilan bir xil); funksiyalar: `getMe`, `getPrices`, `listMuseums`, `getMuseum(id)`, `patchMuseum(id, changes)`, `deleteMuseum(id)`, `uploadServerMedia(id, file, {caption,taken_on}, onProgress)`, `deleteServerMedia(id, mid)`, `importMuseum(body)`, `createOrder(product, museumId|null, method)`, `getOrder(code)`, `uploadReceipt(code, file, onProgress)`, `createTransfer(id)`, `cancelTransfer(id)`, `publicMuseum(slug)`, `uploadTgMedia(file, purpose, onProgress) -> {token, kind}`, `tgMediaUrl(token) -> string`. Fayl yuklashlar `XMLHttpRequest` bilan (progress uchun).

- [ ] Tests: `falls back when the SDK is missing` (window.Telegram yo'q → `available=false`, `cloud` localStorage'ga yozadi), `wraps CloudStorage callbacks in promises` (soxta `CloudStorage.getItems(keys, cb)`), `sends initData header`, `maps {error} bodies to ApiError` (`409 {"error":"locked"}` → `code==="locked"`), `reports upload progress` (soxta XHR) → FAIL → implement → PASS → commit.

### Task 5: i18n va katalog

**Files:** Create `src/i18n/index.ts`, `uz.ts`, `ru.ts`, `src/catalog.ts`; Test `tests/i18n.spec.ts`

**Interfaces — Produces:** `THEMES`, `OPENINGS`, `MASCOTS`, `TEMPLATES` — `{ key, emoji, i18nKey }[]` (kalitlar spec §6a); `TEMPLATE_DEFAULTS: Record<TemplateKey, {theme, opening, letterKey}>`; `errorText(code: string): string` (`start_bot`, `too_large`, `media_full`, `locked`, `slots_full`, `media_gone`, `telegram_unavailable`, `bad_format`, `unauthorized`, boshqasi → umumiy). `setupI18n(languageCode?: string)` — `ru` → rus.

- [ ] Tests: `catalog keys match the backend contract` (aynan spec ro'yxatlari, hammasi `^[a-z0-9_]{1,32}$`), `every message key exists in uz and ru`, `picks russian only for ru` → FAIL → implement → PASS → commit.

### Task 6: Akkaunt-muzey xotirasi (CloudStorage)

**Files:** Create `src/account/rooms.ts`, `src/account/store.ts`; Test `tests/account-store.spec.ts`

**Interfaces:**
- Consumes: `cloud` (Task 4).
- Produces:
  - `type LocalMedia = { t: string; k: "image"|"video"; c?: string; d?: string }`
  - `type LocalMuseum = { id: string; v: 1; title; recipient; theme; mascot; opening; music_id?; voice?; music?; open_at?; template; created: number; letter: string; media: LocalMedia[]; gift?: { draft: number; state: "draft"|"paid" } }`
  - `roomsNeeded(images, videos): number` (backend bilan bir xil formula), `MAX_IMAGES=130`, `MAX_VIDEOS=25`.
  - `listMuseums(): Promise<LocalMuseum[]>` (idx tartibida, buzilgan yozuv o'tkazib yuboriladi), `loadMuseum(id)`, `newMuseum(template): LocalMuseum` (yozmaydi), `saveMuseum(m): Promise<void>`, `deleteMuseum(id): Promise<void>`.
  - `packPages(media: LocalMedia[], limit = 4000): string[]` — har bir sahifa `JSON.stringify` uzunligi ≤ limit.

- [ ] Tests: `round-trips a museum with 130 photos and 25 videos`, `packPages never exceeds 4000 chars`, `saveMuseum keeps the previous version when a page write fails` (soxta cloud 3-yozuvda xato → `loadMuseum` eski versiyani qaytaradi, `idx` o'zgarmagan), `shrinking a museum removes stale pages`, `delete removes all keys and the index entry last`, `roomsNeeded matches the backend table` (Task 2 jadvali) → FAIL → implement → PASS → commit.

**Atomiklik qoidasi:** yangi versiya sahifalari **yangi kalitlarga** yoziladi (`m_<id>_p<n>` o'rniga versiya qo'shimchasi: `m_<id>_<rev>p<n>`, `rev` = `m_<id>` dagi `rev+1`), keyin `m_<id>` (yangi `rev` va `pages` soni bilan), keyin `idx`, so'ng eski versiya sahifalari o'chiriladi. Kalit sxemasi spec'dagi `m_<id>_p<n>` dan shu qadar farq qiladi — Ruling sifatida yozing.

### Task 7: Yuklash navbati

**Files:** Create `src/upload/queue.ts`; Test `tests/queue.spec.ts`

**Interfaces — Produces:** `createQueue(send: (file: File, onProgress: (p: number) => void) => Promise<{token: string, kind: string}>, concurrency = 2)` → `{ items: Ref<QueueItem[]>, add(files: File[]): void, retry(id: string): void, remove(id: string): void }`; `QueueItem = { id, file, state: "waiting"|"uploading"|"done"|"error", progress: number, error?: string, result?: {token, kind} }`.

- [ ] Tests: `never runs more than two uploads at once`, `one failed upload does not stop the queue` (2-fayl `ApiError("start_bot")` → qolganlari `done`, 2-si `error` va `error==="start_bot"`), `retry re-sends a failed item` → FAIL → implement → PASS → commit.

### Task 8: Bosh sahifa va muzeylar ro'yxati

**Files:** Create `views/Home.vue`, `components/StatusBadge.vue`; Test `tests/home.spec.ts`

**Interfaces:** Consumes `listMuseums` (Task 6), `api.listMuseums`, `api.getMe` (Task 4). Ro'yxat: akkaunt-muzeylar (badge "Bepul · akkauntda" yoki `gift.state==="paid"` bo'lsa "🎁 Sovg'a qilingan · N kun") + akkauntda nusxasi yo'q server muzeylari (topshirib olinganlar). Hisoblagich `used/total` (`used` = akkaunt-muzeylar soni). To'la bo'lsa "Yangi muzey" → "+5 muzey" taklifi (`createOrder("slots", null, method)`).

- [ ] Tests: `shows account and server museums with the right badges`, `counter uses account museums and slots.total`, `full slots offer the +5 pack instead of a new museum` → FAIL → implement → PASS → commit.

### Task 9: Yaratish — suratlar, bezash, ko'rib chiqish

**Files:** Create `views/NewMedia.vue`, `NewDecor.vue`, `NewReview.vue`, `components/MediaGrid.vue`, `MediaEditor.vue`, `OptionPicker.vue`; Test `tests/create.spec.ts`

**Interfaces:** Consumes Task 5–7. Har o'zgarish `saveMuseum` (600 ms debounce). MediaGrid: tartiblash (yuqoriga/pastga tugmalar + sudrash), ★ = birinchi element. Hisoblagich 📷 n/130 · 🎬 n/25 va "+N xona" ko'rsatkichi. Bezash maydonlari Global Constraints chegaralari bilan; ochilish sanasi: kelajak va ≤ 120 kun. Ovoz: `MediaRecorder` mavjud bo'lsa yozish, aks holda fayl tanlash (`purpose=voice`). Ko'rib chiqish: 2D galereya (`tgMediaUrl`, `loading="lazy"`).

- [ ] Tests: `adding photos saves tokens to the museum`, `limits stop at 130 photos and 25 videos`, `shows rooms needed when over 30 photos`, `text fields enforce max lengths`, `open date must be within 120 days` → FAIL → implement → PASS → commit.

### Task 10: Sovg'a qilish, karta to'lovi, tayyor ekran

**Files:** Create `views/Gift.vue`, `Order.vue`, `Done.vue`, `components/PriceSummary.vue`, `QrCard.vue`; Test `tests/gift.spec.ts`

**Interfaces:** Consumes `getPrices`, `importMuseum`, `deleteMuseum(api)`, `createOrder`, `getOrder`, `uploadReceipt`, `tg.openInvoice`, `saveMuseum`.
- Oqim: `gift.state==="draft"` bo'lsa avval `api.deleteMuseum(gift.draft)` (404 e'tiborsiz) → `importMuseum` → `gift={draft:id,state:"draft"}` saqlash → `createOrder("museum", id, method)` → Stars: `openInvoice` → `"paid"` yoki so'rov orqali `status==="paid"` → `gift.state="paid"` → Done. Karta: `#/order/:code`.
- Order: karta raqami nusxalash, summa, kod, chek yuklash (progress), holat 3 s so'rov; `rejected` → sabab (`amount|unreadable|notfound` tarjimasi) + qayta yuborish; `paid` → Done.
- Done: havola (Global Constraints), QR (`qrcode` dynamic import, PNG yuklab olish), "Telegram'da yuborish" → `openTelegramLink("https://t.me/share/url?url=...")`.

- [ ] Tests: `summary adds rooms automatically` (45 rasm → 2 xona, narx `/api/prices` dan), `regifting deletes the unpaid draft first`, `stars payment marks the museum paid`, `card order shows rejection reason and allows resend`, `done screen builds the t.me link from bot_username` → FAIL → implement → PASS → commit.

### Task 11: Sovg'a qilingan muzey va akkaunt-muzey sahifalari

**Files:** Create `views/ServerMuseum.vue`, `LocalMuseum.vue`; Test `tests/museum-pages.spec.ts`

**Interfaces:** ServerMuseum (`#/museum/:id`): holat va muddat, havola/QR (QrCard), "Surat qo'shish" (`uploadServerMedia`, limit `limits`), media o'chirish, "Xona qo'shish" (`createOrder("room", id, method)` → Gift'dagi to'lov komponentlari), "Uzaytirish" (`reactivate`), "Topshirish" (`createTransfer` → havola nusxalash/yuborish; mavjud bo'lsa bekor qilish), "O'chirish" (tasdiq bilan). `locked===true` — sozlamalar faqat o'qish. LocalMuseum (`#/local/:id`): tahrirlash (Task 9 ekranlariga), "Sovg'a qilish", "O'chirish" (chatdagi fayllar qolishi aytiladi).

- [ ] Tests: `locked settings are read-only`, `transfer link can be copied and cancelled`, `deleting asks for confirmation` → FAIL → implement → PASS → commit.

### Task 12: Sovg'ani ko'rish (2D)

**Files:** Create `views/Viewer.vue`; Test `tests/viewer.spec.ts`

**Interfaces:** `#/m/:slug` → `publicMuseum(slug)`: `open` → nom, "kim uchun", maktub, galereya (izoh/sana), video, ovoz/musiqa tugmasi; `locked` → orqaga sanoq (har soniya); `expired` → xabar; 404 → "topilmadi"; pastda "O'zingiz ham yarating" (`https://t.me/<bot>`; bot nomi `VITE_BOT_USERNAME` dan). Ilova ishga tushganda `tg.startParam` `m_<slug>` bo'lsa shu sahifaga yo'naltiradi.

- [ ] Tests: `viewer works without Telegram SDK`, `locked shows a countdown and no media`, `start_param m_<slug> routes to the viewer` → FAIL → implement → PASS → commit.

### Task 13: Build, GitHub Pages workflow, hujjat

**Files:** Create `.github/workflows/pages.yml` (push → `npm ci && npm run build` (`VITE_BASE=/<repo>/`, `VITE_API_URL`, `VITE_BOT_USERNAME` repo secrets/vars'dan) → `actions/deploy-pages`), `frontend/README.md`.

- [ ] `npx vitest run` — hammasi PASS; `npm run build` — `dist/` hosil, asosiy JS gzip ≤ 200 KB (chiqishdagi o'lcham); `npx vite preview` + brauzerda `#/` va `#/m/test` ochiladi (Telegram'siz) → commit `chore: pages workflow and frontend docs`.
