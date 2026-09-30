"""
Media & Video Stream Downloader Engine using yt-dlp integration.
Extracts and downloads audio/video streams with live progress hooks.
"""

from __future__ import annotations
import os
import time
import threading
from typing import Optional, Callable
import yt_dlp

from .models import DownloadTask, DownloadStatus
from .os_utils import OSUtils

_CACHED_COOKIE_BROWSER = None
_COOKIE_BROWSER_CHECKED = False
_COOKIE_LOCK = threading.Lock()


def get_cached_cookie_browser():
    """Detects and caches browser cookies once across all threads to avoid repeated DPAPI freezes."""
    global _CACHED_COOKIE_BROWSER, _COOKIE_BROWSER_CHECKED
    with _COOKIE_LOCK:
        if _COOKIE_BROWSER_CHECKED:
            return _CACHED_COOKIE_BROWSER

        # Try firefox first as it reads directly without DPAPI decryption locks
        for b in ("firefox", "chrome", "edge", "brave", "opera"):
            try:
                from yt_dlp.cookies import extract_cookies_from_browser
                jar = extract_cookies_from_browser(b)
                if jar and len(jar) > 0:
                    _CACHED_COOKIE_BROWSER = (b,)
                    break
            except Exception:
                continue

        _COOKIE_BROWSER_CHECKED = True
        return _CACHED_COOKIE_BROWSER


class MediaDownloader:
    """Downloader for video & audio media streams (YouTube, Vimeo, etc.)."""

    def __init__(
        self,
        task: DownloadTask,
        on_progress: Optional[Callable[[DownloadTask], None]] = None,
        on_status_change: Optional[Callable[[DownloadTask], None]] = None,
        on_error: Optional[Callable[[DownloadTask, str], None]] = None,
        on_complete: Optional[Callable[[DownloadTask], None]] = None,
    ):
        self.task = task
        self.on_progress = on_progress
        self.on_status_change = on_status_change
        self.on_error = on_error
        self.on_complete = on_complete

        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._last_progress_notify_time = 0.0

    def start(self) -> None:
        self._stop_event.clear()
        supervisor = threading.Thread(target=self._run, daemon=True, name=f"Media-{self.task.task_id}")
        supervisor.start()

    def pause(self) -> None:
        # Note: yt-dlp native downloads resume on next start
        self._stop_event.set()
        with self._state_lock:
            self.task.status = DownloadStatus.PAUSED
            self.task.speed_bytes_per_sec = 0.0
            self.task.eta_seconds = None
            self.task.save_meta()
        if self.on_status_change:
            self.on_status_change(self.task)

    def cancel(self) -> None:
        self._stop_event.set()
        with self._state_lock:
            self.task.status = DownloadStatus.CANCELLED
            self.task.speed_bytes_per_sec = 0.0
            self.task.eta_seconds = None
            self.task.save_meta()
        if self.on_status_change:
            self.on_status_change(self.task)

    def _progress_hook(self, d: dict) -> None:
        if self._stop_event.is_set():
            raise Exception("Download stopped by user")

        status = d.get("status")
        if status == "downloading":
            now = time.monotonic()
            should_notify = (now - self._last_progress_notify_time) >= 0.15
            if should_notify:
                self._last_progress_notify_time = now

            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            speed = d.get("speed", 0.0) or 0.0
            eta = d.get("eta")

            frag_idx = d.get("fragment_index")
            frag_cnt = d.get("fragment_count")

            with self._state_lock:
                self.task.status = DownloadStatus.DOWNLOADING
                if downloaded:
                    self.task.downloaded_bytes = downloaded
                if total:
                    self.task.total_bytes = total
                elif frag_idx and frag_cnt and self.task.total_bytes > 0:
                    self.task.downloaded_bytes = int(self.task.total_bytes * (frag_idx / frag_cnt))
                self.task.speed_bytes_per_sec = float(speed)
                self.task.eta_seconds = int(eta) if eta is not None else None

            if should_notify and self.on_progress:
                self.on_progress(self.task)

        elif status == "finished":
            with self._state_lock:
                if self.task.total_bytes > 0:
                    self.task.downloaded_bytes = self.task.total_bytes
                self.task.speed_bytes_per_sec = 0.0
                self.task.eta_seconds = 0
            if self.on_progress:
                self.on_progress(self.task)

    def _postprocessor_hook(self, d: dict) -> None:
        if self._stop_event.is_set():
            raise Exception("Download stopped by user")

    def _run(self) -> None:
        try:
            OSUtils.set_thread_low_priority()
            with self._state_lock:
                self.task.status = DownloadStatus.DOWNLOADING
            if self.on_status_change:
                self.on_status_change(self.task)

            # Check if user specified a custom filename to preserve
            custom_name_specified = False
            custom_stem = ""
            if self.task.filename:
                base, ext = os.path.splitext(self.task.filename)
                clean_base = "".join(c for c in base if c not in '<>:"/\\|?*').strip()
                if clean_base and clean_base.lower() not in ("media stream", "youtube video", "video", "media", "audio", "stream"):
                    custom_name_specified = True
                    custom_stem = clean_base

            base_name = custom_stem if custom_name_specified else "%(title)s"

            import shutil
            import tempfile

            # Isolate all intermediate fragment and .ytdl files in a dedicated system temp folder
            temp_dir = os.path.join(tempfile.gettempdir(), "TurboDownloadManager", f"media_{self.task.task_id}")
            os.makedirs(temp_dir, exist_ok=True)

            try:
                out_template = os.path.join(temp_dir, f"{base_name}.%(ext)s")

                # Optimal fragment concurrency (4-8 parallel fragment streams)
                frag_conns = min(max(self.task.num_connections or 6, 2), 8)

                # Determine requested format & audio-only settings
                audio_only = bool(getattr(self.task, "audio_only", False))
                quality_str = getattr(self.task, "media_quality", "best") or "best"

                if audio_only:
                    raw_fmt = (getattr(self.task, "media_format", None) or "mp3").lower()
                    audio_codecs = ("mp3", "m4a", "aac", "wav", "flac", "opus", "vorbis")
                    target_format = "mp3"
                    for ac in audio_codecs:
                        if ac in raw_fmt:
                            target_format = ac
                            break
                else:
                    raw_fmt = (getattr(self.task, "media_format", None) or "mp4").lower()
                    video_formats = ("mp4", "mkv", "webm")
                    target_format = "mp4"
                    for vf in video_formats:
                        if vf in raw_fmt:
                            target_format = vf
                            break

                class YtDlpQuietLogger:
                    def debug(self, msg): pass
                    def info(self, msg): pass
                    def warning(self, msg): pass
                    def error(self, msg): pass

                ydl_opts = {
                    "paths": {"home": temp_dir, "temp": temp_dir},
                    "outtmpl": out_template,
                    "progress_hooks": [self._progress_hook],
                    "postprocessor_hooks": [self._postprocessor_hook],
                    "logger": YtDlpQuietLogger(),
                    "js_runtimes": {"node": {}},
                    "quiet": True,
                    "no_warnings": True,
                    "no_color": True,
                    "nocheckcertificate": True,
                    "socket_timeout": 20,
                    "retries": 25,
                    "fragment_retries": 40,
                    "file_access_retries": 5,
                    "buffersize": 2 * 1024 * 1024,
                    "concurrent_fragment_downloads": frag_conns,
                }

                url_lower = self.task.url.lower()
                if "youtube.com" in url_lower or "youtu.be" in url_lower:
                    ydl_opts["allowed_extractors"] = ["youtube", "youtube:playlist", "generic"]
                elif "twitch.tv" in url_lower:
                    ydl_opts["allowed_extractors"] = ["twitch", "generic"]
                elif "tiktok.com" in url_lower:
                    ydl_opts["allowed_extractors"] = ["tiktok", "generic"]
                elif "vimeo.com" in url_lower:
                    ydl_opts["allowed_extractors"] = ["vimeo", "generic"]

                if audio_only:
                    ydl_opts["format"] = "bestaudio/best"
                    ydl_opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": target_format,
                        "preferredquality": "320" if target_format == "mp3" else "0",
                    }]
                else:
                    # Parse height constraint from quality string (e.g. "1080p (Full HD)" -> 1080)
                    height_limit = None
                    for h in (2160, 1440, 1080, 720, 480, 360, 240, 144):
                        if str(h) in quality_str:
                            height_limit = h
                            break

                    if height_limit:
                        ydl_opts["format"] = (
                            f"bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/"
                            f"bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}]/best"
                        )
                    else:
                        ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

                    if target_format in ("mp4", "mkv", "webm"):
                        ydl_opts["merge_output_format"] = target_format
                    if target_format == "mp4":
                        ydl_opts["postprocessor_args"] = {"merger": ["-movflags", "+faststart"]}

                # Use robust player clients that bypass "page reload" and bot-check interstitials
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": ["android", "web"]
                    }
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        info = ydl.extract_info(self.task.url, download=True)
                    except Exception as extract_err:
                        # Fallback to cookies if private/age-restricted and standard extraction failed
                        err_str = str(extract_err).lower()
                        if any(k in err_str for k in ("sign in", "private", "members", "age")):
                            cookie_browser = get_cached_cookie_browser()
                            if cookie_browser:
                                ydl_opts.pop("extractor_args", None)
                                ydl_opts["cookiesfrombrowser"] = cookie_browser
                                with yt_dlp.YoutubeDL(ydl_opts) as ydl_retry:
                                    info = ydl_retry.extract_info(self.task.url, download=True)
                            else:
                                raise
                        else:
                            raise

                    if info:
                        if custom_name_specified:
                            clean_title = custom_stem
                        else:
                            title = info.get("title") or base_name
                            clean_title = "".join(c for c in title if c not in '<>:"/\\|?*').strip()
                            clean_title = clean_title or f"media_{self.task.task_id[:8]}"

                        target_file = os.path.join(self.task.save_path, f"{clean_title}.{target_format}")

                        # Locate compiled final video/audio in temp_dir
                        candidates = []
                        for fname in os.listdir(temp_dir):
                            if not fname.endswith((".part", ".ytdl", ".temp", ".json", ".part-Frag", ".aria2")):
                                fpath = os.path.join(temp_dir, fname)
                                if os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
                                    candidates.append(fpath)

                        if candidates:
                            # Prefer candidate matching target format or largest file size
                            target_candidates = [c for c in candidates if c.lower().endswith(f".{target_format}")]
                            compiled_file = max(target_candidates, key=os.path.getsize) if target_candidates else max(candidates, key=os.path.getsize)
                            ext = os.path.splitext(compiled_file)[1].lstrip(".").lower() or target_format
                            target_file = os.path.join(self.task.save_path, f"{clean_title}.{ext}")

                            os.makedirs(self.task.save_path, exist_ok=True)
                            shutil.copy2(compiled_file, target_file)
                            self.task.filename = os.path.basename(target_file)
                            actual_size = os.path.getsize(target_file)
                            self.task.total_bytes = actual_size
                            self.task.downloaded_bytes = actual_size

            finally:
                pass

            with self._state_lock:
                if not self._stop_event.is_set():
                    self.task.status = DownloadStatus.COMPLETED
                    self.task.completed_at = time.time()
                    self.task.speed_bytes_per_sec = 0.0
                    self.task.eta_seconds = 0
                    self.task.delete_meta()
                    if self.on_complete:
                        self.on_complete(self.task)

            if self.on_status_change:
                self.on_status_change(self.task)

        except Exception as e:
            if not self._stop_event.is_set():
                err_msg = str(e)
                if "ERROR:" in err_msg:
                    err_msg = err_msg.split("ERROR:")[-1].strip()
                err_msg = err_msg.replace("unable to download video data: ", "").strip()
                with self._state_lock:
                    self.task.status = DownloadStatus.ERROR
                    self.task.error_message = err_msg
                    self.task.save_meta()
                if self.on_error:
                    self.on_error(self.task, err_msg)
                if self.on_status_change:
                    self.on_status_change(self.task)



