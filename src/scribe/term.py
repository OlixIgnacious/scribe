"""Terminal styling for the CLI.

Written against raw ANSI rather than a rendering library: scribe has one runtime
dependency and this is not worth a second. Everything here writes to stderr,
because stdout carries the transcript — colouring that would corrupt the bytes
someone redirected into a file.

Colour turns itself off when stderr is not a terminal, when NO_COLOR is set (see
no-color.org), when TERM is `dumb`, and when --no-color is passed. The checks run
per call rather than at import so that a captured stream in tests is honoured.
"""

from __future__ import annotations

import itertools
import os
import sys
import threading
import time
from types import TracebackType

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"

_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"
_CLEAR_LINE = "\r\033[2K"

# Braille frames advance in a way that reads as motion even at 12 fps.
_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_forced_off = False


def _stream():
    """The stream everything here writes to.

    Resolved through a function rather than read straight off `sys` so there is
    one seam to redirect — test harnesses reassign `sys.stderr` at times of their
    own choosing, which a captured module-level reference would miss.
    """
    return sys.stderr


def disable() -> None:
    """Turn styling off for the rest of the process (--no-color)."""
    global _forced_off
    _forced_off = True


def enabled() -> bool:
    if _forced_off or os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(_stream(), "isatty", lambda: False)())


def style(text: str, *codes: str) -> str:
    """Wrap `text` in ANSI codes, or return it untouched when styling is off."""
    if not codes or not enabled():
        return text
    return f"{''.join(codes)}{text}{RESET}"


def log(msg: str) -> None:
    """Progress goes to stderr so `scribe file.mp3 > out.txt` stays clean."""
    print(msg, file=_stream())


class Spinner:
    """An animated status line, replaced in place by whatever follows it.

    Degrades to a single static line when stderr is not a terminal, so piped and
    redirected output stays readable instead of accumulating control characters.
    """

    def __init__(self, text: str, interval: float = 0.08) -> None:
        self.text = text
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Spinner:
        if not enabled():
            print(f"  {self.text}", file=_stream())
            return self
        _stream().write(_HIDE_CURSOR)
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def _spin(self) -> None:
        for frame in itertools.cycle(_FRAMES):
            if self._stop.is_set():
                return
            out = _stream()
            out.write(f"{_CLEAR_LINE}  {CYAN}{frame}{RESET}  {self.text}")
            out.flush()
            time.sleep(self.interval)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            out = _stream()
            out.write(f"{_CLEAR_LINE}{_SHOW_CURSOR}")
            out.flush()
