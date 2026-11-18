from __future__ import annotations

import asyncio
import json
import shutil
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image

from config import Settings


def format_bytes(n: int) -> str:
    value=float(n); units=("B","KB","MB","GB","TB"); i=0
    while value>=1024 and i<len(units)-1: value/=1024; i+=1
    return f"{value:.2f} {units[i]}"


def format_duration(n: float) -> str:
    n=max(0,int(n)); h,r=divmod(n,3600); m,s=divmod(r,60)
    return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


async def probe(path: Path) -> dict:
    proc=await asyncio.create_subprocess_exec(
        "ffprobe","-v","quiet","-print_format","json","-show_format","-show_streams",str(path),
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE
    )
    out,err=await proc.communicate()
    if proc.returncode: raise RuntimeError(f"ffprobe failed: {err.decode(errors='replace')[-500:]}")
    data=json.loads(out); streams=data.get("streams",[]); fmt=data.get("format",{})
    video=next((x for x in streams if x.get("codec_type")=="video"),{})
    audio=next((x for x in streams if x.get("codec_type")=="audio"),{})
    fps_raw=video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    try:
        a,b=fps_raw.split("/",1); fps=round(float(a)/float(b),2) if float(b) else 0
    except Exception: fps=0
    return {
        "duration":float(fmt.get("duration") or video.get("duration") or 0),
        "width":int(video.get("width") or 0),"height":int(video.get("height") or 0),
        "videoCodec":str(video.get("codec_name") or "unknown").upper(),
        "audioCodec":str(audio.get("codec_name") or "unknown").upper(),
        "fps":fps,"size":path.stat().st_size,
    }


async def create_thumbnail(path: Path, settings: Settings) -> Path | None:
    if not shutil.which("ffmpeg"): return None
    target=settings.temp_dir/f"{path.stem}_thumb.jpg"
    vf=f"scale='min({settings.thumbnail_width},iw)':-2"
    quality=max(2,min(31,round((100-settings.thumbnail_quality)/4)))
    proc=await asyncio.create_subprocess_exec(
        "ffmpeg","-y","-ss",str(settings.thumbnail_timestamp),"-i",str(path),
        "-frames:v","1","-vf",vf,"-q:v",str(quality),str(target),
        stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()
    if proc.returncode==0 and target.exists() and target.stat().st_size<200*1024: return target
    return None


async def download_post_thumbnail(url: str, job_id: str, settings: Settings) -> Path | None:
    if not url: return None
    try:
        timeout=aiohttp.ClientTimeout(total=10,connect=5)
        async with aiohttp.ClientSession(timeout=timeout,headers={"User-Agent":"Mozilla/5.0"}) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                raw=await response.content.read(5*1024*1024)
        image=Image.open(BytesIO(raw)).convert("RGB")
        image.thumbnail((settings.thumbnail_width, settings.thumbnail_width))
        target=settings.temp_dir/f"{job_id}_post_thumb.jpg"
        image.save(target,"JPEG",quality=settings.thumbnail_quality,optimize=True)
        if target.stat().st_size>200*1024:
            image.save(target,"JPEG",quality=65,optimize=True)
        return target if target.exists() and target.stat().st_size<200*1024 else None
    except Exception:
        return None


async def prepare(path: Path, settings: Settings, job_id: str="", source_thumbnail_url: str="") -> tuple[dict,Path|None]:
    metadata=await probe(path)
    thumb=await download_post_thumbnail(source_thumbnail_url,job_id,settings) if source_thumbnail_url else None
    if thumb is None:
        thumb=await create_thumbnail(path,settings)
    return metadata,thumb
