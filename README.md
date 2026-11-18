# VeloFetch

Python-only Telegram video downloader and uploader.

## Architecture

- **Telegram control and MTProto uploads:** WZGram
- **Authentication:** `BOT_TOKEN`, `API_ID`, `API_HASH`
- **Downloader:** yt-dlp + aria2c
- **Media processing:** FFmpeg + FFprobe
- **Queue:** Python asyncio, in-memory only
- **Persistence:** none — no SQLite, PostgreSQL, Redis or JSON job store

## Commands

- `/start`, `/help` — help
- `/ytdlp <url>` — direct URL download with quality selection
- `/fetch <url>` — scan a page for discovered posts and direct streams
- `/queue` — show current in-memory jobs
- `/cancel <job_id>` — cancel a job

Reply to a message containing a URL with `/ytdlp` or `/fetch` to use its URL.

## Fetch behaviour being preserved

- yt-dlp JSON extraction and HTML scraping run concurrently.
- HTML extraction checks OG/video metadata, base64 player parameters, anchors, video/source tags and script/JSON video URLs.
- Discovered posts are deduplicated; HTML post discovery is capped at 45.
- yt-dlp playlist extraction is capped at 35 entries.
- Results show five posts per page.
- Individual post download, individual post stream inspection, direct-stream selection and Top 3/5/10/All batch actions are supported.
- Batch quality selection supports 1080p, 720p and 480p.
- Hybrid pages can switch between post results and direct streams.

## Upload behaviour

WZGram authenticates using the bot token together with API ID and API hash. Videos are sent using MTProto `send_video`; when both chat and channel delivery are selected, the bot tries a server-side message copy for the secondary destination.

Set `TARGET_CHANNEL` to enable the Chat + Channel / Chat Only destination choice. The bot must have permission to post in the target channel.

## Google Colab

Open [VeloFetch_Colab.ipynb](VeloFetch_Colab.ipynb) in Google Colab and run the cells from top to bottom. The notebook clones the repository, installs FFmpeg/aria2 and Python requirements, prompts for `BOT_TOKEN`, `API_ID`, and `API_HASH`, then starts the bot with live logs. `TARGET_CHANNEL` is optional.

The credentials are entered at runtime rather than saved in the notebook. Keep the final run cell active while the bot is running. Colab runtimes are temporary, so the in-memory queue, WZGram session files and local downloads do not survive a runtime reset.

## Setup

1. Install Python 3.11 or newer.
2. Install system packages `ffmpeg` and `aria2`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in Telegram credentials.
5. Run `python main.py`.

## Volatile queue

Jobs, pending fetch sessions and settings are not persisted. Restarting the process clears in-memory jobs and pending selections. Downloaded files remain in `downloads/`; failed files are retained for manual retry/inspection. Successful uploads are cleaned up.

## Development status

The first working Python pipeline and Telegram handlers are in place. The original Node-to-Python IPC and web dashboard have been removed. Run the tests and verify WZGram against your credentials before using it for real uploads.

Never commit real credentials or WZGram session files.
