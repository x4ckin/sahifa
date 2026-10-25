import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict
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


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="allow")


class MediaPatch(BaseModel):
    caption: str | None = None
    taken_on: str | None = None
    position: int | None = None


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
    if isinstance(changes.get("open_at"), str):
        try:
            changes["open_at"] = datetime.fromisoformat(changes["open_at"])
        except ValueError as e:
            raise DomainError("open_at") from e
        if changes["open_at"].tzinfo is None:
            raise DomainError("open_at")
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
    caption: str | None = Form(None),
    taken_on: str | None = Form(None),
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
