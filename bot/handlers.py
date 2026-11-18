from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

from wzgram import filters
from wzgram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards import quality_keyboard, fetch_keyboard
from core.models import DownloadJob
from extractor.fetch import fetch_direct_links, resolve_post_stream

URL_RE=re.compile(r"https?://[^\s<>]+",re.I)

class BotHandlers:
    def __init__(self, client, settings, queue, workers, notify):
        self.client=client; self.settings=settings; self.queue=queue; self.workers=workers; self.notify=notify
        self.pending={}; self._seen=set()

    def register(self):
        @self.client.on_message(filters.command(["start","help"]))
        async def start(_, message):
            await message.reply_text("⚡ **VeloFetch**\n\n/ytdlp <url> — direct downloader\n/fetch <url> — scan posts and direct streams\n/queue — active in-memory jobs")
        @self.client.on_message(filters.command(["ytdlp","ytdl"]))
        async def ytdlp(_, message):
            text=message.text or ""; reply=getattr(message,"reply_to_message",None)
            match=URL_RE.search(text) or URL_RE.search(getattr(reply,"text","") or "")
            if not match:
                await message.reply_text("Send /ytdlp followed by a URL, or reply /ytdlp to a message containing one."); return
            url=match.group(0).rstrip(".,)")
            key=uuid.uuid4().hex[:8]
            self.pending[key]={"url":url,"chat_id":message.chat.id,"reply_id":message.id}
            await message.reply_text(f"🎬 Select quality for {url}",reply_markup=quality_keyboard(key))
        @self.client.on_message(filters.command(["fetch"]))
        async def fetch(_, message):
            text=message.text or ""; reply=getattr(message,"reply_to_message",None)
            match=URL_RE.search(text) or URL_RE.search(getattr(reply,"text","") or "")
            if not match:
                await message.reply_text("Send /fetch followed by a website/category/post URL."); return
            url=match.group(0).rstrip(".,)")
            status=await message.reply_text("🔍 Scanning with yt-dlp + HTML extractor…")
            key=uuid.uuid4().hex[:8]
            self.pending[key]={"url":url,"chat_id":message.chat.id,"reply_id":status.id}
            try:
                result=await fetch_direct_links(url)
                data=result.to_dict()
                self.pending[key]["result"]=data
                mode="links" if data["directLinks"] and not data["discoveredPosts"] else "posts"
                await status.edit_text(f"🌐 **{data['title']}**\nPosts: {len(data['discoveredPosts'])} · Streams: {len(data['directLinks'])}",reply_markup=fetch_keyboard(key,data,0,mode))
            except Exception as exc:
                await status.edit_text(f"❌ Extraction failed: {exc}\nTry /ytdlp with the post URL.")
        @self.client.on_message(filters.command(["queue"]))
        async def queue_cmd(_, message):
            jobs=self.queue.snapshot()
            if not jobs: await message.reply_text("Queue is empty (in-memory queue)."); return
            lines=[f"{j.id} · {j.status} · {j.progress:.0f}% · {j.title or j.url}" for j in jobs[-20:]]
            await message.reply_text("📊 **VeloFetch Queue**\n"+"\n".join(lines))
        @self.client.on_message(filters.command(["cancel"]))
        async def cancel(_, message):
            parts=(message.text or "").split(maxsplit=1)
            if len(parts)<2: await message.reply_text("Usage: /cancel JOB_ID"); return
            job=await self.queue.get(parts[1].strip())
            if not job: await message.reply_text("Job not found."); return
            await self.queue.cancel(job.id); await self.workers.downloader.cancel(job.id)
            await message.reply_text(f"Cancelled {job.id}")
        @self.client.on_callback_query()
        async def callbacks(_, query):
            data=(query.data or "").split("|")
            if not data: return
            action=data[0]
            if action=="noop": await query.answer(); return
            if action=="qual" and len(data)==3:
                key,quality=data[1],data[2]; req=self.pending.get(key)
                if not req: await query.answer("Request expired",show_alert=True); return
                job=DownloadJob(url=req["url"],source="ytdlp",quality=quality,destination=str(req["chat_id"]),title=None)
                await self.queue.add(job); await query.answer(f"Queued {quality}")
                await query.message.edit_text(f"⏳ Queued {job.id} · {quality}")
            elif action=="fpage" and len(data)==3:
                key,page=data[1],int(data[2]); req=self.pending.get(key)
                if not req or "result" not in req: await query.answer("Session expired",show_alert=True); return
                result=req["result"]; mode="posts"
                await query.message.edit_reply_markup(reply_markup=fetch_keyboard(key,result,page,mode)); await query.answer()
            elif action=="fmode" and len(data)==3:
                key,mode=data[1],data[2]; req=self.pending.get(key)
                if not req or "result" not in req: await query.answer("Session expired",show_alert=True); return
                await query.message.edit_reply_markup(reply_markup=fetch_keyboard(key,req["result"],0,mode)); await query.answer()
            elif action=="fpostdl" and len(data)==3:
                key,idx=data[1],int(data[2]); req=self.pending.get(key)
                if not req: await query.answer("Session expired",show_alert=True); return
                post=req["result"]["discoveredPosts"][idx]
                job=DownloadJob(url=post["postUrl"],source="fetch",quality="1080p",destination=str(req["chat_id"]),title=post["title"],metadata={"thumbnail_url":post.get("thumbnail","")})
                await self.queue.add(job); await query.answer("Post queued")
            elif action=="finspect" and len(data)==3:
                key,idx=data[1],int(data[2]); req=self.pending.get(key)
                if not req: await query.answer("Session expired",show_alert=True); return
                post=req["result"]["discoveredPosts"][idx]
                await query.answer("Extracting streams…")
                result=await fetch_direct_links(post["postUrl"])
                req["result"]["directLinks"]=result.to_dict()["directLinks"]
                req["result"]["title"]=post["title"]
                req["result"]["thumbnail"]=post.get("thumbnail") or result.thumbnail
                await query.message.edit_text(f"🔗 **Streams for {post['title']}**",reply_markup=fetch_keyboard(key,req["result"],0,"links"))
            elif action=="fdl" and len(data)==3:
                key,idx=data[1],int(data[2]); req=self.pending.get(key)
                if not req: await query.answer("Session expired",show_alert=True); return
                link=req["result"]["directLinks"][idx]
                job=DownloadJob(url=link["directUrl"],source="fetch-direct",quality=link.get("quality","best"),destination=str(req["chat_id"]),title=req["result"]["title"])
                await self.queue.add(job); await query.answer("Stream queued")
            elif action=="fbatch" and len(data)==3:
                key,amount=data[1],data[2]; req=self.pending.get(key)
                if not req: await query.answer("Session expired",show_alert=True); return
                posts=req["result"]["discoveredPosts"]
                selected=posts if amount=="all" else posts[:int(amount)]
                batch=uuid.uuid4().hex[:8]
                for post in selected:
                    await self.queue.add(DownloadJob(url=post["postUrl"],source="fetch",quality="1080p",destination=str(req["chat_id"]),batch_id=batch,title=post["title"],metadata={"thumbnail_url":post.get("thumbnail","")}))
                await query.answer(f"Queued {len(selected)} posts")
                await query.message.edit_text(f"🚀 Batch queued: {len(selected)} posts · Batch {batch}")
