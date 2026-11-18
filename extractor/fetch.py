from __future__ import annotations

import asyncio
import json
import re
import shutil
from urllib.parse import urlparse

from extractor.html_scraper import scrape_html, humanize
from extractor.models import DirectLink, FetchResult, DiscoveredPost

def _fmt_bytes(n: int) -> str:
    if not n: return "0 B"
    units=("B","KB","MB","GB","TB")
    i=0
    while n>=1024 and i<len(units)-1: n/=1024; i+=1
    return f"{n:.2f} {units[i]}"

def _duration(n: float) -> str:
    n=max(0,int(n)); h,r=divmod(n,3600); m,s=divmod(r,60)
    return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

async def _yt_json(url: str):
    if not shutil.which("yt-dlp"): return None
    proc=await asyncio.create_subprocess_exec(
        "yt-dlp","--dump-single-json","--flat-playlist","--playlist-end","35",
        "--no-warnings","--no-check-certificates","--socket-timeout","12",url,
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        out,err=await asyncio.wait_for(proc.communicate(),timeout=15)
    except asyncio.TimeoutError:
        proc.kill(); await proc.wait(); return None
    if proc.returncode or not out.strip(): return None
    try: return json.loads(out)
    except json.JSONDecodeError: return None

async def fetch_direct_links(raw_url: str) -> FetchResult:
    url=raw_url.strip()
    parsed=urlparse(url)
    if parsed.scheme not in ("http","https") or not parsed.netloc:
        raise ValueError("URL must start with http:// or https://")
    yt_data, html_data = await asyncio.gather(_yt_json(url), scrape_html(url), return_exceptions=True)
    if isinstance(html_data, Exception): html_data={"title":"","thumbnail":"","links":[],"discoveredPosts":[]}
    if isinstance(yt_data, Exception): yt_data=None
    links: list[DirectLink]=[]
    seen: set[str]=set()
    posts=list(html_data["discoveredPosts"])
    seen_posts={p.postUrl.rstrip("/").lower() for p in posts}
    if yt_data:
        entries=yt_data.get("entries") if yt_data.get("_type")=="playlist" else []
        for entry in entries or []:
            entry_url=entry.get("webpage_url") or entry.get("url")
            if not entry_url: continue
            from urllib.parse import urljoin
            full=urljoin(url,entry_url)
            norm=full.rstrip("/").lower()
            if norm in seen_posts: continue
            seen_posts.add(norm)
            thumbs=entry.get("thumbnails") or []
            posts.append(DiscoveredPost(f"yt-post-{len(posts)+1}",full,entry.get("title") or humanize(full),entry.get("thumbnail") or (thumbs[-1].get("url") if thumbs else ""),_duration(entry.get("duration") or 0) if entry.get("duration") else "",f"{entry.get('height')}p" if entry.get("height") else "Video"))
        formats=yt_data.get("formats") or []
        formats=sorted([f for f in formats if f.get("url","").startswith("http") and f.get("vcodec")!="none"],key=lambda f:(bool(f.get("acodec") and f.get("acodec")!="none"),int(f.get("height") or 0),int(f.get("filesize") or f.get("filesize_approx") or 0)),reverse=True)
        for f in formats:
            direct=f["url"]
            if direct in seen: continue
            seen.add(direct)
            h=int(f.get("height") or 0); ext=str(f.get("ext") or "mp4").lower()
            size=int(f.get("filesize") or f.get("filesize_approx") or 0)
            audio=f.get("acodec")!="none"
            links.append(DirectLink(f"yt-{f.get('format_id') or len(links)+1}",direct,f"{h}p" if h else "best",f"{h}p" if h else (f.get("format_note") or "Source"),ext,size,_fmt_bytes(size) if size else "Stream",str(f.get("vcodec") or "H264").split(".")[0].upper(),str(f.get("acodec") or "AAC").split(".")[0].upper() if audio else "Video Only",audio,"hls-stream" if ext=="m3u8" or "m3u8" in str(f.get("protocol")) else "yt-dlp-direct",f"{h or 'Source'}p {ext.upper()}"))
        if yt_data.get("url") and yt_data["url"] not in seen:
            f=yt_data; size=int(f.get("filesize") or f.get("filesize_approx") or 0)
            links.insert(0,DirectLink("yt-primary",f["url"],f"{f.get('height')}p" if f.get("height") else "best",f"{f.get('height')}p" if f.get("height") else "Best",str(f.get("ext") or "mp4"),size,_fmt_bytes(size) if size else "Direct Stream"))
    for item in html_data["links"]:
        if item.directUrl not in seen: seen.add(item.directUrl); links.append(item)
    if not links and not posts:
        raise RuntimeError("No direct video streams or video post links were found on this URL.")
    page_type="hybrid" if links and posts else "single_post" if links else "listing"
    duration=float((yt_data or {}).get("duration") or 0)
    domain=urlparse(url).hostname or ""
    return FetchResult(url,(yt_data or {}).get("title") or html_data.get("title") or f"Posts on {domain}",domain,(yt_data or {}).get("extractor_key") or (yt_data or {}).get("extractor") or ("Website Post Crawler" if page_type=="listing" else "HTML Direct Scraper"),duration,_duration(duration) if duration else (f"{len(posts)} Posts" if page_type=="listing" else "Direct File"),(yt_data or {}).get("thumbnail") or html_data.get("thumbnail") or next((p.thumbnail for p in posts if p.thumbnail),""),page_type,links,posts)

async def resolve_post_stream(post_url: str, quality: str="best") -> dict:
    try:
        html_data=await scrape_html(post_url)
        if html_data["links"]:
            links=html_data["links"]
            chosen=_choose(links,quality)
            return {"downloadUrl":chosen.directUrl,"title":html_data["title"] or humanize(post_url),"extractor":f"CDN Direct ({chosen.quality})","quality":chosen.quality,"thumbnail":html_data["thumbnail"]}
    except Exception: pass
    try:
        result=await fetch_direct_links(post_url)
        if result.directLinks:
            chosen=_choose(result.directLinks,quality)
            return {"downloadUrl":chosen.directUrl,"title":result.title,"extractor":f"{result.extractor} Direct ({chosen.quality})","quality":chosen.quality,"thumbnail":result.thumbnail}
    except Exception: pass
    return {"downloadUrl":post_url,"title":humanize(post_url),"extractor":"auto","quality":quality,"thumbnail":""}

def _choose(links, quality):
    if quality=="best": return links[0]
    exact=next((x for x in links if x.quality.lower()==quality.lower()),None)
    if exact: return exact
    target=int(re.sub(r"\D","",quality) or 0)
    return next((x for x in links if int(re.sub(r"\D","",x.quality) or 0) and int(re.sub(r"\D","",x.quality) or 0)<=target),links[0])
