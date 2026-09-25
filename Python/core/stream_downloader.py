"""
Fallback Stream Downloader for servers without HTTP Range support.
Handles single-connection streaming, live speed calculation, and rate limiting.
"""

from __future__ import annotations
import os
import time
import random
import threading
from typing import Optional, Callable
import requests

from .models import DownloadTask, DownloadStatus
from .rate_limiter import RateLimiter

CHUNK_SIZE = 64 * 1024  # 64 KB


class StreamDownloader:
    """Single-connection streaming download engine with rate limiting."""

    def __init__(
        self,
        task: DownloadTask,
        rate_limiter: Optional[RateLimiter] = None,
        on_progress: Optional[Callable[[DownloadTask], None]] = None,
        on_status_change: Optional[Callable[[DownloadTask], None]] = None,
        on_error: Optional[Callable[[DownloadTask, str], None]] = None,
        on_complete: Optional[Callable[[DownloadTask], None]] = None,
    ):
        self.task = task
        self.rate_limiter = rate_limiter or RateLimiter(task.speed_limit_bytes)
        self.on_progress = on_progress
        self.on_status_change = on_status_change
        self.on_error = on_error
        self.on_complete = on_complete

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._state_lock = threading.Lock()

        self._last_downloaded = 0
        self._last_time = time.monotonic()
        self._speed_history = []

    def start(self) -> None:
        self._stop_event.clear()
        self._pause_event.clear()
        supervisor = threading.Thread(target=self._run, daemon=True, name=f"Stream-{self.task.task_id}")
        supervisor.start()

    def pause(self) -> None:
        self._pause_event.set()
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

    def _run(self) -> None:
        try:
            with self._state_lock:
                self.task.status = DownloadStatus.DOWNLOADING
            if self.on_status_change:
                self.on_status_change(self.task)

            dest_path = self.task.full_output_path
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 TurboDownload/2.0",
                "Accept": "*/*",
            }
            if self.task.custom_headers:
                headers.update(self.task.custom_headers)

            # Check if partially downloaded
            downloaded = 0
            mode = "wb"
            if os.path.exists(dest_path) and self.task.downloaded_bytes > 0:
                downloaded = os.path.getsize(dest_path)
                mode = "ab"
                headers["Range"] = f"bytes={downloaded}-"

            with requests.get(self.task.url, headers=headers, stream=True, timeout=(10.0, 30.0)) as resp:
                if resp.status_code not in (200, 206):
                    raise IOError(f"Server returned HTTP {resp.status_code}")

                # If server restarted from 0 on 200 OK
                if resp.status_code == 200:
                    mode = "wb"
                    downloaded = 0

                with open(dest_path, mode) as f:
                    self._last_time = time.monotonic()
                    self._last_downloaded = downloaded

                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if self._stop_event.is_set():
                            break

                        if not chunk:
                            continue

                        chunk_len = len(chunk)
                        if self.rate_limiter:
                            self.rate_limiter.acquire(chunk_len)

                        f.write(chunk)
                        downloaded += chunk_len

                        # Update metrics
                        now = time.monotonic()
                        elapsed = now - self._last_time
                        if elapsed >= 0.25:
                            with self._state_lock:
                                self.task.downloaded_bytes = downloaded
                                speed = (downloaded - self._last_downloaded) / elapsed
                                self._speed_history.append(speed)
                                if len(self._speed_history) > 6:
                                    self._speed_history.pop(0)
                                avg_speed = sum(self._speed_history) / len(self._speed_history)
                                self.task.speed_bytes_per_sec = avg_speed

                                if self.task.total_bytes > 0 and avg_speed > 100:
                                    remaining = max(0, self.task.total_bytes - downloaded)
                                    self.task.eta_seconds = int(remaining / avg_speed)

                                self._last_downloaded = downloaded
                                self._last_time = now

                            if self.on_progress:
                                self.on_progress(self.task)

            with self._state_lock:
                if self._pause_event.is_set():
                    self.task.status = DownloadStatus.PAUSED
                    self.task.downloaded_bytes = downloaded
                    self.task.save_meta()
                elif self._stop_event.is_set() and self.task.status == DownloadStatus.CANCELLED:
                    self.task.save_meta()
                else:
                    self.task.status = DownloadStatus.COMPLETED
                    self.task.downloaded_bytes = downloaded
                    if self.task.total_bytes == 0:
                        self.task.total_bytes = downloaded
                    self.task.completed_at = time.time()
                    self.task.speed_bytes_per_sec = 0.0
                    self.task.eta_seconds = 0
                    self.task.delete_meta()
                    if self.on_complete:
                        self.on_complete(self.task)

            if self.on_status_change:
                self.on_status_change(self.task)

        except Exception as e:
            with self._state_lock:
                self.task.status = DownloadStatus.ERROR
                self.task.error_message = str(e)
                self.task.save_meta()
            if self.on_error:
                self.on_error(self.task, str(e))
            if self.on_status_change:
                self.on_status_change(self.task)
