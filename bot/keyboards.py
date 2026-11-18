from __future__ import annotations
from wzgram.types import InlineKeyboardMarkup, InlineKeyboardButton

QUALITIES=["best","2160p","1440p","1080p","720p","480p","360p"]

def quality_keyboard(key: str, include_destination: bool=True):
    rows=[]
    labels={"best":"Best","2160p":"4K","1440p":"2K","1080p":"1080p","720p":"720p","480p":"480p","360p":"360p"}
    rows.append([InlineKeyboardButton(labels[q],callback_data=f"qual|{key}|{q}") for q in QUALITIES[:4]])
    rows.append([InlineKeyboardButton(labels[q],callback_data=f"qual|{key}|{q}") for q in QUALITIES[4:]])
    return InlineKeyboardMarkup(rows)

def fetch_keyboard(key: str, info: dict, page: int=0, mode: str="posts"):
    rows=[]; posts=info.get("discoveredPosts",[]); links=info.get("directLinks",[])
    if mode=="posts" and posts:
        start=page*5
        for idx,p in enumerate(posts[start:start+5],start):
            rows.append([InlineKeyboardButton(f"🎬 {p.get('title','Post')[:48]}",callback_data=f"fpost|{key}|{idx}")])
            rows.append([InlineKeyboardButton("⬇️ Download",callback_data=f"fpostdl|{key}|{idx}"),InlineKeyboardButton("🔍 Streams",callback_data=f"finspect|{key}|{idx}")])
        rows.append([InlineKeyboardButton("Top 3",callback_data=f"fbatch|{key}|3"),InlineKeyboardButton("Top 5",callback_data=f"fbatch|{key}|5"),InlineKeyboardButton("Top 10",callback_data=f"fbatch|{key}|10")])
        rows.append([InlineKeyboardButton("Download All",callback_data=f"fbatch|{key}|all")])
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
    return InlineKeyboardMarkup(rows)
