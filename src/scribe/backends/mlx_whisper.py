"""mlx-whisper backend — runs on the Apple Silicon GPU via MLX.

Considerably faster than CPU inference on an M-series Mac, at the cost of being
Mac-only. Selected with `--backend mlx`, never automatically, so that behaviour
stays identical across machines unless you ask for it.
"""

from __future__ import annotations

import platform
from pathlib import Path

from scribe import vad
from scribe.backends.base import Backend, BackendUnavailable
from scribe.types import Segment, Transcript

# mlx-whisper resolves models from the Hugging Face hub rather than by short name.
MODEL_ALIASES = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}


def _segment(raw: dict) -> Segment:
    """One mlx segment as a Segment, tolerating its occasional bad timestamps.

    mlx-whisper can emit a span that ends before it starts (129.88 → 129.78) at a
    decode-window boundary. Segment rejects that, so left alone a single malformed
    span aborts the whole file. The words are real; only the timing is nonsense, so
    the span collapses to a point and the text survives.
    """
    start = max(0.0, float(raw["start"]))
    end = max(start, float(raw["end"]))
    return Segment(start=start, end=end, text=raw["text"])


class MLXWhisperBackend(Backend):
    name = "mlx"

    @staticmethod
    def available() -> bool:
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            return False
        try:
            import mlx_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def transcribe(self, wav_path: Path, language: str | None = None) -> Transcript:
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise BackendUnavailable(
                "the mlx backend requires Apple Silicon; use --backend faster-whisper instead"
            )
        try:
            import mlx_whisper
        except ImportError as exc:
            raise BackendUnavailable(
                "mlx-whisper is not installed. Install it with: uv pip install 'scribe[mlx]'"
            ) from exc

        repo = MODEL_ALIASES.get(self.model, self.model)
        vad_filter = self.options.get("vad_filter", True)
        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=repo,
            language=language,
            verbose=None,
            # Not a tuning knob — this prevents losing real speech. Each window is
            # decoded conditioned on the text of the last, so once the model starts
            # repeating over music or noise it stays locked in that state and skips
            # the audio underneath: on a webinar opening with intro music it emitted
            # "Thank you." per window and silently dropped the next 150 seconds,
            # host introduction and all. Decoding each window fresh costs a little
            # cross-sentence coherence and buys back the content.
            condition_on_previous_text=False,
        )

        segments = [
            _segment(s) for s in result.get("segments", []) if s["text"].strip()
        ]
        if vad_filter:
            segments = vad.drop_silent(segments, vad.speech_spans(wav_path))

        # Deliberately not segments[-1].end: that is where speech stopped, not how
        # long the media runs. core.transcribe overwrites this with the container's
        # duration; this stands in only if a backend is driven directly.
        duration = segments[-1].end if segments else 0.0

        return Transcript(
            segments=segments,
            language=result.get("language", language or "unknown"),
            duration=duration,
            backend=self.name,
            model=repo,
            metadata={"vad_filter": vad_filter},
        )
