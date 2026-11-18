from extractor.models import FetchResult, DirectLink, DiscoveredPost


def test_fetch_result_serializes_original_field_names():
    result = FetchResult(
        postUrl="https://site.test/category",
        title="Example",
        domain="site.test",
        extractor="Website Post Crawler",
        duration=0,
        durationFormatted="1 Posts",
        thumbnail="",
        pageType="listing",
        directLinks=[],
        discoveredPosts=[DiscoveredPost("post-1", "https://site.test/video/1", "Video 1")],
    )
    data = result.to_dict()
    assert data["pageType"] == "listing"
    assert data["discoveredPosts"][0]["postUrl"].endswith("/video/1")
