from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Callable

from wzgram import Client

log = logging.getLogger("velofetch.uploader")


def apply_wzgram_tuning() -> None:
    """Port the runtime tuning used by the original VeloFetch WZGram bridge."""
    try:
        from pyrogram.session.session import Session
        Session.MAX_SKEW_AHEAD = 86400
        Session.MAX_SKEW_BEHIND = 86400
        Session.MEDIA_WAIT_TIMEOUT = int(os.getenv("WZGRAM_MEDIA_TIMEOUT", "90"))
        Session.MAX_INFLIGHT_MEDIA = int(os.getenv("WZGRAM_MAX_INFLIGHT_MEDIA", "12"))
        Session.MAX_INFLIGHT_PACKETS = int(os.getenv("WZGRAM_MAX_INFLIGHT_PACKETS", "32"))
    except Exception:
        log.debug("WZGram session tuning not available", exc_info=True)
    try:
        from pyrogram.connection.transport.tcp.tcp import TCP
        TCP.TIMEOUT = int(os.getenv("WZGRAM_TCP_TIMEOUT", "30"))
        TCP.SOCKET_BUFFER = int(os.getenv("WZGRAM_SOCKET_BUFFER", "4194304"))
    except Exception:
        log.debug("WZGram TCP tuning not available", exc_info=True)
    try:
        from pyrogram.client import Client as PyroClient, _transfer_budgets
        target = int(os.getenv("WZGRAM_MAX_READ_AHEAD", "256"))
        if PyroClient.MAX_READ_AHEAD_CHUNKS != target:
            PyroClient.MAX_READ_AHEAD_CHUNKS = target
            _transfer_budgets.clear()
    except Exception:
        log.debug("WZGram read-ahead tuning not available", exc_info=True)
    try:
        import pyrogram.methods.advanced.save_file as save_file
        save_file.READ_BUFFER = 16 * 1024 * 1024
        save_file.MAX_BATCH = 32 * 1024 * 1024
        save_file.PACER_BURST = 32
        save_file.WORKERS_PER_SESSION = max(1, int(os.getenv("WZGRAM_UPLOAD_WORKERS_PER_SESSION", "4")))
    except Exception:
        log.debug("WZGram save-file tuning not available", exc_info=True)


class WzgramUploader:
    """MTProto media transport through WZGram; control updates use the same WZGram client."""
    def __init__(self, client: Client, upload_workers: int = 1):
        self.client = client
        self.semaphore = asyncio.Semaphore(upload_workers)

    async def upload(
        self, chat_id: int | str, path: Path, caption: str,
        thumbnail: Path | None = None, metadata: dict | None = None,
        progress: Callable | None = None,
    ):
        if not path.exists() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"Video file missing or empty: {path}")
        metadata = metadata or {}
        kwargs = {
            "chat_id": chat_id,
            "video": str(path),
            "caption": caption[:1024],
            "supports_streaming": True,
        }
        if thumbnail and thumbnail.exists():
            kwargs["thumb"] = str(thumbnail)
        for key in ("duration", "width", "height"):
            if metadata.get(key):
                kwargs[key] = int(metadata[key])
        if progress:
            async def callback(current, total):
                await progress(current, total)
            kwargs["progress"] = callback
        async with self.semaphore:
            return await self.client.send_video(**kwargs)

    async def copy_to(self, sent_message, chat_id: int | str):
        """Use Telegram's server-side MTProto copy where possible; no second local upload."""
        if sent_message is not None and hasattr(sent_message, "copy"):
            return await sent_message.copy(chat_id)
        raise RuntimeError("WZGram message copy is unavailable")
