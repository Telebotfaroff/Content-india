from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int, minimum: int = 1) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    target_channel: str
    api_id: int
    api_hash: str
    session_name: str
    session_dir: Path
    download_dir: Path
    temp_dir: Path
    download_workers: int
    upload_workers: int
    max_pending_uploads: int
    aria2c_connections: int
    aria2c_split: int
    default_quality: str
    thumbnail_timestamp: int
    thumbnail_width: int
    thumbnail_quality: int
    progress_update_interval: int


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    if not token or not api_id or not api_hash:
        raise RuntimeError("Set BOT_TOKEN, API_ID and API_HASH in .env")

    settings = Settings(
        bot_token=token,
        target_channel=os.getenv("TARGET_CHANNEL", "").strip(),
        api_id=int(api_id),
        api_hash=api_hash,
        session_name=os.getenv("SESSION_NAME", "velofetch"),
        session_dir=Path(os.getenv("SESSION_DIR", "sessions")),
        download_dir=Path(os.getenv("DOWNLOAD_DIR", "downloads")),
        temp_dir=Path(os.getenv("TEMP_DIR", "temp")),
        download_workers=_int("DOWNLOAD_WORKERS", 1),
        upload_workers=_int("UPLOAD_WORKERS", 1),
        max_pending_uploads=_int("MAX_PENDING_UPLOADS", 1),
        aria2c_connections=_int("ARIA2C_CONNECTIONS", 16),
        aria2c_split=_int("ARIA2C_SPLIT", 16),
        default_quality=os.getenv("DEFAULT_QUALITY", "best"),
        thumbnail_timestamp=_int("THUMBNAIL_TIMESTAMP", 2, 0),
        thumbnail_width=_int("THUMBNAIL_WIDTH", 320),
        thumbnail_quality=_int("THUMBNAIL_QUALITY", 85),
        progress_update_interval=_int("PROGRESS_UPDATE_INTERVAL", 3),
    )
    for directory in (settings.session_dir, settings.download_dir, settings.temp_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return settings
