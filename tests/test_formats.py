import json

import pytest

from scribe import formats
from scribe.formats import _clock


class TestClock:
    def test_zero(self):
        assert _clock(0, ",") == "00:00:00,000"

    def test_milliseconds_are_truncated_not_rounded(self):
        # 1.9999s must not become 00:00:02,000 — a cue would then claim time it lacks.
        assert _clock(1.9999, ",") == "00:00:01,999"

    def test_hours_roll_over(self):
        assert _clock(3671.5, ",") == "01:01:11,500"

    def test_negative_clamps_to_zero(self):
        assert _clock(-5, ",") == "00:00:00,000"

    def test_separator_is_respected(self):
        assert _clock(1.5, ".") == "00:00:01.500"


class TestSrt:
    def test_cue_numbers_are_contiguous_despite_skipped_segments(self, transcript):
        out = formats.to_srt(transcript)
        # One segment is whitespace-only and dropped, so numbering must be 1,2,3 — not 1,2,4.
        assert [line for line in out.splitlines() if line.isdigit()] == ["1", "2", "3"]

    def test_uses_comma_separator(self, transcript):
        assert "00:00:00,000 --> 00:00:02,500" in formats.to_srt(transcript)

    def test_blank_segment_text_absent(self, transcript):
        assert "   \n" not in formats.to_srt(transcript)


class TestVtt:
    def test_has_header(self, transcript):
        assert formats.to_vtt(transcript).startswith("WEBVTT\n\n")

    def test_uses_dot_separator(self, transcript):
        assert "00:00:02.500 --> 00:00:05.250" in formats.to_vtt(transcript)


class TestJson:
    def test_round_trips(self, transcript):
        data = json.loads(formats.to_json(transcript))
        assert data["language"] == "en"
        assert data["backend"] == "faster-whisper"
        assert len(data["segments"]) == 4

    def test_text_excludes_whitespace_segment(self, transcript):
        data = json.loads(formats.to_json(transcript))
        assert data["text"] == "Hello there. This is a test. And a long one."


class TestRender:
    @pytest.mark.parametrize("fmt", formats.FORMATS)
    def test_every_declared_format_renders(self, transcript, fmt):
        assert formats.render(transcript, fmt).strip()

    def test_unknown_format_raises(self, transcript):
        with pytest.raises(ValueError, match="unknown format"):
            formats.render(transcript, "docx")
