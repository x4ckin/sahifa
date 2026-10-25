"""Real Telegram bridge for free museums: files live in the user's chat with the bot."""

from io import BytesIO
from pathlib import Path

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile

from sahifa.domain.lifecycle import DomainError

CAPTION = "🗂 Sahifa muzeyingiz fayli — o'chirmang, aks holda muzeydan yo'qoladi."


def make_tg_uploader(bot):
    async def upload(user_id: int, path: Path, kind: str) -> str:
        # sent as a document so Telegram keeps our processed file byte-for-byte
        try:
            message = await bot.send_document(
                user_id, FSInputFile(path), caption=CAPTION, disable_notification=True
            )
        except (TelegramForbiddenError, TelegramBadRequest) as e:  # blocked bot / never started it
            raise DomainError("start_bot") from e
        return message.document.file_id

    return upload


def make_tg_fetcher(bot):
    async def fetch(file_id: str) -> bytes:
        try:
            file = await bot.get_file(file_id)
            buffer = await bot.download_file(file.file_path, destination=BytesIO())  # memory only
        except TelegramBadRequest as e:  # deleted message, wrong id, or over the 20 MB limit
            raise DomainError("media_gone") from e
        return buffer.getvalue()

    return fetch
