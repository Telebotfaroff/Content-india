from pathlib import Path
from types import SimpleNamespace

from media.processor import cleanup_job_files


def test_cleanup_removes_only_the_completed_jobs_artifacts(tmp_path):
    downloads = tmp_path / "downloads"
    temp = tmp_path / "temp"
    downloads.mkdir()
    temp.mkdir()

    video = downloads / "job_abc123.mp4"
    aria2_control = downloads / "job_abc123.mp4.aria2"
    partial = downloads / "job_abc123.f137.mp4.part"
    thumbnail = temp / "job_abc123_thumb.jpg"
    post_thumbnail = temp / "abc123_post_thumb.jpg"
    other_video = downloads / "job_other999.mp4"

    for path in (video, aria2_control, partial, thumbnail, post_thumbnail, other_video):
        path.write_bytes(b"x" * 10)

    settings = SimpleNamespace(download_dir=downloads, temp_dir=temp)
    removed, freed = cleanup_job_files("abc123", settings, video, thumbnail)

    assert removed == 5
    assert freed == 50
    assert not video.exists()
    assert not aria2_control.exists()
    assert not partial.exists()
    assert not thumbnail.exists()
    assert not post_thumbnail.exists()
    assert other_video.exists()


def test_cleanup_is_safe_when_artifacts_are_already_missing(tmp_path):
    downloads = tmp_path / "downloads"
    temp = tmp_path / "temp"
    downloads.mkdir()
    temp.mkdir()
    settings = SimpleNamespace(download_dir=downloads, temp_dir=temp)

    assert cleanup_job_files("missing1", settings) == (0, 0)
