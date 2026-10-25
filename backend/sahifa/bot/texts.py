"""User-facing bot copy (Uzbek, Latin). Russian arrives with the Mini App plan."""

WELCOME = (
    "Assalomu alaykum, {name}! 🎁\n\n"
    "<b>Sahifa</b> — suratlaringiz va videolaringizdan yaqiningiz uchun "
    "jonli 3D sovg'a-muzey yaratadi.\n\n"
    "1️⃣ Suratlarni tanlang — muzey bir zumda quriladi\n"
    "2️⃣ Qahramon, ko'rinish, musiqa va ochilish uslubini tanlang\n"
    "3️⃣ Havola yoki QR orqali sovg'a qiling — ochgan odam hayratda qoladi ✨"
)
BTN_CREATE = "🎁 Sovg'a-muzey yaratish"
BTN_MY = "📂 Muzeylarim"
BTN_OPEN_MUSEUM = "🏛 Muzeyni ochish"
OPEN_MUSEUM = "Sizga atalgan muzey shu yerda 👇"

TRANSFER_OFFER = (
    "🎁 <b>{giver}</b> sizga «{title}» muzeyini topshirmoqchi.\n"
    "Qabul qilsangiz, muzey sizning «Muzeylarim» bo'limingizga o'tadi."
)
BTN_ACCEPT = "✅ Qabul qilish"
BTN_DECLINE = "✖️ Rad etish"
TRANSFER_ACCEPTED = "✅ «{title}» muzeyi endi sizniki!"
TRANSFER_DECLINED = "Topshirish rad etildi."
TRANSFER_DONE_GIVER = "✅ «{title}» muzeyini {taker} qabul qildi."
ERRORS = {
    "transfer_invalid": "Bu topshirish havolasi yaroqsiz yoki allaqachon ishlatilgan.",
    "transfer_expired": "Bu topshirish havolasining muddati tugagan.",
    "transfer_self": "O'z muzeyingizni o'zingizga topshira olmaysiz 🙂",
}

PRECHECKOUT_FAIL = "Bu buyurtma eskirgan. Iltimos, ilovadan qaytadan to'lovni oching."
PAID = "✅ To'lov qabul qilindi! «{product}» faollashtirildi."
PAYMENT_REFUNDED = (
    "Bu to'lov qayta yuborilgan yoki muzey o'chirilgan edi — yulduzlaringiz qaytarildi."
)
