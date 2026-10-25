import asyncio
import shutil
from pathlib import Path

import pytest
from PIL import Image

from sahifa.services.media import (
    MediaError,
    process_audio,
    process_image,
    process_video,
    probe_duration,
)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_jpeg(path: Path, size=(4000, 3000)) -> Path:
    Image.new("RGB", size, (200, 120, 90)).save(path, "JPEG")
    return path


async def ffmpeg(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-loglevel", "error", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    assert proc.returncode == 0, err.decode()


def test_image_resized_to_webp(tmp_path):
    main, thumb = process_image(make_jpeg(tmp_path / "in.jpg"), tmp_path / "out")
    assert main.suffix == thumb.suffix == ".webp"
    with Image.open(main) as im:
        assert max(im.size) == 2048
    with Image.open(thumb) as im:
        assert max(im.size) == 480
    assert main.parent == tmp_path / "out"
    assert "in" not in main.name  # user file names are never reused


def test_small_image_not_upscaled(tmp_path):
    main, _ = process_image(make_jpeg(tmp_path / "s.jpg", (800, 600)), tmp_path / "out")
    with Image.open(main) as im:
        assert im.size == (800, 600)


def test_image_rejects_non_image(tmp_path):
    bad = tmp_path / "x.jpg"
    bad.write_text("not an image")
    with pytest.raises(MediaError) as err:
        process_image(bad, tmp_path / "out")
    assert err.value.code == "bad_format"


@needs_ffmpeg
async def test_video_too_long_rejected(tmp_path):
    src = tmp_path / "long.mp4"
    await ffmpeg("-f", "lavfi", "-i", "color=c=red:s=320x240:d=61:r=5", str(src))
    with pytest.raises(MediaError) as err:
        await process_video(src, tmp_path / "out")
    assert err.value.code == "too_long"


@needs_ffmpeg
async def test_video_transcoded_720p(tmp_path):
    src = tmp_path / "hd.mov"
    await ffmpeg("-f", "lavfi", "-i", "testsrc=s=1920x1080:d=3:r=10", str(src))
    video, poster = await process_video(src, tmp_path / "out")
    assert video.suffix == ".mp4" and poster.suffix == ".jpg"
    with Image.open(poster) as im:
        assert im.size[1] == 720
    assert 2.5 < await probe_duration(video) < 3.5


@needs_ffmpeg
async def test_audio_length_limit(tmp_path):
    src = tmp_path / "v.ogg"
    await ffmpeg("-f", "lavfi", "-i", "sine=d=5", "-c:a", "libopus", str(src))
    out = await process_audio(src, tmp_path / "out", max_seconds=120)
    assert out.suffix == ".m4a"
    with pytest.raises(MediaError) as err:
        await process_audio(src, tmp_path / "out", max_seconds=3)
    assert err.value.code == "too_long"
