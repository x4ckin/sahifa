from sahifa.domain.pricing import Product
from sahifa.services.settings_store import set_price


async def test_prices_reflect_settings(client, sessionmaker):
    async with sessionmaker() as s:
        await set_price(s, Product.ROOM, "uzs", 4000)
        await s.commit()
    r = await client.get("/api/prices")  # no login needed
    assert r.status_code == 200
    assert r.json() == {
        "museum": {"uzs": 15000, "stars": 75},
        "reactivate": {"uzs": 15000, "stars": 75},
        "room": {"uzs": 4000, "stars": 15},
        "slots": {"uzs": 5000, "stars": 25},
    }


async def test_me_has_bot_username(client, auth, settings):
    assert (await client.get("/api/me", headers=auth(1))).json()["bot_username"] == settings.bot_username


def test_default_rate_limit_is_300():
    from sahifa.api.routes_tgmedia import RateLimiter

    assert RateLimiter().per_minute == 300
