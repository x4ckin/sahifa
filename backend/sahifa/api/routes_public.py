from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.api.auth import get_session, optional_user
from sahifa.api.routes_museums import _items
from sahifa.api.serialize import media_out, museum_settings
from sahifa.domain.lifecycle import DomainError, public_state
from sahifa.models import Museum, User

router = APIRouter()


@router.get("/public/m/{slug}")
async def view(
    slug: str, request: Request,
    user: User | None = Depends(optional_user), s: AsyncSession = Depends(get_session),
):
    """What a gift recipient sees. Never exposes ids, owner, or media before opening time."""
    settings = request.app.state.settings
    m = await s.scalar(select(Museum).where(Museum.slug == slug))
    if m is None:
        raise DomainError("not_found")
    state = public_state(m.status, m.open_at, m.expires_at, request.app.state.clock())
    is_owner = user is not None and user.id == m.owner_id

    if state == "deleted" or (state == "draft" and not is_owner):
        raise DomainError("not_found")
    if state == "expired":
        return {"state": "expired"}
    if state == "locked" and not is_owner:
        return {
            "state": "locked",
            "open_at": m.open_at.isoformat(),
            "opening_style": m.opening_style,
            "recipient_name": m.recipient_name,
            "title": m.title,
        }
    return {
        "state": state,
        "slug": m.slug,
        **museum_settings(settings, m),
        "media": [media_out(settings, i) for i in await _items(s, m.id)],
    }
