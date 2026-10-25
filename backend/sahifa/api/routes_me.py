from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.api.auth import current_user, get_session
from sahifa.models import User
from sahifa.services.users import is_free_now, slots_status

router = APIRouter()


@router.get("/me")
async def me(request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    now = request.app.state.clock()
    used, total = await slots_status(s, user, now)
    return {
        "id": user.id,
        "first_name": user.first_name,
        "lang": user.lang,
        "is_free": is_free_now(user, now),
        "slots": {"used": used, "total": total},
    }
