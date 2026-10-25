import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sahifa.domain.lifecycle import (
    DomainError,
    MuseumState,
    limits_for,
    locked_fields,
    rooms_needed,
    validate_open_at,
)
from sahifa.models import MediaItem, Museum, Order, User
from sahifa.services.media import (
    MAX_MUSIC_SECONDS,
    adopt_image,
    adopt_video,
    MAX_VOICE_SECONDS,
    process_audio,
    process_image,
    process_video,
)
from sahifa.services.users import slots_status

SETTINGS_FIELDS = {
    "title",
    "recipient_name",
    "theme",
    "mascot",
    "opening_style",
    "letter_text",
    "music_id",
    "open_at",
}
# settings field -> lock name in LOCKED_AFTER_PAYMENT
_LOCK_NAME = {"music_id": "music"}
EDITABLE_STATES = {MuseumState.DRAFT, MuseumState.ACTIVE}


def _rel(path: Path, media_dir: Path) -> str:
    return path.relative_to(media_dir).as_posix()


def _unlink(media_dir: Path, *rel_paths: str | None) -> None:
    for rel in rel_paths:
        if rel:
            (media_dir / rel).unlink(missing_ok=True)


async def create_museum(
    s: AsyncSession, user: User, now: datetime, template: str | None = None
) -> Museum:
    used, total = await slots_status(s, user, now)
    if total is not None and used >= total:
        raise DomainError("slots_full")
    museum = Museum(
        owner_id=user.id, created_by_id=user.id, template=template, created_at=now, updated_at=now
    )
    s.add(museum)
    await s.flush()
    return museum


async def get_owned(s: AsyncSession, user: User, museum_id: int) -> Museum:
    museum = await s.get(Museum, museum_id)
    if museum is None or museum.owner_id != user.id or museum.status == MuseumState.DELETED:
        raise DomainError("not_found")
    return museum


def _ensure_editable(museum: Museum) -> None:
    if museum.status not in EDITABLE_STATES:
        raise DomainError("not_editable")


def _ensure_unlocked(museum: Museum, names: set[str]) -> None:
    if locked_fields(names, paid=museum.paid_at is not None):
        raise DomainError("locked")


async def update_settings(s: AsyncSession, museum: Museum, changes: dict, now: datetime) -> Museum:
    _ensure_editable(museum)
    unknown = set(changes) - SETTINGS_FIELDS
    if unknown:
        raise DomainError("bad_field", ",".join(sorted(unknown)))
    changed = {k for k, v in changes.items() if getattr(museum, k) != v}
    _ensure_unlocked(museum, {_LOCK_NAME.get(k, k) for k in changed})
    if "open_at" in changed and changes["open_at"] is not None:
        validate_open_at(now, changes["open_at"])
    for key, value in changes.items():
        setattr(museum, key, value)
    museum.updated_at = now
    await s.flush()
    return museum


async def _set_audio(
    s: AsyncSession, museum: Museum, src: Path, now: datetime, media_dir: Path,
    lock: str, attr: str, max_seconds: int,
) -> Museum:
    _ensure_editable(museum)
    _ensure_unlocked(museum, {lock})
    out = await process_audio(src, media_dir / str(museum.id), max_seconds)
    _unlink(media_dir, getattr(museum, attr))
    setattr(museum, attr, _rel(out, media_dir))
    museum.updated_at = now
    await s.flush()
    return museum


async def set_voice(s: AsyncSession, museum: Museum, src: Path, now: datetime, media_dir: Path) -> Museum:
    return await _set_audio(s, museum, src, now, media_dir, "voice", "voice_path", MAX_VOICE_SECONDS)


async def set_music_file(
    s: AsyncSession, museum: Museum, src: Path, now: datetime, media_dir: Path
) -> Museum:
    museum = await _set_audio(s, museum, src, now, media_dir, "music", "music_path", MAX_MUSIC_SECONDS)
    museum.music_id = None
    return museum


async def media_counts(s: AsyncSession, museum_id: int) -> dict[str, int]:
    rows = await s.execute(
        select(MediaItem.kind, func.count()).where(MediaItem.museum_id == museum_id).group_by(MediaItem.kind)
    )
    counts = {"image": 0, "video": 0}
    counts.update(dict(rows.all()))
    return counts


async def add_media(
    s: AsyncSession,
    museum: Museum,
    src: Path,
    kind: str,
    caption: str | None,
    taken_on: str | None,
    now: datetime,
    media_dir: Path,
    preprocessed: bool = False,
) -> MediaItem:
    _ensure_editable(museum)
    if kind not in ("image", "video"):
        raise DomainError("bad_format")
    limit = getattr(limits_for(museum.extra_rooms), f"{kind}s")
    if (await media_counts(s, museum.id))[kind] >= limit:
        raise DomainError("media_full")

    out_dir = media_dir / str(museum.id)
    if preprocessed:
        main, thumb = await (adopt_image(src, out_dir) if kind == "image" else adopt_video(src, out_dir))
    elif kind == "image":
        main, thumb = await asyncio.to_thread(process_image, src, out_dir)
    else:
        main, thumb = await process_video(src, out_dir)

    last = await s.scalar(select(func.max(MediaItem.position)).where(MediaItem.museum_id == museum.id))
    item = MediaItem(
        museum_id=museum.id, kind=kind, path=_rel(main, media_dir), thumb_path=_rel(thumb, media_dir),
        caption=caption, taken_on=taken_on, position=(last or 0) + 1, created_at=now,
    )
    s.add(item)
    await s.flush()
    # re-count after insert: a parallel upload may have taken the last place meanwhile
    if (await media_counts(s, museum.id))[kind] > limit:
        await s.delete(item)
        await s.flush()
        _unlink(media_dir, item.path, item.thumb_path)
        raise DomainError("media_full")
    museum.updated_at = now
    await s.flush()
    return item


async def _get_item(s: AsyncSession, museum: Museum, media_id: int) -> MediaItem:
    item = await s.get(MediaItem, media_id)
    if item is None or item.museum_id != museum.id:
        raise DomainError("not_found")
    return item


async def update_media(
    s: AsyncSession,
    museum: Museum,
    media_id: int,
    caption: str | None = None,
    taken_on: str | None = None,
    position: int | None = None,
) -> MediaItem:
    _ensure_editable(museum)
    item = await _get_item(s, museum, media_id)
    if caption is not None:
        item.caption = caption
    if taken_on is not None:
        item.taken_on = taken_on
    if position is not None:
        item.position = position
    await s.flush()
    return item


async def remove_media(s: AsyncSession, museum: Museum, media_id: int, media_dir: Path) -> None:
    _ensure_editable(museum)
    item = await _get_item(s, museum, media_id)
    await s.delete(item)
    await s.flush()
    _unlink(media_dir, item.path, item.thumb_path)


async def delete_museum(s: AsyncSession, museum: Museum, now: datetime, media_dir: Path) -> None:
    items = (await s.scalars(select(MediaItem).where(MediaItem.museum_id == museum.id))).all()
    for item in items:
        _unlink(media_dir, item.path, item.thumb_path)
        await s.delete(item)
    _unlink(media_dir, museum.voice_path, museum.music_path)
    museum.voice_path = museum.music_path = None
    museum.status = MuseumState.DELETED
    museum.updated_at = now
    await s.execute(
        update(Order)
        # only unpaid ones: a receipt under review means money was sent, the admin must see it
        .where(Order.museum_id == museum.id, Order.status == "pending")
        .values(status="rejected", reject_reason="museum_deleted")
    )
    await s.flush()


_IMPORT_SUFFIX = {"image": ".webp", "video": ".mp4", "audio": ".m4a"}


async def import_account_museum(
    s: AsyncSession,
    user: User,
    settings_in: dict,
    items: list[dict],
    fetch,
    secret: bytes,
    now: datetime,
    media_dir: Path,
    voice_token: str | None = None,
    music_token: str | None = None,
) -> Museum:
    """Copy a free, Telegram-held museum onto the server so it can be paid for and shared.

    Every token must be this user's. On any failure the half-built museum is removed (files too)
    and the error is re-raised; the caller's transaction is rolled back.
    """
    from sahifa.services.tgmedia import verify_media

    def own(token: str, kinds: tuple[str, ...]) -> tuple[str, str]:
        user_id, file_id, kind = verify_media(secret, token)
        if user_id != user.id:
            raise DomainError("bad_token")
        if kind not in kinds:
            raise DomainError("bad_format")
        return file_id, kind

    # check every token, and the limits, before touching Telegram or the disk
    wall = [(own(i["token"], ("image", "video")), i) for i in items]
    images = sum(kind == "image" for (_, kind), _ in wall)
    rooms = rooms_needed(images, len(wall) - images)  # paid together with the museum
    voice = own(voice_token, ("audio",))[0] if voice_token else None
    music = own(music_token, ("audio",))[0] if music_token else None

    museum = await create_museum(s, user, now)
    museum.extra_rooms = rooms
    try:
        await update_settings(s, museum, settings_in, now)
        with tempfile.TemporaryDirectory() as tmp:
            for n, ((file_id, kind), item) in enumerate(wall):
                src = Path(tmp) / f"{n}{_IMPORT_SUFFIX[kind]}"
                src.write_bytes(await fetch(file_id))
                await add_media(
                    s, museum, src, kind, item.get("caption"), item.get("taken_on"), now, media_dir,
                    preprocessed=True,  # already WebP / 720p from /api/tg-media: no second lossy pass
                )
            for file_id, setter in ((voice, set_voice), (music, set_music_file)):
                if file_id:
                    src = Path(tmp) / f"audio-{setter.__name__}.m4a"
                    src.write_bytes(await fetch(file_id))
                    await setter(s, museum, src, now, media_dir)
    except BaseException:
        await delete_museum(s, museum, now, media_dir=media_dir)
        raise
    return museum
