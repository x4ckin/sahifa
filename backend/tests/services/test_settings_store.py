from sahifa.domain.pricing import Product
from sahifa.services.settings_store import get_cards, get_price, set_cards, set_price


async def test_prices_default_then_override(session):
    assert await get_price(session, Product.MUSEUM, "uzs") == 15000
    assert await get_price(session, Product.ROOM, "stars") == 15
    await set_price(session, Product.MUSEUM, "uzs", 17000)
    assert await get_price(session, Product.MUSEUM, "uzs") == 17000
    assert await get_price(session, Product.MUSEUM, "stars") == 75


async def test_cards_roundtrip(session):
    assert await get_cards(session) == []
    cards = [{"number": "8600 1234 5678 9012", "holder": "Ali Valiyev"}]
    await set_cards(session, cards)
    assert await get_cards(session) == cards
