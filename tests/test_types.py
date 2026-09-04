import pytest

from scribe.types import Segment, Transcript


class TestSegment:
    def test_duration(self):
        assert Segment(1.0, 3.5, "hi").duration == 2.5

    def test_rejects_negative_timestamps(self):
        with pytest.raises(ValueError, match="non-negative"):
            Segment(-1.0, 2.0, "hi")

    def test_rejects_end_before_start(self):
        with pytest.raises(ValueError, match="ends before it starts"):
            Segment(5.0, 2.0, "hi")

    def test_zero_length_is_allowed(self):
        assert Segment(2.0, 2.0, "hi").duration == 0.0


class TestTranscript:
    def test_text_strips_and_joins(self):
        t = Transcript(
            segments=[Segment(0, 1, "  a  "), Segment(1, 2, "b")],
            language="en", duration=2, backend="x", model="base",
        )
        assert t.text == "a b"

    def test_text_is_empty_when_no_speech(self):
        t = Transcript(segments=[], language="en", duration=0, backend="x", model="base")
        assert t.text == ""
