"""
Core download engine package.
"""

from .models import DownloadTask, DownloadStatus, DownloadCategory, DownloadSettings, Segment, format_eta
from .prober import probe_url, ProbeResult
from .queue_manager import QueueManager
from .segment_downloader import SegmentDownloader
from .stream_downloader import StreamDownloader
from .media_downloader import MediaDownloader
from .rate_limiter import RateLimiter
from .checksum import calculate_file_hash, verify_file_checksum
from .clipboard_monitor import ClipboardMonitor
from .categories import categorize_filename
from .os_utils import OSUtils

__all__ = [
    "DownloadTask",
    "DownloadStatus",
    "DownloadCategory",
    "DownloadSettings",
    "Segment",
    "probe_url",
    "ProbeResult",
    "QueueManager",
    "SegmentDownloader",
    "StreamDownloader",
    "MediaDownloader",
    "RateLimiter",
    "calculate_file_hash",
    "verify_file_checksum",
    "ClipboardMonitor",
    "categorize_filename",
    "OSUtils",
]
