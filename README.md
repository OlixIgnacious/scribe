<div align="center">

# scribe

**Transcribe audio and video, entirely on your own machine.**

No API keys. No upload. No per-minute billing.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)

</div>

---

Point it at an `.mp4`, `.mp3`, `.mkv`, `.m4a`, `.wav` — anything ffmpeg can open — and get back text, subtitles, or structured JSON. Everything runs locally: the audio never leaves the machine.

```bash
scribe interview.mp4 -f srt -o ./out
```

## Install

Requires [ffmpeg](https://ffmpeg.org/) on your PATH.

```bash
# macOS
brew install ffmpeg

# Debian / Ubuntu
sudo apt install ffmpeg
```

Then:

```bash
git clone https://github.com/OlixIgnacious/scribe.git
cd scribe
uv venv && uv pip install -e ".[api]"
```

On Apple Silicon, add the GPU backend:

```bash
uv pip install -e ".[api,mlx]"
```

## Use

```bash
# a single file, transcript to stdout
scribe talk.mp3

# subtitles and plain text, written to a directory
scribe lecture.mp4 -f srt,txt -o ./out

# a whole folder, with a bigger model and a known language
scribe ./recordings -m small -l en -o ./out

# on Apple Silicon, run on the GPU
scribe podcast.m4a --backend mlx -m turbo

# what's installed?
scribe backends
```

Progress goes to stderr and the transcript to stdout, so redirection does the obvious thing:

```bash
scribe talk.mp3 > talk.txt
```

### Output formats

| Format | Flag | Use |
|---|---|---|
| Plain text | `txt` | Default. One paragraph, no timings. |
| SubRip | `srt` | Subtitles for video players and editors. |
| WebVTT | `vtt` | Subtitles for the web (`<track>`). |
| JSON | `json` | Segments with timings, language, model metadata. |
| Markdown | `md` | Timestamped reading copy. |

## HTTP API

```bash
scribe serve --port 8000
```

Upload returns a job id immediately; transcription runs in the background.

```bash
# submit
curl -F "file=@meeting.mp4" "localhost:8000/transcribe?model=small"
# → {"id":"a1b2c3d4e5f6","status":"queued",...}

# poll
curl localhost:8000/jobs/a1b2c3d4e5f6

# collect
curl "localhost:8000/jobs/a1b2c3d4e5f6/result?format=srt" -o meeting.srt
```

| Method | Path | |
|---|---|---|
| `GET` | `/health` | Liveness and installed backends |
| `GET` | `/backends` | Backend availability |
| `POST` | `/transcribe` | Upload a file, returns a job |
| `GET` | `/jobs` | All jobs |
| `GET` | `/jobs/{id}` | One job's status |
| `GET` | `/jobs/{id}/result?format=` | Rendered transcript |
| `DELETE` | `/jobs/{id}` | Forget a job |

Interactive docs at `/docs`. Upload size is capped at 512 MB, override with `SCRIBE_MAX_UPLOAD_MB`.

## Backends

| Backend | Runs on | Notes |
|---|---|---|
| `faster-whisper` | CPU, anywhere | Default. CTranslate2. Same behaviour on your laptop, CI, and a container. |
| `mlx` | Apple Silicon GPU | Much faster on an M-series Mac. Mac-only, so never selected automatically. |

Models are `tiny`, `base`, `small`, `medium`, `large-v3`, and (mlx) `turbo`. They download on first use and are cached. `base` is a reasonable default; `small` is noticeably better on accented speech for roughly twice the time.

Adding a backend means subclassing `Backend`, implementing one method, and adding a line to the registry in [`backends/__init__.py`](src/scribe/backends/__init__.py) — nothing else in the codebase knows which engine is running.

## How it works

```
media file  →  ffmpeg  →  16 kHz mono WAV  →  backend  →  Transcript  →  formatter
   any            drops video,                 whisper      segments +      txt/srt/
   container      resamples                    inference    language        vtt/json/md
```

Decoding is delegated to ffmpeg rather than a Python audio library, because ffmpeg actually handles the containers people have — variable frame rate mp4s, mkvs with several audio tracks, whatever a phone produced. The temp WAV is removed even if inference raises.

## Known limits

- **Jobs are in-memory.** They do not survive a restart and do not span replicas. [`jobs.py`](src/scribe/jobs.py) is the only module that knows this — swap it for Redis if you need durability.
- **No speaker diarization.** Whisper does not do it. `pyannote.audio` would, as a separate pass.
- **Long files are slow on CPU.** An hour of audio on `base`/CPU is roughly 10–15 minutes. Use `--backend mlx` on a Mac, or a smaller model.

## Development

```bash
uv pip install -e ".[api,dev]"
pytest
ruff check .
```

Tests generate their own audio with ffmpeg, so no fixtures are committed and no model is downloaded. Tests that need ffmpeg skip cleanly without it.

## License

Apache 2.0 — see [LICENSE](LICENSE).
