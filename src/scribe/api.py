"""HTTP API.

Upload a file, get a job id back immediately, poll for the result. Transcription
runs in a background thread because it is CPU-bound and can take minutes — doing
it inline would hold the connection open for the whole run.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

from scribe import __version__, formats
from scribe.backends import DEFAULT_BACKEND, available_backends, backend_names
from scribe.core import transcribe
from scribe.jobs import JobStatus, JobStore

# Cap uploads so a stray multi-gigabyte file cannot fill the disk.
MAX_UPLOAD_BYTES = int(os.environ.get("SCRIBE_MAX_UPLOAD_MB", "512")) * 1024 * 1024

app = FastAPI(
    title="scribe",
    version=__version__,
    description="Local audio and video transcription.",
)
store = JobStore()


def _run_job(job_id: str, tmp_path: Path, backend: str, model: str, language: str | None) -> None:
    store.mark_running(job_id)
    try:
        result = transcribe(tmp_path, backend=backend, model=model, language=language)
        store.mark_done(job_id, result)
    except Exception as exc:  # surfaced to the client via the job record
        store.mark_failed(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "backends": available_backends()}


@app.get("/backends")
def backends() -> dict:
    installed = available_backends()
    return {
        "default": DEFAULT_BACKEND,
        "backends": [
            {"name": n, "available": n in installed} for n in backend_names()
        ],
    }


@app.post("/transcribe", status_code=202)
async def create_job(
    background: BackgroundTasks,
    file: UploadFile,
    backend: str = Query(DEFAULT_BACKEND),
    model: str = Query("base"),
    language: str | None = Query(None),
) -> dict:
    if backend not in backend_names():
        raise HTTPException(400, f"unknown backend {backend!r}")

    suffix = Path(file.filename or "upload").suffix
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    written = 0
    try:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    413, f"file exceeds {MAX_UPLOAD_BYTES // 1024 // 1024} MB limit"
                )
            tmp.write(chunk)
    except HTTPException:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    finally:
        if not tmp.closed:
            tmp.close()

    job = store.create(file.filename or "upload")
    background.add_task(_run_job, job.id, Path(tmp.name), backend, model, language)
    return job.summary()


@app.get("/jobs")
def list_jobs() -> dict:
    return {"jobs": [j.summary() for j in store.list()]}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.summary()


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str) -> None:
    if not store.delete(job_id):
        raise HTTPException(404, "job not found")


@app.get("/jobs/{job_id}/result", response_class=PlainTextResponse)
def get_result(job_id: str, format: str = Query("txt")) -> PlainTextResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status is JobStatus.FAILED:
        raise HTTPException(422, job.error or "transcription failed")
    if job.status is not JobStatus.DONE or job.transcript is None:
        raise HTTPException(409, f"job is {job.status.value}, not ready")
    if format not in formats.FORMATS:
        raise HTTPException(400, f"unknown format {format!r}")

    media_types = {
        "json": "application/json",
        "srt": "application/x-subrip",
        "vtt": "text/vtt",
        "md": "text/markdown",
        "txt": "text/plain",
    }
    return PlainTextResponse(
        formats.render(job.transcript, format),
        media_type=media_types[format],
        headers={
            "Content-Disposition": f'attachment; filename="{Path(job.filename).stem}.{format}"'
        },
    )
