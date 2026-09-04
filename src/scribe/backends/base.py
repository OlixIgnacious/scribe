"""Backend contract.

A backend turns a 16 kHz mono WAV into a Transcript. Everything else — container
handling, output formatting, the CLI, the API — is backend-agnostic and lives
elsewhere, so adding an engine means implementing exactly this one method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from scribe.types import Transcript


class BackendUnavailable(RuntimeError):
    """Raised when a backend's optional dependency or hardware is missing."""


class Backend(ABC):
    name: str = "base"

    def __init__(self, model: str = "base", **options) -> None:
        self.model = model
        self.options = options

    @abstractmethod
    def transcribe(self, wav_path: Path, language: str | None = None) -> Transcript:
        """Transcribe a 16 kHz mono WAV file.

        `language` is an ISO 639-1 code, or None to auto-detect.
        """

    @staticmethod
    def available() -> bool:
        """Whether this backend can actually run in the current environment."""
        return False
