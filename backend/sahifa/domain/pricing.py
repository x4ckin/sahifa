from enum import StrEnum


class Product(StrEnum):
    MUSEUM = "museum"
    REACTIVATE = "reactivate"
    ROOM = "room"
    SLOTS = "slots"


BASE_ROOMS = 3
BASE_IMAGES = 30
BASE_VIDEOS = 5
ROOM_IMAGES = 10
ROOM_VIDEOS = 2

ACTIVE_DAYS = 120
DRAFT_TTL_DAYS = 7
EXPIRED_RETENTION_DAYS = 30
REMINDER_DAYS = (7, 1)

BASE_SLOTS = 10
SLOT_PACK = 5
TRANSFER_TTL_DAYS = 7

DEFAULT_PRICES_UZS: dict[Product, int] = {
    Product.MUSEUM: 15000,
    Product.REACTIVATE: 15000,
    Product.ROOM: 3000,
    Product.SLOTS: 5000,
}

DEFAULT_PRICES_STARS: dict[Product, int] = {
    Product.MUSEUM: 75,
    Product.REACTIVATE: 75,
    Product.ROOM: 15,
    Product.SLOTS: 25,
}

PRODUCT_TITLES_UZ: dict[Product, str] = {
    Product.MUSEUM: "Muzey (120 kun)",
    Product.REACTIVATE: "Qayta faollashtirish (120 kun)",
    Product.ROOM: "Qo'shimcha xona",
    Product.SLOTS: "+5 muzey ochish huquqi",
}
