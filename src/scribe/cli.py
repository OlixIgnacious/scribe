"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from scribe import __version__, formats
from scribe.backends import DEFAULT_BACKEND, BackendUnavailable, available_backends, backend_names
from scribe.core import find_media, transcribe
from scribe.media import MediaError

SUBCOMMANDS = {"transcribe", "serve", "backends"}


def _log(msg: str) -> None:
    """Progress goes to stderr so `scribe file.mp3 > out.txt` stays clean."""
    print(msg, file=sys.stderr)


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
                _log(f"warning: no media files found in {item}")
            files.extend(found)
        else:
            files.append(item)
    return files


def _cmd_backends() -> int:
    installed = set(available_backends())
    for name in backend_names():
        mark = "available" if name in installed else "not installed"
        default = "  (default)" if name == DEFAULT_BACKEND else ""
        print(f"  {name:<16} {mark}{default}")
    if not installed:
        print("\nNo backends installed. Try: uv pip install faster-whisper", file=sys.stderr)
        return 1
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        _log("The API needs extra deps. Install with: uv pip install 'scribe[api]'")
        return 1
    uvicorn.run("scribe.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_transcribe(args: argparse.Namespace) -> int:
    fmts = [f.strip() for f in args.format.split(",") if f.strip()]
    unknown = [f for f in fmts if f not in formats.FORMATS]
    if unknown:
        _log(f"error: unknown format(s): {', '.join(unknown)}")
        _log(f"       available: {', '.join(formats.FORMATS)}")
        return 2

    files = _collect_inputs(args.inputs)
    if not files:
        _log("error: no input files to transcribe")
        return 2

    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)

    options = {"device": args.device, "compute_type": args.compute_type}
    if args.no_vad:
        options["vad_filter"] = False

    failures = 0
    for i, path in enumerate(files, start=1):
        prefix = f"[{i}/{len(files)}] " if len(files) > 1 else ""
        _log(f"{prefix}{path.name} — transcribing with {args.backend}:{args.model}…")
        started = time.monotonic()

        try:
            result = transcribe(
                path,
                backend=args.backend,
                model=args.model,
                language=args.language,
                **options,
            )
        except (MediaError, BackendUnavailable) as exc:
            _log(f"{prefix}{path.name} — failed: {exc}")
            failures += 1
            continue
        except KeyboardInterrupt:
            _log("\ninterrupted")
            return 130

        elapsed = time.monotonic() - started
        speed = f"{result.duration / elapsed:.1f}x" if elapsed > 0 else "—"
        _log(
            f"{prefix}{path.name} — done in {_hms(elapsed)} "
            f"({_hms(result.duration)} audio, {speed} realtime, lang={result.language})"
        )

        for fmt in fmts:
            rendered = formats.render(result, fmt)
            if args.output:
                dest = args.output / f"{path.stem}.{fmt}"
                dest.write_text(rendered, encoding="utf-8")
                _log(f"{prefix}wrote {dest}")
            else:
                sys.stdout.write(rendered)

    if failures:
        _log(f"\n{failures} of {len(files)} file(s) failed")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Allow `scribe file.mp4` as shorthand for `scribe transcribe file.mp4`.
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "transcribe")

    args = build_parser().parse_args(argv)

    if args.command == "backends":
        return _cmd_backends()
    if args.command == "serve":
        return _cmd_serve(args)
    return _cmd_transcribe(args)


if __name__ == "__main__":
    raise SystemExit(main())
