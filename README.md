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
- `/autofetch` — learn a site's pagination from page 1 and page 2 URLs, scan a chosen number of pages, deduplicate posts and queue them as one batch (default quality: 1080p)
- `/queue` — show current in-memory jobs
- `/channel` — owner-only private upload-channel manager; add/change/remove the destination from Telegram
- `/cancel <job_id>` — cancel a job

Reply to a message containing a URL with `/ytdlp` or `/fetch` to use its URL. `/autofetch` is a separate guided flow: send the base URL, the page-2 URL, then the total page count (2–200). Use `/cancel` during setup to stop it.

## Fetch behaviour being preserved

- yt-dlp JSON extraction and HTML scraping run concurrently.
- HTML extraction checks OG/video metadata, base64 player parameters, anchors, video/source tags and script/JSON video URLs.
- Discovered posts are deduplicated; HTML post discovery is capped at 45.
- yt-dlp playlist extraction is capped at 35 entries.
- Results show five posts per page.
- Individual post download, individual post stream inspection, direct-stream selection and Top 3/5/10/All batch actions are supported.
- Batch quality selection supports 1080p, 720p and 480p.
- Hybrid pages can switch between post results and direct streams.

## Download/upload pipeline

Batch downloads run one video at a time by default. As soon as a video finishes downloading and processing, it is handed to the upload worker; the next video downloads while the previous one uploads. The pipeline is bounded to the active upload plus one next file, so a large batch does not fill Colab's local disk before uploads begin. After every selected Telegram destination confirms the upload, VeloFetch automatically removes the video, thumbnail, and job-specific temporary/partial files (including downloader sidecars) from its managed download/temp folders. Failed uploads keep their files for retry or inspection. Increase `DOWNLOAD_WORKERS` only if you intentionally want parallel downloads and have enough storage.

## Upload behaviour

WZGram authenticates using the bot token together with API ID and API hash. Videos are sent using MTProto `send_video`; when both chat and channel delivery are selected, the bot tries a server-side message copy for the secondary destination.

Set `ADMIN_ID` to your numeric Telegram user ID to enable owner-only `/channel` management. Use `/channel` in Telegram, tap **Add / Change private channel**, then send the private channel ID (usually `-100...`) or forward a post from it. VeloFetch checks that the bot is an administrator and can post before saving the destination. The selected channel ID is stored in `sessions/target_channel.txt` (no database) and overrides optional `TARGET_CHANNEL`. Use `/channel` to remove it. New jobs offer Chat Only, Channel Only, and Chat + Channel choices. Channel Only uploads directly to the configured channel without sending a copy to the command chat. The bot must be an administrator with permission to post in the target channel.

## Telegram notifications

Each download uses one editable live status message from start to finish—download, processing, upload and completion. Batch jobs share one dashboard-style message showing total completion, the active download and active Telegram upload with separate progress bars. Updates are throttled to avoid flooding Telegram, and the bot edits the existing message instead of sending a new message for every stage.

## Google Colab

Open [VeloFetch_Colab.ipynb](VeloFetch_Colab.ipynb) in Google Colab and run the cells from top to bottom. The notebook clones the repository, installs FFmpeg/aria2 and Python requirements, prompts for `BOT_TOKEN`, `API_ID`, `API_HASH`, and `ADMIN_ID`, then starts the bot with live logs. `TARGET_CHANNEL` is optional; you can also add a private channel later with `/channel`.

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
