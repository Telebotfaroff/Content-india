import pytest

from core.models import DownloadJob, JobStatus
from core.queue import InMemoryJobQueue


@pytest.mark.asyncio
async def test_add_job_is_volatile_and_queued():
    queue = InMemoryJobQueue()
    job = DownloadJob(url="https://example.com/video", source="ytdlp")

    await queue.add(job)

    assert await queue.get(job.id) is job
    assert await queue.download_queue.get() is job
    assert job.status is JobStatus.QUEUED


@pytest.mark.asyncio
async def test_cancel_job():
    queue = InMemoryJobQueue()
    job = await queue.add(DownloadJob(url="https://example.com/video"))

    assert await queue.cancel(job.id) is True
    assert job.status is JobStatus.CANCELLED


def test_clear_finished_jobs():
    queue = InMemoryJobQueue()
    completed = DownloadJob(url="https://example.com/done")
    completed.status = JobStatus.COMPLETED
    active = DownloadJob(url="https://example.com/active")
    queue.jobs[completed.id] = completed
    queue.jobs[active.id] = active

    assert queue.clear_finished() == 1
    assert list(queue.jobs) == [active.id]
