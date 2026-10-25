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

MAX_IMAGE_PIXELS = 50_000_000  # checked from the header, before decoding
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS * 2  # Pillow's own guard; ours runs first

FFMPEG_TIMEOUT_SECONDS = 180
# ffprobe format names we accept; playlists (hls, concat, ...) can make ffmpeg read other files/URLs
ALLOWED_FORMATS = {"mov", "mp4", "m4a", "3gp", "3g2", "mj2", "matroska", "webm", "mp3", "ogg", "wav", "aac", "flac"}
_SAFE_INPUT = ("-protocol_whitelist", "file", "-f")
_transcode_slots = asyncio.Semaphore(2)


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
            if im.size[0] * im.size[1] > MAX_IMAGE_PIXELS:
                raise MediaError("too_large")
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
        raise RuntimeError(f"{args[0]} is not installed") from e  # server fault, not the user's
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), FFMPEG_TIMEOUT_SECONDS)
    except TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise MediaError("timeout") from e
    if proc.returncode != 0:
        raise MediaError("bad_format")
    return out


async def probe(src: Path) -> tuple[str, float]:
    """Return (format, duration); refuse anything that is not a plain media container."""
    out = await _run(
        "ffprobe", "-v", "error", "-protocol_whitelist", "file",
        "-show_entries", "format=format_name,duration", "-of", "default=noprint_wrappers=1", str(src),
    )
    info = dict(line.split("=", 1) for line in out.decode(errors="replace").splitlines() if "=" in line)
    names = set(info.get("format_name", "").split(","))
    if not names & ALLOWED_FORMATS:
        raise MediaError("bad_format")
    try:
        return info["format_name"].split(",")[0], float(info["duration"])
    except (KeyError, ValueError) as e:
        raise MediaError("bad_format") from e


async def probe_duration(src: Path) -> float:
    return (await probe(src))[1]


async def process_video(src: Path, out_dir: Path) -> tuple[Path, Path]:
    check_size(src, MAX_VIDEO_BYTES)
    fmt, duration = await probe(src)
    if duration > MAX_VIDEO_SECONDS:
        raise MediaError("too_long")
    video = _name(out_dir, ".mp4")
    async with _transcode_slots:
        await _transcode(
            "-y", "-loglevel", "error", *_SAFE_INPUT, fmt, "-i", str(src), "-t", str(MAX_VIDEO_SECONDS),
            "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(video), cleanup=video,
        )
        poster = _name(out_dir, ".jpg")
        await _transcode(
            "-y", "-loglevel", "error", *_SAFE_INPUT, "mp4", "-i", str(video),
            "-frames:v", "1", "-q:v", "4", str(poster), cleanup=(video, poster),
        )
    return video, poster


async def process_audio(src: Path, out_dir: Path, max_seconds: int) -> Path:
    check_size(src, MAX_AUDIO_BYTES)
    fmt, duration = await probe(src)
    if duration > max_seconds:
        raise MediaError("too_long")
    out = _name(out_dir, ".m4a")
    async with _transcode_slots:
        await _transcode(
            "-y", "-loglevel", "error", *_SAFE_INPUT, fmt, "-i", str(src), "-t", str(max_seconds),
            "-vn", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out), cleanup=out,
        )
    return out


async def _transcode(*args: str, cleanup: Path | tuple[Path, ...]) -> None:
    """Run ffmpeg; on any failure remove the half-written outputs."""
    try:
        await _run("ffmpeg", *args)
    except BaseException:
        for path in cleanup if isinstance(cleanup, tuple) else (cleanup,):
            path.unlink(missing_ok=True)
        raise
