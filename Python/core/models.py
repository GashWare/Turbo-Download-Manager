"""
Data models and state definitions for the Download Manager.
"""

from __future__ import annotations
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class DownloadStatus(str, Enum):
    QUEUED = "QUEUED"
    CONNECTING = "CONNECTING"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


def format_eta(seconds: Optional[int]) -> str:
    """
    Formats seconds into human-readable ETA string:
    - Under 60s: '45s'
    - 60s to 1 hour: '12m 34s'
    - Over 1 hour: '2h 15m 30s'
    """
    if seconds is None or seconds < 0:
        return "--:--"
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}h {mins}m {secs}s"


class DownloadCategory(str, Enum):
    ALL = "All"
    DOWNLOADING = "Downloading"
    COMPLETED = "Completed"
    PAUSED = "Paused"
    TORRENT = "Torrents"
    DOCUMENTS = "Documents"
    COMPRESSED = "Compressed"
    PROGRAMS = "Programs"
    VIDEO = "Video"
    AUDIO = "Audio"
    IMAGES = "Images"
    OTHER = "Other"


@dataclass
class Segment:
    """Represents a specific byte range download segment."""
    segment_id: int
    start_byte: int
    end_byte: int
    current_byte: int
    status: str = "WAITING"  # WAITING, DOWNLOADING, COMPLETED, ERROR
    speed_bytes_per_sec: float = 0.0
    error_message: Optional[str] = None

    @property
    def total_bytes(self) -> int:
        if self.end_byte < self.start_byte:
            return 0
        return self.end_byte - self.start_byte + 1

    @property
    def downloaded_bytes(self) -> int:
        if self.current_byte < self.start_byte:
            return 0
        return min(self.current_byte - self.start_byte, self.total_bytes)

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.total_bytes - self.downloaded_bytes)

    @property
    def progress_pct(self) -> float:
        if self.total_bytes <= 0:
            return 100.0 if self.status == "COMPLETED" else 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Segment:
        return cls(
            segment_id=data["segment_id"],
            start_byte=data["start_byte"],
            end_byte=data["end_byte"],
            current_byte=data["current_byte"],
            status=data.get("status", "WAITING"),
            speed_bytes_per_sec=data.get("speed_bytes_per_sec", 0.0),
            error_message=data.get("error_message")
        )


@dataclass
class DownloadTask:
    """Represents a full file download task with metadata and state persistence."""
    url: str
    save_path: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    filename: str = ""
    total_bytes: int = 0
    downloaded_bytes: int = 0
    status: DownloadStatus = DownloadStatus.QUEUED
    speed_bytes_per_sec: float = 0.0
    eta_seconds: Optional[int] = None
    supports_range: bool = False
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    num_connections: int = 8
    segments: List[Segment] = field(default_factory=list)
    category: DownloadCategory = DownloadCategory.OTHER
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)
    speed_limit_bytes: int = 0  # 0 means unlimited
    checksum_algo: Optional[str] = None
    expected_checksum: Optional[str] = None
    actual_checksum: Optional[str] = None
    is_media_stream: bool = False
    media_quality: str = "best"
    media_format: str = "mp4"
    audio_only: bool = False
    is_torrent: bool = False
    leech_only: bool = True
    sequential_download: bool = False
    max_peers: int = 100
    download_limit_kbps: int = 0
    upload_limit_kbps: int = 0
    dht_enabled: bool = True
    uploaded_bytes: int = 0
    upload_speed_bytes_per_sec: float = 0.0
    num_peers: int = 0
    num_seeds: int = 0
    torrent_info_hash: Optional[str] = None

    def reset_for_redownload(self) -> None:
        """Resets download progress and segments to re-download from scratch."""
        self.downloaded_bytes = 0
        self.uploaded_bytes = 0
        self.status = DownloadStatus.QUEUED
        self.speed_bytes_per_sec = 0.0
        self.upload_speed_bytes_per_sec = 0.0
        self.eta_seconds = None
        self.error_message = None
        self.completed_at = None
        for s in self.segments:
            s.current_byte = s.start_byte
            s.status = "WAITING"
            s.speed_bytes_per_sec = 0.0
            s.error_message = None
        self.save_meta()

    @property
    def progress_pct(self) -> float:
        if self.total_bytes <= 0:
            return 100.0 if self.status == DownloadStatus.COMPLETED else 0.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100.0)

    @property
    def full_output_path(self) -> str:
        return os.path.join(self.save_path, self.filename) if self.filename else self.save_path

    @property
    def meta_file_path(self) -> str:
        return f"{self.full_output_path}.dm_meta.json"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["category"] = self.category.value
        data["segments"] = [s.to_dict() for s in self.segments]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DownloadTask:
        segments_data = data.pop("segments", [])
        status_val = data.pop("status", DownloadStatus.QUEUED.value)
        category_val = data.pop("category", DownloadCategory.OTHER.value)
        
        task = cls(
            status=DownloadStatus(status_val) if isinstance(status_val, str) else status_val,
            category=DownloadCategory(category_val) if isinstance(category_val, str) else category_val,
            **data
        )
        task.segments = [Segment.from_dict(s) for s in segments_data]
        return task

    def save_meta(self) -> None:
        """Persist state to disk for reliable pause/resume and crash recovery."""
        if self.status == DownloadStatus.COMPLETED:
            self.delete_meta()
            return
        try:
            meta_path = self.meta_file_path
            meta_dir = os.path.dirname(meta_path)
            if meta_dir and not os.path.exists(meta_dir):
                os.makedirs(meta_dir, exist_ok=True)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception:
            pass

    def delete_meta(self) -> None:
        """Clean up state metadata file on completion or cancellation."""
        try:
            if os.path.exists(self.meta_file_path):
                os.remove(self.meta_file_path)
        except Exception:
            pass
        try:
            if self.save_path and self.filename:
                alt_path = os.path.join(self.save_path, f"{self.filename}.dm_meta.json")
                if os.path.exists(alt_path):
                    os.remove(alt_path)
        except Exception:
            pass


@dataclass
class DownloadSettings:
    """Global configuration settings for the download manager."""
    default_save_dir: str = field(default_factory=lambda: os.path.join(os.path.expanduser("~"), "Downloads"))
    max_concurrent_downloads: int = 5
    default_connections_per_task: int = 16
    global_speed_limit_bytes_per_sec: int = 0  # 0 for unlimited
    clipboard_monitoring: bool = True
    sound_notifications: bool = True
    theme: str = "dark"  # "dark" or "light"
    auto_start_downloads: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 TurboDownload/2.0"
    torrent_leech_only_default: bool = True
    torrent_sequential_default: bool = False
    torrent_max_peers_default: int = 100
    torrent_dht_default: bool = True
    torrent_download_limit_default: int = 0
    torrent_upload_limit_default: int = 0
    associate_magnet_protocol: bool = True
    associate_torrent_files: bool = True
    close_to_tray: bool = True
    minimize_to_tray: bool = True
    start_minimized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DownloadSettings:
        # Filter out unknown keys for backwards-compatibility
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    @classmethod
    def load(cls, config_path: str) -> DownloadSettings:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return cls.from_dict(json.load(f))
            except Exception:
                pass
        return cls()

    def save(self, config_path: str) -> None:
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception:
            pass
