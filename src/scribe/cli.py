"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from scribe import __version__, formats, term
from scribe.backends import DEFAULT_BACKEND, BackendUnavailable, available_backends, backend_names
from scribe.core import find_media, transcribe
from scribe.media import MediaError
from scribe.term import BLUE, BOLD, CYAN, DIM, GREEN, RED, YELLOW, style

SUBCOMMANDS = {"transcribe", "serve", "backends"}

# Options accepted before a subcommand, so `scribe --no-color file.mp4` still
# resolves to the transcribe shorthand rather than tripping the subparser.
GLOBAL_FLAGS = {"--no-color"}


_log = term.log

TICK = "✓"
CROSS = "✗"
ARROW = "→"


def _error(msg: str) -> None:
    _log(f"  {style(CROSS, RED, BOLD)} {msg}")


def _hint(msg: str) -> None:
    _log(f"    {style(msg, DIM)}")


def _hms(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scribe",
        description="Transcribe audio and video files locally.",
    )
    parser.add_argument("--version", action="version", version=f"scribe {__version__}")
    parser.add_argument(
        "--no-color", action="store_true",
        help="disable coloured output (also honours the NO_COLOR environment variable)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("transcribe", help="transcribe one or more files (default)")
    t.add_argument("inputs", nargs="+", type=Path, help="media files, or a directory of them")
    t.add_argument(
        "-f", "--format", default="txt",
        help=f"output format(s), comma-separated: {', '.join(formats.FORMATS)} (default: txt)",
    )
    t.add_argument(
        "-o", "--output", type=Path,
        help="directory to write results into (default: print to stdout)",
    )
    t.add_argument("-b", "--backend", default=DEFAULT_BACKEND, choices=backend_names())
    t.add_argument("-m", "--model", default="base", help="model size or path (default: base)")
    t.add_argument("-l", "--language", help="ISO 639-1 code; omit to auto-detect")
    t.add_argument("--device", default="cpu", help="faster-whisper device (default: cpu)")
    t.add_argument("--compute-type", default="int8", help="faster-whisper precision")
    t.add_argument("--no-vad", action="store_true", help="disable voice-activity filtering")
    # SUPPRESS so that a subparser default cannot clobber the top-level flag,
    # which argparse would otherwise do when both write the same namespace key.
    t.add_argument("--no-color", action="store_true", default=argparse.SUPPRESS,
                   help="disable coloured output")

    s = sub.add_parser("serve", help="run the HTTP API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")

    sub.add_parser("backends", help="list transcription backends and their availability")
    return parser


def _collect_inputs(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        if item.is_dir():
            found = find_media(item)
            if not found:
                _log(f"  {style('!', YELLOW, BOLD)} no media files found in {item}")
            files.extend(found)
        else:
            files.append(item)
    return files


def _cmd_backends() -> int:
    installed = set(available_backends())
    for name in backend_names():
        if name in installed:
            dot, mark = style("●", GREEN), style("available", GREEN)
        else:
            dot, mark = style("○", DIM), style("not installed", DIM)
        default = style("  (default)", DIM) if name == DEFAULT_BACKEND else ""
        # Pad before styling: escape codes are zero-width on screen but count
        # toward a format spec's width, which knocks the columns out of line.
        print(f"  {dot} {style(f'{name:<16}', BOLD)} {mark}{default}")
    if not installed:
        _error("no backends installed")
        _hint("uv pip install faster-whisper")
        return 1
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        _error("the API needs extra dependencies")
        _hint("uv pip install 'scribe[api]'")
        return 1
    uvicorn.run("scribe.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_transcribe(args: argparse.Namespace) -> int:
    fmts = [f.strip() for f in args.format.split(",") if f.strip()]
    unknown = [f for f in fmts if f not in formats.FORMATS]
    if unknown:
        _error(f"unknown format(s): {style(', '.join(unknown), BOLD)}")
        _hint(f"available: {', '.join(formats.FORMATS)}")
        return 2

    files = _collect_inputs(args.inputs)
    if not files:
        _error("no input files to transcribe")
        return 2

    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)

    options = {"device": args.device, "compute_type": args.compute_type}
    if args.no_vad:
        options["vad_filter"] = False

    _log("")
    _log(
        f"  {style('scribe', CYAN, BOLD)} {style(__version__, DIM)}"
        f"  {style('·', DIM)}  {style(f'{args.backend}:{args.model}', BLUE)}"
        f"  {style('·', DIM)}  {style(f'{len(files)} file(s)', DIM)}"
    )
    _log("")

    failures = 0
    total_audio = 0.0
    run_started = time.monotonic()

    for i, path in enumerate(files, start=1):
        counter = style(f"[{i}/{len(files)}]", DIM) + " " if len(files) > 1 else ""
        started = time.monotonic()

        try:
            with term.Spinner(f"{counter}{style(path.name, BOLD)} {style('transcribing…', DIM)}"):
                result = transcribe(
                    path,
                    backend=args.backend,
                    model=args.model,
                    language=args.language,
                    **options,
                )
        except (MediaError, BackendUnavailable) as exc:
            _error(f"{counter}{style(path.name, BOLD)} {style(str(exc), DIM)}")
            failures += 1
            continue
        except KeyboardInterrupt:
            _log(f"\n  {style('interrupted', YELLOW)}")
            return 130

        elapsed = time.monotonic() - started
        total_audio += result.duration
        speed = f"{result.duration / elapsed:.1f}x" if elapsed > 0 else "—"
        _log(
            f"  {style(TICK, GREEN, BOLD)} {counter}{style(path.name, BOLD)}"
            f"  {style(_hms(result.duration), DIM)} {style(ARROW, DIM)} {_hms(elapsed)}"
            f"  {style(speed, CYAN)}  {style(result.language, DIM)}"
        )

        for fmt in fmts:
            rendered = formats.render(result, fmt)
            if args.output:
                dest = args.output / f"{path.stem}.{fmt}"
                dest.write_text(rendered, encoding="utf-8")
                _log(f"    {style(ARROW, DIM)} {style(str(dest), DIM)}")
            else:
                sys.stdout.write(rendered)

    _log("")
    if failures:
        _error(f"{failures} of {len(files)} file(s) failed")
        _log("")
        return 1

    if len(files) > 1:
        _log(
            f"  {style(TICK, GREEN, BOLD)} {style(f'{len(files)} files', BOLD)}"
            f"  {style('·', DIM)}  {style(_hms(total_audio) + ' audio', DIM)}"
            f"  {style('·', DIM)}  {style(_hms(time.monotonic() - run_started), DIM)}"
        )
        _log("")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Allow `scribe file.mp4` as shorthand for `scribe transcribe file.mp4`,
    # looking past any global flags that precede it.
    head = 0
    while head < len(argv) and argv[head] in GLOBAL_FLAGS:
        head += 1
    if head < len(argv) and argv[head] not in SUBCOMMANDS and not argv[head].startswith("-"):
        argv.insert(head, "transcribe")

    args = build_parser().parse_args(argv)
    if getattr(args, "no_color", False):
        term.disable()

    if args.command == "backends":
        return _cmd_backends()
    if args.command == "serve":
        return _cmd_serve(args)
    return _cmd_transcribe(args)


if __name__ == "__main__":
    raise SystemExit(main())
