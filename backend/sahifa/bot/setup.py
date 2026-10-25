from collections.abc import Callable
from datetime import UTC, datetime

from aiogram import BaseMiddleware, Dispatcher
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.ext.asyncio import async_sessionmaker

from sahifa.config import Settings

BOT_DEFAULTS = DefaultBotProperties(parse_mode="HTML")


class SessionMiddleware(BaseMiddleware):
    """Gives each handler its own `session`; handlers commit explicitly."""

    def __init__(self, sessionmaker: async_sessionmaker):
        self.sessionmaker = sessionmaker

    async def __call__(self, handler, event, data):
        async with self.sessionmaker() as session:
            data["session"] = session
            return await handler(event, data)


def build_dispatcher(
    sessionmaker: async_sessionmaker,
    settings: Settings,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Dispatcher:
    from sahifa.bot import payments, start

    dp = Dispatcher(settings=settings, clock=clock)
    dp.update.outer_middleware(SessionMiddleware(sessionmaker))
    dp.include_routers(start.router, payments.router)
    return dp
