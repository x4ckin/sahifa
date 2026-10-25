"""Free museums keep their media in the user's Telegram chat; this server only passes it through."""

import asyncio
import tempfile
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
from sahifa.services.tgmedia import media_secret, sign_media, verify_media

router = APIRouter()

MAX_TG_FILE_BYTES = 20 * 2**20  # Bot API getFile limit: bigger files could never be shown again
CONTENT_TYPES = {"image": "image/webp", "video": "video/mp4", "audio": "audio/mp4"}
_fetch_slots = asyncio.Semaphore(4)


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
    secret = media_secret(request.app.state.settings.bot_token)
    return {"token": sign_media(secret, user.id, file_id, kind), "kind": kind}


@router.get("/tg-media/{token}")
async def fetch(token: str, request: Request):
    """No login: <img>/<video> tags cannot send headers. The signed token is the permission."""
    _user_id, file_id, kind = verify_media(media_secret(request.app.state.settings.bot_token), token)
    async with _fetch_slots:
        content = await request.app.state.tg_fetcher(file_id)
    return Response(
        content, media_type=CONTENT_TYPES[kind], headers={"Cache-Control": "private, max-age=86400"}
    )
