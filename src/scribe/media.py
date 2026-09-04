"""Media handling: probe files and normalise them to what Whisper expects.

Whisper models want 16 kHz mono PCM. Rather than depend on a Python decoder that
handles a fraction of real-world containers, we shell out to ffmpeg, which handles
essentially all of them — mp4, mkv, mov, mp3, m4a, wav, flac, ogg, webm.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1


class MediaError(RuntimeError):
    """Raised when a media file cannot be read or converted."""


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise MediaError(
            f"{tool} not found on PATH. Install ffmpeg to use scribe "
            "(macOS: brew install ffmpeg, Debian/Ubuntu: apt install ffmpeg)."
        )
    return path


def probe(path: Path) -> dict:
    """Return duration and stream info for a media file.

    Raises MediaError if the file is missing, unreadable, or has no audio stream.
    """
    if not path.exists():
        raise MediaError(f"file not found: {path}")

    ffprobe = _require("ffprobe")
    proc = subprocess.run(
        [
            ffprobe, "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise MediaError(f"ffprobe could not read {path.name}: {proc.stderr.strip()}")

    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - ffprobe emits valid JSON
        raise MediaError(f"could not parse ffprobe output for {path.name}") from exc

    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise MediaError(f"{path.name} contains no audio stream — nothing to transcribe")

    # Container duration is the most reliable; fall back to the audio stream's own.
    raw_duration = info.get("format", {}).get("duration") or audio_streams[0].get("duration")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        duration = 0.0

    return {
        "duration": duration,
        "audio_codec": audio_streams[0].get("codec_name", "unknown"),
        "sample_rate": int(audio_streams[0].get("sample_rate", 0) or 0),
        "channels": int(audio_streams[0].get("channels", 0) or 0),
        "has_video": any(s.get("codec_type") == "video" for s in info.get("streams", [])),
        "size_bytes": int(info.get("format", {}).get("size", 0) or 0),
    }


@contextmanager
def as_wav(path: Path, *, probed: dict | None = None) -> Iterator[Path]:
    """Yield `path` decoded to a temporary 16 kHz mono WAV, cleaned up on exit.

    Works for both audio and video inputs — the video stream is simply dropped.
    Pass `probed` to reuse an earlier `probe()` result instead of running ffprobe
    a second time; the probe is only here to fail fast with a clear message.
    """
    ffmpeg = _require("ffmpeg")
    if probed is None:
        probe(path)  # fail fast with a clear message before spawning the decode

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out = Path(tmp.name)

    try:
        proc = subprocess.run(
            [
                ffmpeg, "-nostdin", "-y",
                "-i", str(path),
                "-vn",                          # drop video
                "-acodec", "pcm_s16le",
                "-ar", str(TARGET_SAMPLE_RATE),
                "-ac", str(TARGET_CHANNELS),
                str(out),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise MediaError(f"ffmpeg failed to decode {path.name}: {proc.stderr.strip()[-500:]}")
        yield out
    finally:
        out.unlink(missing_ok=True)
