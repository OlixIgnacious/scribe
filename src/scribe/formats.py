"""Transcript serialisation: plain text, SRT, WebVTT, JSON, Markdown."""

from __future__ import annotations

import json

from scribe.types import Transcript

FORMATS = ("txt", "srt", "vtt", "json", "md")


def _clock(seconds: float, millis_sep: str) -> str:
    """Format seconds as HH:MM:SS<sep>mmm.

    Milliseconds are truncated rather than rounded, so a cue never advertises a
    start time later than the audio it covers.
    """
    if seconds < 0:
        seconds = 0.0
    total_ms = int(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{millis_sep}{ms:03d}"


def to_txt(t: Transcript) -> str:
    return t.text + "\n"


def to_srt(t: Transcript) -> str:
    blocks = []
    # SRT cue numbers are 1-based and must be contiguous, so we enumerate the
    # non-empty segments rather than using the original segment index.
    for i, seg in enumerate((s for s in t.segments if s.text.strip()), start=1):
        blocks.append(
            f"{i}\n"
            f"{_clock(seg.start, ',')} --> {_clock(seg.end, ',')}\n"
            f"{seg.text.strip()}\n"
        )
    return "\n".join(blocks)


def to_vtt(t: Transcript) -> str:
    body = []
    for seg in t.segments:
        if not seg.text.strip():
            continue
        body.append(f"{_clock(seg.start, '.')} --> {_clock(seg.end, '.')}\n{seg.text.strip()}\n")
    return "WEBVTT\n\n" + "\n".join(body)


def to_json(t: Transcript) -> str:
    return json.dumps(t.to_dict(), indent=2, ensure_ascii=False) + "\n"


def to_md(t: Transcript) -> str:
    head = (
        f"# Transcript\n\n"
        f"- **Language:** {t.language}\n"
        f"- **Duration:** {_clock(t.duration, '.')}\n"
        f"- **Backend:** {t.backend} (`{t.model}`)\n\n---\n\n"
    )
    lines = [
        f"**[{_clock(s.start, '.')}]** {s.text.strip()}"
        for s in t.segments
        if s.text.strip()
    ]
    return head + "\n\n".join(lines) + "\n"


_WRITERS = {"txt": to_txt, "srt": to_srt, "vtt": to_vtt, "json": to_json, "md": to_md}


def render(t: Transcript, fmt: str) -> str:
    """Serialise a transcript in the named format."""
    try:
        return _WRITERS[fmt](t)
    except KeyError:
        raise ValueError(f"unknown format {fmt!r}. Available: {', '.join(FORMATS)}") from None
