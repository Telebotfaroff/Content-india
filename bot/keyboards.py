from __future__ import annotations
from wzgram.types import InlineKeyboardMarkup, InlineKeyboardButton

QUALITIES=["best","2160p","1440p","1080p","720p","480p","360p"]
LABELS={"best":"Best","2160p":"4K","1440p":"2K","1080p":"1080p","720p":"720p","480p":"480p","360p":"360p"}

def quality_keyboard(key: str, has_channel: bool=False):
    rows=[
        [InlineKeyboardButton(LABELS[q],callback_data=f"qual|{key}|{q}") for q in QUALITIES[:4]],
        [InlineKeyboardButton(LABELS[q],callback_data=f"qual|{key}|{q}") for q in QUALITIES[4:]],
    ]
    if has_channel:
        rows.append([
            InlineKeyboardButton("📥📤 Chat + Channel",callback_data=f"dest|{key}|both"),
            InlineKeyboardButton("📥 Chat Only",callback_data=f"dest|{key}|chat"),
        ])
    return InlineKeyboardMarkup(rows)

def fetch_keyboard(key: str, info: dict, page: int=0, mode: str="posts", has_channel: bool=False, dest_mode: str="both"):
    rows=[]; posts=info.get("discoveredPosts",[]); links=info.get("directLinks",[])
    if mode=="posts" and posts:
        start=page*5
        for idx,p in enumerate(posts[start:start+5],start):
            rows.append([InlineKeyboardButton("⬇️ Download",callback_data=f"fpostdl|{key}|{idx}"),InlineKeyboardButton("🔍 Streams",callback_data=f"finspect|{key}|{idx}")])
        rows.append([InlineKeyboardButton("Top 3",callback_data=f"fbatch|{key}|3"),InlineKeyboardButton("Top 5",callback_data=f"fbatch|{key}|5"),InlineKeyboardButton("Top 10",callback_data=f"fbatch|{key}|10")])
        rows.append([InlineKeyboardButton("Download All",callback_data=f"fbatch|{key}|all")])
        rows.append([InlineKeyboardButton(f"Quality: {info.get('batchQuality','1080p')}",callback_data=f"fqualmenu|{key}")])
        if links:
            rows.append([InlineKeyboardButton(f"🎬 View Direct Streams ({len(links)})",callback_data=f"fmode|{key}|links")])
        pages=max(1,(len(posts)+4)//5)
        nav=[]
        if page>0: nav.append(InlineKeyboardButton("◀️",callback_data=f"fpage|{key}|{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{pages}",callback_data="noop"))
        if page+1<pages: nav.append(InlineKeyboardButton("▶️",callback_data=f"fpage|{key}|{page+1}"))
        rows.append(nav)
    else:
        for idx,l in enumerate(links[:8]):
            rows.append([InlineKeyboardButton(f"⬇️ {l.get('quality','best')} {l.get('ext','mp4')} · {l.get('filesizeFormatted','Stream')}"[:60],callback_data=f"fdl|{key}|{idx}")])
        if posts: rows.append([InlineKeyboardButton(f"📂 View {len(posts)} posts",callback_data=f"fmode|{key}|posts")])
    if has_channel:
        rows.append([
            InlineKeyboardButton(("✅ " if dest_mode=="both" else "")+"📥📤 Chat + Channel",callback_data=f"fdest|{key}|both"),
            InlineKeyboardButton(("✅ " if dest_mode=="chat" else "")+"📥 Chat Only",callback_data=f"fdest|{key}|chat"),
        ])
    return InlineKeyboardMarkup(rows)

def batch_quality_keyboard(key: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(q,callback_data=f"fqual|{key}|{q}") for q in ("1080p","720p","480p")]
    ])
