"""
Automatic categorization module for downloaded files based on extension and MIME types.
"""

import os
from .models import DownloadCategory

EXTENSION_MAP = {
    # Video
    ".mp4": DownloadCategory.VIDEO,
    ".mkv": DownloadCategory.VIDEO,
    ".avi": DownloadCategory.VIDEO,
    ".mov": DownloadCategory.VIDEO,
    ".wmv": DownloadCategory.VIDEO,
    ".flv": DownloadCategory.VIDEO,
    ".webm": DownloadCategory.VIDEO,
    ".m4v": DownloadCategory.VIDEO,
    ".ts": DownloadCategory.VIDEO,
    ".3gp": DownloadCategory.VIDEO,

    # Audio
    ".mp3": DownloadCategory.AUDIO,
    ".wav": DownloadCategory.AUDIO,
    ".flac": DownloadCategory.AUDIO,
    ".aac": DownloadCategory.AUDIO,
    ".ogg": DownloadCategory.AUDIO,
    ".m4a": DownloadCategory.AUDIO,
    ".wma": DownloadCategory.AUDIO,
    ".opus": DownloadCategory.AUDIO,

    # Documents
    ".pdf": DownloadCategory.DOCUMENTS,
    ".docx": DownloadCategory.DOCUMENTS,
    ".doc": DownloadCategory.DOCUMENTS,
    ".xlsx": DownloadCategory.DOCUMENTS,
    ".xls": DownloadCategory.DOCUMENTS,
    ".pptx": DownloadCategory.DOCUMENTS,
    ".ppt": DownloadCategory.DOCUMENTS,
    ".txt": DownloadCategory.DOCUMENTS,
    ".epub": DownloadCategory.DOCUMENTS,
    ".csv": DownloadCategory.DOCUMENTS,
    ".odt": DownloadCategory.DOCUMENTS,
    ".rtf": DownloadCategory.DOCUMENTS,
    ".md": DownloadCategory.DOCUMENTS,

    # Compressed
    ".zip": DownloadCategory.COMPRESSED,
    ".rar": DownloadCategory.COMPRESSED,
    ".7z": DownloadCategory.COMPRESSED,
    ".tar": DownloadCategory.COMPRESSED,
    ".gz": DownloadCategory.COMPRESSED,
    ".bz2": DownloadCategory.COMPRESSED,
    ".xz": DownloadCategory.COMPRESSED,
    ".iso": DownloadCategory.COMPRESSED,
    ".tgz": DownloadCategory.COMPRESSED,

    # Programs / Executables
    ".exe": DownloadCategory.PROGRAMS,
    ".msi": DownloadCategory.PROGRAMS,
    ".bat": DownloadCategory.PROGRAMS,
    ".cmd": DownloadCategory.PROGRAMS,
    ".sh": DownloadCategory.PROGRAMS,
    ".apk": DownloadCategory.PROGRAMS,
    ".jar": DownloadCategory.PROGRAMS,
    ".deb": DownloadCategory.PROGRAMS,
    ".rpm": DownloadCategory.PROGRAMS,
    ".dmg": DownloadCategory.PROGRAMS,
    ".pkg": DownloadCategory.PROGRAMS,

    # Images
    ".jpg": DownloadCategory.IMAGES,
    ".jpeg": DownloadCategory.IMAGES,
    ".png": DownloadCategory.IMAGES,
    ".gif": DownloadCategory.IMAGES,
    ".webp": DownloadCategory.IMAGES,
    ".svg": DownloadCategory.IMAGES,
    ".bmp": DownloadCategory.IMAGES,
    ".ico": DownloadCategory.IMAGES,
    ".tiff": DownloadCategory.IMAGES,
    ".psd": DownloadCategory.IMAGES,

    # BitTorrent
    ".torrent": DownloadCategory.TORRENT,
}


def categorize_filename(filename: str, content_type: str = "") -> DownloadCategory:
    """Categorizes a download based on its filename or Content-Type header."""
    _, ext = os.path.splitext(filename.lower())
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]

    ct = content_type.lower()
    if "bittorrent" in ct or "torrent" in ct:
        return DownloadCategory.TORRENT
    if "video/" in ct:
        return DownloadCategory.VIDEO
    if "audio/" in ct:
        return DownloadCategory.AUDIO
    if "image/" in ct:
        return DownloadCategory.IMAGES
    if "pdf" in ct or "text/" in ct or "officedocument" in ct:
        return DownloadCategory.DOCUMENTS
    if "zip" in ct or "compressed" in ct or "tar" in ct or "archive" in ct:
        return DownloadCategory.COMPRESSED
    if "executable" in ct or "octet-stream" in ct and filename.endswith((".exe", ".msi")):
        return DownloadCategory.PROGRAMS

    return DownloadCategory.OTHER
