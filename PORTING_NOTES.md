# VeloFetch porting notes

This repository is the Python rewrite. The original source archive was audited before implementation; the command workflows below are compatibility requirements.

## `/ytdlp`

Preserve the direct URL workflow:
- Accept a URL in the command or from a replied-to message.
- Present quality choices: Best, 2160p, 1440p, 1080p, 720p, 480p and 360p.
- Preserve destination selection where configured.
- Pass the selected format to yt-dlp and use aria2c for supported HTTP downloads.
- Run media probing/thumbnail processing before upload.

## `/fetch`

Preserve the existing extraction strategy rather than replacing it with a generic playlist command:
- Run yt-dlp JSON extraction and raw HTML extraction concurrently.
- Parse page metadata, anchors, video/source tags, embedded player configuration and script/JSON data.
- Merge and deduplicate discovered posts and direct media URLs.
- Show five posts per results page.
- Support individual post inspection, direct-stream selection, Top 3/5/10 and All batch actions.
- Keep the existing initial extraction bounds (yt-dlp entries: 35; HTML posts: 45) unless source-level tests prove the original implementation differs.
- Keep extraction results and callback context in memory only.

## Runtime and persistence

- No database, Redis, JSON job store or persistent queue.
- Queue, job state, fetch sessions and callback selections are process-memory state.
- Restarting the process discards active queue state. Files already downloaded remain on disk.
- Never delete a downloaded file until WZGram confirms a successful upload.

## Porting status

The command handlers, extraction implementation and WZGram adapter must be ported from the original source and tested before this project is considered runnable. Do not invent WZGram method names; verify them against the original bridge and installed WZGram package.
