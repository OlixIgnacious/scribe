from pathlib import Path

import pytest

from scribe import media
from scribe.media import MediaError
from tests.conftest import requires_ffmpeg


class TestProbe:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(MediaError, match="file not found"):
            media.probe(tmp_path / "nope.mp3")

    @requires_ffmpeg
    def test_reads_audio_properties(self, tone_wav):
        info = media.probe(tone_wav)
        assert info["sample_rate"] == 16000
        assert info["channels"] == 1
        assert info["has_video"] is False
        assert info["duration"] == pytest.approx(2.0, abs=0.1)

    @requires_ffmpeg
    def test_detects_video_stream(self, video_with_audio):
        assert media.probe(video_with_audio)["has_video"] is True

    @requires_ffmpeg
    def test_video_without_audio_is_rejected_clearly(self, silent_video):
        with pytest.raises(MediaError, match="no audio stream"):
            media.probe(silent_video)

    @requires_ffmpeg
    def test_non_media_file_is_rejected(self, tmp_path):
        junk = tmp_path / "notes.txt"
        junk.write_text("this is not media")
        with pytest.raises(MediaError):
            media.probe(junk)


class TestAsWav:
    @requires_ffmpeg
    def test_converts_video_to_16k_mono(self, video_with_audio):
        with media.as_wav(video_with_audio) as wav:
            info = media.probe(wav)
            assert info["sample_rate"] == media.TARGET_SAMPLE_RATE
            assert info["channels"] == media.TARGET_CHANNELS
            assert info["has_video"] is False

    @requires_ffmpeg
    def test_temp_file_is_removed_on_exit(self, tone_wav):
        with media.as_wav(tone_wav) as wav:
            produced = Path(wav)
            assert produced.exists()
        assert not produced.exists()

    @requires_ffmpeg
    def test_temp_file_is_removed_when_body_raises(self, tone_wav):
        produced = None
        with pytest.raises(RuntimeError, match="boom"):
            with media.as_wav(tone_wav) as wav:
                produced = Path(wav)
                raise RuntimeError("boom")
        assert produced is not None and not produced.exists()
