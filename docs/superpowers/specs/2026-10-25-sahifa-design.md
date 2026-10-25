# Sahifa — Telegram 3D muzey-sovg'a boti: dizayn

_Sana: 2026-10-25. Holat: foydalanuvchi bilan kelishilgan, rejalashtirishga tayyor._

## 1. Maqsad va nima uchun

Sahifa — har qanday Telegram foydalanuvchisi o'z rasm va videolaridan **3D virtual muzey** yasab,
uni yaqiniga **sovg'a** sifatida havola yoki QR orqali yuboradigan Telegram bot + Mini App.

G'oya @Muzeychabot'dan ilhomlangan (bu bot boshqa birovniki; uning kodi, nomi, dizayni yoki
fayllaridan **foydalanilmaydi** — hammasi noldan, o'zimizniki). Sahifa undan quyidagilar bilan ustun:
to'lovdan keyin ham rasm/video qo'shish, muzeyni boshqa odamga topshirish, xonalarni sotib olib kengaytirish, ko'p qahramon va ko'rinishlar,
va eng muhimi — **sovg'a ochilish tajribasi**.

**Asosiy his (egasi aytgan):** havolani ochgan odam _hayratlanadi va bu sovg'a aynan u uchun
tayyorlanganini his qiladi_.

**Muvaffaqiyat:** foydalanuvchilar soni o'sishi (virusli tarqalish: ko'ruvchi → yaratuvchi) va
to'lovlar.

## 2. Maqsadlar / maqsad emas / anti-maqsadlar

**Maqsadlar (1-versiya)**
- Hamma uchun ochiq: istalgan Telegram foydalanuvchisi muzey yarata oladi.
- Ko'rish har doim bepul (havola orqali, Telegram ichida va oddiy brauzerda).
- To'lov: Telegram Stars + kartaga o'tkazma (chekni admin tasdiqlaydi).
- Quyidagi barcha xususiyatlar (§4).

**Maqsad emas (hozircha)**
- Payme / Click / Uzum integratsiyasi — keyin, egasi YaTT/MChJ ochgach. Lekin to'lov qatlami
  yangi provayderni qo'shish oson bo'ladigan qilib yoziladi.
- Email/parol bilan akkaunt (Muzeycha'dagidek). Shaxs faqat Telegram orqali aniqlanadi.
- Telegram'dan tashqarida (oddiy saytda) muzey **yaratish**. Saytda faqat ko'rish.
- Sirli xona, mehmonlar kitobi, birgalikda to'ldirish — 2-versiya.
- .uz domen — keyin; hozircha GitHub Pages + Tailscale Funnel.

**Anti-maqsadlar (texnik ishlasa ham muvaffaqiyatsizlik)**
- Muzeycha'ning nomi, matnlari, dizayni, 3D modellarini ko'chirish.
- Kuchsiz telefonda muzey sekin ochilishi yoki qotishi (auditoriya asosan o'rta/arzon Android).
- Pul to'langan, lekin kontent yo'qolishi yoki muzey ochilmasligi.
- Chek tekshirilmasdan avtomatik "to'landi" bo'lishi.
- Ko'ruvchidan ro'yxatdan o'tish yoki pul talab qilish.

## 3. Cheklovlar

- **Server:** egasining uyidagi Ubuntu server, router ortida (ochiq IP yo'q).
  HTTPS manzil **Tailscale Funnel** orqali (`<host>.<tailnet>.ts.net`). Server tarmoq
  o'tkazuvchanligi haqida egasi "o'ylama" dedi — optimallashtirish qilinadi, lekin cheklov emas.
- **Frontend hosting:** GitHub Pages (`<user>.github.io/sahifa`), bepul, HTTPS.
- **Domen yo'q** — keyin .uz olinadi; API manzili va sayt manzili bitta konfiguratsiyada
  turishi va almashtirish oson bo'lishi shart.
- **Bot tokeni bor.** Payme merchant yo'q. YaTT/MChJ yo'q.
- Byudjet ≈ 0 (bepul xizmatlar).

## 4. Mahsulot — egasi kelishgan qismlar

### 4.1 Narxlar va limitlar (egasi belgilagan)

| Mahsulot | Narx | Nima beradi |
|---|---|---|
| Muzey (asosiy) | 15 000 so'm | 30 rasm + 5 video, 120 kun |
| Qayta faollashtirish | 15 000 so'm | yana 120 kun |
| Qo'shimcha xona | 3 000 so'm | +1 xona, +10 rasm, +2 video |
| Muzey limiti kengaytmasi | 5 000 so'm | +5 ta muzey ochish huquqi |
| Ko'rish | bepul | — |

- Foydalanuvchi boshida **10 tagacha** muzey ocha oladi; har 5 000 so'm +5 ta.
- **To'lovdan keyin faqat rasm/video qo'shish yoki olib tashlash** mumkin (egasi belgilagan).
  Bitta to'lov bilan muzeyni boshqa odamga qayta sovg'a qilib bo'lmasligi uchun qolgan
  shaxsiy sozlamalar qulflanadi. _(Mening qarorim, nima qulflanadi: oluvchi ismi, muzey nomi,
  ochilish uslubi, maktub matni, ovozli tabrik, mavzu, qahramon, musiqa, ochilish sanasi.
  Ochiq qoladi: rasm/video qo'shish va olib tashlash, ularning izoh va sanasi, tartibi,
  qo'shimcha xona sotib olish.)_
- **Muzeyni boshqa odamga topshirish (egasi so'ragan):** yaratuvchi (admin ham, oddiy
  foydalanuvchi ham) muzeyni boshqa Telegram foydalanuvchisiga **egalik bilan berib yuboradi**.
  Masalan, admin buyurtmachi uchun muzeyni o'zi yasaydi va unga topshiradi. Jarayon: "Topshirish"
  → bir martalik topshirish havolasi → qabul qiluvchi botda ochib "Qabul qilish"ni bosadi →
  muzey uning "Muzeylarim"iga o'tadi, avvalgi egadan chiqadi. Yangi ega rasm/video qo'shadi
  yoki olib tashlaydi, xona sotib oladi, qayta faollashtiradi; muzey havolasi o'zgarmaydi.
  _(Mening qarorlarim: havola 7 kun amal qiladi va bekor qilinishi mumkin; topshirilgan muzey
  yangi egasining 10 ta muzey limitiga kirmaydi; qoralama ham, to'langan muzey ham topshirilishi
  mumkin — qoralamani yangi ega o'zi to'laydi.)_
- Stars narxlari: admin har bir mahsulot uchun alohida belgilaydi (so'm bilan qat'iy bog'lanmaydi).

### 4.2 Yaratish oqimi
1. Bot `/start` → salom + **"Muzey yaratish"** va **"Muzeylarim"** (WebApp tugmalar), menyu tugmasi ham Mini App.
2. Mini App: shablon tanlash (yoki bo'sh) → rasm/video tanlash → **darhol bepul 3D ko'rish**.
3. Sozlash: nom, ko'rinish (mavzu), qahramon, ochilish uslubi, musiqa, ovozli tabrik,
   rasm izohlari va sanalari, kim uchun (oluvchi ismi), ochilish vaqti.
4. "Yuborish" → to'lov (Stars yoki karta) → havola + QR + Stories'ga ulashish.

### 4.3 Sovg'a ochilish tajribasi (eng muhim qism)
Yaratuvchi muzey uchun 4 ochilish uslubidan birini tanlaydi (namunalar:
`.superpowers/brainstorm/ochilish-lahzasi.html`):
- **A. Sovg'a qutisi** — ism yozilgan quti, bosilganda qopqoq uchadi, konfetti, muzey ochiladi.
- **B. Muhrlangan maktub** — muhr ochiladi, yuboruvchining xati (yoki ovozli tabrik), keyin muzey.
- **C. Oltin kalit** — eshik tepasida oluvchi ismi, kalit buraladi, eshiklar yorug'lik bilan ochiladi.
- **D. Yulduzli osmon** — ism yulduzlardan yoziladi, kamera muzeyga tushadi.

Ochilish ekranining birinchi bosilishi brauzerda ovoz/musiqani yoqish uchun ham ishlatiladi.

### 4.4 1-versiya xususiyatlari (egasi tasdiqlagan)
1. **Ovozli tabrik** — yuboruvchi yozib oladi (botga voice yoki Mini App'da yozish); kirishda yoki tanlangan rasm oldida eshitiladi.
2. **Fon musiqasi** — tayyor kutubxonadan (litsenziyasi erkin kuylar) yoki o'z MP3'i.
3. **Rasm ostida izoh va sana** — ramka ostidagi plakat.
4. **Belgilangan kunda ochilish** — tanlangan sana/soatgacha havola orqaga sanoq ko'rsatadi.
5. **"Rahmat" javobi** — ko'ruvchi yurakcha yoki qisqa matn qoldiradi → yaratuvchiga botda bildirishnoma.
6. **Bayram shablonlari** — tug'ilgan kun, sevgi, onamga, to'y, bitiruv, 8-mart (mavzu + musiqa + ochilish + bezak + tayyor matn to'plami).

### 4.5 Qahramonlar (10)
Odamcha, qizcha, pingvin, mushuk, kuchukcha, ayiqcha, quyon, tulki, robot, ajdarcha.
Erkin litsenziyali (CC0 yoki shunga o'xshash) tayyor 3D modellar; yurish/turish/o'tirish animatsiyasi.
Ro'yxat serverdagi manifestdan o'qiladi — yangi qahramon kod o'zgartirmasdan qo'shiladi.

### 4.6 Muzey ko'rinishlari (6)
Yorug' galereya, Tungi galereya, **Sharqona saroy** (o'zbek naqshlari, koshin, gumbaz),
Bahorgi bog', Qishki ertak, Kosmos. Har biri: devor/pol/yorug'lik/bezaklar + o'tirish joyi.
Muzey xonalardan iborat; xonalar soni sotib olingan xonalarga bog'liq.

### 4.7 3D ichida
Telefonda joystik, kompyuterda WASD/strelkalar; o'tirish/turish; rasmni bosib katta ko'rish
va varaqlash; videolar ramkada o'ynaydi; ovozni yoqish/o'chirish.

### 4.8 O'sish (virusli) mexanikalari
- Ko'ruvchiga oxirida **"O'zingiz ham yarating"** (botga deep link).
- **Telegram Stories'ga ulashish** (Mini App `shareToStory`, muzey muqovasi rasmi bilan).
- **Referal:** taklif havolasi; taklif qilingan do'st birinchi to'lovini qilsa, taklif qilgan
  odamga **bepul qo'shimcha xona** (bitta muzeyiga) beriladi.
- **Bayram eslatmalari:** botni boshlagan foydalanuvchilarga bayramdan oldin xabar
  (masalan "8-martga 3 kun qoldi"); foydalanuvchi o'chirib qo'ya oladi.

### 4.9 Til
O'zbek (lotin) — asosiy; rus. Til Telegram tilidan aniqlanadi, almashtirsa bo'ladi.

### 4.10 To'lov
- **Telegram Stars:** Mini App ichida invoice (`currency = XTR`). To'lov tasdig'i bot
  `successful_payment` hodisasi orqali; shundan keyingina huquq beriladi.
- **Kartaga o'tkazma:** foydalanuvchi mahsulotni tanlaydi → karta raqami, summa va **noyob
  buyurtma kodi** ko'rsatiladi → u chek rasmini yuklaydi → admin guruhiga chek + ma'lumot +
  **✅ Tasdiqlash / ❌ Rad etish** tugmalari → tasdiqlansa huquq beriladi va foydalanuvchiga xabar.
  Rad etilsa, sababi bilan xabar. Karta raqami(lari) admin sozlamasida.
- To'lov qatlami provayderga bog'liq bo'lmagan "buyurtma → to'landi → huquq berish" modeli;
  Payme/Click keyin shu modelga ulanadi.

### 4.11 Admin (bot ichida)
Cheklarni tasdiqlash/rad etish, narxlarni (so'm va Stars) va karta raqamini o'zgartirish,
statistika (foydalanuvchilar, muzeylar, to'lovlar, daromad), ommaviy xabar, Stars qaytarish.
Adminlar ro'yxati konfiguratsiyada.

**Bepul foydalanuvchilar (egasi so'ragan):** admin istalgan foydalanuvchiga (Telegram ID yoki
@username, yoki uning xabarini forward qilib) **"bepul" maqomi** bera oladi. Bunday foydalanuvchi
barcha pullik amallarni to'lovsiz bajaradi: muzey yaratish, qo'shimcha xona, qayta faollashtirish;
muzeylar soni limiti ham unga qo'llanmaydi. Uning muzeylari to'lov sahifasini chetlab o'tib darhol
faol bo'ladi. Admin bu maqomlilar ro'yxatini ko'radi va istalgan payt bekor qiladi; ixtiyoriy
ravishda amal qilish muddatini (masalan 30 kun) belgilash mumkin. Har bir berish/bekor qilish
qaydga yoziladi. _(Mening qarorim: fayl hajmi va rasm/video limitlari xona bo'yicha amal qiladi —
bepul foydalanuvchi ko'proq joy uchun xonalarni bepul qo'shadi; muzeylar soniga cheklov yo'q.)_

### 4.12 Bepul muzey Telegram akkauntida (egasi qarori, 2026-10-25)

To'lanmagan muzey **serverda saqlanmaydi** — u foydalanuvchining Telegram akkauntida yashaydi va
istalgan qurilmada (telefon, kompyuter) ochiladi; egasining o'zi uchun **muddatsiz va bepul**.

- **Sozlamalar** (nom, mavzu, qahramon, ochilish uslubi, maktub, media tartibi/izoh/sana va
  media identifikatorlari) — Mini App **Telegram CloudStorage**'ida (har foydalanuvchiga,
  ~4 MB, serverga tegmaydi).
- **Rasm/video/ovoz** — foydalanuvchining **bot bilan chatiga** yuboriladi (Telegram serverlarida
  turadi). Yuklash Mini App'dan: fayl server orqali o'tadi, bot uni foydalanuvchi chatiga yuboradi
  va server nusxasini **darhol o'chiradi**. Server faqat `file_id`ni imzolab (HMAC) qaytaradi.
- **Ko'rish:** Mini App media'ni `GET /api/tg-media/<imzolangan file_id>` orqali oladi; server
  Telegram'dan olib **saqlamasdan uzatadi** (bot tokeni telefonga berilmaydi). Imzo faqat shu
  foydalanuvchiga tegishli `file_id`ni ochadi. Bepul muzey diskda joy egallamaydi.
- **Sovg'a qilish (to'lov):** to'lov tasdiqlangach server media'ni Telegram'dan yuklab olib,
  oddiy (§4.1) to'langan muzeyga aylantiradi: havola, QR, 120 kun. Telefondagi/akkauntdagi bepul
  nusxa o'zgarmay qoladi.
- **Cheklovlar:** Bot API faqat ≤ 20 MB faylni yuklab bera oladi — bepul muzeyda video ≤ 20 MB
  (aks holda sovg'aga aylantirib bo'lmaydi). Foydalanuvchi bot chatini o'chirsa, bepul muzey
  media'si yo'qoladi — ilovada ogohlantiriladi.
- 10 ta muzey limiti (§4.1) bepul akkaunt-muzeylarga ham taalluqli (CloudStorage hajmi ham
  shuni talab qiladi). Serverda qoralama faqat to'lov jarayonida paydo bo'ladi (`POST /api/museums/import`); u to'lanmasa 7 kundan keyin o'chiriladi — akkauntdagi bepul nusxa saqlanib qoladi.

## 5. Mening qarorlarim (egasi so'ramagan; o'zgartirish mumkin)

- **Stack:** backend — Python (aiogram 3 bot + FastAPI API) bitta loyihada; ma'lumotlar bazasi
  — SQLite (WAL rejimi) — uy serveri va zaxira uchun eng sodda; media — server diskida.
  Frontend — Vue 3 + Vite + TypeScript + Three.js, GitHub Pages'ga GitHub Actions orqali deploy.
  Server — Docker Compose bilan.
- **Kirish:** Mini App `initData` imzosi server tomonda tekshiriladi; boshqa login yo'q.
  Ko'rish sahifasi login talab qilmaydi.
- **Havolalar:** `https://t.me/<bot>/app?startapp=m_<slug>` (Telegram ichida) va
  `https://<user>.github.io/sahifa/#/m/<slug>` (oddiy brauzer). Slug taxmin qilib bo'lmaydigan.
- **Asosiy muzey = 3 xona** (har birida 10 rasm o'rni; videolar xonalar bo'ylab). Qo'shimcha
  xona +10/+2 bilan bu mantiq izchil bo'ladi.
- **Holatlar va muddatlar:**
  - _Qoralama_ (to'lanmagan): faqat egasi ko'radi; **7 kun** o'zgarishsiz tursa o'chiriladi.
  - _Faol_: to'lovdan 120 kun.
  - _Muddati tugagan_: havola "muddati tugagan" + "qayta faollashtirish"ni ko'rsatadi; kontent
    yana **30 kun** saqlanadi, keyin o'chadi. Tugashidan 7 va 1 kun oldin egasiga eslatma.
  - Qayta faollashtirish muddat tugashidan oldin ham mumkin (qolgan kunlarga +120 qo'shiladi).
- **10 muzey limiti** qoralama + faol + muddati tugaganlarni sanaydi (o'chirilganlarni emas).
- **Fayl limitlari:** rasm ≤ 15 MB (serverda WebP'ga, uzun tomoni ≤ 2048px + kichik nusxa);
  video ≤ 50 MB, ≤ 60 soniya (serverda ffmpeg bilan 720p H.264'ga); o'z musiqa MP3 ≤ 10 MB;
  ovozli tabrik ≤ 2 daqiqa.
- **QR:** yurakcha shaklidagi va oddiy QR, PNG yuklab olish va botga yuborish.
- **Unumdorlik:** 3D sahna kuchsiz telefonda ham ochilishi uchun: kam poligonli modellar,
  rasmlar ko'ruvchi yaqinlashganda yuklanadi, tekstura o'lchami qurilmaga moslanadi,
  ochilish ekrani paytida fon yuklash.
- **Zaxira:** har kecha SQLite + media zaxirasi (serverdagi alohida diskka yoki papkaga);
  tiklash yo'riqnomasi.
- **Huquqiy:** bot va saytda ommaviy oferta va maxfiylik sahifasi (yuklangan kontent uchun
  foydalanuvchi javobgar; shikoyat qilish tugmasi; admin kontentni o'chira oladi).

- **Qahramon roli:** qahramon — ko'ruvchining o'zi (uchinchi shaxs kamerasi; ko'ruvchi uni
  joystik/WASD bilan yuritadi, o'tqazadi). Yaratuvchi tanlagan qahramonni ko'ruvchi ham oladi.
- **Qahramon modellari:** imkon qadar bitta uslubdagi bepul to'plamdan, iloji bo'lsa umumiy
  skelet/animatsiyalar bilan (yengil bo'lishi uchun). Hammasi topilmasa — ishga tushishda
  kamida 6 tasi, qolganlari keyin manifest orqali qo'shiladi. Uslublar aralashmasligi kerak.
- **120 kun qachon boshlanadi:** to'lov paytidan; agar belgilangan ochilish sanasi bo'lsa —
  **ochilish sanasidan**. Ochilish sanasi to'lovdan ko'pi bilan 120 kun keyin bo'lishi mumkin.
- **Havola ko'rinishi (preview):** chatda yuboriladigan havola uy serveri orqali beriladi
  (`https://<host>.ts.net/g/<slug>`): u har bir muzey uchun alohida preview (masalan
  "Malika uchun sovg'a 💝" + muqova rasmi) beradi va darhol GitHub Pages'dagi muzeyga
  yo'naltiradi. .uz domen olingach, shu yo'l domenga ko'chadi.

## 6. Quruvchiga qoldirilgan
- Aniq 3D modellar manbai (litsenziya talabiga javob bersa), musiqa kutubxonasi tarkibi.
- Har bir mavzu va shablonning aniq vizual dizayni (yuqoridagi kayfiyatga mos).
- Ma'lumotlar bazasi sxemasi, API yo'llari, kod tuzilishi, testlar.
- Bot va Mini App matnlari (o'zbekcha/ruscha), Muzeycha matnlarini takrorlamasdan.
