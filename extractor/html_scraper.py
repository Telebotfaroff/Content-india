from __future__ import annotations

import asyncio
import base64
import html
import re
from urllib.parse import urljoin, urlparse, unquote

import aiohttp

from extractor.models import DirectLink, DiscoveredPost


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
VIDEO_EXT = re.compile(r"\.(mp4|mkv|webm|mov|avi|flv|m4v|m3u8)(?:\?|$)", re.I)
IMAGE_EXT = re.compile(r"\.(jpg|jpeg|png|gif|webp|svg|css|js|ico|woff|ttf|php|html|htm)(?:\?|$)", re.I)
SKIP_PATH = re.compile(r"/(cat|category|categories|tag|tags|pornstar|pornstars|model|models|channel|channels|user|users|profile|search|login|signup|register|terms|privacy|dmca|contact|about|faq|help|language|photos|pics|gallery|galleries|live|cams|ads|out|go|author|wp-content|wp-json|wp-admin|feed|comments|page)\b", re.I)
KNOWN_POST = re.compile(r"/(video-[a-z0-9_-]+|hd-porn/[a-z0-9_-]+|watch\?v=[a-z0-9_-]+|videos?/[a-z0-9_-]{3,}|v/[a-z0-9_-]{3,}|view_video[^\s\"'<>]*|movie/[a-z0-9_-]+|clip/[a-z0-9_-]+|post/[a-z0-9_-]+|episode/[a-z0-9_-]+|embed/[a-z0-9_-]+)", re.I)

def humanize(url: str) -> str:
    try:
        last = urlparse(url).path.rstrip("/").split("/")[-1] or "Video Post"
        last = unquote(re.sub(r"\.(html|php|htm|asp|aspx)$", "", last, flags=re.I))
        last = re.sub(r"^video-[a-z0-9]+[-_/]?", "", last, flags=re.I).replace("-", " ").replace("_", " ").strip()
        return last[:1].upper() + last[1:] if last else "Video Post"
    except Exception:
        return "Video Post"

def _size(text: str) -> int:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(B|KiB|MiB|GiB|TiB|KB|MB|GB|TB)", text, re.I)
    if not m: return 0
    unit = m.group(2).upper()
    power = {"B":1,"KIB":1024,"MIB":1024**2,"GIB":1024**3,"TIB":1024**4,"KB":1000,"MB":1000**2,"GB":1000**3,"TB":1000**4}
    return int(float(m.group(1))*power[unit])

def _resolve(base: str, raw: str) -> str:
    raw = html.unescape(raw.replace(r"\u0026", "&").replace(r"\/", "/")).strip()
    if not raw or raw.startswith(("javascript:", "data:", "#", "mailto:")): return ""
    out = urljoin(base, raw)
    return out if urlparse(out).scheme in ("http", "https") else ""

def _dedup(url: str) -> str:
    p = urlparse(url)
    return (p.scheme + "://" + p.netloc + p.path.rstrip("/") + ("?" + p.query if p.query else "")).lower()

async def _head_size(session, url: str, referer: str = "") -> int:
    try:
        async with session.head(url, headers={"User-Agent": UA, "Referer": referer}, timeout=aiohttp.ClientTimeout(total=4), allow_redirects=True) as r:
            return int(r.headers.get("Content-Length", "0"))
    except Exception:
        return 0

async def scrape_html(url: str) -> dict:
    timeout = aiohttp.ClientTimeout(total=14, connect=8)
    headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as response:
            response.raise_for_status()
            text = await response.text(errors="replace")
        title = ""
        thumbnail = ""
        links: list[DirectLink] = []
        seen_direct: set[str] = set()
        posts: dict[str, DiscoveredPost] = {}
        base_host = (urlparse(url).hostname or "").removeprefix("www.").lower()
        self_norm = _dedup(url)

        def add_candidate(raw: str, label: str = ""):
            full = _resolve(url, raw)
            if not full or full in seen_direct or IMAGE_EXT.search(full): return
            if not VIDEO_EXT.search(full) and not re.search(r"/(dload|download|dl|get_file|file)/|download=", full, re.I): return
            seen_direct.add(full)
            qm = re.search(r"\b(2160p|1440p|1080p|720p|480p|360p|240p|4k|2k)\b", label + " " + full, re.I)
            quality = qm.group(1).lower() if qm else "best"
            extm = VIDEO_EXT.search(full)
            ext = extm.group(1).lower() if extm else "mp4"
            size = _size(label)
            links.append(DirectLink(
                id=f"html-{len(links)+1}", directUrl=full, quality=quality,
                resolution=quality if quality != "best" else "Direct", ext=ext,
                filesize=size, filesizeFormatted=label if size else "Direct Link",
                sourceType="hls-stream" if ext == "m3u8" else "html-download",
                label=html.unescape(re.sub(r"<[^>]+>", " ", label)) or f"{quality} Direct {ext.upper()}",
            ))

        # Page title and thumbnail metadata.
        m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I|re.S)
        if m: title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        for pattern in [
            r'<meta[^>]+(?:property=["\']og:image(?::url|:secure_url)?["\']|itemprop=["\']thumbnailUrl["\']|name=["\']twitter:image["\'])[^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property=["\']og:image(?::url|:secure_url)?["\']|itemprop=["\']thumbnailUrl["\'])',
            r'poster=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)'
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                thumbnail = _resolve(url, m.group(1)); break

        # OG/video meta tags.
        for m in re.finditer(r'<meta\b[^>]+(?:itemprop=["\']contentUrl["\']|property=["\']og:video(?::url|:secure_url)?["\']|name=["\']twitter:player:stream["\'])[^>]+content=["\']([^"\']+)', text, re.I):
            add_candidate(m.group(1), "CDN Direct Video Stream")

        # Decode known base64 iframe player parameter.
        for m in re.finditer(r"player-x\.php\?q=([A-Za-z0-9+/=%_-]+)", text, re.I):
            try:
                raw = unquote(m.group(1))
                decoded = unquote(base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8", "ignore"))
                for item in re.findall(r"https?://[^\s\"'<>\\]+\.(?:mp4|mkv|webm|m3u8)(?:\?[^\s\"'<>\\]+)?", decoded, re.I):
                    add_candidate(item, "Player Embedded CDN Stream")
                if not thumbnail:
                    im = re.search(r"https?://[^\s\"'<>\\]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>\\]+)?", decoded, re.I)
                    if im: thumbnail = im.group(0)
            except Exception:
                pass

        # Anchor extraction: direct files and same-domain post cards.
        anchor_re = re.compile(r'<a\b([^>]*?)href=["\']([^"\']+)["\']([^>]*)>([\s\S]*?)</a>', re.I)
        for m in anchor_re.finditer(text):
            before, href, after, inner = m.groups()
            attrs = before + " " + after
            inner_text = html.unescape(re.sub(r"<[^>]+>", " ", inner))
            if VIDEO_EXT.search(href) or re.search(r"/(dload|download|dl|get_file|file)/|download=", href, re.I) or (re.search(r"\b(download|mp4|1080p|720p|480p|360p|2160p)\b", inner_text, re.I) and re.search(r"\.(mp4|mkv|webm|mov)|/dload/|download=", href, re.I)):
                add_candidate(href, inner_text)
                continue
            full = _resolve(url, href)
            if not full: continue
            parsed = urlparse(full)
            host = (parsed.hostname or "").removeprefix("www.").lower()
            if host != base_host or _dedup(full) == self_norm or SKIP_PATH.search(parsed.path) or re.search(r"\.(jpg|jpeg|png|gif|webp|svg|css|js|ico|json|xml|rss|txt)$", parsed.path, re.I):
                continue
            if re.match(r"^[/?&]*(page|p|sort|filter|o)=\d+", parsed.query, re.I): continue
            img = re.search(r"<img\b[^>]*>", inner, re.I)
            if not KNOWN_POST.search(parsed.path + "?" + parsed.query) and not img: continue
            context = text[max(0,m.start()-180):min(len(text),m.end()+280)]
            thumb = ""
            img_tag = img.group(0) if img else context
            tm = re.search(r'(?:data-src|data-original|data-lazy|data-thumb|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)', img_tag, re.I) or re.search(r'(?:data-src|src)=["\']([^"\']+)', inner, re.I)
            if tm and not re.search(r"blank|spacer|pixel|^data:", tm.group(1), re.I): thumb = _resolve(url, tm.group(1))
            attr_title = re.search(r'\btitle=["\']([^"\']+)["\']', attrs, re.I)
            alt = re.search(r'\balt=["\']([^"\']+)["\']', img.group(0), re.I) if img else None
            candidate = html.unescape((attr_title or alt).group(1) if attr_title or alt else inner_text).strip()
            if re.fullmatch(r"(\d{1,2}:\d{2}(?::\d{2})?|1080p|720p|480p|360p|4k|hd)", candidate, re.I): candidate = ""
            dur = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", context)
            qual = re.search(r"\b(4K|2160p|1440p|1080p|720p|480p|360p|HD)\b", context, re.I)
            norm = _dedup(full)
            if norm in posts:
                old = posts[norm]
                if not old.thumbnail and thumb: old.thumbnail = thumb
                if candidate and (old.title == humanize(full) or len(candidate)>len(old.title)): old.title = candidate
                if not old.duration and dur: old.duration = dur.group(1)
                if not old.qualityHint and qual: old.qualityHint = qual.group(1).upper()
            elif len(posts) < 45:
                posts[norm] = DiscoveredPost(f"post-{len(posts)+1}", full, candidate or humanize(full), thumb, dur.group(1) if dur else "", qual.group(1).upper() if qual else "HD")

        # <source> and <video> tags.
        for m in re.finditer(r'<(?:source|video)\b[^>]*src=["\']([^"\']+)["\'][^>]*>', text, re.I):
            tag = m.group(0)
            lm = re.search(r'(?:label|res|title|data-res)=["\']([^"\']+)["\']', tag, re.I)
            add_candidate(m.group(1), lm.group(1) if lm else "Direct Video Source")

        # Raw video URLs embedded in scripts/JSON.
        for m in re.finditer(r"https?:\\?/\\?/[^\s\"'<>\\]+\.(?:mp4|mkv|webm|m3u8)(?:\?[^\s\"'<>\\]+)?", text, re.I):
            add_candidate(m.group(0))

        # Enrich at most 10 direct links with HEAD sizes, in parallel.
        pending_sizes = [
            (link, _head_size(session, link.directUrl, url))
            for link in links[:10] if link.filesize <= 0 and link.ext != "m3u8"
        ]
        size_results = await asyncio.gather(
            *(task for _, task in pending_sizes), return_exceptions=True
        )
        for (link, _), size in zip(pending_sizes, size_results):
            if isinstance(size, int) and size > 0:
                link.filesize = size
                link.filesizeFormatted = f"{size / (1024 * 1024):.2f} MB"
        return {"title": title, "thumbnail": thumbnail, "links": links, "discoveredPosts": list(posts.values())}
