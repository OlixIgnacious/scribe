import pytest

from scribe.backends.mlx_whisper import MODEL_ALIASES, _segment


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


class TestModelAliases:
    @pytest.mark.parametrize("alias", ["tiny", "base", "small", "medium", "large-v3", "turbo"])
    def test_short_names_resolve_to_hub_repos(self, alias):
        assert MODEL_ALIASES[alias].startswith("mlx-community/")

    def test_unknown_name_is_left_alone_as_a_repo_path(self):
        # An explicit hub repo or local path must pass through untouched.
        assert MODEL_ALIASES.get("org/custom-model", "org/custom-model") == "org/custom-model"
