from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.api.auth import get_session
from sahifa.domain.pricing import Product
from sahifa.services.settings_store import get_price

router = APIRouter()


@router.get("/prices")
async def prices(s: AsyncSession = Depends(get_session)):
    """Current prices for the Mini App's summaries (public)."""
    return {
        p.value: {"uzs": await get_price(s, p, "uzs"), "stars": await get_price(s, p, "stars")}
        for p in Product
    }
