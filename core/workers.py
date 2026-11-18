from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from core.models import DownloadJob, JobStatus
from core.queue import InMemoryJobQueue
from downloader.engine import DownloadEngine
from media.processor import prepare, format_bytes, format_duration
from uploader.wzgram import WzgramUploader

log=logging.getLogger("velofetch.workers")

class WorkerManager:
    def __init__(self, settings, queue: InMemoryJobQueue, downloader: DownloadEngine, uploader: WzgramUploader, notify):
        self.settings=settings; self.queue=queue; self.downloader=downloader; self.uploader=uploader; self.notify=notify
        self.tasks=[]

    async def start(self):
        for i in range(self.settings.download_workers):
            self.tasks.append(asyncio.create_task(self._download_worker(i+1)))
        for i in range(self.settings.upload_workers):
            self.tasks.append(asyncio.create_task(self._upload_worker(i+1)))

    async def stop(self):
        for task in self.tasks: task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)

    async def _download_worker(self, number):
        while True:
            job=await self.queue.download_queue.get()
            if job.status==JobStatus.CANCELLED: self.queue.download_queue.task_done(); continue
            try:
                job.status=JobStatus.DOWNLOADING
                await self.notify(job,"⬇️ Download started")
                async def progress(percent,speed,eta):
                    job.progress=percent
                    await self.notify(job,f"⬇️ {percent:.1f}% · {speed} · ETA {eta}")
                job.file_path=await self.downloader.download(job.id,job.url,job.quality,progress)
                if job.status==JobStatus.CANCELLED: continue
                job.status=JobStatus.PROCESSING
                metadata,thumb=await prepare(job.file_path,self.settings)
                job.metadata.update(metadata); job.metadata["thumbnail"]=str(thumb) if thumb else ""
                job.status=JobStatus.READY
                await self.queue.upload_queue.put(job)
            except asyncio.CancelledError: raise
            except Exception as exc:
                job.status=JobStatus.FAILED; job.error=str(exc)
                await self.notify(job,f"❌ Download failed: {exc}")
            finally:
                self.queue.download_queue.task_done()

    async def _upload_worker(self, number):
        while True:
            job=await self.queue.upload_queue.get()
            try:
                if job.status==JobStatus.CANCELLED: continue
                job.status=JobStatus.UPLOADING
                thumb=Path(job.metadata["thumbnail"]) if job.metadata.get("thumbnail") else None
                size=format_bytes(job.metadata.get("size",0))
                duration=format_duration(job.metadata.get("duration",0))
                caption=f"🎬 {job.title or job.metadata.get('title') or job.file_path.stem}\n📺 {job.metadata.get('height',0)}p · ⏱ {duration} · 📦 {size}"
                await self.notify(job,"⬆️ Upload started")
                async def progress(current,total):
                    if total: await self.notify(job,f"⬆️ {current/total*100:.1f}% · {format_bytes(current)}/{format_bytes(total)}")
                await self.uploader.upload(job.destination or job.metadata.get("chat_id"),job.file_path,caption,thumb,progress)
                job.status=JobStatus.COMPLETED
                await self.notify(job,"✅ Upload completed")
                try: job.file_path.unlink(missing_ok=True)
                except OSError: pass
                if thumb: thumb.unlink(missing_ok=True)
            except asyncio.CancelledError: raise
            except Exception as exc:
                job.status=JobStatus.FAILED; job.error=str(exc)
                await self.notify(job,f"❌ Upload failed: {exc}")
            finally:
                self.queue.upload_queue.task_done()
