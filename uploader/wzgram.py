from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from wzgram import Client

log=logging.getLogger("velofetch.uploader")

class WzgramUploader:
    """Uses the same WZGram Client(bot_token + API credentials) as the source bridge."""
    def __init__(self, client: Client, upload_workers: int=1):
        self.client=client
        self.semaphore=asyncio.Semaphore(upload_workers)

    async def upload(self, chat_id: int | str, path: Path, caption: str, thumbnail: Path | None=None, progress: Callable | None=None):
        async with self.semaphore:
            kwargs={"chat_id":chat_id,"video":str(path),"caption":caption,"supports_streaming":True}
            if thumbnail and thumbnail.exists(): kwargs["thumb"]=str(thumbnail)
            if progress:
                async def callback(current,total):
                    await progress(current,total)
                kwargs["progress"]=callback
            return await self.client.send_video(**kwargs)
