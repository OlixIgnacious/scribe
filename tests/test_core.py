from contextlib import contextmanager

import pytest

from scribe import core
from scribe.types import Segment, Transcript
from tests.conftest import requires_ffmpeg


@contextmanager
def _null_context(path):
    yield path


class _StubBackend:
    """Stands in for a real engine, reporting duration the way backends do:
    from its own last segment, which stops short of the true media length."""

    def __init__(self, duration: float = 0.6) -> None:
        self.duration = duration
        self.wav_paths: list = []

    def transcribe(self, wav_path, language=None):
        self.wav_paths.append(wav_path)
        return Transcript(
            segments=[Segment(0.0, self.duration, "hi")],
            language=language or "en",
            duration=self.duration,
            backend="stub",
            model="stub",
        )


@pytest.fixture
def stub_backend(monkeypatch):
    backend = _StubBackend()
    monkeypatch.setattr(core, "get_backend", lambda *a, **kw: backend)
    return backend


class TestTranscribeDuration:
    @requires_ffmpeg
    def test_duration_comes_from_the_container_not_the_segments(
        self, stub_backend, video_with_audio
    ):
        # The regression: mlx derived duration from its last segment, so a file
        # ending in silence reported short and two backends disagreed on one file.
        result = core.transcribe(video_with_audio, backend="stub")
        assert result.duration == pytest.approx(1.0, abs=0.2)
        assert result.duration > stub_backend.duration

    @requires_ffmpeg
    def test_backend_duration_survives_an_unreadable_container_duration(
        self, stub_backend, video_with_audio, monkeypatch
    ):
        monkeypatch.setattr(core.media, "probe", lambda p: {"duration": 0.0})
        monkeypatch.setattr(
            core.media, "as_wav", lambda p, probed=None: _null_context(video_with_audio)
        )
        result = core.transcribe(video_with_audio, backend="stub")
        assert result.duration == stub_backend.duration

    @requires_ffmpeg
    def test_source_is_recorded_in_metadata(self, stub_backend, video_with_audio):
        result = core.transcribe(video_with_audio, backend="stub")
        assert result.metadata["source"] == video_with_audio.name

    @requires_ffmpeg
    def test_the_backend_receives_a_wav_not_the_original(
        self, stub_backend, video_with_audio
    ):
        core.transcribe(video_with_audio, backend="stub")
        assert stub_backend.wav_paths[0].suffix == ".wav"
