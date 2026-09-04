"""faster-whisper backend — CTranslate2 inference, runs on CPU anywhere.

This is the default because it is portable: the same code path works on an M-series
Mac, an x86 CI runner, and a Cloud Run container.
"""

from __future__ import annotations

from pathlib import Path

from scribe.backends.base import Backend, BackendUnavailable
from scribe.types import Segment, Transcript


class FasterWhisperBackend(Backend):
    name = "faster-whisper"

    @staticmethod
    def available() -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def transcribe(self, wav_path: Path, language: str | None = None) -> Transcript:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise BackendUnavailable(
                "faster-whisper is not installed. Install it with: uv pip install faster-whisper"
            ) from exc

        model = WhisperModel(
            self.model,
            device=self.options.get("device", "cpu"),
            compute_type=self.options.get("compute_type", "int8"),
        )

        segments_iter, info = model.transcribe(
            str(wav_path),
            language=language,
            beam_size=self.options.get("beam_size", 5),
            vad_filter=self.options.get("vad_filter", True),
        )

        # segments_iter is a generator; consuming it is what actually runs inference.
        segments = [
            Segment(start=float(s.start), end=float(s.end), text=s.text) for s in segments_iter
        ]

        return Transcript(
            segments=segments,
            language=info.language,
            duration=float(info.duration),
            backend=self.name,
            model=self.model,
            metadata={"language_probability": round(float(info.language_probability), 4)},
        )
