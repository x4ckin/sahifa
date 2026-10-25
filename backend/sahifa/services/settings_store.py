from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.domain.pricing import DEFAULT_PRICES_STARS, DEFAULT_PRICES_UZS, Product
from sahifa.models import Setting

Currency = Literal["uzs", "stars"]
_DEFAULTS = {"uzs": DEFAULT_PRICES_UZS, "stars": DEFAULT_PRICES_STARS}


async def _get(s: AsyncSession, key: str, default):
    row = await s.get(Setting, key)
    return default if row is None else row.value


async def _set(s: AsyncSession, key: str, value) -> None:
    row = await s.get(Setting, key)
    if row is None:
        s.add(Setting(key=key, value=value))
    else:
        row.value = value
    await s.flush()


async def get_price(s: AsyncSession, product: Product, currency: Currency) -> int:
    return int(await _get(s, f"price:{currency}:{product}", _DEFAULTS[currency][product]))


async def set_price(s: AsyncSession, product: Product, currency: Currency, value: int) -> None:
    if value < 1:
        raise ValueError("price must be positive")
    await _set(s, f"price:{currency}:{product}", value)


async def get_cards(s: AsyncSession) -> list[dict]:
    return list(await _get(s, "cards", []))


async def set_cards(s: AsyncSession, cards: list[dict]) -> None:
    await _set(s, "cards", cards)
