"""Voice-activity detection, shared so every backend suppresses silence alike.

faster-whisper runs Silero VAD inside its own decode loop. mlx-whisper has no
equivalent and will transcribe silence, inventing text as it goes — a webinar
that opens on two minutes of an empty waiting room comes back with "Thank you."
repeated once per 30-second window. Whisper's own guards do not catch it: those
windows score `no_speech_prob` of 0.000 and a healthy `avg_logprob`, because the
model is genuinely confident about words that were never spoken.

So the same Silero model gates both backends — faster-whisper natively, mlx by
filtering its segments against `speech_spans` afterwards. Both honour `--no-vad`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from scribe.types import Segment

SAMPLE_RATE = 16_000


def speech_spans(wav_path: Path) -> list[tuple[float, float]]:
    """Spans of `wav_path` that contain speech, in seconds.

    Returns an empty list if the file has no detectable speech at all.
    """
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    audio = decode_audio(str(wav_path), sampling_rate=SAMPLE_RATE)
    # Silero's own defaults, which is what faster-whisper applies internally —
    # matching them is the point, so the two backends agree on what silence is.
    stamps = get_speech_timestamps(audio, VadOptions())
    return [(s["start"] / SAMPLE_RATE, s["end"] / SAMPLE_RATE) for s in stamps]


def drop_silent(segments: Iterable[Segment], spans: list[tuple[float, float]]) -> list[Segment]:
    """Keep only segments that overlap a speech span.

    With no spans the audio is silent throughout and everything goes; a segment
    counts as speech if any part of it lands inside any span, so a phrase that
    trails off past the detected end is kept whole rather than truncated.
    """
    if not spans:
        return []
    return [s for s in segments if any(s.start < end and s.end > start for start, end in spans)]
