from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from config import Settings

def format_bytes(n: int) -> str:
    value=float(n); units=("B","KB","MB","GB","TB"); i=0
    while value>=1024 and i<len(units)-1: value/=1024; i+=1
    return f"{value:.2f} {units[i]}"

def format_duration(n: float) -> str:
    n=max(0,int(n)); h,r=divmod(n,3600); m,s=divmod(r,60)
    return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

async def probe(path: Path) -> dict:
    proc=await asyncio.create_subprocess_exec("ffprobe","-v","quiet","-print_format","json","-show_format","-show_streams",str(path),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    out,err=await proc.communicate()
    if proc.returncode: raise RuntimeError(f"ffprobe failed: {err.decode(errors='replace')[-500:]}")
    data=json.loads(out); streams=data.get("streams",[]); fmt=data.get("format",{})
    video=next((x for x in streams if x.get("codec_type")=="video"),{})
    audio=next((x for x in streams if x.get("codec_type")=="audio"),{})
    return {"duration":float(fmt.get("duration") or video.get("duration") or 0),"width":int(video.get("width") or 0),"height":int(video.get("height") or 0),"videoCodec":str(video.get("codec_name") or "unknown").upper(),"audioCodec":str(audio.get("codec_name") or "unknown").upper(),"fps":video.get("avg_frame_rate","0/1"),"size":path.stat().st_size}

async def create_thumbnail(path: Path, settings: Settings) -> Path | None:
    if not shutil.which("ffmpeg"): return None
    target=settings.temp_dir/f"{path.stem}_thumb.jpg"
    vf=f"scale='min({settings.thumbnail_width},iw)':-2"
    proc=await asyncio.create_subprocess_exec("ffmpeg","-y","-ss",str(settings.thumbnail_timestamp),"-i",str(path),"-frames:v","1","-vf",vf,"-q:v",str(max(2,round((100-settings.thumbnail_quality)/10))),str(target),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    if proc.returncode==0 and target.exists() and target.stat().st_size<200*1024: return target
    return None

async def prepare(path: Path, settings: Settings) -> tuple[dict,Path|None]:
    metadata=await probe(path)
    thumb=await create_thumbnail(path,settings)
    return metadata,thumb
