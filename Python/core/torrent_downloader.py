"""
BitTorrent Downloader Engine using libtorrent integration.
Supports Magnet links, .torrent files, Leech Only mode (zero upload/seeding),
sequential downloading, connection limits, and live peer stats.
"""

from __future__ import annotations
import os
import time
import threading
import tempfile
import urllib.request
from typing import Optional, Callable
import libtorrent as lt

from .models import DownloadTask, DownloadStatus


class TorrentDownloader:
    """High-performance BitTorrent Engine wrapping libtorrent."""

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
        self._session: Optional[lt.session] = None
        self._handle: Optional[lt.torrent_handle] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start or resume the torrent download supervisor."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"Torrent-{self.task.task_id}"
        )
        self._thread.start()

    def pause(self) -> None:
        """Pause torrent download."""
        self._stop_event.set()
        with self._state_lock:
            if self._handle and self._handle.is_valid():
                try:
                    self._handle.pause()
                except Exception:
                    pass
            self.task.status = DownloadStatus.PAUSED
            self.task.speed_bytes_per_sec = 0.0
            self.task.upload_speed_bytes_per_sec = 0.0
            self.task.eta_seconds = None
            self.task.save_meta()

        if self.on_status_change:
            self.on_status_change(self.task)

    def cancel(self) -> None:
        """Cancel torrent download."""
        self._stop_event.set()
        with self._state_lock:
            if self._session and self._handle and self._handle.is_valid():
                try:
                    self._session.remove_torrent(self._handle)
                except Exception:
                    pass
            self.task.status = DownloadStatus.CANCELLED
            self.task.speed_bytes_per_sec = 0.0
            self.task.upload_speed_bytes_per_sec = 0.0
            self.task.eta_seconds = None
            self.task.save_meta()

        if self.on_status_change:
            self.on_status_change(self.task)

    def _configure_session(self) -> lt.session:
        """Configures libtorrent session with user preferences & Leech Only restrictions."""
        ses = lt.session()
        s = ses.get_settings()

        # DHT, PeX, and LSD
        dht_on = getattr(self.task, "dht_enabled", True)
        s["enable_dht"] = dht_on
        s["enable_lsd"] = dht_on
        s["dht_bootstrap_nodes"] = "router.bittorrent.com:6881,dht.transmissionbt.com:6881,router.utorrent.com:6881"

        # General networking & timeouts
        s["user_agent"] = "TurboDownloadManager/2.0"
        s["peer_connect_timeout"] = 10
        s["connections_limit"] = max(getattr(self.task, "max_peers", 100) * 2, 200)

        # Global download rate limit
        dl_limit_kbps = getattr(self.task, "download_limit_kbps", 0) or 0
        if dl_limit_kbps > 0:
            s["download_rate_limit"] = dl_limit_kbps * 1024

        # Leech Only Mode Configuration
        leech_only = getattr(self.task, "leech_only", True)
        if leech_only:
            # Enforce strictly 1 byte/s upload limit and zero active seed slots
            s["upload_rate_limit"] = 1
            s["unchoke_slots_limit"] = 0
            s["num_optimistic_unchoke_slots"] = 0
            s["active_seeds"] = 0
        else:
            up_limit_kbps = getattr(self.task, "upload_limit_kbps", 0) or 0
            if up_limit_kbps > 0:
                s["upload_rate_limit"] = up_limit_kbps * 1024

        ses.apply_settings(s)
        return ses

    def _prepare_add_torrent_params(self) -> lt.add_torrent_params:
        """Parses magnet link or .torrent file into add_torrent_params."""
        target_url = self.task.url.strip()
        save_dir = os.path.abspath(self.task.save_path)
        os.makedirs(save_dir, exist_ok=True)

        if target_url.startswith("magnet:"):
            params = lt.parse_magnet_uri(target_url)
            params.save_path = save_dir
        elif os.path.isfile(target_url) and target_url.lower().endswith(".torrent"):
            info = lt.torrent_info(target_url)
            params = lt.add_torrent_params()
            params.ti = info
            params.save_path = save_dir
        elif target_url.lower().startswith(("http://", "https://")) and (".torrent" in target_url.lower()):
            # Download the remote .torrent file to temporary storage
            temp_torrent = os.path.join(tempfile.gettempdir(), f"torrent_{self.task.task_id}.torrent")
            urllib.request.urlretrieve(target_url, temp_torrent)
            info = lt.torrent_info(temp_torrent)
            params = lt.add_torrent_params()
            params.ti = info
            params.save_path = save_dir
        else:
            # Try as magnet URI or file
            try:
                params = lt.parse_magnet_uri(target_url)
                params.save_path = save_dir
            except Exception:
                info = lt.torrent_info(target_url)
                params = lt.add_torrent_params()
                params.ti = info
                params.save_path = save_dir

        # Sequential download flag
        if getattr(self.task, "sequential_download", False):
            params.flags |= lt.torrent_flags.sequential_download

        return params

    def _run(self) -> None:
        """Main supervisor loop tracking live torrent status and pieces."""
        try:
            with self._state_lock:
                self.task.status = DownloadStatus.CONNECTING
            if self.on_status_change:
                self.on_status_change(self.task)

            self._session = self._configure_session()
            params = self._prepare_add_torrent_params()
            self._handle = self._session.add_torrent(params)

            # Apply handle-specific limits
            max_peers = getattr(self.task, "max_peers", 100) or 100
            self._handle.set_max_connections(max_peers)

            leech_only = getattr(self.task, "leech_only", True)
            if leech_only:
                self._handle.set_upload_limit(1)  # 1 byte/sec effectively stops upload
            else:
                up_limit_kbps = getattr(self.task, "upload_limit_kbps", 0) or 0
                if up_limit_kbps > 0:
                    self._handle.set_upload_limit(up_limit_kbps * 1024)

            dl_limit_kbps = getattr(self.task, "download_limit_kbps", 0) or 0
            if dl_limit_kbps > 0:
                self._handle.set_download_limit(dl_limit_kbps * 1024)

            if getattr(self.task, "sequential_download", False):
                self._handle.set_sequential_download(True)

            metadata_resolved = False

            # Monitoring loop
            while not self._stop_event.is_set():
                if not self._handle.is_valid():
                    break

                st = self._handle.status()

                # 1. Update Metadata info if not yet resolved
                if not metadata_resolved:
                    try:
                        tf = self._handle.torrent_file()
                        if tf:
                            metadata_resolved = True
                            if not self.task.filename or self.task.filename == "Torrent Download":
                                self.task.filename = tf.name()
                            if self.task.total_bytes <= 0:
                                self.task.total_bytes = tf.total_size()
                            if not self.task.torrent_info_hash:
                                self.task.torrent_info_hash = str(tf.info_hashes().get_best())
                    except Exception:
                        pass

                # 2. Update Progress & Metrics
                with self._state_lock:
                    self.task.downloaded_bytes = st.total_done
                    if st.total_wanted > 0:
                        self.task.total_bytes = st.total_wanted
                    elif self.task.total_bytes <= 0 and st.total_done > 0:
                        self.task.total_bytes = st.total_done

                    self.task.speed_bytes_per_sec = float(st.download_rate)
                    self.task.upload_speed_bytes_per_sec = float(st.upload_rate)
                    self.task.uploaded_bytes = st.total_upload
                    self.task.num_peers = st.num_peers
                    self.task.num_seeds = st.num_seeds

                    # Calculate ETA
                    rem_bytes = max(0, self.task.total_bytes - self.task.downloaded_bytes)
                    if self.task.speed_bytes_per_sec > 0 and rem_bytes > 0:
                        self.task.eta_seconds = int(rem_bytes / self.task.speed_bytes_per_sec)
                    elif rem_bytes == 0:
                        self.task.eta_seconds = 0
                    else:
                        self.task.eta_seconds = None

                    # State transitions
                    if st.state == lt.torrent_status.downloading_metadata:
                        self.task.status = DownloadStatus.CONNECTING
                    elif st.state in (lt.torrent_status.downloading, lt.torrent_status.checking_files):
                        self.task.status = DownloadStatus.DOWNLOADING

                if self.on_progress:
                    self.on_progress(self.task)

                # 3. Check for Completion
                is_finished = (
                    st.is_finished
                    or st.state in (lt.torrent_status.finished, lt.torrent_status.seeding)
                    or (self.task.total_bytes > 0 and self.task.downloaded_bytes >= self.task.total_bytes)
                )

                if is_finished:
                    with self._state_lock:
                        if self.task.total_bytes > 0:
                            self.task.downloaded_bytes = self.task.total_bytes
                        self.task.status = DownloadStatus.COMPLETED
                        self.task.speed_bytes_per_sec = 0.0
                        self.task.upload_speed_bytes_per_sec = 0.0
                        self.task.eta_seconds = 0
                        self.task.completed_at = time.time()
                        self.task.delete_meta()

                    # In Leech Only mode, pause and shut down immediately so no seeding occurs
                    if leech_only:
                        try:
                            self._handle.pause()
                        except Exception:
                            pass

                    if self.on_progress:
                        self.on_progress(self.task)
                    if self.on_complete:
                        self.on_complete(self.task)
                    break

                time.sleep(0.4)

        except Exception as e:
            if not self._stop_event.is_set():
                err = str(e)
                with self._state_lock:
                    self.task.status = DownloadStatus.ERROR
                    self.task.error_message = err
                    self.task.speed_bytes_per_sec = 0.0
                    self.task.upload_speed_bytes_per_sec = 0.0
                    self.task.save_meta()
                if self.on_error:
                    self.on_error(self.task, err)
                if self.on_status_change:
                    self.on_status_change(self.task)
