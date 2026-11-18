from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from time import time
from typing import Any
from uuid import uuid4


class JobStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    READY = "ready"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class DownloadJob:
    url: str
    source: str = "ytdlp"
    quality: str = "best"
    destination: str | None = None
    batch_id: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex[:10])
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    title: str | None = None
    file_path: Path | None = None
    error: str | None = None
    created_at: float = field(default_factory=time)
    metadata: dict[str, Any] = field(default_factory=dict)
