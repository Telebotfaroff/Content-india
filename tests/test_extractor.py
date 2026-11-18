from extractor.fetch import _choose
from extractor.models import DirectLink
from downloader.engine import is_direct_video_url, quality_selector


def test_choose_exact_and_lower_quality():
    links = [
        DirectLink("1", "https://cdn.test/1080.mp4", quality="1080p"),
        DirectLink("2", "https://cdn.test/720.mp4", quality="720p"),
        DirectLink("3", "https://cdn.test/480.mp4", quality="480p"),
    ]
    assert _choose(links, "720p").directUrl.endswith("720.mp4")
    assert _choose(links, "600p").directUrl.endswith("480.mp4")


def test_quality_selector():
    assert quality_selector("best").startswith("bestvideo")
    assert "height<=1080" in quality_selector("1080p")


def test_direct_video_url_detection():
    assert is_direct_video_url("https://cdn.test/a.mp4?token=1")
    assert not is_direct_video_url("https://site.test/video/slug")
