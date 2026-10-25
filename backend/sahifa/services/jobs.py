"""Once-a-day housekeeping: stale drafts, expiry, reminders, purge."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.domain.lifecycle import MuseumState
from sahifa.domain.pricing import DRAFT_TTL_DAYS, EXPIRED_RETENTION_DAYS, REMINDER_DAYS
from sahifa.models import Museum, Order
from sahifa.services.museums import delete_museum

log = logging.getLogger(__name__)
Notify = Callable[[int, str], Awaitable[None]]

REMINDER_TEXT = (
    "⏳ «{title}» muzeyingiz saqlanish muddati {days} kundan keyin tugaydi.\n"
    "Sovg'angiz ochilib turishi uchun «Muzeylarim» bo'limida muddatni uzaytiring."
)
# orders that mean money was paid or sent for this museum: never auto-delete those drafts
_MONEY_STATUSES = ("paid", "awaiting_review", "reviewing")


async def _museums(s: AsyncSession, *where) -> list[Museum]:
    return list((await s.scalars(select(Museum).where(*where))).all())


async def run_daily(s: AsyncSession, now: datetime, notify: Notify, media_dir: Path) -> dict:
    report = {"drafts_deleted": 0, "expired": 0, "reminded": 0, "purged": 0}

    has_money = exists().where(Order.museum_id == Museum.id, Order.status.in_(_MONEY_STATUSES))
    for m in await _museums(
        s, Museum.status == MuseumState.DRAFT, Museum.updated_at < now - timedelta(days=DRAFT_TTL_DAYS), ~has_money
    ):
        await delete_museum(s, m, now, media_dir=media_dir)
        report["drafts_deleted"] += 1

    for m in await _museums(s, Museum.status == MuseumState.ACTIVE, Museum.expires_at <= now):
        m.status = MuseumState.EXPIRED
        report["expired"] += 1

    horizon = now + timedelta(days=max(REMINDER_DAYS))
    for m in await _museums(s, Museum.status == MuseumState.ACTIVE, Museum.expires_at <= horizon):
        done = set(filter(None, m.reminded_days.split(",")))
        due = [d for d in REMINDER_DAYS if m.expires_at - now <= timedelta(days=d)]
        if not due or set(map(str, due)) <= done:
            continue
        closest = min(due)
        try:
            await notify(m.owner_id, REMINDER_TEXT.format(title=m.title, days=closest))
            report["reminded"] += 1
        except Exception:  # a blocked owner must not stop the job
            log.warning("reminder to %s failed", m.owner_id, exc_info=True)
        m.reminded_days = ",".join(sorted(done | set(map(str, due))))

    for m in await _museums(
        s, Museum.status == MuseumState.EXPIRED, Museum.expires_at < now - timedelta(days=EXPIRED_RETENTION_DAYS)
    ):
        await delete_museum(s, m, now, media_dir=media_dir)
        report["purged"] += 1

    await s.flush()
    return report
