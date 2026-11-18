from __future__ import annotations

import re
from urllib.parse import urlparse


def build_page_url(base_url: str, second_url: str, page_number: int) -> str:
    """Build listing URLs using the numeric page token demonstrated by page 2."""
    if page_number < 1:
        raise ValueError("Page number must be at least 1.")

    base = urlparse(base_url.strip())
    second = urlparse(second_url.strip())
    if base.scheme not in ("http", "https") or not base.netloc:
        raise ValueError("The base URL must be an HTTP or HTTPS URL.")
    if second.scheme not in ("http", "https") or not second.netloc:
        raise ValueError("The page-2 URL must be an HTTP or HTTPS URL.")
    if base.netloc.lower() != second.netloc.lower():
        raise ValueError("Both URLs must use the same website/domain.")
    if base_url.strip().rstrip("/") == second_url.strip().rstrip("/"):
        raise ValueError("The page-2 URL must be different from the base URL.")

    if page_number == 1:
        return base_url.strip()
    if page_number == 2:
        return second_url.strip()

    matches = list(re.finditer(r"\d+", second_url))
    if not matches:
        raise ValueError("The page-2 URL must contain a numeric page value, such as /page/2/.")
    token = matches[-1]
    if int(token.group()) != 2:
        raise ValueError("Could not identify page number 2. Put the page number at the end of the URL, e.g. /page/2/.")
    return second_url[:token.start()] + str(page_number) + second_url[token.end():]
