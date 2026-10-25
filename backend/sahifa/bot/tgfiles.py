"""Real Telegram bridge for free museums: files live in the user's chat with the bot."""

import asyncio
from io import BytesIO
from pathlib import Path

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import FSInputFile

from sahifa.domain.lifecycle import DomainError

CAPTION = "🗂 Sahifa muzeyingiz fayli — o'chirmang, aks holda muzeydan yo'qoladi."
MAX_FLOOD_WAIT = 30
_TEMPORARY = (TelegramNetworkError, TelegramServerError, asyncio.TimeoutError, OSError)


async def _call(make_request):
    """Run a Bot API call: wait out one flood-control pause; network trouble is temporary."""
    for attempt in range(2):
        try:
            return await make_request()
        except TelegramRetryAfter as e:
            if attempt or e.retry_after > MAX_FLOOD_WAIT:
                raise DomainError("telegram_unavailable") from e
            await asyncio.sleep(e.retry_after)
        except _TEMPORARY as e:
            raise DomainError("telegram_unavailable") from e


def make_tg_uploader(bot):
    async def upload(user_id: int, path: Path, kind: str) -> str:
        try:
            message = await _call(lambda: bot.send_document(
                user_id, FSInputFile(path), caption=CAPTION, disable_notification=True,
                disable_content_type_detection=True,  # keep our processed file byte-for-byte
            ))
        except (TelegramForbiddenError, TelegramBadRequest) as e:  # blocked bot / never started it
            raise DomainError("start_bot") from e
        fields = ("document", "video", "animation", "audio", "voice", "sticker")
        sent = next(m for m in (getattr(message, f, None) for f in fields) if m is not None)
        return sent.file_id

    return upload


def make_tg_fetcher(bot):
    async def fetch(file_id: str) -> bytes:
        try:
            file = await _call(lambda: bot.get_file(file_id))
            buffer = await _call(lambda: bot.download_file(file.file_path, destination=BytesIO()))  # memory only
        except TelegramBadRequest as e:  # deleted message, wrong id, or over the 20 MB limit
            raise DomainError("media_gone") from e
        return buffer.getvalue()

    return fetch
