import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.api.auth import current_user, get_session
from sahifa.api.serialize import media_out, museum_full, museum_summary
from sahifa.domain.lifecycle import DomainError, MuseumState
from sahifa.models import MediaItem, Museum, User
from sahifa.services import museums as svc
from sahifa.services.media import MAX_AUDIO_BYTES, MAX_IMAGE_BYTES, MAX_VIDEO_BYTES

router = APIRouter()


class CreateIn(BaseModel):
    template: str | None = None


Key = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,32}$")]
Caption = Annotated[str, StringConstraints(max_length=200)]
TakenOn = Annotated[str, StringConstraints(max_length=32)]


class SettingsIn(BaseModel):
    """Free text is length-capped; theme/mascot/style/music are asset keys, never raw markup."""

    model_config = ConfigDict(extra="forbid", strict=False)

    title: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None = None
    recipient_name: Annotated[str, StringConstraints(max_length=60)] | None = None
    letter_text: Annotated[str, StringConstraints(max_length=3000)] | None = None
    theme: Key | None = None
    mascot: Key | None = None
    opening_style: Key | None = None
    music_id: Key | None = None
    open_at: AwareDatetime | None = None


class MediaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caption: Caption | None = None
    taken_on: TakenOn | None = None
    position: Annotated[int, Field(ge=0, le=10_000)] | None = None


@contextmanager
def _spooled(upload: UploadFile, limit: int):
    """Copy an upload to a temp file, refusing anything over `limit` bytes."""
    if upload.size is not None and upload.size > limit:
        raise DomainError("too_large")
    suffix = Path(upload.filename or "").suffix[:8]
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / f"upload{suffix}"
        with dst.open("wb") as out:
            shutil.copyfileobj(upload.file, out, length=1024 * 1024)
        if dst.stat().st_size > limit:
            raise DomainError("too_large")
        yield dst


def _kind(content_type: str | None) -> str:
    major = (content_type or "").split("/")[0]
    if major not in ("image", "video"):
        raise DomainError("bad_format")
    return major


async def _items(s: AsyncSession, museum_id: int) -> list[MediaItem]:
    rows = await s.scalars(
        select(MediaItem).where(MediaItem.museum_id == museum_id).order_by(MediaItem.position, MediaItem.id)
    )
    return list(rows.all())


async def _full(request: Request, s: AsyncSession, m: Museum) -> dict:
    return museum_full(request.app.state.settings, m, await _items(s, m.id))


@router.get("/museums")
async def list_museums(request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    museums = await s.scalars(
        select(Museum)
        .where(Museum.owner_id == user.id, Museum.status != MuseumState.DELETED)
        .order_by(Museum.created_at.desc())
    )
    out = []
    for m in museums.all():
        items = await _items(s, m.id)
        counts = {"image": sum(i.kind == "image" for i in items), "video": sum(i.kind == "video" for i in items)}
        out.append(museum_summary(request.app.state.settings, m, counts, items[0] if items else None))
    return out


@router.post("/museums")
async def create(body: CreateIn, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    m = await svc.create_museum(s, user, request.app.state.clock(), template=body.template)
    await s.commit()
    return await _full(request, s, m)


@router.get("/museums/{museum_id}")
async def get(museum_id: int, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    return await _full(request, s, await svc.get_owned(s, user, museum_id))


@router.patch("/museums/{museum_id}")
async def patch(
    museum_id: int, body: SettingsIn, request: Request,
    user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
):
    changes = body.model_dump(exclude_unset=True)
    m = await svc.get_owned(s, user, museum_id)
    await svc.update_settings(s, m, changes, request.app.state.clock())
    await s.commit()
    return await _full(request, s, m)


@router.delete("/museums/{museum_id}")
async def delete(museum_id: int, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    m = await svc.get_owned(s, user, museum_id)
    await svc.delete_museum(s, m, request.app.state.clock(), media_dir=request.app.state.settings.media_dir)
    await s.commit()
    return {"ok": True}


@router.post("/museums/{museum_id}/media")
async def upload_media(
    museum_id: int,
    request: Request,
    file: UploadFile = File(...),
    caption: str | None = Form(None, max_length=200),
    taken_on: str | None = Form(None, max_length=32),
    user: User = Depends(current_user),
    s: AsyncSession = Depends(get_session),
):
    kind = _kind(file.content_type)
    m = await svc.get_owned(s, user, museum_id)
    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_VIDEO_BYTES
    with _spooled(file, limit) as src:
        item = await svc.add_media(
            s, m, src, kind, caption, taken_on, request.app.state.clock(),
            media_dir=request.app.state.settings.media_dir,
        )
    await s.commit()
    return media_out(request.app.state.settings, item)


@router.patch("/museums/{museum_id}/media/{media_id}")
async def patch_media(
    museum_id: int, media_id: int, body: MediaPatch, request: Request,
    user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
):
    m = await svc.get_owned(s, user, museum_id)
    item = await svc.update_media(s, m, media_id, **body.model_dump(exclude_unset=True))
    await s.commit()
    return media_out(request.app.state.settings, item)


@router.delete("/museums/{museum_id}/media/{media_id}")
async def delete_media(
    museum_id: int, media_id: int, request: Request,
    user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
):
    m = await svc.get_owned(s, user, museum_id)
    await svc.remove_media(s, m, media_id, media_dir=request.app.state.settings.media_dir)
    await s.commit()
    return {"ok": True}


async def _put_audio(museum_id: int, request: Request, file: UploadFile, user: User, s: AsyncSession, setter) -> dict:
    m = await svc.get_owned(s, user, museum_id)
    with _spooled(file, MAX_AUDIO_BYTES) as src:
        await setter(s, m, src, request.app.state.clock(), media_dir=request.app.state.settings.media_dir)
    await s.commit()
    return await _full(request, s, m)


@router.put("/museums/{museum_id}/voice")
async def put_voice(
    museum_id: int, request: Request, file: UploadFile = File(...),
    user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
):
    return await _put_audio(museum_id, request, file, user, s, svc.set_voice)


@router.put("/museums/{museum_id}/music")
async def put_music(
    museum_id: int, request: Request, file: UploadFile = File(...),
    user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
):
    return await _put_audio(museum_id, request, file, user, s, svc.set_music_file)


class ImportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, StringConstraints(max_length=1024)]
    caption: Caption | None = None
    taken_on: TakenOn | None = None


class ImportIn(BaseModel):
    """A free museum from the user's Telegram account, sent when they decide to gift it."""

    model_config = ConfigDict(extra="forbid")

    settings: SettingsIn
    media: Annotated[list[ImportItem], Field(max_length=155)]  # 130 photos + 25 videos
    voice_token: Annotated[str, StringConstraints(max_length=1024)] | None = None
    music_token: Annotated[str, StringConstraints(max_length=1024)] | None = None


@router.post("/museums/import")
async def import_museum(
    body: ImportIn, request: Request, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)
):
    from sahifa.api.routes_tgmedia import fetch_limited
    from sahifa.services.tgmedia import media_key

    state = request.app.state

    async def fetch(file_id: str) -> bytes:
        return await fetch_limited(state.tg_fetcher, file_id)

    m = await svc.import_account_museum(
        s, user, body.settings.model_dump(exclude_unset=True), [i.model_dump() for i in body.media],
        fetch, media_key(state.settings), state.clock(), state.settings.media_dir,
        voice_token=body.voice_token, music_token=body.music_token,
    )
    await s.commit()
    return await _full(request, s, m)
