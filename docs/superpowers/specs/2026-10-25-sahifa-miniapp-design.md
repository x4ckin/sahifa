# Sahifa — Mini App (2-reja) dizayni

_Sana: 2026-10-25. Asosiy dizayn: `2026-10-25-sahifa-design.md` (ayniqsa §4.1–4.12). Backend:
`backend/` (API tayyor). Ekranlar namunasi: `.superpowers/brainstorm/miniapp-ekranlar.html` (egasi tasdiqlagan)._

## 1. Maqsad
Telegram ichida ochiladigan Mini App: foydalanuvchi bepul muzey yasaydi (akkauntida saqlanadi),
uni bezaydi, xohlasa pul to'lab sovg'a qiladi (havola + QR), o'z muzeylarini boshqaradi.
3D ko'rinish va ochilish effektlari — 3-reja; bu reja ularning o'rnini oddiy 2D galereya bilan to'ldiradi,
shunda butun oqim boshidan oxirigacha ishlaydi.

**His:** iliq, "sovg'a" kayfiyati; hamma narsa bir-ikki bosishda; yuklanayotgani doim ko'rinadi.

## 2. Maqsadlar / maqsad emas / anti-maqsadlar
**Maqsadlar:** quyidagi barcha ekranlar (§4), o'zbek (lotin) + rus tillari, Telegram yorug'/qorong'i
rejimi, kuchsiz Android'da tez ochilish.

**Maqsad emas (bu rejada):** 3D sahna, ochilish animatsiyalari, qahramon modellari, yurakcha QR
dizayni (3-reja; bu yerda oddiy QR); Stories, referal, `/g/<slug>` preview havola, GitHub repo va
deploy (4-reja); sharh/fikr qoldirish (spec'da yo'q — namunadagi satr olib tashlanadi).

**Anti-maqsadlar:** foydalanuvchi faylni yuklayotganini bilmay qolishi; bepul muzey ma'lumoti
yo'qolishi (CloudStorage'ga yozilmay qolsa); to'langan muzeyda qulflangan maydonni tahrirlashga
ruxsat berib, keyin server xatosi bilan "jazolash"; 2 MB dan og'ir boshlang'ich yuklama.

## 3. Cheklovlar
- Hosting: GitHub Pages (statik), hash-router (`#/...`), `base` — repo nomi bilan sozlanadigan.
- Backend manzili build vaqtida `VITE_API_URL` dan.
- Telegram WebApp SDK: `telegram-web-app.js`; `initData` har so'rovda `X-Telegram-Init-Data` sarlavhasida.
- **Telegram CloudStorage chegaralari:** 1024 kalit, kalit ≤ 128 belgi `[A-Za-z0-9_-]`, qiymat ≤ 4096 belgi.
- Bepul muzey fayllari ≤ 20 MB (backend qayta ishlaganidan keyin); video ≤ 60 s.
- Kompyuterda Node.js yo'q — o'rnatiladi (LTS).

## 4. Ekranlar va oqimlar (egasi tasdiqlagan namuna asosida)
1. **Bosh sahifa** `#/` — hero + "Yangi muzey"; shablonlar (Tug'ilgan kun, Sevgi, Onamga, To'y,
   Bitiruv, 8-mart, Bo'sh); "Muzeylarim": akkaunt-muzeylar (yorliq "Bepul · akkauntda") va server
   muzeylari (yorliq "🎁 Sovg'a qilingan · N kun qoldi" / "Muddati tugagan"); `used / total` hisoblagich.
2. **Yangi muzey — 3 qadam** `#/new/:id/(media|decor|review)`:
   - *Suratlar:* tanlash (bir nechta), har biri `POST /api/tg-media` ga alohida yuklanadi (bir vaqtda
     2 ta), har birida progress; surib tartiblash; ★ muqova (birinchi element); bosilganda izoh (≤200)
     va sana (≤32); hisoblagich 📷 n/30 · 🎬 n/5; "fayllar Telegram chatingizda" eslatmasi.
     `start_bot` xatosi → "Botni ishga tushiring" oynasi + botga havola.
   - *Bezash:* kim uchun (≤60), nom (≤80), ko'rinish (6), ochilish (4), qahramon, musiqa (ro'yxat yoki
     o'z faylim → `purpose=music`), ovozli tabrik (yozib olish yoki fayl → `purpose=voice`),
     maktub (≤3000), ochilish sanasi (ixtiyoriy, kelajakda, ≤ 120 kun).
   - *Ko'rib chiqish:* 2D galereya (3D o'rni) + "Sovg'a qilish" + "Saqlash".
   Har o'zgarish darhol CloudStorage'ga yoziladi (debounce 600 ms).
3. **Sovg'a qilish** `#/gift/:id` — xulosa (muzey + kerakli qo'shimcha xonalar avtomatik: rasm >30
   yoki video >5 bo'lsa), Stars yoki karta. Bosilganda: `POST /api/museums/import` → server qoralamasi
   → `POST /api/orders` (muzey, keyin har xona uchun `room`) → Stars: `WebApp.openInvoice(link)`;
   karta: karta ekrani. To'lov tasdig'i `GET /api/orders/:code` ni 3 s da so'rab kutish.
4. **Karta orqali to'lov** `#/order/:code` — karta raqami (bosib nusxalash), egasi, summa, kod
   (izohga yozish), chek yuklash, "Tekshirilmoqda…", rad etilsa sabab + qayta yuborish.
5. **Tayyor** — havola `https://t.me/<bot>?start=m_<slug>`, oddiy QR (PNG yuklab olish),
   "Telegram'da yuborish" (`WebApp.openTelegramLink(share url)`), "Ochish".
6. **Muzey sahifasi** `#/museum/:serverId` (sovg'a qilingan) — holat, muddat, havola/QR, "Surat
   qo'shish" (`POST /api/museums/:id/media` — to'langan muzeyga to'g'ridan-to'g'ri), "Xona qo'shish
   (+3 000)", "Uzaytirish", "Topshirish" (havola nusxalash/yuborish), "O'chirish". Qulflangan
   sozlamalar faqat o'qish uchun ko'rinadi.
7. **Akkaunt-muzey sahifasi** `#/local/:id` — tahrirlash (3 qadamga qaytish), "Sovg'a qilish",
   "O'chirish" (CloudStorage'dan; chatdagi fayllar qoladi — aytiladi).
8. **Topshirib olish** — bot deep link orqali (backend tayyor); Mini App'da `#/my` yangilanadi.
9. **Sovg'ani ko'rish** `#/m/:slug` — `GET /api/public/m/:slug`: `open` → 2D galereya (izoh/sana,
   video, ovoz/musiqa tugmasi); `locked` → orqaga sanoq; `expired` → "muddati tugagan"; oxirida
   "O'zingiz ham yarating" (botga havola).
10. **Til** — `initDataUnsafe.user.language_code` (`ru` → rus, aks holda o'zbek); sozlamada almashtirish.

## 5. Bepul muzeyning CloudStorage sxemasi (mening qarorim)
- `idx` → `["a1b2c3", ...]` (lokal id: 6 belgi).
- `m_<id>` → `{v:1, title, recipient, theme, mascot, opening, music_id, voice, music, open_at,
  template, created, gifted: serverId|null}` (`voice`/`music` — media tokenlar).
- `m_<id>_l` → maktub matni (alohida, ≤ 3000).
- `m_<id>_p<n>` → media sahifalari: `[{t: token, k: kind, c: caption, d: taken_on}]`, har sahifa
  ≤ 4000 belgi bo'lguncha to'ldiriladi; tartib = sahifalar ketma-ketligi.
- Yozish tartibi: avval sahifalar, keyin `m_<id>`, oxirida `idx` — uzilish bo'lsa ham indeks
  buzilmaydi. O'chirish teskari tartibda.
- Muzeylar soni: akkaunt-muzeylar ≤ `slots.total` (`GET /api/me`); to'lsa — "+5 muzey (5 000)" taklifi (§6a).

## 6. Backend'ga qo'shimchalar (shu rejada)
- `GET /api/prices` → `{museum:{uzs,stars}, reactivate:{…}, room:{…}, slots:{…}}` (loginsiz).
- `GET /api/me` javobiga `bot_username` qo'shish (havola qurish uchun).
- **Katta bepul muzey (egasi qarori):** bepul muzeyga 30/5 dan ko'p media qo'shish mumkin —
  ko'pi bilan 10 qo'shimcha xona hajmigacha (**130 rasm, 25 video**; mening qarorim). Kerakli xonalar
  `rooms = max(ceil((rasm−30)/10), ceil((video−5)/2), 0)`.
- `POST /api/museums/import` media'ni xonalar bilan qabul qiladi: qoralama `extra_rooms = rooms`
  bilan yaratiladi (≤ 155 element). Limit tekshiruvi shu hajmga nisbatan.
- **Bitta to'lov:** `POST /api/orders` `{product:"museum", museum_id}` — summa = muzey + qoralamaning
  `extra_rooms` × xona narxi (so'm va Stars); to'langanda xonalar allaqachon qoralamada bo'ladi.
  Alohida `room` buyurtmalari kerak emas.

## 6a. Tekshiruvdan keyingi qarorlarim
- **Muzeylar hisobi:** bosh sahifadagi `used / total` = akkaunt-muzeylar soni / `slots.total`.
  Sovg'a qilingan muzey akkaunt nusxasi orqali bir marta sanaladi.
- **Qayta "Sovg'a qilish":** `m_<id>.gift = {draft: serverId, state: "draft"|"paid"}`. To'lanmagan
  qoralama bo'lsa — u o'chiriladi (`DELETE /api/museums/:id`) va yangidan import qilinadi.
  To'langandan keyin akkaunt nusxasi alohida, tahrirlanadigan bo'lib qoladi; sovg'a nusxasi
  `#/museum/:serverId` da boshqariladi.
- **Havola:** `https://t.me/<bot>?start=m_<slug>` (4-rejada `/g/<slug>` preview qo'shiladi).
- **Brauzerda ko'rish:** `#/m/:slug` Telegram'siz ham ishlaydi (`telegram.ts` SDK bo'lmasa
  zaxira: MainButton o'rniga oddiy tugma, CloudStorage kerak emas, mavzu — tizim rejimi).
- **Kalitlar (3-reja bilan shartnoma):**
  - mavzular: `gallery_light`, `gallery_night`, `oriental_palace`, `spring_garden`, `winter_tale`, `cosmos`
  - ochilish: `gift_box`, `sealed_letter`, `golden_key`, `starry_sky`
  - qahramonlar: `boy`, `girl`, `penguin`, `cat`, `puppy`, `bear`, `bunny`, `fox`, `robot`, `dragon`
  - shablonlar: `birthday`, `love`, `mom`, `wedding`, `graduation`, `march8`, `blank` — har biri
    mavzu, ochilish va maktub uchun tayyor matnni oldindan to'ldiradi (foydalanuvchi o'zgartira oladi).
- **Bepul muzey rasmlari:** ekranga kirganda yuklanadi (lazy), brauzer keshi 1 kun; galereyada bir
  vaqtda ≤ 4 so'rov. Backend IP limiti 300/daqiqaga ko'tariladi.

## 7. Mening texnik qarorlarim
- Vue 3 + Vite + TypeScript, Pinia (holat), vue-router (hash), vue-i18n, `qrcode` (QR), Vitest +
  @vue/test-utils (mantiq va komponent testlari, Telegram SDK soxta obyekt bilan). UI kutubxonasi
  yo'q — o'z CSS'imiz (namunadagi ranglar/shriftlar; shriftlar Google Fonts'dan, `display=swap`).
- Telegram integratsiyasi bitta modulda (`src/telegram.ts`): MainButton, BackButton, haptics,
  CloudStorage (promise o'rami), openInvoice, openTelegramLink, theme params → CSS o'zgaruvchilar.
- API mijozi bitta modulda (`src/api.ts`): xatolar `{error: code}` → tarjima qilingan xabar.
- `npm run build` → `dist/`; GitHub Actions workflow fayli tayyorlab qo'yiladi (ishga tushirish 4-rejada).

## 8. Quruvchiga qoldirilgan
Komponentlar bo'linishi, aniq CSS, ikonlar (emoji yetarli), animatsiya mayda-chuydalari, matnlarning
aniq so'zlari (Muzeycha matnlarini takrorlamasdan), musiqa ro'yxati tarkibi (bo'sh ro'yxat bilan
boshlash mumkin — 3-reja to'ldiradi).
