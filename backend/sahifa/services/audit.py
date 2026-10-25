from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.models import AuditLog


async def log(s: AsyncSession, actor_id: int | None, action: str, **payload) -> None:
    s.add(AuditLog(actor_id=actor_id, action=action, payload=payload))
    await s.flush()
