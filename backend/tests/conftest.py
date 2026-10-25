from datetime import UTC, datetime

import pytest

from sahifa.config import Settings


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        bot_token="123456:TEST-TOKEN",
        bot_username="SahifaTestBot",
        admin_ids=[999],
        admin_chat_id=-1001,
        database_url="sqlite+aiosqlite:///:memory:",
        media_dir=tmp_path / "media",
        public_api_url="https://api.test",
        webapp_url="https://web.test",
    )
