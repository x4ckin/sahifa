from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, read from SAHIFA_* environment variables or .env."""

    model_config = SettingsConfigDict(env_prefix="SAHIFA_", env_file=".env", extra="ignore")

    bot_token: str
    bot_username: str = "SahifaBot"
    admin_ids: list[int] = []
    admin_chat_id: int = 0
    database_url: str = "sqlite+aiosqlite:///./data/sahifa.db"
    media_dir: Path = Path("./data/media")
    public_api_url: str = "http://localhost:8000"
    webapp_url: str = "http://localhost:5173"
    api_host: str = "127.0.0.1"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
