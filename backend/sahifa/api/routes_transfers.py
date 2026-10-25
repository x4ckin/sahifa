from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.api.auth import current_user, get_session
from sahifa.api.routes_museums import _full
from sahifa.models import User
from sahifa.services import museums
from sahifa.services import transfers as svc

router = APIRouter()


def transfer_link(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start=tr_{token}"


@router.post("/museums/{museum_id}/transfer")
async def create(museum_id: int, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    m = await museums.get_owned(s, user, museum_id)
    t = await svc.create_transfer(s, m, user, request.app.state.clock())
    await s.commit()
    return {
        "link": transfer_link(request.app.state.settings.bot_username, t.token),
        "expires_at": t.expires_at.isoformat(),
    }


@router.delete("/museums/{museum_id}/transfer")
async def cancel(museum_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    m = await museums.get_owned(s, user, museum_id)
    t = await svc.pending_transfer(s, m)
    if t is not None:
        await svc.cancel_transfer(s, t, user)
        await s.commit()
    return {"ok": True}


@router.post("/transfers/{token}/accept")
async def accept(token: str, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    m = await svc.accept_transfer(s, token, user, request.app.state.clock())
    await s.commit()
    return await _full(request, s, m)
