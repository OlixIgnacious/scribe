import io

import pytest

from scribe import term


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def tty(monkeypatch):
    """A stderr that claims to be a terminal, with styling forced back on."""
    stream = _Tty()
    monkeypatch.setattr(term, "_forced_off", False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.setattr(term, "_stream", lambda: stream)
    return stream


class TestEnabled:
    def test_on_for_a_terminal(self, tty):
        assert term.enabled() is True

    def test_off_when_not_a_terminal(self, monkeypatch):
        monkeypatch.setattr(term, "_stream", lambda: io.StringIO())
        assert term.enabled() is False

    def test_no_color_env_wins_over_a_terminal(self, tty, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        assert term.enabled() is False

    def test_dumb_terminal_gets_no_codes(self, tty, monkeypatch):
        monkeypatch.setenv("TERM", "dumb")
        assert term.enabled() is False

    def test_disable_is_sticky(self, tty, monkeypatch):
        monkeypatch.setattr(term, "_forced_off", True)
        assert term.enabled() is False


class TestStyle:
    def test_wraps_and_resets(self, tty):
        assert term.style("hi", term.GREEN) == f"{term.GREEN}hi{term.RESET}"

    def test_combines_codes(self, tty):
        assert term.style("hi", term.BOLD, term.RED).startswith(term.BOLD + term.RED)

    def test_returns_text_untouched_when_disabled(self, monkeypatch):
        monkeypatch.setattr(term, "_stream", lambda: io.StringIO())
        assert term.style("hi", term.GREEN) == "hi"

    def test_no_codes_is_a_passthrough(self, tty):
        assert term.style("hi") == "hi"


class TestSpinner:
    def test_prints_one_static_line_when_not_a_terminal(self, monkeypatch):
        stream = io.StringIO()
        monkeypatch.setattr(term, "_stream", lambda: stream)
        with term.Spinner("working"):
            pass
        # No escape codes, and nothing that would accumulate in a redirect.
        assert stream.getvalue() == "  working\n"
        assert "\033" not in stream.getvalue()

    def test_animates_and_restores_the_cursor_on_a_terminal(self, tty):
        with term.Spinner("working", interval=0.01):
            pass
        out = tty.getvalue()
        assert term._HIDE_CURSOR in out
        assert term._SHOW_CURSOR in out

    def test_exits_cleanly_when_the_body_raises(self, tty):
        with pytest.raises(RuntimeError, match="boom"):
            with term.Spinner("working", interval=0.01):
                raise RuntimeError("boom")
        assert term._SHOW_CURSOR in tty.getvalue()
