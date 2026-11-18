from extractor.pagination import build_page_url


def test_path_pagination_pattern():
    assert build_page_url(
        "https://desixclip.net/",
        "https://desixclip.net/page/2/",
        3,
    ) == "https://desixclip.net/page/3/"


def test_query_pagination_pattern():
    assert build_page_url(
        "https://example.com/videos",
        "https://example.com/videos?page=2",
        12,
    ) == "https://example.com/videos?page=12"


def test_first_and_second_pages_are_preserved():
    base = "https://example.com/"
    second = "https://example.com/page/2/"
    assert build_page_url(base, second, 1) == base
    assert build_page_url(base, second, 2) == second


def test_rejects_different_domains():
    try:
        build_page_url("https://example.com/", "https://other.com/page/2/", 3)
    except ValueError as exc:
        assert "same website" in str(exc)
    else:
        raise AssertionError("Expected a domain validation error")


def test_rejects_second_url_without_page_number():
    try:
        build_page_url("https://example.com/", "https://example.com/archive/", 3)
    except ValueError as exc:
        assert "numeric page value" in str(exc)
    else:
        raise AssertionError("Expected a pagination token validation error")
