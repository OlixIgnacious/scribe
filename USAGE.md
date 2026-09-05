# Running scribe from the terminal

A practical guide. Every command here was run against real files on an M2 Pro; the
timings are measured, not estimated.

## One-time setup

```bash
brew install ffmpeg                     # scribe shells out to it for decoding
uv tool install "scribe[api,mlx] @ git+https://github.com/OlixIgnacious/scribe.git"
```

That puts `scribe` in `~/.local/bin`, on your PATH, callable from any directory —
no virtualenv to activate and nothing to remember. Drop `,mlx` if you are not on
an Apple Silicon Mac.

```bash
uv tool upgrade scribe      # pull in later changes
uv tool uninstall scribe    # remove it
```

Check what you got:

```bash
scribe backends
```

```
  faster-whisper   available  (default)
  mlx              available
```

If `mlx` says `not installed`, you are on the CPU path — everything still works,
just slower. `mlx` requires an M-series Mac.

### If `scribe` is not found

`uv tool install` puts the binary in `~/.local/bin`. If your shell cannot find it,
that directory is not on your PATH — `uv tool update-shell` adds it, or do it by
hand in `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

One wrinkle worth knowing: inside a clone with an active `.venv`, the project's own
`.venv/bin` sits earlier on PATH, so `scribe` there runs the checkout rather than
the installed tool. That is usually what you want while developing. `which scribe`
tells you which one you are getting.

## The command you actually want

On an Apple Silicon Mac, this is the default worth memorising:

```bash
scribe transcribe video.mp4 --backend mlx -m turbo -f txt,srt -o ./out
```

It runs `large-v3-turbo` on the GPU at roughly 20x realtime while leaving the CPU
free. A 46-minute recording finishes in about two minutes.

Without `--backend mlx` you get `faster-whisper` on the CPU with the `base` model,
which is portable but noticeably worse on accented speech and domain vocabulary.

## Anatomy of the command

```
scribe transcribe  INPUT...  --backend mlx  -m turbo  -f txt,srt  -o ./out  -l en
                   ^^^^^^^   ^^^^^^^^^^^^   ^^^^^^^^  ^^^^^^^^^^  ^^^^^^^^  ^^^^^
                   files or  engine         model     formats     where     language
                   a folder                                       to write
```

`transcribe` is the default subcommand, so `scribe video.mp4` works too.

| Flag | Does |
|---|---|
| `-o DIR` | Write files into `DIR`. **Omit it and the transcript goes to stdout instead.** |
| `-f LIST` | Comma-separated: `txt`, `srt`, `vtt`, `json`, `md`. Default `txt`. |
| `-m NAME` | `tiny`, `base`, `small`, `medium`, `large-v3`, or `turbo` (mlx only). |
| `-l CODE` | ISO 639-1, e.g. `en`. Omit to auto-detect — reliable, and costs nothing. |
| `--backend` | `faster-whisper` (default) or `mlx`. |
| `--no-vad` | Stop skipping silence. See the warning below. |
| `--device` | faster-whisper only: `cpu` (default) or `cuda`. |

## Recipes

**A single file, transcript straight to the screen**

```bash
scribe talk.mp3
```

**Save it to a text file** — progress goes to stderr, transcript to stdout, so
redirection does the obvious thing:

```bash
scribe talk.mp3 > talk.txt
```

**Subtitles for a video**

```bash
scribe lecture.mp4 --backend mlx -m turbo -f srt -o ./out
```

**Several files at once** — one pass, model loaded once:

```bash
scribe part1.mp4 part2.mp4 --backend mlx -m turbo -f txt,srt -o ./out
```

**A whole folder** — every media file directly inside it:

```bash
scribe ./recordings --backend mlx -m turbo -f txt -o ./out
```

**Every format, for archiving**

```bash
scribe interview.mp4 --backend mlx -m turbo -f txt,srt,vtt,json,md -o ./out
```

Output files take the input's name: `interview.mp4` becomes `interview.txt`,
`interview.srt`, and so on.

## Which format for what

| Format | Use it for |
|---|---|
| `txt` | Reading, or pasting into something else. One paragraph, no timings. |
| `srt` | Subtitles. Video players, Premiere, YouTube. |
| `vtt` | Subtitles for the web (`<track>`). |
| `json` | Programmatic use. Per-segment `start`/`end`/`text`, plus language and duration. |
| `md` | Skimming a long recording — every line carries a timestamp. |

## Choosing a model

Measured on a 17:49 recording of accented technical speech:

| Command | Time | Notes |
|---|---|---|
| `-m base` (CPU) | 0:48 | Mangles domain terms badly. Fine for clear speech. |
| `-m small` (CPU) | 2:13 | Much better, 2.8x the time, pins the CPU. |
| `--backend mlx -m turbo` | 0:53 | **Best.** Big model, same time as CPU `base`, 29% CPU. |

The pattern: on an M-series Mac there is no reason to run `base` on the CPU. MLX
turbo costs the same wall time and is dramatically more accurate.

First use of any model downloads it (turbo is ~1.6 GB) and caches it under
`~/.cache/huggingface`. That download is counted in the reported time, so the
first run of a new model looks slower than it is.

## Things that will bite you

**Silence gets skipped, and that is deliberate.** Point Whisper at a recording
that opens on a silent waiting room and it will invent text over it — "Thank you."
repeated once per 30-second window, before anyone has spoken. scribe gates both
backends on voice-activity detection to prevent this. The trade-off: genuinely
quiet speech at the edges can get trimmed with the silence. `--no-vad` keeps it,
along with whatever the model makes up.

**Check the opening of anything that starts with intro music.** Music is the case
VAD handles least well, and the real cost is not the invented text but the real
speech that goes missing after it. Skim the first minute of the transcript against
the recording before trusting it.

**Proper nouns come back phonetically.** NASSCOM becomes "NASCOM", Saarthi becomes
"SARTI". No model size fixes this — Whisper has no way to be told your vocabulary.
Budget a find-and-replace pass over the transcript for names that matter.

**`-o` is what makes it write files.** Without it everything goes to stdout, which
is easy to lose on a 46-minute recording.

**Long files on the CPU are genuinely slow.** An hour of audio on `base`/CPU is
10–15 minutes. Use `--backend mlx`, or expect to wait.

**Run long jobs so a closed laptop cannot kill them:**

```bash
caffeinate -i scribe long-recording.mp4 --backend mlx -m turbo -f txt,srt -o ./out
```

## The HTTP API

For scripting against it, or transcribing from another machine:

```bash
scribe serve --port 8123
```

Jobs are asynchronous — POST returns immediately with an id, then you poll:

Note the shape: the **file** is multipart form data, but `backend`, `model`, and
`language` are **query-string** parameters. Passing them with `-F` is a silent
no-op — the job runs on the defaults and you get a `base` faster-whisper
transcript wondering why it looks worse than the CLI's.

```bash
# submit
curl -s -X POST "http://127.0.0.1:8123/transcribe?backend=mlx&model=turbo&language=en" \
  -F "file=@video.mp4"
# {"id":"4b32a3c9236c","status":"queued",...}

# check on it
curl -s http://127.0.0.1:8123/jobs/4b32a3c9236c

# collect it (txt by default; add ?format=srt or ?format=json)
curl -s "http://127.0.0.1:8123/jobs/4b32a3c9236c/result?format=srt" -o video.srt
```

| Route | Does |
|---|---|
| `GET /health` | Liveness and installed backends |
| `GET /backends` | Backend availability |
| `POST /transcribe` | Submit a file, get a job id |
| `GET /jobs` | List jobs |
| `GET /jobs/{id}` | One job's status |
| `GET /jobs/{id}/result` | The transcript, `?format=` to pick |
| `DELETE /jobs/{id}` | Discard a job |

Jobs are held in memory and do not survive a restart. Interactive docs at `/docs`.

## When something goes wrong

| Symptom | Cause |
|---|---|
| `ffmpeg not found on PATH` | `brew install ffmpeg` |
| `contains no audio stream` | Video-only file — nothing to transcribe. |
| `the mlx backend requires Apple Silicon` | Drop `--backend mlx`. |
| `mlx-whisper is not installed` | `uv pip install -e ".[api,mlx]"` |
| Transcript is empty | The VAD found no speech. Confirm with `--no-vad`. |
| Repeated phrases over quiet stretches | Model hallucinating on silence — do not use `--no-vad`. |
| Nothing written to disk | You forgot `-o DIR`. |

## Development

```bash
uv pip install -e ".[api,dev]"
pytest
ruff check .
```
