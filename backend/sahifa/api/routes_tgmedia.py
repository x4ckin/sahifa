"""Free museums keep their media in the user's Telegram chat; this server only passes it through."""

import asyncio
import re
import tempfile
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response

from sahifa.api.auth import current_user
from sahifa.api.routes_museums import _spooled
from sahifa.domain.lifecycle import DomainError
from sahifa.models import User
from sahifa.services.media import (
    MAX_AUDIO_BYTES,
    MAX_IMAGE_BYTES,
    MAX_MUSIC_SECONDS,
    MAX_VIDEO_BYTES,
    MAX_VOICE_SECONDS,
    process_audio,
    process_image,
    process_video,
)
from sahifa.services.tgmedia import media_key, sign_media, verify_media

router = APIRouter()

MAX_TG_FILE_BYTES = 20 * 2**20  # Bot API getFile limit: bigger files could never be shown again
CONTENT_TYPES = {"image": "image/webp", "video": "video/mp4", "audio": "audio/mp4"}
_fetch_slots = asyncio.Semaphore(4)
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


class RateLimiter:
    """Sliding one-minute window per client IP: a leaked link cannot drain the home uplink."""

    def __init__(self, per_minute: int = 300):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True


_limiter = RateLimiter()


async def fetch_limited(fetcher, file_id: str) -> bytes:
    async with _fetch_slots:  # at most 4 files (<= 20 MB each) in memory at once
        return await fetcher(file_id)


def _kind(content_type: str | None) -> str:
    major = (content_type or "").split("/")[0]
    if major not in ("image", "video", "audio"):
        raise DomainError("bad_format")
    return major


async def _process(src: Path, out_dir: Path, kind: str, purpose: str) -> Path:
    if kind == "image":
        main, _thumb = await asyncio.to_thread(process_image, src, out_dir)
        return main
    if kind == "video":
        video, _poster = await process_video(src, out_dir)
        return video
    return await process_audio(src, out_dir, MAX_MUSIC_SECONDS if purpose == "music" else MAX_VOICE_SECONDS)


@router.post("/tg-media")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    purpose: str = Form("media", pattern="^(media|voice|music)$"),
    user: User = Depends(current_user),
):
    kind = _kind(file.content_type)
    limit = {"image": MAX_IMAGE_BYTES, "video": MAX_VIDEO_BYTES, "audio": MAX_AUDIO_BYTES}[kind]
    with _spooled(file, limit) as src, tempfile.TemporaryDirectory() as tmp:
        out = await _process(src, Path(tmp), kind, purpose)  # everything lives in temp dirs only
        if out.stat().st_size > MAX_TG_FILE_BYTES:
            raise DomainError("too_large")
        file_id = await request.app.state.tg_uploader(user.id, out, kind)
    secret = media_key(request.app.state.settings)
    return {"token": sign_media(secret, user.id, file_id, kind), "kind": kind}


@router.get("/tg-media/{token}")
async def fetch(token: str, request: Request):
    """No login: <img>/<video> tags cannot send headers. The signed token is the permission."""
    _user_id, file_id, kind = verify_media(media_key(request.app.state.settings), token)
    if not _limiter.allow(request.client.host if request.client else "?"):
        return Response(status_code=429, headers={"Retry-After": "60"})
    content = await fetch_limited(request.app.state.tg_fetcher, file_id)
    headers = {"Cache-Control": "private, max-age=86400", "Accept-Ranges": "bytes"}
    media_type, size = CONTENT_TYPES[kind], len(content)

    # iOS WebKit plays <video> only from servers that answer byte ranges
    match = RANGE.match(request.headers.get("range", ""))
    if match and (match[1] or match[2]):
        if match[1]:
            start, end = int(match[1]), min(int(match[2]) if match[2] else size - 1, size - 1)
        else:  # "bytes=-N": the last N bytes
            start, end = max(size - int(match[2]), 0), size - 1
        if start >= size or start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return Response(content[start : end + 1], status_code=206, media_type=media_type, headers=headers)
    return Response(content, media_type=media_type, headers=headers)
