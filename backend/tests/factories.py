"""Small helpers that build test data through the real services."""

from pathlib import Path

from PIL import Image

from sahifa.services.users import upsert_user


async def make_user(session, uid: int = 1, username: str | None = None):
    return await upsert_user(session, {"id": uid, "first_name": f"U{uid}", "username": username})


def tiny_jpeg(path: Path) -> Path:
    Image.new("RGB", (64, 48), (10, 160, 90)).save(path, "JPEG")
    return path
