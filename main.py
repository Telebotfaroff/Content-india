from __future__ import annotations

import asyncio
import logging

from config import load_settings
from core.queue import InMemoryJobQueue
from core.workers import WorkerManager
from downloader.engine import DownloadEngine
from uploader.wzgram import WzgramUploader
from bot.handlers import BotHandlers


async def main():
    settings = load_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # This mirrors the original bridge: WZGram Client authenticates with
    # API_ID + API_HASH + BOT_TOKEN and handles both updates and MTProto media.
    from wzgram import Client

    client = Client(
        name=settings.session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
        workdir=str(settings.session_dir),
        in_memory=False,
        no_updates=False,
        skip_updates=True,
        workers=4,
        max_concurrent_transmissions=1,
    )

    queue = InMemoryJobQueue(settings.max_pending_uploads)
    downloader = DownloadEngine(settings)

    async def notify(job, text):
        chat_id = job.metadata.get("telegram_chat_id") or job.destination
        message_id = job.metadata.get("telegram_message_id")
        if not chat_id:
            return
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
