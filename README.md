# VeloFetch

Python-only Telegram video downloader and uploader.

## Architecture

- **Telegram interface:** WZGram
- **MTProto authentication:** `API_ID`, `API_HASH`, `BOT_TOKEN`
- **Downloader:** yt-dlp + aria2c
- **Media inspection and thumbnails:** FFprobe + FFmpeg
- **Queue:** asyncio, in-memory only
- **Persistence:** none — no SQLite, PostgreSQL, Redis, or JSON job database

## Commands

- `/start` — open the control panel
- `/help` — command help
- `/ytdlp <url>` — direct URL download with quality selection
- `/fetch <url>` — scan a page, inspect discovered posts/direct streams, and select downloads
- `/queue` — show current in-memory jobs
- `/cancel <job_id>` — cancel a job

## Important runtime behaviour

The queue and pending `/fetch` selections live in memory. Restarting the process clears pending jobs and extraction sessions. Downloaded files already written to disk remain on disk.

## Current development status

The initial Python scaffold and volatile queue are committed. The original `/ytdlp` and `/fetch` handlers, extractor, downloader pipeline, media processor and verified WZGram client adapter are still being ported. `main.py` is currently a bootstrap placeholder and is not yet a running bot.

## Setup prerequisites

1. Python 3.11 or newer.
2. System packages: `ffmpeg` and `aria2`.
3. Python dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and configure credentials.

The bot will become runnable after the command handlers and WZGram adapter are connected. Never commit real Telegram credentials or session files.
