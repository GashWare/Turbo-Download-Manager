"""
URL probing and metadata inspection engine.
Analyzes remote resources for size, Range request support, headers, and filename detection.
"""

from __future__ import annotations
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Dict, Any
import requests

from .models import DownloadCategory
from .categories import categorize_filename

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 TurboDownload/2.0"


@dataclass
class ProbeResult:
    url: str
    final_url: str
    filename: str
    total_bytes: int
    supports_range: bool
    etag: Optional[str]
    last_modified: Optional[str]
    content_type: str
    category: DownloadCategory
    is_media_stream: bool = False
    media_title: Optional[str] = None
    media_thumbnail: Optional[str] = None
    is_torrent: bool = False
    torrent_info_hash: Optional[str] = None
    is_playlist: bool = False
    playlist_title: Optional[str] = None
    playlist_count: int = 0
    playlist_entries: Optional[List[dict]] = None


def extract_filename_from_headers(headers: Dict[str, str], fallback_url: str) -> str:
    """Extracts a valid filename from Content-Disposition header or URL path."""
    cd = headers.get("Content-Disposition", "") or headers.get("content-disposition", "")
    filename = ""

    if cd:
        # Check for RFC 5987 filename*=UTF-8''encoded_name
        rfc_match = re.search(r"filename\*\s*=\s*UTF-8''([^;\r\n]+)", cd, re.IGNORECASE)
        if rfc_match:
            filename = urllib.parse.unquote(rfc_match.group(1))
        else:
            # Check for standard filename="..." or filename=...
            std_match = re.search(r'filename\s*=\s*(?:"([^"]+)"|([^;\r\n]+))', cd, re.IGNORECASE)
            if std_match:
                filename = std_match.group(1) or std_match.group(2)
                filename = filename.strip()

    if not filename:
        parsed = urllib.parse.urlparse(fallback_url)
        path = urllib.parse.unquote(parsed.path)
        base = os.path.basename(path.rstrip("/"))
        if base:
            filename = base

    # Clean filename
    if filename:
        # Strip query params if any slipped through
        filename = filename.split("?")[0].split("#")[0]
        # Remove invalid Windows filename characters: < > : " / \ | ? *
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename).strip()

    if not filename or filename in (".", ".."):
        filename = f"download_{int(urllib.parse.time.time()) if hasattr(urllib.parse, 'time') else 'file'}"

    return filename


def is_likely_playlist_url(url: str) -> bool:
    """Detect if URL is a YouTube playlist or video URL containing a playlist parameter."""
    if not url:
        return False
    lower = url.lower()
    if ("youtube.com" in lower or "youtu.be" in lower) and ("list=" in lower or "/playlist" in lower):
        return True
    return False


def is_likely_media_streaming_url(url: str) -> bool:
    """Detect if URL is from YouTube, Facebook, Instagram, TikTok, Vimeo, Twitch, etc."""
    if not url:
        return False
    lower = url.lower()
    media_domains = [
        "youtube.com", "youtu.be",
        "facebook.com", "fb.watch", "fb.com", "fb.gg",
        "instagram.com", "threads.net",
        "vimeo.com", "dailymotion.com",
        "tiktok.com", "twitch.tv", "soundcloud.com", "twitter.com",
        "x.com", "reddit.com", "bilibili.com", "rumble.com"
    ]
    return any(domain in lower for domain in media_domains)


def is_likely_torrent_url(url: str) -> bool:
    """Detect if input is a Magnet URI or points to a .torrent file."""
    if not url:
        return False
    trimmed = url.strip()
    if trimmed.startswith("magnet:"):
        return True
    lower = trimmed.lower()
    if lower.endswith(".torrent") or ".torrent?" in lower:
        return True
    if os.path.isfile(trimmed) and lower.endswith(".torrent"):
        return True
    return False


def probe_url(
    url: str,
    custom_headers: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
    check_media: bool = True
) -> ProbeResult:
    """
    Probes remote URL using intelligent HTTP Range queries, HEAD requests, or P2P inspection.
    Detects if the resource supports parallel multipart acceleration, YouTube streams, or BitTorrent.
    """
    url_stripped = url.strip()

    # 1. Check for Magnet links or local .torrent files
    if url_stripped.startswith("magnet:"):
        name = "Torrent Download"
        info_hash = None
        try:
            import libtorrent as lt
            params = lt.parse_magnet_uri(url_stripped)
            if params.name:
                name = params.name
            if params.info_hashes:
                info_hash = str(params.info_hashes.get_best())
        except Exception:
            # Fallback regex extraction
            match_dn = re.search(r"[?&]dn=([^&]+)", url_stripped)
            if match_dn:
                name = urllib.parse.unquote(match_dn.group(1))
            match_xt = re.search(r"urn:btih:([a-zA-Z0-9]+)", url_stripped)
            if match_xt:
                info_hash = match_xt.group(1)

        clean_name = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        return ProbeResult(
            url=url_stripped,
            final_url=url_stripped,
            filename=clean_name,
            total_bytes=0,
            supports_range=True,
            etag=None,
            last_modified=None,
            content_type="application/x-bittorrent",
            category=DownloadCategory.TORRENT,
            is_torrent=True,
            torrent_info_hash=info_hash
        )

    if os.path.isfile(url_stripped) and url_stripped.lower().endswith(".torrent"):
        name = os.path.splitext(os.path.basename(url_stripped))[0]
        total_size = 0
        info_hash = None
        try:
            import libtorrent as lt
            info = lt.torrent_info(url_stripped)
            if info.name():
                name = info.name()
            total_size = info.total_size()
            info_hash = str(info.info_hashes().get_best())
        except Exception:
            pass

        clean_name = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        return ProbeResult(
            url=url_stripped,
            final_url=url_stripped,
            filename=clean_name,
            total_bytes=total_size,
            supports_range=True,
            etag=None,
            last_modified=None,
            content_type="application/x-bittorrent",
            category=DownloadCategory.TORRENT,
            is_torrent=True,
            torrent_info_hash=info_hash
        )

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",  # Ensure uncompressed length is returned
    }
    if custom_headers:
        headers.update(custom_headers)

    # Check for media streaming sites if requested
    if check_media and is_likely_media_streaming_url(url_stripped):
        try:
            import yt_dlp
            cookie_browser = None
            for b in ("edge", "chrome", "firefox", "brave", "opera"):
                try:
                    from yt_dlp.cookies import extract_cookies_from_browser
                    jar = extract_cookies_from_browser(b)
                    if jar and len(jar) > 0:
                        cookie_browser = (b,)
                        break
                except Exception:
                    continue

            is_playlist_candidate = is_likely_playlist_url(url_stripped)
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 20,
                "extract_flat": True if is_playlist_candidate else "in_playlist",
                "js_runtimes": {"node": {}},
            }
            if cookie_browser:
                ydl_opts["cookiesfrombrowser"] = cookie_browser
            else:
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": ["android_vr", "web_safari", "web"]
                    }
                }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url_stripped, download=False)
                if info:
                    _type = info.get("_type")
                    entries = info.get("entries")
                    if _type == "playlist" or (entries is not None and len(list(entries or [])) > 0):
                        entries_list = []
                        raw_entries = list(entries or [])
                        for idx, e in enumerate(raw_entries):
                            if not e:
                                continue
                            e_id = e.get("id") or ""
                            e_url = e.get("url")
                            if not e_url or "://" not in e_url:
                                if e_id:
                                    e_url = f"https://www.youtube.com/watch?v={e_id}"
                                else:
                                    continue
                            e_title = e.get("title") or f"Track {idx + 1}"
                            entries_list.append({
                                "index": idx + 1,
                                "id": e_id,
                                "url": e_url,
                                "title": e_title,
                                "duration": e.get("duration"),
                                "uploader": e.get("uploader") or e.get("channel") or ""
                            })

                        playlist_title = info.get("title") or "YouTube Playlist"
                        clean_pl_title = re.sub(r'[<>:"/\\|?*]', '_', playlist_title).strip()
                        return ProbeResult(
                            url=url_stripped,
                            final_url=url_stripped,
                            filename=f"{clean_pl_title} ({len(entries_list)} items)",
                            total_bytes=0,
                            supports_range=True,
                            etag=None,
                            last_modified=None,
                            content_type="video/mp4",
                            category=DownloadCategory.VIDEO,
                            is_media_stream=True,
                            media_title=playlist_title,
                            media_thumbnail=info.get("thumbnail"),
                            is_playlist=True,
                            playlist_title=playlist_title,
                            playlist_count=len(entries_list),
                            playlist_entries=entries_list
                        )

                    title = info.get("title") or "video"
                    ext = info.get("ext", "mp4")
                    clean_title = re.sub(r'[<>:"/\\|?*]', '_', title).strip()
                    clean_title = clean_title or f"media_stream_{int(time.time()) if hasattr(time, 'time') else 'file'}"
                    filename = f"{clean_title}.{ext}"
                    filesize = info.get("filesize") or info.get("filesize_approx") or 0
                    return ProbeResult(
                        url=url_stripped,
                        final_url=url_stripped,
                        filename=filename,
                        total_bytes=filesize,
                        supports_range=True,
                        etag=None,
                        last_modified=None,
                        content_type="video/mp4",
                        category=DownloadCategory.VIDEO,
                        is_media_stream=True,
                        media_title=title,
                        media_thumbnail=info.get("thumbnail")
                    )
        except Exception:
            # Fall back to standard probe if yt-dlp fails
            pass

    session = requests.Session()
    session.headers.update(headers)

    final_url = url
    total_bytes = 0
    supports_range = False
    etag = None
    last_modified = None
    content_type = "application/octet-stream"
    resp_headers: Dict[str, str] = {}

    try:
        # Step 1: Try a Range GET for bytes 0-0
        # This is the most reliable check: servers supporting Range return 206 Partial Content
        range_headers = headers.copy()
        range_headers["Range"] = "bytes=0-0"
        
        resp = session.get(url, headers=range_headers, timeout=timeout, stream=True, allow_redirects=True)
        final_url = str(resp.url)
        resp_headers = dict(resp.headers)
        
        if resp.status_code == 206:
            supports_range = True
            content_range = resp.headers.get("Content-Range", "")
            if "/" in content_range:
                try:
                    total_bytes = int(content_range.split("/")[-1])
                except (ValueError, IndexError):
                    pass
        elif resp.status_code == 200:
            # Server ignored Range header or doesn't support ranges
            supports_range = False
            total_bytes = int(resp.headers.get("Content-Length", 0))
        
        etag = resp.headers.get("ETag")
        last_modified = resp.headers.get("Last-Modified")
        content_type = resp.headers.get("Content-Type", content_type).split(";")[0]
        resp.close()

    except Exception:
        # Fallback to standard HEAD request
        try:
            head_resp = session.head(url, timeout=timeout, allow_redirects=True)
            final_url = str(head_resp.url)
            resp_headers = dict(head_resp.headers)
            total_bytes = int(head_resp.headers.get("Content-Length", 0))
            accept_ranges = head_resp.headers.get("Accept-Ranges", "")
            if "bytes" in accept_ranges.lower():
                supports_range = True
            etag = head_resp.headers.get("ETag")
            last_modified = head_resp.headers.get("Last-Modified")
            content_type = head_resp.headers.get("Content-Type", content_type).split(";")[0]
        except Exception:
            pass

    filename = extract_filename_from_headers(resp_headers, final_url)
    category = categorize_filename(filename, content_type)

    return ProbeResult(
        url=url,
        final_url=final_url,
        filename=filename,
        total_bytes=total_bytes,
        supports_range=supports_range,
        etag=etag,
        last_modified=last_modified,
        content_type=content_type,
        category=category,
        is_media_stream=False
    )
