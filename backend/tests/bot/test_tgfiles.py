from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from sahifa.bot.tgfiles import make_tg_fetcher, make_tg_uploader
from sahifa.domain.lifecycle import DomainError


class ChatBot:
    def __init__(self):
        self.sent = []
        self.files = {"FID": b"hello"}

    async def send_document(self, chat_id, document, **kwargs):
        if chat_id == 13:
            raise TelegramForbiddenError(method=None, message="Forbidden: bot was blocked by the user")
        if chat_id == 14:
            raise TelegramBadRequest(method=None, message="Bad Request: chat not found")
        self.sent.append((chat_id, document, kwargs))
        return SimpleNamespace(document=SimpleNamespace(file_id="FID"), video=None, audio=None)

    async def get_file(self, file_id):
        if file_id == "BIG":
            raise TelegramBadRequest(method=None, message="Bad Request: file is too big")
        if file_id not in self.files:
            raise TelegramBadRequest(method=None, message="Bad Request: wrong file_id or the file is temporarily unavailable")
        return SimpleNamespace(file_path=f"documents/{file_id}")

    async def download_file(self, file_path, destination):
        destination.write(self.files[file_path.split("/")[1]])
        return destination


async def test_uploader_sends_document_silently(tmp_path):
    bot = ChatBot()
    path = tmp_path / "x.webp"
    path.write_bytes(b"RIFF")
    assert await make_tg_uploader(bot)(7, path, "image") == "FID"
    chat_id, _doc, kwargs = bot.sent[0]
    assert chat_id == 7 and kwargs["disable_notification"] is True


@pytest.mark.parametrize("uid", [13, 14])
async def test_uploader_maps_forbidden_to_start_bot(tmp_path, uid):
    path = tmp_path / "x.webp"
    path.write_bytes(b"RIFF")
    with pytest.raises(DomainError) as err:
        await make_tg_uploader(ChatBot())(uid, path, "image")
    assert err.value.code == "start_bot"


async def test_fetcher_reads_into_memory():
    assert await make_tg_fetcher(ChatBot())("FID") == b"hello"


@pytest.mark.parametrize("file_id", ["MISSING", "BIG"])
async def test_fetcher_maps_missing_to_media_gone(file_id):
    with pytest.raises(DomainError) as err:
        await make_tg_fetcher(ChatBot())(file_id)
    assert err.value.code == "media_gone"


