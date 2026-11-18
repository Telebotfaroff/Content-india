from __future__ import annotations

import re
import uuid

from wzgram import filters
from wzgram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards import quality_keyboard, fetch_keyboard, batch_quality_keyboard
from core.models import DownloadJob
from extractor.fetch import fetch_direct_links

URL_RE = re.compile(r"https?://[^\s<>]+", re.I)


class BotHandlers:
    def __init__(self, client, settings, queue, workers, notify):
        self.client = client
        self.settings = settings
        self.queue = queue
        self.workers = workers
        self.notify = notify
        self.pending = {}
        self.autofetch_sessions = {}

    def _metadata(self, req: dict) -> dict:
        return {
            "telegram_chat_id": req["chat_id"],
            "telegram_message_id": req.get("reply_id"),
            "dest_mode": req.get("dest_mode", "both" if self.settings.target_channel else "chat"),
            "target_channel": self.settings.target_channel,
        }

    async def _queue_post(self, req: dict, post: dict, quality: str, batch_id: str | None = None):
        metadata = self._metadata(req)
        metadata["thumbnail_url"] = post.get("thumbnail", "")
        job = DownloadJob(
            url=post["postUrl"], source="fetch", quality=quality,
            destination=str(req["chat_id"]), batch_id=batch_id,
            title=post.get("title"), metadata=metadata,
        )
        await self.queue.add(job)
        return job

    def register(self):
        @self.client.on_message(filters.command(["start", "help"]))
        async def start(_, message):
            await message.reply_text(
                "⚡ **VeloFetch**\n\n"
                "/ytdlp <url> — direct video download with quality selection\n"
                "/fetch <url> — scan a page for posts and direct streams\n"
                "/autofetch — learn pagination and queue posts from multiple pages\n"
                "/queue — show in-memory jobs\n"
                "/cancel <job_id> — cancel a job\n\n"
                "You can also reply to a message containing a URL with /ytdlp or /fetch."
            )

        @self.client.on_message(filters.command(["ytdlp", "ytdl"]))
        async def ytdlp(_, message):
            text = message.text or ""
            reply = getattr(message, "reply_to_message", None)
            match = URL_RE.search(text) or URL_RE.search(getattr(reply, "text", "") or "")
            if not match:
                await message.reply_text("Send /ytdlp followed by a URL, or reply /ytdlp to a message containing one.")
                return
            url = match.group(0).rstrip(".,)")
            key = uuid.uuid4().hex[:8]
            req = {
                "url": url, "chat_id": message.chat.id, "reply_id": message.id,
                "dest_mode": "both" if self.settings.target_channel else "chat",
            }
            prompt = await message.reply_text(
                f"🎬 Select quality for {url}",
                reply_markup=quality_keyboard(key, bool(self.settings.target_channel)),
            )
            req["reply_id"] = prompt.id

        @self.client.on_message(filters.command(["fetch"]))
        async def fetch(_, message):
            text = message.text or ""
            reply = getattr(message, "reply_to_message", None)
            match = URL_RE.search(text) or URL_RE.search(getattr(reply, "text", "") or "")
            if not match:
                await message.reply_text("Send /fetch followed by a website/category/post URL.")
                return
            url = match.group(0).rstrip(".,)")
            status = await message.reply_text("🔍 Scanning with yt-dlp + HTML extractor…")
            key = uuid.uuid4().hex[:8]
            req = {
                "url": url, "chat_id": message.chat.id, "reply_id": status.id,
                "dest_mode": "both" if self.settings.target_channel else "chat",
                "batch_quality": "1080p", "posts_page": 0,
            }
            self.pending[key] = req
            try:
                result = await fetch_direct_links(url)
                data = result.to_dict()
                req["result"] = data
                mode = "links" if data["directLinks"] and not data["discoveredPosts"] else "posts"
                await status.edit_text(
                    f"🌐 **{data['title']}**\nPosts: {len(data['discoveredPosts'])} · Streams: {len(data['directLinks'])}",
                    reply_markup=fetch_keyboard(
                        key, data, 0, mode, bool(self.settings.target_channel), req["dest_mode"]
                    ),
                )
            except Exception as exc:
                await status.edit_text(f"❌ Extraction failed: {exc}\nTry /ytdlp with the post URL.")

        @self.client.on_message(filters.command(["autofetch"]))
        async def autofetch(_, message):
            session_key = (message.chat.id, getattr(message.from_user, "id", message.chat.id))
            self.autofetch_sessions[session_key] = {"step": "base"}
            await message.reply_text(
                "🌐 **AutoFetch · Step 1/3**\nSend the base listing URL (page 1).\n"
                "Send /cancel to stop."
            )

        @self.client.on_message(filters.text)
        async def autofetch_input(_, message):
            text = (message.text or "").strip()
            if text.startswith("/"):
                return
            session_key = (message.chat.id, getattr(message.from_user, "id", message.chat.id))
            session = self.autofetch_sessions.get(session_key)
            if not session:
                return

            if session["step"] == "base":
                match = URL_RE.search(text)
                if not match:
                    await message.reply_text("Please send a valid base URL, or /cancel.")
                    return
                session["base_url"] = match.group(0).rstrip(".,)")
                session["step"] = "second"
                await message.reply_text(
                    "🔎 **AutoFetch · Step 2/3**\n"
                    "Now send the URL for page 2, so I can detect the pagination pattern."
                )
                return

            if session["step"] == "second":
                match = URL_RE.search(text)
                if not match:
                    await message.reply_text("Please send a valid page-2 URL.")
                    return
                second_url = match.group(0).rstrip(".,)")
                try:
                    from extractor.pagination import build_page_url
                    build_page_url(session["base_url"], second_url, 3)
                except ValueError as exc:
                    await message.reply_text(f"❌ Could not detect pagination: {exc}\nSend the page-2 URL again.")
                    return
                session["second_url"] = second_url
                session["step"] = "count"
                await message.reply_text(
                    "📚 **AutoFetch · Step 3/3**\n"
                    "Send the total number of pages to scan (for example: 20). "
                    "Page 1 and page 2 are included."
                )
                return

            if session["step"] == "count":
                if not text.isdigit() or int(text) < 2 or int(text) > 200:
                    await message.reply_text("Send a number from 2 to 200. This is the total page count.")
                    return
                page_count = int(text)
                self.autofetch_sessions.pop(session_key, None)
                status = await message.reply_text(
                    f"🔍 AutoFetch started · scanning {page_count} pages…"
                )
                try:
                    from extractor.pagination import build_page_url
                    base_url = session["base_url"]
                    second_url = session["second_url"]
                    found = {}
                    errors = []
                    for page_no in range(1, page_count + 1):
                        page_url = build_page_url(base_url, second_url, page_no)
                        try:
                            result = await fetch_direct_links(page_url)
                            for post in result.to_dict().get("discoveredPosts", []):
                                post_url = post.get("postUrl", "").rstrip("/").lower()
                                if post_url:
                                    found.setdefault(post_url, post)
                        except Exception as exc:
                            errors.append(f"Page {page_no}: {str(exc)[:120]}")
                        if page_no == page_count or page_no % 2 == 0:
                            await status.edit_text(
                                f"🔍 AutoFetch scanning: {page_no}/{page_count} pages\n"
                                f"🎞 Unique posts found: {len(found)}"
                            )

                    if not found:
                        detail = "\n".join(errors[:5])
                        await status.edit_text(
                            "❌ AutoFetch found no posts across the selected pages."
                            + (f"\n{detail}" if detail else "")
                        )
                        return

                    req = {
                        "chat_id": message.chat.id,
                        "reply_id": status.id,
                        "dest_mode": "both" if self.settings.target_channel else "chat",
                    }
                    batch_id = uuid.uuid4().hex[:8]
                    queued = 0
                    for post in found.values():
                        await self._queue_post(req, post, "1080p", batch_id)
                        queued += 1
                    summary = (
                        f"🚀 **AutoFetch queued**\n"
                        f"📄 Pages scanned: {page_count}\n"
                        f"🎞 Unique posts queued: {queued}\n"
                        f"⚡ Batch: {batch_id}\n"
                        f"🎚 Quality: 1080p"
                    )
                    if errors:
                        summary += f"\n⚠️ Pages with errors: {len(errors)}"
                    await status.edit_text(summary)
                except Exception as exc:
                    await status.edit_text(f"❌ AutoFetch failed: {exc}")
                return

        @self.client.on_message(filters.command(["queue"]))
        async def queue_cmd(_, message):
            jobs = self.queue.snapshot()
            if not jobs:
                await message.reply_text("Queue is empty (in-memory queue).")
                return
            lines = [f"{j.id} · {j.status} · {j.progress:.0f}% · {j.title or j.url}" for j in jobs[-20:]]
            await message.reply_text("📊 **VeloFetch Queue**\n" + "\n".join(lines))

        @self.client.on_message(filters.command(["cancel"]))
        async def cancel(_, message):
            parts = (message.text or "").split(maxsplit=1)
            session_key = (message.chat.id, getattr(message.from_user, "id", message.chat.id))
            if len(parts) < 2:
                if self.autofetch_sessions.pop(session_key, None):
                    await message.reply_text("🛑 AutoFetch setup cancelled.")
                else:
                    await message.reply_text("Usage: /cancel JOB_ID")
                return
            job = await self.queue.get(parts[1].strip())
            if not job:
                await message.reply_text("Job not found.")
                return
            await self.queue.cancel(job.id)
            await self.workers.downloader.cancel(job.id)
            await message.reply_text(f"Cancelled {job.id}")

        @self.client.on_callback_query()
        async def callbacks(_, query):
            parts = (query.data or "").split("|")
            if not parts:
                return
            action = parts[0]
            if action == "noop":
                await query.answer()
                return

            if action in ("qual", "dest") and len(parts) == 3:
                key, value = parts[1], parts[2]
                req = self.pending.get(key)
                if not req:
                    await query.answer("Request expired", show_alert=True)
                    return
                if action == "dest":
                    if not self.settings.target_channel:
                        await query.answer("No TARGET_CHANNEL is configured", show_alert=True)
                        return
                    req["dest_mode"] = value
                    await query.answer("Destination updated")
                    await query.message.edit_reply_markup(
                        reply_markup=quality_keyboard(key, True)
                    )
                    return
                job = DownloadJob(
                    url=req["url"], source="ytdlp", quality=value,
                    destination=str(req["chat_id"]), metadata=self._metadata(req),
                )
                await self.queue.add(job)
                await query.answer(f"Queued {value}")
                await query.message.edit_text(f"⏳ Queued {job.id} · {value}")

            elif action == "fpage" and len(parts) == 3:
                key, page = parts[1], int(parts[2])
                req = self.pending.get(key)
                if not req or "result" not in req:
                    await query.answer("Session expired", show_alert=True)
                    return
                req["posts_page"] = page
                await query.message.edit_reply_markup(reply_markup=fetch_keyboard(
                    key, req["result"], page, "posts", bool(self.settings.target_channel), req["dest_mode"]
                ))
                await query.answer()

            elif action == "fmode" and len(parts) == 3:
                key, mode = parts[1], parts[2]
                req = self.pending.get(key)
                if not req or "result" not in req:
                    await query.answer("Session expired", show_alert=True)
                    return
                await query.message.edit_reply_markup(reply_markup=fetch_keyboard(
                    key, req["result"], req.get("posts_page", 0), mode,
                    bool(self.settings.target_channel), req["dest_mode"]
                ))
                await query.answer()

            elif action == "fqualmenu" and len(parts) == 2:
                key = parts[1]
                if key not in self.pending:
                    await query.answer("Session expired", show_alert=True)
                    return
                await query.message.reply_text("Choose batch quality:", reply_markup=batch_quality_keyboard(key))
                await query.answer()

            elif action == "fqual" and len(parts) == 3:
                key, quality = parts[1], parts[2]
                req = self.pending.get(key)
                if not req:
                    await query.answer("Session expired", show_alert=True)
                    return
                req["batch_quality"] = quality
                req["result"]["batchQuality"] = quality
                await query.answer(f"Batch quality: {quality}")
                await query.message.edit_text(
                    f"Batch quality set to {quality}.",
                    reply_markup=fetch_keyboard(
                        key, req["result"], req.get("posts_page", 0), "posts",
                        bool(self.settings.target_channel), req["dest_mode"]
                    ),
                )

            elif action == "fdest" and len(parts) == 3:
                key, mode = parts[1], parts[2]
                req = self.pending.get(key)
                if not req:
                    await query.answer("Session expired", show_alert=True)
                    return
                req["dest_mode"] = mode
                await query.answer("Destination updated")
                await query.message.edit_reply_markup(reply_markup=fetch_keyboard(
                    key, req["result"], req.get("posts_page", 0),
                    "posts" if req["result"]["discoveredPosts"] else "links",
                    bool(self.settings.target_channel), mode
                ))

            elif action == "fpostdl" and len(parts) == 3:
                key, idx = parts[1], int(parts[2])
                req = self.pending.get(key)
                if not req:
                    await query.answer("Session expired", show_alert=True)
                    return
                posts = req["result"]["discoveredPosts"]
                if idx < 0 or idx >= len(posts):
                    await query.answer("Post not found", show_alert=True)
                    return
                job = await self._queue_post(req, posts[idx], req["batch_quality"])
                await query.answer("Post queued")
                await self.notify(job, "⏳ Added to download queue")

            elif action == "finspect" and len(parts) == 3:
                key, idx = parts[1], int(parts[2])
                req = self.pending.get(key)
                if not req:
                    await query.answer("Session expired", show_alert=True)
                    return
                post = req["result"]["discoveredPosts"][idx]
                await query.answer("Extracting streams…")
                result = await fetch_direct_links(post["postUrl"])
                req["result"]["directLinks"] = result.to_dict()["directLinks"]
                req["result"]["title"] = post["title"]
                req["result"]["thumbnail"] = post.get("thumbnail") or result.thumbnail
                await query.message.edit_text(
                    f"🔗 **Streams for {post['title']}**",
                    reply_markup=fetch_keyboard(
                        key, req["result"], 0, "links",
                        bool(self.settings.target_channel), req["dest_mode"]
                    ),
                )

            elif action == "fdl" and len(parts) == 3:
                key, idx = parts[1], int(parts[2])
                req = self.pending.get(key)
                if not req:
                    await query.answer("Session expired", show_alert=True)
                    return
                link = req["result"]["directLinks"][idx]
                metadata = self._metadata(req)
                metadata["source_thumbnail_url"] = req["result"].get("thumbnail", "")
                job = DownloadJob(
                    url=link["directUrl"], source="fetch-direct",
                    quality=link.get("quality", "best"),
                    destination=str(req["chat_id"]), title=req["result"]["title"],
                    metadata=metadata,
                )
                await self.queue.add(job)
                await query.answer("Stream queued")

            elif action == "fbatch" and len(parts) == 3:
                key, amount = parts[1], parts[2]
                req = self.pending.get(key)
                if not req:
                    await query.answer("Session expired", show_alert=True)
                    return
                posts = req["result"]["discoveredPosts"]
                selected = posts if amount == "all" else posts[:int(amount)]
                batch = uuid.uuid4().hex[:8]
                for post in selected:
                    await self._queue_post(req, post, req["batch_quality"], batch)
                await query.answer(f"Queued {len(selected)} posts")
                await query.message.edit_text(f"🚀 Batch queued: {len(selected)} posts · Batch {batch}")
