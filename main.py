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
    last_notification_edit = {}

    async def notify(job, text):
        chat_id = job.metadata.get("telegram_chat_id") or job.destination
        message_id = job.metadata.get("telegram_message_id")
        if not chat_id:
            return
        now = time.monotonic()
        key = job.id
        terminal = str(job.status) in ("completed", "failed", "cancelled")
        if not terminal and now - last_notification_edit.get(key, 0) < settings.progress_update_interval:
            return
        last_notification_edit[key] = now
        try:
            content = f"**{job.id}** · {job.status}\n{text}"
            if message_id:
                await client.edit_message_text(chat_id, int(message_id), content)
            else:
                sent = await client.send_message(chat_id, content)
                job.metadata["telegram_message_id"] = sent.id
        except Exception:
            logging.getLogger("velofetch").debug("Telegram notification update failed", exc_info=True)

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
