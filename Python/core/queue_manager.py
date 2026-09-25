"""
Central Queue and Task Orchestration Manager.
Handles concurrency limits, session persistence, automatic task starting,
event publishing, and engine lifecycle management.
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import List, Dict, Optional, Callable, Any

from .models import DownloadTask, DownloadStatus, DownloadCategory, DownloadSettings, Segment
from .prober import probe_url, ProbeResult
from .rate_limiter import RateLimiter
from .segment_downloader import SegmentDownloader
from .stream_downloader import StreamDownloader
from .media_downloader import MediaDownloader
from .torrent_downloader import TorrentDownloader
from .checksum import verify_file_checksum
from .os_utils import OSUtils


class QueueManager:
    """Manages the lifecycle of multiple download tasks and concurrent workers."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".turbo_downloader")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.db_path = os.path.join(self.data_dir, "downloads.json")
        self.config_path = os.path.join(self.data_dir, "settings.json")

        self.settings = DownloadSettings.load(self.config_path)
        self.global_rate_limiter = RateLimiter(self.settings.global_speed_limit_bytes_per_sec)

        self._tasks: Dict[str, DownloadTask] = {}
        self._engines: Dict[str, Any] = {}
        self._lock = threading.RLock()

        # Callbacks
        self._listeners: List[Callable[[str, DownloadTask], None]] = []

        self._load_tasks()

        # Background scheduler
        self._stop_event = threading.Event()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="QueueScheduler")
        self._scheduler_thread.start()

    def add_listener(self, callback: Callable[[str, DownloadTask], None]) -> None:
        """Register event listener: (event_name, task)."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, DownloadTask], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _notify(self, event: str, task: DownloadTask) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(event, task)
            except Exception:
                pass

    def get_all_tasks(self) -> List[DownloadTask]:
        with self._lock:
            return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status in (DownloadStatus.DOWNLOADING, DownloadStatus.CONNECTING))

    def _resolve_unique_filename(self, save_dir: str, desired_name: str) -> str:
        """Ensures a unique filename so existing files and queued tasks are never overwritten."""
        base_name, ext = os.path.splitext(desired_name)
        target = desired_name
        counter = 1
        with self._lock:
            existing_task_files = {
                t.filename for t in self._tasks.values()
                if os.path.abspath(t.save_path) == os.path.abspath(save_dir)
            }

        while os.path.exists(os.path.join(save_dir, target)) or target in existing_task_files:
            target = f"{base_name} ({counter}){ext}"
            counter += 1
        return target

    def create_and_add_task(
        self,
        url: str,
        save_path: Optional[str] = None,
        filename: Optional[str] = None,
        num_connections: Optional[int] = None,
        category: Optional[DownloadCategory] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        expected_checksum: Optional[str] = None,
        checksum_algo: Optional[str] = None,
        auto_start: Optional[bool] = None,
        total_bytes: Optional[int] = None,
        supports_range: Optional[bool] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        is_media_stream: Optional[bool] = None,
        media_quality: Optional[str] = "best",
        media_format: Optional[str] = "mp4",
        audio_only: Optional[bool] = False,
        is_torrent: Optional[bool] = None,
        leech_only: Optional[bool] = None,
        sequential_download: Optional[bool] = None,
        max_peers: Optional[int] = None,
        download_limit_kbps: Optional[int] = None,
        upload_limit_kbps: Optional[int] = None,
        dht_enabled: Optional[bool] = None,
        torrent_info_hash: Optional[str] = None
    ) -> DownloadTask:
        """Initializes task, avoids duplicate network probing if already probed, and adds to queue."""
        save_dir = save_path or self.settings.default_save_dir
        conns = num_connections or self.settings.default_connections_per_task
        should_start = self.settings.auto_start_downloads if auto_start is None else auto_start

        # Check if we already have probe metadata
        if total_bytes is not None and supports_range is not None and filename:
            final_fname = filename
            final_total_bytes = total_bytes
            final_supports_range = supports_range
            final_etag = etag
            final_last_modified = last_modified
            final_is_media = is_media_stream or False
            final_is_torrent = is_torrent or (category == DownloadCategory.TORRENT) or False
            final_category = category or (DownloadCategory.TORRENT if final_is_torrent else (DownloadCategory.AUDIO if audio_only else categorize_filename(final_fname)))
        else:
            # Probe resource
            probe = probe_url(url, custom_headers=custom_headers)
            final_fname = filename or probe.filename
            final_total_bytes = probe.total_bytes
            final_supports_range = probe.supports_range
            final_etag = probe.etag
            final_last_modified = probe.last_modified
            final_is_media = probe.is_media_stream
            final_is_torrent = probe.is_torrent or bool(is_torrent)
            final_category = category or (DownloadCategory.TORRENT if final_is_torrent else (DownloadCategory.AUDIO if audio_only else probe.category))

        # Check if output file already exists or is already queued, and resolve collision
        target_path = os.path.join(save_dir, final_fname)
        meta_path = f"{target_path}.dm_meta.json"
        
        with self._lock:
            existing_task_files = {
                t.filename for t in self._tasks.values()
                if os.path.abspath(t.save_path) == os.path.abspath(save_dir)
            }

        # Only resolve new name if there's no metadata for resuming or another task already has this name
        if (os.path.exists(target_path) and not os.path.exists(meta_path)) or final_fname in existing_task_files:
            fname = self._resolve_unique_filename(save_dir, final_fname)
        else:
            fname = final_fname

        # Determine torrent-specific settings
        task_leech_only = self.settings.torrent_leech_only_default if leech_only is None else leech_only
        task_sequential = self.settings.torrent_sequential_default if sequential_download is None else sequential_download
        task_max_peers = self.settings.torrent_max_peers_default if max_peers is None else max_peers
        task_dht = self.settings.torrent_dht_default if dht_enabled is None else dht_enabled
        task_dl_limit = self.settings.torrent_download_limit_default if download_limit_kbps is None else download_limit_kbps
        task_up_limit = self.settings.torrent_upload_limit_default if upload_limit_kbps is None else upload_limit_kbps

        task = DownloadTask(
            url=url,
            save_path=save_dir,
            filename=fname,
            total_bytes=final_total_bytes,
            supports_range=final_supports_range,
            etag=final_etag,
            last_modified=final_last_modified,
            num_connections=conns,
            category=final_category,
            custom_headers=custom_headers or {},
            expected_checksum=expected_checksum,
            checksum_algo=checksum_algo,
            is_media_stream=final_is_media,
            media_quality=media_quality or "best",
            media_format=media_format or ("mp3" if audio_only else "mp4"),
            audio_only=bool(audio_only),
            is_torrent=final_is_torrent,
            leech_only=task_leech_only,
            sequential_download=task_sequential,
            max_peers=task_max_peers,
            download_limit_kbps=task_dl_limit,
            upload_limit_kbps=task_up_limit,
            dht_enabled=task_dht,
            torrent_info_hash=torrent_info_hash,
            status=DownloadStatus.QUEUED
        )

        with self._lock:
            self._tasks[task.task_id] = task
            self._save_tasks()

        self._notify("task_added", task)

        if should_start:
            self.start_task(task.task_id)

        return task

    def create_and_add_batch_tasks(
        self,
        urls: List[str],
        save_path: Optional[str] = None,
        num_connections: Optional[int] = None,
        auto_start: bool = True
    ) -> List[DownloadTask]:
        """Adds a list of URLs to the queue in bulk with parallel probing."""
        tasks: List[DownloadTask] = []
        for url in urls:
            cleaned = url.strip()
            if cleaned and cleaned.startswith(("http://", "https://")):
                try:
                    task = self.create_and_add_task(
                        url=cleaned,
                        save_path=save_path,
                        num_connections=num_connections,
                        auto_start=auto_start
                    )
                    tasks.append(task)
                except Exception:
                    pass
        return tasks

    def start_task(self, task_id: str) -> bool:
        """Starts or resumes a task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if task.status == DownloadStatus.DOWNLOADING:
                return True

            # If concurrency limit reached, mark as queued
            if self.get_active_count() >= self.settings.max_concurrent_downloads:
                task.status = DownloadStatus.QUEUED
                self._save_tasks()
                self._notify("status_changed", task)
                return True

            task.status = DownloadStatus.CONNECTING
            self._notify("status_changed", task)

            # Pick appropriate engine
            if task.is_torrent or task.category == DownloadCategory.TORRENT or task.url.startswith("magnet:") or task.url.lower().endswith(".torrent"):
                engine = TorrentDownloader(
                    task=task,
                    on_progress=lambda t: self._notify("progress", t),
                    on_status_change=self._on_engine_status_change,
                    on_error=self._on_engine_error,
                    on_complete=self._on_engine_complete,
                )
            elif task.is_media_stream:
                engine = MediaDownloader(
                    task=task,
                    on_progress=lambda t: self._notify("progress", t),
                    on_status_change=self._on_engine_status_change,
                    on_error=self._on_engine_error,
                    on_complete=self._on_engine_complete,
                )
            elif task.supports_range and task.total_bytes > 0:
                engine = SegmentDownloader(
                    task=task,
                    rate_limiter=self.global_rate_limiter,
                    on_progress=lambda t: self._notify("progress", t),
                    on_status_change=self._on_engine_status_change,
                    on_error=self._on_engine_error,
                    on_complete=self._on_engine_complete,
                )
            else:
                engine = StreamDownloader(
                    task=task,
                    rate_limiter=self.global_rate_limiter,
                    on_progress=lambda t: self._notify("progress", t),
                    on_status_change=self._on_engine_status_change,
                    on_error=self._on_engine_error,
                    on_complete=self._on_engine_complete,
                )

            self._engines[task_id] = engine
            engine.start()
            self._save_tasks()
            return True

    def pause_task(self, task_id: str) -> bool:
        with self._lock:
            engine = self._engines.get(task_id)
            task = self._tasks.get(task_id)
            if engine:
                engine.pause()
                self._engines.pop(task_id, None)
            elif task:
                task.status = DownloadStatus.PAUSED
                task.speed_bytes_per_sec = 0.0
                task.eta_seconds = None
                task.save_meta()
                self._notify("status_changed", task)
            self._save_tasks()
            return True

    def pause_all(self) -> None:
        with self._lock:
            task_ids = list(self._tasks.keys())
        for tid in task_ids:
            task = self.get_task(tid)
            if task and task.status in (DownloadStatus.DOWNLOADING, DownloadStatus.CONNECTING, DownloadStatus.QUEUED):
                self.pause_task(tid)

    def resume_all(self) -> None:
        with self._lock:
            task_ids = list(self._tasks.keys())
        for tid in task_ids:
            task = self.get_task(tid)
            if task and task.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
                self.start_task(tid)

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            engine = self._engines.pop(task_id, None)
            task = self._tasks.get(task_id)
            if engine:
                engine.cancel()
            elif task:
                task.status = DownloadStatus.CANCELLED
                task.speed_bytes_per_sec = 0.0
                task.eta_seconds = None
                task.save_meta()
                self._notify("status_changed", task)
            self._save_tasks()
            return True

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            engine = self._engines.pop(task_id, None)
            if engine:
                engine.cancel()
            task = self._tasks.pop(task_id, None)
            if task:
                task.delete_meta()
                self._save_tasks()
                self._notify("task_removed", task)
                return True
        return False

    def retry_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.error_message = None
            task.status = DownloadStatus.QUEUED
            self._save_tasks()
            self._notify("status_changed", task)
        return self.start_task(task_id)

    def set_speed_limit(self, bytes_per_sec: int) -> None:
        self.settings.global_speed_limit_bytes_per_sec = bytes_per_sec
        self.global_rate_limiter.set_limit(bytes_per_sec)
        self.settings.save(self.config_path)

    def _on_engine_status_change(self, task: DownloadTask) -> None:
        with self._lock:
            self._save_tasks()
        self._notify("status_changed", task)

    def _on_engine_error(self, task: DownloadTask, error_msg: str) -> None:
        with self._lock:
            self._engines.pop(task.task_id, None)
            self._save_tasks()
        self._notify("error", task)

    def redownload_task(self, task_id: str) -> bool:
        """Resets a task to 0% and starts downloading from scratch."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            self.cancel_task(task_id)
            task.reset_for_redownload()
            self._save_tasks()
            self._notify("status_changed", task)
        return self.start_task(task_id)

    def _play_completion_sound(self) -> None:
        """Plays completion audio alert cross-platform in background thread."""
        OSUtils.play_completion_alert()

    def _on_engine_complete(self, task: DownloadTask) -> None:
        with self._lock:
            self._engines.pop(task.task_id, None)

            # Checksum verification if configured
            if task.expected_checksum and task.checksum_algo:
                try:
                    verified = verify_file_checksum(
                        task.full_output_path,
                        task.expected_checksum,
                        task.checksum_algo
                    )
                    if not verified:
                        task.status = DownloadStatus.ERROR
                        task.error_message = f"Checksum mismatch ({task.checksum_algo})"
                except Exception as e:
                    task.status = DownloadStatus.ERROR
                    task.error_message = f"Checksum check failed: {e}"

            self._save_tasks()

        # Play sound alert and desktop notification if enabled
        if task.status == DownloadStatus.COMPLETED:
            task.delete_meta()
            if self.settings.sound_notifications:
                threading.Thread(target=self._play_completion_sound, daemon=True).start()
            OSUtils.show_desktop_notification(
                title="Download Complete",
                message=f"Successfully downloaded {task.filename or 'file'}"
            )

        self._notify("completed", task)

    def _scheduler_loop(self) -> None:
        """Background loop to pick queued tasks when slots are free."""
        while not self._stop_event.is_set():
            try:
                time.sleep(1.0)
                with self._lock:
                    active = self.get_active_count()
                    slots = self.settings.max_concurrent_downloads - active

                    if slots > 0:
                        queued = [t for t in self._tasks.values() if t.status == DownloadStatus.QUEUED]
                        for task in queued[:slots]:
                            self.start_task(task.task_id)
            except Exception:
                pass

    def _save_tasks(self) -> None:
        """Saves current state of all tasks into database file."""
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self._tasks.values()], f, indent=2)
        except Exception:
            pass

    def _load_tasks(self) -> None:
        """Loads previous tasks from database file."""
        if not os.path.exists(self.db_path):
            return
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
                for item in raw_list:
                    task = DownloadTask.from_dict(item)
                    # Reset active downloading status on app restart to PAUSED
                    if task.status in (DownloadStatus.DOWNLOADING, DownloadStatus.CONNECTING):
                        task.status = DownloadStatus.PAUSED
                    self._tasks[task.task_id] = task
        except Exception:
            pass

    def close(self) -> None:
        self._stop_event.set()
        self.pause_all()
        self._save_tasks()
        self.settings.save(self.config_path)
