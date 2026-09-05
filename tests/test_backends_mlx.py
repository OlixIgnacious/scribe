import sys
import types

import pytest

from scribe.backends.mlx_whisper import MODEL_ALIASES, MLXWhisperBackend, _segment


class TestSegmentCoercion:
    def test_normal_span_passes_through(self):
        seg = _segment({"start": 1.0, "end": 2.5, "text": " hi "})
        assert (seg.start, seg.end, seg.text) == (1.0, 2.5, " hi ")

    def test_inverted_span_collapses_instead_of_raising(self):
        # mlx emits these at decode-window boundaries; Segment rejects them, so
        # unguarded a single bad span aborted the whole file.
        seg = _segment({"start": 129.88, "end": 129.78, "text": "words"})
        assert seg.start == 129.88
        assert seg.end == 129.88
        assert seg.text == "words"

    def test_negative_start_is_clamped_to_zero(self):
        seg = _segment({"start": -0.2, "end": 1.0, "text": "x"})
        assert seg.start == 0.0
        assert seg.end == 1.0

    def test_both_negative_collapses_at_zero(self):
        seg = _segment({"start": -0.5, "end": -0.9, "text": "x"})
        assert seg.start == 0.0 and seg.end == 0.0

    def test_integer_timestamps_become_floats(self):
        seg = _segment({"start": 1, "end": 2, "text": "x"})
        assert isinstance(seg.start, float) and isinstance(seg.end, float)


class TestDecodeOptions:
    @pytest.fixture
    def fake_mlx(self, monkeypatch):
        """Stand in for mlx_whisper so decode options can be inspected off-GPU."""
        calls = {}
        module = types.ModuleType("mlx_whisper")

        def transcribe(audio, **kwargs):
            calls.update(kwargs)
            return {"segments": [{"start": 0.0, "end": 1.0, "text": "hi"}], "language": "en"}

        module.transcribe = transcribe
        monkeypatch.setitem(sys.modules, "mlx_whisper", module)
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("platform.machine", lambda: "arm64")
        return calls

    def test_windows_are_decoded_independently(self, fake_mlx, monkeypatch, tmp_path):
        # Conditioning each window on the last text lets a repetition loop lock in
        # over music and skip the speech underneath — 150 seconds of it, once.
        monkeypatch.setattr("scribe.vad.speech_spans", lambda p: [(0.0, 10.0)])
        MLXWhisperBackend(model="turbo").transcribe(tmp_path / "a.wav", language="en")
        assert fake_mlx["condition_on_previous_text"] is False

    def test_short_model_name_is_resolved_to_a_repo(self, fake_mlx, monkeypatch, tmp_path):
        monkeypatch.setattr("scribe.vad.speech_spans", lambda p: [(0.0, 10.0)])
        MLXWhisperBackend(model="turbo").transcribe(tmp_path / "a.wav")
        assert fake_mlx["path_or_hf_repo"] == MODEL_ALIASES["turbo"]

    def test_vad_is_skipped_entirely_when_disabled(self, fake_mlx, monkeypatch, tmp_path):
        def boom(path):  # pragma: no cover - must never run
            raise AssertionError("VAD ran despite vad_filter=False")

        monkeypatch.setattr("scribe.vad.speech_spans", boom)
        result = MLXWhisperBackend(model="turbo", vad_filter=False).transcribe(tmp_path / "a.wav")
        assert result.metadata["vad_filter"] is False
        assert [s.text for s in result.segments] == ["hi"]


class TestModelAliases:
    @pytest.mark.parametrize("alias", ["tiny", "base", "small", "medium", "large-v3", "turbo"])
    def test_short_names_resolve_to_hub_repos(self, alias):
        assert MODEL_ALIASES[alias].startswith("mlx-community/")

    def test_unknown_name_is_left_alone_as_a_repo_path(self):
        # An explicit hub repo or local path must pass through untouched.
        assert MODEL_ALIASES.get("org/custom-model", "org/custom-model") == "org/custom-model"
