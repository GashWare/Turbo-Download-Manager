"""
High-Performance Segmented Turbo Downloader.
Features:
- Parallel multi-connection HTTP Range requests (up to 32 connections).
- Adaptive Dynamic Work-Stealing: Idle workers dynamically split lagging segments.
- Zero-merging Direct I/O: Writes chunks directly into pre-allocated target byte offsets.
- Crash-resilient State Checkpointing for instant Pause/Resume.
- Integrated Token-Bucket Bandwidth Throttling.
- Exponential Backoff Auto-Reconnect on network drops.
"""

from __future__ import annotations
import os
import sys
import time
import math
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import DownloadTask, DownloadStatus, Segment
from .rate_limiter import RateLimiter

MIN_BUFFER_SIZE = 64 * 1024       # 64 KB minimum buffer
MAX_BUFFER_SIZE = 512 * 1024      # 512 KB maximum buffer for high-bandwidth links
MIN_SPLIT_SIZE = 2 * 1024 * 1024  # 2 MB minimum remaining to split dynamically
PROGRESS_INTERVAL = 0.25          # Report progress every 250ms


class SegmentDownloader:
    """Multi-threaded Segmented Accelerated Download Engine."""

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
        self._file_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._worker_threads: List[threading.Thread] = []
        self._file_handle = None

        # Speed estimation state
        self._last_downloaded = 0
        self._last_time = time.monotonic()
        self._speed_history: List[float] = []

    def start(self) -> None:
        """Starts the download process in a dedicated supervisor thread."""
        self._stop_event.clear()
        self._pause_event.clear()
        supervisor = threading.Thread(target=self._run, daemon=True, name=f"Supervisor-{self.task.task_id}")
        supervisor.start()

    def pause(self) -> None:
        """Signals all workers to pause and checkpoints state."""
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
        """Cancels download."""
        self._stop_event.set()
        with self._state_lock:
            self.task.status = DownloadStatus.CANCELLED
            self.task.speed_bytes_per_sec = 0.0
            self.task.eta_seconds = None
            self.task.save_meta()
        if self.on_status_change:
            self.on_status_change(self.task)

    def _create_http_session(self) -> requests.Session:
        """Creates a tuned requests session with high connection pooling and keep-alive."""
        session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(
            pool_connections=self.task.num_connections + 4,
            pool_maxsize=self.task.num_connections + 4,
            max_retries=retry_strategy
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 TurboDownload/2.0",
            "Accept": "*/*",
            "Accept-Encoding": "identity"
        })
        if self.task.custom_headers:
            session.headers.update(self.task.custom_headers)
        return session

    def _initialize_file_and_segments(self) -> None:
        """Allocates target file and partitions byte ranges if not already initialized."""
        dest_path = self.task.full_output_path
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Pre-allocate or ensure file existence
        if not os.path.exists(dest_path):
            with open(dest_path, "wb") as f:
                if self.task.total_bytes > 0:
                    # Sparse file / seek write to preallocate size without blocking
                    f.seek(self.task.total_bytes - 1)
                    f.write(b"\0")

        # Partition segments if not resuming from existing state
        if not self.task.segments and self.task.total_bytes > 0:
            num_conns = max(1, min(self.task.num_connections, 32))
            part_size = self.task.total_bytes // num_conns
            segments: List[Segment] = []

            for i in range(num_conns):
                start = i * part_size
                end = (self.task.total_bytes - 1) if (i == num_conns - 1) else ((i + 1) * part_size - 1)
                segments.append(Segment(
                    segment_id=i,
                    start_byte=start,
                    end_byte=end,
                    current_byte=start,
                    status="WAITING"
                ))
            self.task.segments = segments
            self.task.save_meta()

    def _run(self) -> None:
        """Main download loop."""
        try:
            with self._state_lock:
                self.task.status = DownloadStatus.DOWNLOADING
            if self.on_status_change:
                self.on_status_change(self.task)

            self._initialize_file_and_segments()

            dest_path = self.task.full_output_path

            # Spawn worker threads for each active/waiting segment
            threads: List[threading.Thread] = []
            for seg in self.task.segments:
                if seg.status != "COMPLETED":
                    t = threading.Thread(
                        target=self._worker_loop,
                        args=(seg, dest_path),
                        daemon=True,
                        name=f"Worker-{seg.segment_id}"
                    )
                    threads.append(t)
                    t.start()

            self._worker_threads = threads

            # Progress & Work-Stealing monitor loop
            last_checkpoint = time.monotonic()
            while not self._stop_event.is_set():
                time.sleep(PROGRESS_INTERVAL)
                self._update_progress_and_speed()

                # Dynamic Work-Stealing Check
                self._check_and_steal_work(dest_path)

                # Check if all segments are finished
                with self._state_lock:
                    all_done = all(s.status == "COMPLETED" for s in self.task.segments)
                    if all_done:
                        break

                # Periodic state checkpointing
                if time.monotonic() - last_checkpoint > 2.0:
                    self.task.save_meta()
                    last_checkpoint = time.monotonic()

            # Wait for all workers to finish or acknowledge pause
            for t in threads:
                t.join(timeout=1.0)

            # Finalize status
            with self._state_lock:
                if self._pause_event.is_set():
                    self.task.status = DownloadStatus.PAUSED
                    self.task.save_meta()
                elif self._stop_event.is_set() and self.task.status == DownloadStatus.CANCELLED:
                    self.task.save_meta()
                elif all(s.status == "COMPLETED" for s in self.task.segments):
                    self.task.status = DownloadStatus.COMPLETED
                    self.task.downloaded_bytes = self.task.total_bytes
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

    def _get_dynamic_buffer_size(self) -> int:
        """Dynamically scales chunk buffer size based on current transfer rate."""
        speed = self.task.speed_bytes_per_sec
        if speed > 20 * 1024 * 1024:  # > 20 MB/s
            return MAX_BUFFER_SIZE  # 512 KB
        elif speed > 5 * 1024 * 1024:  # > 5 MB/s
            return 256 * 1024       # 256 KB
        elif speed > 1024 * 1024:      # > 1 MB/s
            return 128 * 1024       # 128 KB
        return MIN_BUFFER_SIZE      # 64 KB

    def _worker_loop(self, segment: Segment, dest_path: str) -> None:
        """Worker loop that downloads a single segment with thread-local file handles."""
        session = self._create_http_session()
        retry_delay = 1.0

        while not self._stop_event.is_set():
            if segment.current_byte > segment.end_byte:
                segment.status = "COMPLETED"
                break

            segment.status = "DOWNLOADING"
            range_header = f"bytes={segment.current_byte}-{segment.end_byte}"
            headers = {"Range": range_header}

            try:
                with open(dest_path, "r+b") as fh:
                    with session.get(self.task.url, headers=headers, stream=True, timeout=(10.0, 30.0)) as resp:
                        if resp.status_code not in (200, 206):
                            raise IOError(f"HTTP {resp.status_code} for range {range_header}")

                        buf_size = self._get_dynamic_buffer_size()
                        for chunk in resp.iter_content(chunk_size=buf_size):
                            if self._stop_event.is_set():
                                break

                            if not chunk:
                                continue

                            chunk_len = len(chunk)
                            
                            # Apply bandwidth limiter
                            if self.rate_limiter:
                                self.rate_limiter.acquire(chunk_len)

                            # Write directly to destination at current segment offset
                            fh.seek(segment.current_byte)
                            fh.write(chunk)

                            segment.current_byte += chunk_len
                            retry_delay = 1.0  # Reset retry on successful chunk

                        if segment.current_byte > segment.end_byte:
                            segment.status = "COMPLETED"
                            break

            except Exception as e:
                segment.error_message = str(e)
                if self._stop_event.is_set():
                    break
                # Backoff retry
                time.sleep(retry_delay + random.uniform(0.1, 0.5))
                retry_delay = min(retry_delay * 2, 16.0)

        session.close()

    def _check_and_steal_work(self, dest_path: str) -> None:
        """
        Speed-Differential Dynamic Work-Stealing Algorithm:
        Only triggers when at least one segment has completed and another segment is lagging.
        """
        with self._state_lock:
            # Only steal if at least one segment is finished
            has_completed_worker = any(s.status == "COMPLETED" for s in self.task.segments)
            if not has_completed_worker:
                return

            # Find candidate lagging segment with the largest remaining bytes > 10 MB
            lagging_seg = None
            max_remaining = 10 * 1024 * 1024

            for seg in self.task.segments:
                if seg.status == "DOWNLOADING" and seg.remaining_bytes > max_remaining:
                    max_remaining = seg.remaining_bytes
                    lagging_seg = seg

            # If a candidate is found and total connections < 16, perform dynamic split
            if lagging_seg and len(self.task.segments) < 16:
                split_point = lagging_seg.current_byte + (lagging_seg.end_byte - lagging_seg.current_byte) // 2
                
                if (lagging_seg.end_byte - split_point) >= 5 * 1024 * 1024:
                    new_seg_id = len(self.task.segments)
                    new_seg = Segment(
                        segment_id=new_seg_id,
                        start_byte=split_point + 1,
                        end_byte=lagging_seg.end_byte,
                        current_byte=split_point + 1,
                        status="WAITING"
                    )
                    lagging_seg.end_byte = split_point
                    self.task.segments.append(new_seg)

                    t = threading.Thread(
                        target=self._worker_loop,
                        args=(new_seg, dest_path),
                        daemon=True,
                        name=f"Worker-{new_seg.segment_id}"
                    )
                    self._worker_threads.append(t)
                    t.start()

    def _update_progress_and_speed(self) -> None:
        """Computes current speed, estimated time remaining, and total downloaded bytes."""
        now = time.monotonic()
        elapsed = now - self._last_time
        if elapsed <= 0.001:
            return

        with self._state_lock:
            total_downloaded = sum(s.downloaded_bytes for s in self.task.segments)
            self.task.downloaded_bytes = total_downloaded

            bytes_delta = max(0, total_downloaded - self._last_downloaded)
            instant_speed = bytes_delta / elapsed

            # Rolling average over recent samples for smooth speed rendering
            self._speed_history.append(instant_speed)
            if len(self._speed_history) > 8:
                self._speed_history.pop(0)

            avg_speed = sum(self._speed_history) / len(self._speed_history)
            self.task.speed_bytes_per_sec = avg_speed

            # Calculate ETA
            remaining = max(0, self.task.total_bytes - total_downloaded)
            if avg_speed > 100 and remaining > 0:
                self.task.eta_seconds = int(remaining / avg_speed)
            else:
                self.task.eta_seconds = None

            self._last_downloaded = total_downloaded
            self._last_time = now

        if self.on_progress:
            self.on_progress(self.task)
