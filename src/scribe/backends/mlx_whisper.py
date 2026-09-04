"""mlx-whisper backend — runs on the Apple Silicon GPU via MLX.

Considerably faster than CPU inference on an M-series Mac, at the cost of being
Mac-only. Selected with `--backend mlx`, never automatically, so that behaviour
stays identical across machines unless you ask for it.
"""

from __future__ import annotations

import platform
from pathlib import Path

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
        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=repo,
            language=language,
            verbose=None,
        )

        segments = [
            Segment(start=float(s["start"]), end=float(s["end"]), text=s["text"])
            for s in result.get("segments", [])
        ]
        duration = segments[-1].end if segments else 0.0

        return Transcript(
            segments=segments,
            language=result.get("language", language or "unknown"),
            duration=duration,
            backend=self.name,
            model=repo,
        )
