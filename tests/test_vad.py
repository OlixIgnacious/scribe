import subprocess
from pathlib import Path

import pytest

from scribe import vad
from scribe.types import Segment
from tests.conftest import requires_ffmpeg


class TestDropSilent:
    def test_keeps_segments_inside_a_span(self):
        segs = [Segment(10.0, 12.0, "hello"), Segment(20.0, 22.0, "world")]
        assert vad.drop_silent(segs, [(9.0, 25.0)]) == segs

    def test_drops_segments_outside_every_span(self):
        # The failure this exists for: text invented over a silent lead-in.
        segs = [
            Segment(0.0, 30.0, "Thank you."),
            Segment(30.0, 60.0, "Thank you."),
            Segment(126.0, 130.0, "Hi everyone."),
        ]
        kept = vad.drop_silent(segs, [(125.0, 130.0)])
        assert [s.text for s in kept] == ["Hi everyone."]

    def test_partial_overlap_keeps_the_whole_segment(self):
        # A phrase that trails past where VAD called the end is kept intact,
        # rather than being cut at the span boundary.
        seg = Segment(120.0, 127.0, "Hello, hi everyone.")
        assert vad.drop_silent([seg], [(126.7, 130.0)]) == [seg]

    def test_touching_but_not_overlapping_is_dropped(self):
        assert vad.drop_silent([Segment(10.0, 20.0, "x")], [(20.0, 30.0)]) == []

    def test_no_spans_means_no_speech_at_all(self):
        assert vad.drop_silent([Segment(0.0, 5.0, "ghost")], []) == []

    def test_empty_input_is_empty_output(self):
        assert vad.drop_silent([], [(0.0, 10.0)]) == []


class TestSpeechSpans:
    @requires_ffmpeg
    def test_silence_yields_no_spans(self, tmp_path: Path):
        silent = tmp_path / "silent.wav"
        subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
             "-t", "3", str(silent)],
            capture_output=True, check=True,
        )
        assert vad.speech_spans(silent) == []

    @requires_ffmpeg
    def test_spans_are_ordered_seconds_within_the_file(self, tone_wav):
        # A sine tone is not speech, so this pins the shape of whatever comes back
        # rather than asserting anything is detected: seconds, ordered, in bounds.
        spans = vad.speech_spans(tone_wav)
        for start, end in spans:
            assert 0.0 <= start < end <= pytest.approx(2.0, abs=0.5)
        assert spans == sorted(spans)
