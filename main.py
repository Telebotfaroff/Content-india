from __future__ import annotations

import asyncio
import logging
import time

from config import load_settings
from core.queue import InMemoryJobQueue
from core.workers import WorkerManager
from downloader.engine import DownloadEngine
from uploader.wzgram import WzgramUploader, apply_wzgram_tuning
from bot.handlers import BotHandlers
from bot.notifications import render_job_notification, render_batch_notification


async def main():
    settings = load_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    from wzgram import Client
    apply_wzgram_tuning()

    client = Client(
        name=settings.session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
        workdir=str(settings.session_dir),
        in_memory=False,
        no_updates=False,
        skip_updates=True,
        sleep_threshold=60,
        workers=4,
        max_concurrent_transmissions=settings.upload_workers,
    )

    queue = InMemoryJobQueue(settings.max_pending_uploads)
    downloader = DownloadEngine(settings)
    last_notification_edit: dict[str, float] = {}
    notification_locks: dict[str, asyncio.Lock] = {}
    batch_notification_ids: dict[str, int] = {}

    async def notify(job, detail=""):
        chat_id = job.metadata.get("telegram_chat_id") or job.destination
        if not chat_id:
            return

        is_batch = bool(job.batch_id)
        key = f"batch:{job.batch_id}" if is_batch else f"job:{job.id}"
        lock = notification_locks.setdefault(key, asyncio.Lock())

        async with lock:
            now = time.monotonic()
            jobs = (
                [item for item in queue.snapshot() if item.batch_id == job.batch_id]
                if is_batch else [job]
            )
            terminal = all(
                str(item.status) in ("completed", "failed", "cancelled")
                for item in jobs
            )
            if not terminal and now - last_notification_edit.get(key, 0) < settings.progress_update_interval:
                return
            last_notification_edit[key] = now

            content = (
                render_batch_notification(job.batch_id, jobs, detail)
                if is_batch else render_job_notification(job, detail)
            )

            message_id = (
                batch_notification_ids.get(job.batch_id) if is_batch
                else job.metadata.get("telegram_message_id")
            ) or job.metadata.get("telegram_message_id")
            try:
                if message_id:
                    await client.edit_message_text(chat_id, int(message_id), content)
                else:
                    sent = await client.send_message(chat_id, content)
                    message_id = sent.id
                    if is_batch:
                        batch_notification_ids[job.batch_id] = message_id
                        for item in jobs:
                            item.metadata["telegram_message_id"] = message_id
                    else:
                        job.metadata["telegram_message_id"] = message_id
            except Exception:
                # Never send a replacement message after an edit failure:
                # that would create duplicate notifications.
                logging.getLogger("velofetch").debug(
                    "Telegram notification update failed", exc_info=True
                )

    uploader = WzgramUploader(client, settings.upload_workers)
    workers = WorkerManager(settings, queue, downloader, uploader, notify)
    handlers = BotHandlers(client, settings, queue, workers, notify)
    handlers.register()

    await client.start()
    try:
        await workers.start()
        me = await client.get_me()
        logging.getLogger("velofetch").info(
            "Connected as @%s", getattr(me, "username", None)
        )
        await asyncio.Event().wait()
    finally:
        await workers.stop()
        await client.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
