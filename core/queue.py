from __future__ import annotations

import asyncio
from collections import OrderedDict

from core.models import DownloadJob, JobStatus


class InMemoryJobQueue:
    """Volatile queue by design. Nothing is written to a database or JSON file."""

    def __init__(self, max_pending_uploads: int = 2) -> None:
        self.jobs: OrderedDict[str, DownloadJob] = OrderedDict()
        self.download_queue: asyncio.Queue[DownloadJob] = asyncio.Queue()
        self.upload_queue: asyncio.Queue[DownloadJob] = asyncio.Queue(maxsize=max_pending_uploads)
        self._lock = asyncio.Lock()

    async def add(self, job: DownloadJob) -> DownloadJob:
        async with self._lock:
            self.jobs[job.id] = job
            await self.download_queue.put(job)
        return job

    async def get(self, job_id: str) -> DownloadJob | None:
        return self.jobs.get(job_id)

    async def cancel(self, job_id: str) -> bool:
        async with self._lock:
            job = self.jobs.get(job_id)
            if job is None or job.status in {
                JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED
            }:
                return False
            job.status = JobStatus.CANCELLED
            return True

    def snapshot(self) -> list[DownloadJob]:
        return list(self.jobs.values())

    def clear_finished(self) -> int:
        finished = {
            JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED
        }
        ids = [key for key, job in self.jobs.items() if job.status in finished]
        for key in ids:
            del self.jobs[key]
        return len(ids)
