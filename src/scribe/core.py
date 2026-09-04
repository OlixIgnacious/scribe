"""The one function everything else wraps: file in, Transcript out."""

from __future__ import annotations

from pathlib import Path

from scribe import media
from scribe.backends import DEFAULT_BACKEND, get_backend
from scribe.types import Transcript

# Anything ffmpeg can demux will work; this list only drives the CLI's directory scan.
MEDIA_SUFFIXES = frozenset(
    {
        ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma", ".aiff",
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv",
    }
)


def transcribe(
    path: str | Path,
    *,
    backend: str = DEFAULT_BACKEND,
    model: str = "base",
    language: str | None = None,
    **options,
) -> Transcript:
    """Transcribe an audio or video file.

    The file is decoded to 16 kHz mono WAV in a temp file, handed to the backend,
    and the temp file is removed whether or not inference succeeds.
    """
    path = Path(path)
    engine = get_backend(backend, model=model, **options)

    info = media.probe(path)
    with media.as_wav(path, probed=info) as wav:
        transcript = engine.transcribe(wav, language=language)

    # Backends report duration from their own segment timings, which drift from the
    # real length — trailing silence is never transcribed, so the last segment ends
    # early. The container knows, and knows the same answer for every backend.
    if info["duration"] > 0:
        transcript.duration = info["duration"]

    transcript.metadata.setdefault("source", path.name)
    return transcript


def find_media(directory: Path) -> list[Path]:
    """Every media file directly inside `directory`, sorted by name."""
    return sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES
    )
