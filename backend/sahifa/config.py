from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, read from SAHIFA_* environment variables or .env."""

    model_config = SettingsConfigDict(env_prefix="SAHIFA_", env_file=".env", extra="ignore")

    bot_token: str
    bot_username: str = "SahifaBot"
    admin_ids: list[int] = Field(min_length=1)  # nobody could approve receipts otherwise
    admin_chat_id: int  # group that receives card receipts
    database_url: str = "sqlite+aiosqlite:///./data/sahifa.db"
    media_dir: Path = Path("./data/media")
    public_api_url: str = "http://localhost:8000"
    webapp_url: str = "http://localhost:5173"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # signs free-museum media tokens; set it so rotating the bot token keeps free museums working
    media_secret: str | None = None

    @property
    def receipts_dir(self) -> Path:
        """Private: payment receipts contain card details and are never served."""
        return self.media_dir.parent / "receipts"


@lru_cache
def get_settings() -> Settings:
    return Settings()
