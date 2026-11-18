from __future__ import annotations
from dataclasses import asdict, dataclass, field

@dataclass(slots=True)
class DirectLink:
    id: str
    directUrl: str
    quality: str = "best"
    resolution: str = "Direct"
    ext: str = "mp4"
    filesize: int = 0
    filesizeFormatted: str = "Direct Link"
    vcodec: str = "H264"
    acodec: str = "AAC"
    hasAudio: bool = True
    sourceType: str = "html-download"
    label: str = "Direct video"

@dataclass(slots=True)
class DiscoveredPost:
    id: str
    postUrl: str
    title: str
    thumbnail: str = ""
    duration: str = ""
    qualityHint: str = "HD"

@dataclass(slots=True)
class FetchResult:
    postUrl: str
    title: str
    domain: str
    extractor: str
    duration: float
    durationFormatted: str
    thumbnail: str
    pageType: str
    directLinks: list[DirectLink] = field(default_factory=list)
    discoveredPosts: list[DiscoveredPost] = field(default_factory=list)

    def to_dict(self):
        return {
            "postUrl": self.postUrl, "title": self.title, "domain": self.domain,
            "extractor": self.extractor, "duration": self.duration,
            "durationFormatted": self.durationFormatted, "thumbnail": self.thumbnail,
            "pageType": self.pageType,
            "directLinks": [asdict(x) for x in self.directLinks],
            "discoveredPosts": [asdict(x) for x in self.discoveredPosts],
        }
