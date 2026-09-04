"""Core data types shared across backends, formats, and the API."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Segment:
    """One timestamped span of transcribed speech."""

    start: float
    end: float
    text: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError(
                f"segment timestamps must be non-negative, got {self.start}-{self.end}"
            )
        if self.end < self.start:
            raise ValueError(f"segment ends before it starts: {self.start} > {self.end}")

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Transcript:
    """The result of transcribing one media file."""

    segments: list[Segment]
    language: str
    duration: float
    backend: str
    model: str
    metadata: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        """The full transcript as a single normalised string."""
        return " ".join(s.text.strip() for s in self.segments if s.text.strip())

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "duration": self.duration,
            "backend": self.backend,
            "model": self.model,
            "text": self.text,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text.strip()} for s in self.segments
            ],
            "metadata": self.metadata,
        }
