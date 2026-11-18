from __future__ import annotations

from core.models import DownloadJob, JobStatus


def _bar(value: float, width: int = 12) -> str:
    value = max(0.0, min(100.0, float(value or 0)))
    filled = round(width * value / 100)
    return "▰" * filled + "▱" * (width - filled)


def _title(job: DownloadJob) -> str:
    value = job.title or job.metadata.get("title") or job.url
    return str(value).replace("\n", " ").replace("`", "'")[:52]


def _status(job: DownloadJob) -> str:
    labels = {
        JobStatus.QUEUED: "🕓 Queued",
        JobStatus.EXTRACTING: "🔎 Extracting",
        JobStatus.DOWNLOADING: "⬇️ Downloading",
        JobStatus.PROCESSING: "⚙️ Processing",
        JobStatus.READY: "📦 Ready to upload",
        JobStatus.UPLOADING: "⬆️ Uploading",
        JobStatus.COMPLETED: "✅ Completed",
        JobStatus.FAILED: "❌ Failed",
        JobStatus.CANCELLED: "🚫 Cancelled",
    }
    return labels.get(job.status, str(job.status).title())


def render_job_notification(job: DownloadJob, detail: str = "") -> str:
    title = _title(job)
    lines = [
        "⚡ **VELOFETCH · TRANSFER**",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🎬 **{title}**",
        f"🆔 `{job.id}`  ·  🎯 **{job.quality}**",
        "",
        f"**Status:** {_status(job)}",
    ]

    if job.status in (JobStatus.DOWNLOADING, JobStatus.PROCESSING, JobStatus.READY,
                      JobStatus.UPLOADING, JobStatus.COMPLETED):
        pct = 100 if job.status in (JobStatus.READY, JobStatus.UPLOADING, JobStatus.COMPLETED) else job.download_progress
        lines.extend(["", f"⬇️ **Download**  {pct:.0f}%", f"`{_bar(pct)}`"])

    if job.status in (JobStatus.UPLOADING, JobStatus.COMPLETED):
        pct = 100 if job.status == JobStatus.COMPLETED else job.upload_progress
        lines.extend(["", f"⬆️ **Telegram upload**  {pct:.0f}%", f"`{_bar(pct)}`"])

    if job.status == JobStatus.FAILED and job.error:
        lines.extend(["", f"⚠️ {job.error[:250]}"])
    elif detail and job.status not in (JobStatus.DOWNLOADING, JobStatus.UPLOADING):
        lines.extend(["", detail[:250]])

    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "🌐 **VeloFetch** · Live transfer status"])
    return "\n".join(lines)


def render_batch_notification(batch_id: str, jobs: list[DownloadJob], detail: str = "") -> str:
    total = len(jobs)
    completed = sum(j.status == JobStatus.COMPLETED for j in jobs)
    failed = sum(j.status == JobStatus.FAILED for j in jobs)
    cancelled = sum(j.status == JobStatus.CANCELLED for j in jobs)
    finished = completed + failed + cancelled
    overall = (finished / total * 100) if total else 0.0

    lines = [
        "⚡ **VELOFETCH · BATCH TRANSFER**",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📚 **Batch** `{batch_id}`",
        f"📊 **Progress:** {finished}/{total} finished  ·  {overall:.0f}%",
        f"`{_bar(overall)}`",
        "",
        f"✅ Completed: **{completed}**    ❌ Failed: **{failed}**",
        f"🕓 Remaining: **{total - finished}**",
    ]

    downloading = next((j for j in jobs if j.status == JobStatus.DOWNLOADING), None)
    uploading = next((j for j in jobs if j.status == JobStatus.UPLOADING), None)
    if downloading:
        lines.extend([
            "",
            f"⬇️ **NOW DOWNLOADING** · {_title(downloading)}",
            f"`{_bar(downloading.download_progress)}` {downloading.download_progress:.0f}%",
        ])
    if uploading:
        lines.extend([
            "",
            f"⬆️ **NOW UPLOADING** · {_title(uploading)}",
            f"`{_bar(uploading.upload_progress)}` {uploading.upload_progress:.0f}%",
        ])

    waiting = sum(j.status == JobStatus.QUEUED for j in jobs)
    processing = sum(j.status in (JobStatus.PROCESSING, JobStatus.READY) for j in jobs)
    if waiting or processing:
        lines.extend(["", f"⏳ Queue: **{waiting}** waiting  ·  ⚙️ Processing: **{processing}**"])

    recent = [j for j in jobs if j.status in (JobStatus.FAILED, JobStatus.CANCELLED)]
    if recent:
        lines.extend(["", "**Needs attention**"])
        for item in recent[:3]:
            lines.append(f"• {_title(item)} — {_status(item)}")

    if finished == total and total:
        lines.extend(["", "🏁 **Batch finished**"])
    elif detail and not (downloading or uploading):
        lines.extend(["", detail[:180]])

    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "🌐 **VeloFetch** · One live batch notification"])
    return "\n".join(lines)
