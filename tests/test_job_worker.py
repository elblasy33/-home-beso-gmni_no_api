import pytest
import asyncio
from src.queue.job_worker import JobWorker
from src.models import JobStatus

@pytest.fixture
def worker():
    w = JobWorker()
    return w

def test_create_and_get_job(worker):
    job = worker.create_job(
        config_name="mock_site",
        url="http://localhost:8000/mock-site/chat",
        prompt="Analyze attached data"
    )
    assert job.id is not None
    assert job.status == JobStatus.QUEUED
    assert len(job.logs) == 1

    fetched = worker.get_job(job.id)
    assert fetched is not None
    assert fetched.id == job.id

def test_resume_job(worker):
    job = worker.create_job(
        config_name="mock_site",
        url="http://localhost:8000/mock-site/chat",
        prompt="Test Resume"
    )
    job.status = JobStatus.LOGIN_REQUIRED
    resumed = worker.resume_job(job.id)
    assert resumed is True
    assert any("resuming" in log.message.lower() for log in job.logs)

def test_cancel_job(worker):
    job = worker.create_job(
        config_name="mock_site",
        url="http://localhost:8000/mock-site/chat",
        prompt="Test Cancel"
    )
    assert worker.cancel_job(job.id) is True
    assert job.status == JobStatus.CANCELLED
