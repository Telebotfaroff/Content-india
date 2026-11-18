from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

from config import Settings

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
DIRECT_EXT={".mp4",".mkv",".webm",".mov",".avi",".flv",".m4v"}

def is_direct_video_url(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in DIRECT_EXT

def quality_selector(quality: str) -> str:
    q=(quality or "best").lower()
    if q=="best": return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    if q.isdigit() or re.fullmatch(r"\d+p",q):
        h=int(q.rstrip("p"))
        return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
    return q

class DownloadEngine:
    def __init__(self, settings: Settings):
        self.settings=settings
        self.processes: dict[str, asyncio.subprocess.Process]={}

    async def cancel(self, job_id: str):
        proc=self.processes.get(job_id)
        if proc and proc.returncode is None:
            proc.terminate()
            try: await asyncio.wait_for(proc.wait(),3)
            except asyncio.TimeoutError: proc.kill()

    async def download(self, job_id: str, url: str, quality: str, progress=None) -> Path:
        self.settings.download_dir.mkdir(parents=True,exist_ok=True)
        ext=Path(urlparse(url).path).suffix.lower()
        output=self.settings.download_dir/f"job_{job_id}{ext if ext in DIRECT_EXT else '.%(ext)s'}"
        if is_direct_video_url(url) and shutil.which("aria2c"):
            final=self.settings.download_dir/f"job_{job_id}{ext}"
            args=["aria2c",f"--max-connection-per-server={self.settings.aria2c_connections}",f"--split={self.settings.aria2c_split}","--min-split-size=1M","--file-allocation=none","--continue=true","--allow-overwrite=true","--auto-file-renaming=false","--check-certificate=false",f"--user-agent={UA}","--summary-interval=1","--console-log-level=warn","--dir",str(self.settings.download_dir),"--out",final.name,url]
            proc=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
            self.processes[job_id]=proc
            async for raw in proc.stdout:
                line=raw.decode(errors="replace")
                m=re.search(r"\[#[0-9a-f]+\s+([^\s/]+)/([^\s(]+)\((\d+)%\).*?DL:([^\s\]]+)(?:\s+ETA:([^\]]+))?",line,re.I)
                if m and progress: await progress(float(m.group(3)),m.group(4),m.group(5) or "")
            code=await proc.wait(); self.processes.pop(job_id,None)
            if code==0 and final.exists() and final.stat().st_size: return final
            raise RuntimeError(f"aria2c failed (exit {code})")
        args=["yt-dlp","--no-warnings","--no-check-certificates","--socket-timeout","20","--retries","3","--fragment-retries","3","--concurrent-fragments",str(self.settings.aria2c_connections)]
        if shutil.which("aria2c"):
            args.extend(["--downloader-args",f"aria2c:-x{self.settings.aria2c_connections} -s{self.settings.aria2c_split} -k1M"])
        args.extend(["--format",quality_selector(quality),"--merge-output-format","mp4","--newline","--progress","--output",str(output),url])
        proc=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        self.processes[job_id]=proc
        async for raw in proc.stdout:
            line=raw.decode(errors="replace")
            m=re.search(r"(\d+(?:\.\d+)?)%.*?at\s+([^\s]+).*?ETA\s+([^\s]+)",line)
            if m and progress: await progress(float(m.group(1)),m.group(2),m.group(3))
        code=await proc.wait(); self.processes.pop(job_id,None)
        if code!=0: raise RuntimeError(f"yt-dlp failed (exit {code})")
        candidates=list(self.settings.download_dir.glob(f"job_{job_id}.*"))
        candidates=[p for p in candidates if p.is_file() and not p.name.endswith((".part",".ytdl"))]
        if not candidates: raise RuntimeError("yt-dlp finished but output file was not found")
        return max(candidates,key=lambda p:p.stat().st_size)
