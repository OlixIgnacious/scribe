import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")
from fastapi.testclient import TestClient  # noqa: E402

from scribe.api import app, store  # noqa: E402
from scribe.jobs import JobStatus  # noqa: E402
from scribe.types import Segment, Transcript  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_store():
    for job in store.list():
        store.delete(job.id)
    yield


class TestMeta:
    def test_health(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_backends_lists_all_with_availability(self, client):
        body = client.get("/backends").json()
        names = {b["name"] for b in body["backends"]}
        assert {"faster-whisper", "mlx"} <= names
        assert body["default"] == "faster-whisper"


class TestJobs:
    def test_unknown_job_is_404(self, client):
        assert client.get("/jobs/deadbeef").status_code == 404

    def test_unknown_backend_rejected(self, client):
        r = client.post(
            "/transcribe",
            params={"backend": "nonsense"},
            files={"file": ("a.wav", b"RIFF....", "audio/wav")},
        )
        assert r.status_code == 400

    def test_result_before_completion_is_409(self, client):
        job = store.create("pending.mp3")
        r = client.get(f"/jobs/{job.id}/result")
        assert r.status_code == 409

    def test_failed_job_result_is_422_with_reason(self, client):
        job = store.create("bad.mp3")
        store.mark_failed(job.id, "MediaError: no audio stream")
        r = client.get(f"/jobs/{job.id}/result")
        assert r.status_code == 422
        assert "no audio stream" in r.json()["detail"]

    def test_completed_job_renders_requested_format(self, client):
        job = store.create("ok.mp3")
        store.mark_done(
            job.id,
            Transcript(
                segments=[Segment(0, 1.5, "hello")],
                language="en", duration=1.5, backend="faster-whisper", model="base",
            ),
        )
        r = client.get(f"/jobs/{job.id}/result", params={"format": "srt"})
        assert r.status_code == 200
        assert "00:00:00,000 --> 00:00:01,500" in r.text
        assert "attachment" in r.headers["content-disposition"]

    def test_bad_format_rejected(self, client):
        job = store.create("ok.mp3")
        store.mark_done(
            job.id,
            Transcript(segments=[], language="en", duration=0, backend="x", model="base"),
        )
        assert client.get(f"/jobs/{job.id}/result", params={"format": "docx"}).status_code == 400

    def test_delete_removes_job(self, client):
        job = store.create("x.mp3")
        assert client.delete(f"/jobs/{job.id}").status_code == 204
        assert client.get(f"/jobs/{job.id}").status_code == 404


class TestJobStore:
    def test_status_transitions(self):
        job = store.create("a.mp3")
        assert job.status is JobStatus.QUEUED
        store.mark_running(job.id)
        assert store.get(job.id).status is JobStatus.RUNNING
