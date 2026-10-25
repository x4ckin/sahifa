"""Turn uploaded files into web-ready media. Output names are random; user file names are never used."""

import asyncio
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from sahifa.domain.lifecycle import DomainError

MAX_IMAGE_BYTES = 15 * 2**20
MAX_VIDEO_BYTES = 50 * 2**20
MAX_VIDEO_SECONDS = 60
MAX_AUDIO_BYTES = 10 * 2**20
MAX_VOICE_SECONDS = 120
MAX_MUSIC_SECONDS = 15 * 60

IMAGE_MAX_SIDE = 2048
THUMB_MAX_SIDE = 480

Image.MAX_IMAGE_PIXELS = 80_000_000  # guards against decompression bombs


class MediaError(DomainError):
    pass


def _name(out_dir: Path, suffix: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{uuid.uuid4().hex}{suffix}"


def check_size(src: Path, limit: int) -> None:
    if src.stat().st_size > limit:
        raise MediaError("too_large")


def process_image(src: Path, out_dir: Path) -> tuple[Path, Path]:
    check_size(src, MAX_IMAGE_BYTES)
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
            main = _name(out_dir, ".webp")
            big = im.copy()
            big.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
            big.save(main, "WEBP", quality=82, method=4)  # no exif= → metadata dropped
            thumb = _name(out_dir, ".webp")
            im.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE))
            im.save(thumb, "WEBP", quality=75)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise MediaError("bad_format") from e
    return main, thumb


async def _run(*args: str) -> bytes:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError as e:
        raise MediaError("ffmpeg_missing") from e
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        raise MediaError("bad_format")
    return out


async def probe_duration(src: Path) -> float:
    out = await _run(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(src),
    )
    try:
        return float(out.strip())
    except ValueError as e:
        raise MediaError("bad_format") from e


async def process_video(src: Path, out_dir: Path) -> tuple[Path, Path]:
    check_size(src, MAX_VIDEO_BYTES)
    if await probe_duration(src) > MAX_VIDEO_SECONDS:
        raise MediaError("too_long")
    video = _name(out_dir, ".mp4")
    await _run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(video),
    )
    poster = _name(out_dir, ".jpg")
    await _run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
        "-frames:v", "1", "-q:v", "4", str(poster),
    )
    return video, poster


async def process_audio(src: Path, out_dir: Path, max_seconds: int) -> Path:
    check_size(src, MAX_AUDIO_BYTES)
    if await probe_duration(src) > max_seconds:
        raise MediaError("too_long")
    out = _name(out_dir, ".m4a")
    await _run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-vn", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    )
    return out
