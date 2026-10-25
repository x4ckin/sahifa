"""Regression tests for the Task 7 checkpoint review (untrusted media)."""

import shutil

import pytest
from PIL import Image

from sahifa.services import media
from sahifa.services.media import MediaError, process_audio, process_image, process_video

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@needs_ffmpeg
@pytest.mark.parametrize("payload", [
    "#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nfile:///etc/hosts\n#EXT-X-ENDLIST\n",
    "ffconcat version 1.0\nfile '/etc/hosts'\n",
])
async def test_playlists_are_refused(tmp_path, payload):
    src = tmp_path / "evil.mp4"
    src.write_text(payload)
    with pytest.raises(MediaError) as err:
        await process_video(src, tmp_path / "out")
    assert err.value.code == "bad_format"
    with pytest.raises(MediaError):
        await process_audio(src, tmp_path / "out", max_seconds=120)
    assert not any((tmp_path / "out").glob("*")) if (tmp_path / "out").exists() else True


def test_huge_pixel_count_refused_before_decoding(tmp_path):
    src = tmp_path / "big.png"
    Image.new("1", (8000, 8000)).save(src)  # 64 MP, tiny file
    with pytest.raises(MediaError) as err:
        process_image(src, tmp_path / "out")
    assert err.value.code == "too_large"


@needs_ffmpeg
async def test_transcode_has_a_time_limit(tmp_path, monkeypatch):
    from tests.services.test_media import ffmpeg

    src = tmp_path / "v.mp4"
    await ffmpeg("-f", "lavfi", "-i", "testsrc=s=1920x1080:d=5:r=30", str(src))
    monkeypatch.setattr(media, "FFMPEG_TIMEOUT_SECONDS", 0.05)
    with pytest.raises(MediaError) as err:
        await process_video(src, tmp_path / "out")
    assert err.value.code == "timeout"


async def test_missing_ffmpeg_is_not_a_client_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    with pytest.raises(RuntimeError):
        await process_video(src, tmp_path / "out")
