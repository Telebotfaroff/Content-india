from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from core.models import DownloadJob, JobStatus
from core.queue import InMemoryJobQueue
from downloader.engine import DownloadEngine
from media.processor import prepare, format_bytes, cleanup_job_files
from uploader.wzgram import WzgramUploader
from extractor.fetch import resolve_post_stream

log = logging.getLogger("velofetch.workers")


class WorkerManager:
    def __init__(self, settings, queue: InMemoryJobQueue, downloader: DownloadEngine,
                 uploader: WzgramUploader, notify):
        self.settings = settings
        self.queue = queue
        self.downloader = downloader
        self.uploader = uploader
        self.notify = notify
        self.tasks = []

        # Keep at most one upload in progress and one next file on disk.
        # A slot is acquired before downloading and released only after upload
        # cleanup (or a failed/cancelled download).
        self._pipeline_slots = asyncio.Semaphore(max(1, settings.upload_workers + 1))

    async def start(self):
        for i in range(self.settings.download_workers):
            self.tasks.append(asyncio.create_task(self._download_worker(i + 1)))
        for i in range(self.settings.upload_workers):
            self.tasks.append(asyncio.create_task(self._upload_worker(i + 1)))

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def _download_worker(self, number):
        while True:
            job = await self.queue.download_queue.get()
            slot_owned = False
            try:
                if job.status == JobStatus.CANCELLED:
                    continue

                await self._pipeline_slots.acquire()
                slot_owned = True

                job.status = JobStatus.DOWNLOADING
                await self.notify(job, "⬇️ Download started")

                async def progress(percent, speed, eta):
                    job.download_progress = percent
                    job.progress = percent
                    await self.notify(job, f"⬇️ {percent:.1f}% · {speed} · ETA {eta}")

                download_url = job.url
                if job.source == "fetch":
                    resolved = await resolve_post_stream(job.url, job.quality)
                    download_url = resolved["downloadUrl"]
                    job.title = job.title or resolved.get("title")
                    if resolved.get("thumbnail"):
                        job.metadata["source_thumbnail_url"] = resolved["thumbnail"]

                job.file_path = await self.downloader.download(
                    job.id, download_url, job.quality, progress
                )
                if job.status == JobStatus.CANCELLED:
                    continue

                job.status = JobStatus.PROCESSING
                metadata, thumb = await prepare(
                    job.file_path,
                    self.settings,
                    job.id,
                    job.metadata.get("thumbnail_url")
                    or job.metadata.get("source_thumbnail_url", ""),
                )
                job.metadata.update(metadata)
                job.metadata["thumbnail"] = str(thumb) if thumb else ""
                job.status = JobStatus.READY

                # Transfer ownership of the slot to the upload worker. The
                # next download can start while this file is being uploaded.
                await self.queue.upload_queue.put(job)
                slot_owned = False

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                await self.notify(job, f"❌ Download failed: {exc}")
            finally:
                if slot_owned:
                    self._pipeline_slots.release()
                self.queue.download_queue.task_done()

    async def _upload_worker(self, number):
        while True:
            job = await self.queue.upload_queue.get()
            thumb = None
            try:
                if job.status == JobStatus.CANCELLED:
                    continue

                job.status = JobStatus.UPLOADING
                job.upload_progress = 0.0
                thumb = Path(job.metadata["thumbnail"]) if job.metadata.get("thumbnail") else None
                title = job.title or job.metadata.get("title") or job.file_path.stem
                caption = f"🎬 {title}"
                await self.notify(job, "⬆️ Upload started")

                async def progress(current, total):
                    if total:
                        job.upload_progress = current / total * 100
                        job.progress = job.upload_progress
                        await self.notify(
                            job,
                            f"⬆️ {job.progress:.1f}% · "
                            f"{format_bytes(current)}/{format_bytes(total)}",
                        )

                dest_mode = job.metadata.get("dest_mode", "chat")
                chat_destination = job.destination or job.metadata.get("telegram_chat_id")
                channel_destination = job.metadata.get("target_channel")

                if dest_mode == "channel":
                    if not channel_destination:
                        raise RuntimeError("Channel Only was selected, but no upload channel is configured.")
                    await self.uploader.upload(
                        channel_destination, job.file_path, caption, thumb, job.metadata, progress
                    )
                else:
                    sent_message = await self.uploader.upload(
                        chat_destination, job.file_path, caption, thumb, job.metadata, progress
                    )
                    if dest_mode == "both" and channel_destination:
                        try:
                            await self.uploader.copy_to(sent_message, channel_destination)
                        except Exception:
                            # Fallback to a second MTProto upload if server-side copy is unavailable.
                            await self.uploader.upload(
                                channel_destination, job.file_path, caption,
                                thumb, job.metadata, progress
                            )

                job.status = JobStatus.COMPLETED
                await self.notify(job, "✅ Upload completed")
                # Only clean local artifacts after every selected Telegram
                # destination has accepted the video. Failed uploads retain
                # their files so the job can be retried or inspected.
                cleanup_job_files(job.id, self.settings, job.file_path, thumb)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                await self.notify(job, f"❌ Upload failed: {exc}")
            finally:
                self._pipeline_slots.release()
                self.queue.upload_queue.task_done()
