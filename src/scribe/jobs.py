"""In-memory job store for the HTTP API.

Deliberately simple: a dict behind a lock, living in one process. That is enough
for a single-node deployment and keeps the service dependency-free. If you need
work to survive a restart or spread across replicas, swap this module for Redis
or a database — nothing outside it knows how jobs are stored.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from scribe.types import Transcript


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    filename: str
    status: JobStatus = JobStatus.QUEUED
    created_at: str = field(default_factory=_now)
    finished_at: str | None = None
    error: str | None = None
    transcript: Transcript | None = None

    def summary(self) -> dict:
        body = {
            "id": self.id,
            "filename": self.filename,
            "status": self.status.value,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }
        if self.status is JobStatus.FAILED:
            body["error"] = self.error
        if self.status is JobStatus.DONE and self.transcript is not None:
            body["language"] = self.transcript.language
            body["duration"] = self.transcript.duration
            body["segments"] = len(self.transcript.segments)
        return body


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, filename: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], filename=filename)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            if job := self._jobs.get(job_id):
                job.status = JobStatus.RUNNING

    def mark_done(self, job_id: str, transcript: Transcript) -> None:
        with self._lock:
            if job := self._jobs.get(job_id):
                job.status = JobStatus.DONE
                job.transcript = transcript
                job.finished_at = _now()

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            if job := self._jobs.get(job_id):
                job.status = JobStatus.FAILED
                job.error = error
                job.finished_at = _now()
