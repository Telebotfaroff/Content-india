from core.models import DownloadJob, JobStatus
from bot.notifications import render_job_notification, render_batch_notification


def test_single_notification_shows_download_and_upload_stages():
    job = DownloadJob(url="https://example.com/video", title="Sample video", quality="1080p")
    job.status = JobStatus.UPLOADING
    job.download_progress = 100
    job.upload_progress = 42

    text = render_job_notification(job)

    assert "VELOFETCH · TRANSFER" in text
    assert "Download" in text
    assert "Telegram upload" in text
    assert "42%" in text


def test_batch_notification_shows_concurrent_download_and_upload():
    downloading = DownloadJob(url="https://example.com/one", title="Video one", batch_id="batch1")
    downloading.status = JobStatus.DOWNLOADING
    downloading.download_progress = 55

    uploading = DownloadJob(url="https://example.com/two", title="Video two", batch_id="batch1")
    uploading.status = JobStatus.UPLOADING
    uploading.upload_progress = 25

    completed = DownloadJob(url="https://example.com/three", title="Video three", batch_id="batch1")
    completed.status = JobStatus.COMPLETED

    text = render_batch_notification("batch1", [downloading, uploading, completed])

    assert "1/3 finished" in text
    assert "NOW DOWNLOADING" in text
    assert "NOW UPLOADING" in text
    assert "55%" in text
    assert "25%" in text
