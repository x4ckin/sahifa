"""Run the API, the bot and the daily jobs in one process: `python -m sahifa.main`."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.types import MenuButtonWebApp, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from sahifa.api.app import create_app
from sahifa.bot.payments import make_stars_invoice_link
from sahifa.bot.review import make_receipt_notifier
from sahifa.bot.setup import BOT_DEFAULTS, build_dispatcher
from sahifa.bot.tgfiles import make_tg_fetcher, make_tg_uploader
from sahifa.config import Settings, get_settings
from sahifa.db import init_db, make_engine, make_sessionmaker
from sahifa.services.jobs import run_daily

log = logging.getLogger("sahifa")
TASHKENT = timezone(timedelta(hours=5))
DAILY_HOUR = 3  # 03:00 Tashkent time


@dataclass
class Runtime:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    bot: Bot
    dp: Dispatcher
    app: object


def build(settings: Settings) -> Runtime:
    if settings.database_url.startswith("sqlite") and ":memory:" not in settings.database_url:
        db_path = settings.database_url.split("///", 1)[1]
        __import__("pathlib").Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.database_url)
    sm = make_sessionmaker(engine)
    bot = Bot(settings.bot_token, default=BOT_DEFAULTS)
    dp = build_dispatcher(sm, settings)
    app = create_app(
        settings,
        sm,
        invoice_link_factory=lambda order, rooms: make_stars_invoice_link(bot, order, rooms),
        receipt_notifier=make_receipt_notifier(bot, settings, sm),
        tg_uploader=make_tg_uploader(bot),
        tg_fetcher=make_tg_fetcher(bot),
    )
    return Runtime(settings, engine, sm, bot, dp, app)


async def daily_loop(rt: Runtime) -> None:
    last_day = None
    while True:
        local = datetime.now(TASHKENT)
        if local.hour == DAILY_HOUR and local.date() != last_day:
            last_day = local.date()
            try:
                async with rt.sessionmaker() as s:
                    report = await run_daily(
                        s, datetime.now(UTC), lambda chat, text: rt.bot.send_message(chat, text),
                        media_dir=rt.settings.media_dir,
                    )
                log.info("daily jobs: %s", report)
            except Exception:
                log.exception("daily jobs failed")
        await asyncio.sleep(600)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    rt = build(get_settings())
    await init_db(rt.engine)
    try:
        await rt.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Sahifa", web_app=WebAppInfo(url=rt.settings.webapp_url))
        )
    except TelegramAPIError as e:  # e.g. webapp_url is not https yet
        log.warning("menu button not set: %s", e)
    server = uvicorn.Server(
        uvicorn.Config(
            rt.app, host=rt.settings.api_host, port=rt.settings.api_port,
            proxy_headers=True, forwarded_allow_ips="127.0.0.1", log_level="info",
        )
    )
    try:
        await asyncio.gather(
            server.serve(),
            rt.dp.start_polling(rt.bot, handle_signals=False),
            daily_loop(rt),
        )
    finally:
        await rt.bot.session.close()
        await rt.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
