"""
Comprehensive Unit & Integration Test Suite for Turbo Download Manager.
Tests:
- Range-enabled local HTTP server
- Multi-connection segmented downloads with direct I/O
- Pause and Resume integrity validation
- Non-Range fallback streaming
- Checksum verification (MD5 & SHA256)
- File categorization
- Queue manager and event listeners
- CLI and GUI initialization smoke tests
"""

import sys
import os
import time
import hashlib
import unittest
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import DownloadTask, DownloadStatus, DownloadCategory, Segment, format_eta
from core.categories import categorize_filename
from core.checksum import calculate_file_hash, verify_file_checksum
from core.rate_limiter import RateLimiter
from core.prober import probe_url
from core.segment_downloader import SegmentDownloader
from core.stream_downloader import StreamDownloader
from core.queue_manager import QueueManager

# Test payload: 4 MB random binary data
TEST_DATA = os.urandom(4 * 1024 * 1024)
TEST_MD5 = hashlib.md5(TEST_DATA).hexdigest()
TEST_SHA256 = hashlib.sha256(TEST_DATA).hexdigest()


class MockRangeHTTPHandler(BaseHTTPRequestHandler):
    """Mock HTTP Server supporting Range requests (RFC 7233)."""

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(TEST_DATA)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'attachment; filename="test_sample.bin"')
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            # Parse bytes=start-end
            byte_range = range_header[6:].split("-")
            start = int(byte_range[0])
            end = int(byte_range[1]) if byte_range[1] else len(TEST_DATA) - 1
            end = min(end, len(TEST_DATA) - 1)

            if start > end or start >= len(TEST_DATA):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{len(TEST_DATA)}")
                self.end_headers()
                return

            chunk = TEST_DATA[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(TEST_DATA)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(TEST_DATA)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Disposition", 'attachment; filename="test_sample.bin"')
            self.end_headers()
            self.wfile.write(TEST_DATA)

    def log_message(self, format, *args):
        # Suppress log output during unit tests
        pass


class TestDownloadManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start mock HTTP server on random free port
        cls.server = HTTPServer(("127.0.0.1", 0), MockRangeHTTPHandler)
        cls.port = cls.server.server_port
        cls.server_url = f"http://127.0.0.1:{cls.port}/test_sample.bin"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

        cls.test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_outputs")
        os.makedirs(cls.test_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_01_categorization(self):
        self.assertEqual(categorize_filename("movie.mp4"), DownloadCategory.VIDEO)
        self.assertEqual(categorize_filename("song.mp3"), DownloadCategory.AUDIO)
        self.assertEqual(categorize_filename("doc.pdf"), DownloadCategory.DOCUMENTS)
        self.assertEqual(categorize_filename("archive.zip"), DownloadCategory.COMPRESSED)
        self.assertEqual(categorize_filename("installer.exe"), DownloadCategory.PROGRAMS)
        self.assertEqual(categorize_filename("photo.jpg"), DownloadCategory.IMAGES)

    def test_02_url_probe(self):
        res = probe_url(self.server_url, check_media=False)
        self.assertTrue(res.supports_range)
        self.assertEqual(res.total_bytes, len(TEST_DATA))
        self.assertEqual(res.filename, "test_sample.bin")

    def test_03_segmented_download_and_integrity(self):
        """Test full accelerated download across 8 connections and verify byte-for-byte SHA256."""
        out_file = "downloaded_8conns.bin"
        task = DownloadTask(
            url=self.server_url,
            save_path=self.test_dir,
            filename=out_file,
            total_bytes=len(TEST_DATA),
            supports_range=True,
            num_connections=8,
            expected_checksum=TEST_SHA256,
            checksum_algo="sha256"
        )

        completed_event = threading.Event()
        error_event = threading.Event()

        engine = SegmentDownloader(
            task=task,
            on_complete=lambda t: completed_event.set(),
            on_error=lambda t, err: error_event.set()
        )
        engine.start()

        # Wait for completion (up to 10 seconds)
        success = completed_event.wait(timeout=10.0)
        self.assertTrue(success, "Download timed out")
        self.assertFalse(error_event.is_set(), f"Download encountered error: {task.error_message}")
        self.assertEqual(task.status, DownloadStatus.COMPLETED)
        self.assertEqual(task.downloaded_bytes, len(TEST_DATA))

        # Check integrity
        full_path = task.full_output_path
        self.assertTrue(os.path.exists(full_path))
        computed_sha = calculate_file_hash(full_path, algorithm="sha256")
        self.assertEqual(computed_sha, TEST_SHA256)
        self.assertTrue(verify_file_checksum(full_path, TEST_SHA256, algorithm="sha256"))

    def test_04_pause_and_resume(self):
        """Test pausing midway through a segmented download and resuming to completion."""
        out_file = "downloaded_resumed.bin"
        task = DownloadTask(
            url=self.server_url,
            save_path=self.test_dir,
            filename=out_file,
            total_bytes=len(TEST_DATA),
            supports_range=True,
            num_connections=8
        )

        # Start with rate limiter to give us time to pause
        limiter = RateLimiter(max_bytes_per_sec=512 * 1024)  # 512 KB/s
        engine = SegmentDownloader(task=task, rate_limiter=limiter)
        engine.start()

        # Wait until some bytes are downloaded
        for _ in range(30):
            if task.downloaded_bytes > 0:
                break
            time.sleep(0.05)
        engine.pause()
        self.assertEqual(task.status, DownloadStatus.PAUSED)
        self.assertGreater(task.downloaded_bytes, 0)
        self.assertLess(task.downloaded_bytes, len(TEST_DATA))

        # Check metadata was persisted
        self.assertTrue(os.path.exists(task.meta_file_path))

        # Resume with unlimited speed
        limiter.set_limit(0)
        completed_event = threading.Event()
        engine_resumed = SegmentDownloader(
            task=task,
            rate_limiter=limiter,
            on_complete=lambda t: completed_event.set()
        )
        engine_resumed.start()

        success = completed_event.wait(timeout=10.0)
        self.assertTrue(success, "Resumed download timed out")
        self.assertEqual(task.status, DownloadStatus.COMPLETED)

        # Verify integrity
        computed_sha = calculate_file_hash(task.full_output_path, algorithm="sha256")
        self.assertEqual(computed_sha, TEST_SHA256)

    def test_05_fallback_stream_downloader(self):
        """Test stream downloader when range is disabled."""
        out_file = "downloaded_stream.bin"
        task = DownloadTask(
            url=self.server_url,
            save_path=self.test_dir,
            filename=out_file,
            total_bytes=len(TEST_DATA),
            supports_range=False
        )

        completed_event = threading.Event()
        engine = StreamDownloader(
            task=task,
            on_complete=lambda t: completed_event.set()
        )
        engine.start()

        success = completed_event.wait(timeout=10.0)
        self.assertTrue(success)
        self.assertEqual(task.status, DownloadStatus.COMPLETED)
        computed_sha = calculate_file_hash(task.full_output_path, algorithm="sha256")
        self.assertEqual(computed_sha, TEST_SHA256)

    def test_06_queue_manager_integration(self):
        """Test QueueManager creating, tracking, and completing tasks."""
        qm_dir = os.path.join(self.test_dir, "qm_session")
        qm = QueueManager(data_dir=qm_dir)

        task = qm.create_and_add_task(
            url=self.server_url,
            save_path=self.test_dir,
            filename="qm_test.bin",
            num_connections=4,
            auto_start=True
        )

        # Poll until complete
        start = time.monotonic()
        while task.status not in (DownloadStatus.COMPLETED, DownloadStatus.ERROR):
            time.sleep(0.1)
            if time.monotonic() - start > 10.0:
                break

        self.assertEqual(task.status, DownloadStatus.COMPLETED)
        qm.close()

    def test_07_batch_and_duplicate_handling(self):
        """Test batch queueing and automatic unique duplicate filename generation."""
        qm_dir = os.path.join(self.test_dir, "qm_batch_session")
        qm = QueueManager(data_dir=qm_dir)

        # First create an existing file
        existing_file = os.path.join(self.test_dir, "batch_target.bin")
        with open(existing_file, "wb") as f:
            f.write(b"existing content")

        tasks = qm.create_and_add_batch_tasks(
            urls=[self.server_url, self.server_url],
            save_path=self.test_dir,
            num_connections=4,
            auto_start=False
        )

        self.assertEqual(len(tasks), 2)
        # Should have generated unique filenames
        self.assertNotEqual(tasks[0].filename, tasks[1].filename)
        qm.close()

    def test_08_redownload(self):
        """Test resetting and re-downloading a completed task from scratch."""
        qm_dir = os.path.join(self.test_dir, "qm_redownload_session")
        qm = QueueManager(data_dir=qm_dir)

        task = qm.create_and_add_task(
            url=self.server_url,
            save_path=self.test_dir,
            filename="redownload_sample.bin",
            num_connections=4,
            auto_start=True
        )

        # Wait for completion
        start = time.monotonic()
        while task.status not in (DownloadStatus.COMPLETED, DownloadStatus.ERROR):
            time.sleep(0.1)
            if time.monotonic() - start > 10.0:
                break

        self.assertEqual(task.status, DownloadStatus.COMPLETED)

        # Re-download
        qm.redownload_task(task.task_id)
        self.assertIn(task.status, (DownloadStatus.CONNECTING, DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED))

        # Wait for second completion
        start = time.monotonic()
        while task.status not in (DownloadStatus.COMPLETED, DownloadStatus.ERROR):
            time.sleep(0.1)
            if time.monotonic() - start > 10.0:
                break

        self.assertEqual(task.status, DownloadStatus.COMPLETED)
        qm.close()

    def test_09_format_eta(self):
        """Test formatting ETA for seconds, minutes/seconds, and hours/minutes/seconds."""
        self.assertEqual(format_eta(None), "--:--")
        self.assertEqual(format_eta(-1), "--:--")
        self.assertEqual(format_eta(0), "0s")
        self.assertEqual(format_eta(45), "45s")
        self.assertEqual(format_eta(59), "59s")
        self.assertEqual(format_eta(60), "1m 0s")
        self.assertEqual(format_eta(125), "2m 5s")
        self.assertEqual(format_eta(3599), "59m 59s")
        self.assertEqual(format_eta(3600), "1h 0m 0s")
        self.assertEqual(format_eta(3665), "1h 1m 5s")
        self.assertEqual(format_eta(7325), "2h 2m 5s")

    def test_10_os_utils(self):
        """Test OSUtils platform detection and download folder resolution."""
        from core.os_utils import OSUtils
        os_type = OSUtils.get_os_type()
        self.assertIn(os_type, ("windows", "linux", "macos", "other"))

        dl_dir = OSUtils.get_default_download_dir()
        self.assertTrue(bool(dl_dir))
        self.assertTrue(isinstance(dl_dir, str))

    def test_11_theme_system(self):
        """Test theme definitions, color keys, normalization, and display names."""
        from gui.themes import THEMES, get_theme, get_theme_display_names, normalize_theme_name

        expected_themes = ["dark", "light", "cyberpunk", "neon", "neo_tokyo", "matrix"]
        for t in expected_themes:
            self.assertIn(t, THEMES)
            palette = get_theme(t)
            self.assertIn("bg_main", palette)
            self.assertIn("toolbar_bg", palette)
            self.assertIn("sidebar_bg", palette)
            self.assertIn("card_bg", palette)
            self.assertIn("accent", palette)
            self.assertIn("progress_fill", palette)
            self.assertIn("completed_fill", palette)
            self.assertIn("ctk_mode", palette)

        # Test normalization
        self.assertEqual(normalize_theme_name("Neo Tokyo"), "neo_tokyo")
        self.assertEqual(normalize_theme_name("Cyberpunk"), "cyberpunk")
        self.assertEqual(normalize_theme_name("Matrix"), "matrix")

        # Test display names
        names = get_theme_display_names()
        self.assertIn("Cyberpunk", names)
        self.assertIn("Neo Tokyo", names)
        self.assertIn("Matrix", names)
        self.assertIn("Neon", names)
    def test_12_gui_card_rendering(self):
        """Test DownloadCard instantiation and dynamic theme switching across all statuses."""
        import customtkinter as ctk
        from gui.components.download_card import DownloadCard
        from gui.themes import THEMES, get_theme

        # Setup root test window (hidden)
        root = ctk.CTk()
        root.withdraw()

        task = DownloadTask(
            url=self.server_url,
            save_path=self.test_dir,
            filename="gui_test_file.bin",
            total_bytes=1048576,
            downloaded_bytes=524288,
            status=DownloadStatus.DOWNLOADING
        )

        card = DownloadCard(
            root,
            task=task,
            on_pause_resume=lambda t: None,
            on_cancel=lambda t: None,
            on_details=lambda t: None
        )

        # Test updating across statuses
        for st in DownloadStatus:
            task.status = st
            card.update_task_view(task)

        # Test applying all 6 themes to card
        for theme_name in THEMES.keys():
            card.apply_theme(get_theme(theme_name))

        root.destroy()

    def test_13_matrix_rain_and_settings_theme_save(self):
        """Test MatrixRainCanvas lifecycle and SettingsDialog theme selection saving."""
        import customtkinter as ctk
        from gui.components.matrix_rain import MatrixRainCanvas
        from gui.components.settings_dialog import SettingsDialog
        from core.models import DownloadSettings

        root = ctk.CTk()
        root.withdraw()

        # 1. Test Matrix Rain Canvas lifecycle
        rain = MatrixRainCanvas(root, width=400, height=300)
        rain.start()
        self.assertTrue(rain._is_running)
        rain.stop()
        self.assertFalse(rain._is_running)

        # 2. Test SettingsDialog theme selection saving
        saved_settings = []
        dlg = SettingsDialog(root, DownloadSettings(theme="dark"), on_save=lambda s: saved_settings.append(s))
        dlg.combo_theme.set("Matrix")
        dlg._save()
        self.assertEqual(saved_settings[0].theme, "matrix")

        # 3. Test Cancel does not trigger on_save
        saved_cancel = []
        dlg2 = SettingsDialog(root, DownloadSettings(theme="dark"), on_save=lambda s: saved_cancel.append(s))
        dlg2.combo_theme.set("Cyberpunk")
        dlg2._on_cancel()
        self.assertEqual(len(saved_cancel), 0)

        # 4. Test MatrixButtonAnimator hover mechanics
        from gui.components.matrix_rain import MatrixButtonAnimator
        btn = ctk.CTkButton(root, text="+ Add URL")
        btn.pack()
        root.active_palette = {"matrix_rain": True, "btn_border_width": 1, "btn_border_color": "#00ff41", "text_primary": "#00ff41"}
        MatrixButtonAnimator.attach(btn, app_ref=root)
        self.assertTrue(getattr(btn, "_has_matrix_hover", False))
        
        # Simulate enter & leave
        event = type("Event", (), {})()
        btn.event_generate("<Enter>")
        btn.event_generate("<Leave>")

        root.destroy()

    def test_14_theme_transition_cleanliness(self):
        """Test full theme transition between Matrix and other themes (Dark, Light, etc.) to ensure complete cleanup."""
        import customtkinter as ctk
        from gui.themes import THEMES, get_theme
        from gui.gui_app import TurboDownloadApp

        app = TurboDownloadApp()
        app.withdraw()

        # 1. Switch to Matrix
        app.apply_theme("matrix")
        self.assertEqual(app.active_palette["display_name"], "Matrix")
        self.assertEqual(app.btn_add.cget("border_width"), 1)
        self.assertEqual(app.btn_add.cget("border_color"), "#00ff41")

        # Simulate hover on all category buttons while Matrix is active
        for cat_k, btn in app.cat_buttons.items():
            btn.event_generate("<Enter>")
            btn.event_generate("<Leave>")
            self.assertEqual(btn.cget("border_width"), 1)
            self.assertEqual(btn.cget("border_color"), "#00ff41")

        # 2. Switch back to Dark theme
        app.apply_theme("dark")
        self.assertEqual(app.active_palette["display_name"], "Dark")
        self.assertEqual(app.btn_add.cget("border_width"), 0)
        self.assertEqual(app.btn_add.cget("border_color"), "#2b2d35")
        self.assertEqual(app.btn_settings.cget("border_width"), 0)
        self.assertEqual(app.btn_settings.cget("border_color"), "#2b2d35")

        # 3. Simulate hover on all category buttons while Dark is active
        for cat_k, btn in app.cat_buttons.items():
            btn.event_generate("<Enter>")
            btn.event_generate("<Leave>")
            # Ensure border is 0 and text is NOT green
            self.assertEqual(btn.cget("border_width"), 0)
            self.assertEqual(btn.cget("border_color"), "#2b2d35")
            if cat_k == app.current_category:
                self.assertEqual(btn.cget("text_color"), "#00b4d8")  # Dark accent
            else:
                self.assertEqual(btn.cget("text_color"), "#a0a5b5")  # Dark secondary text
            self.assertFalse(btn.cget("text").startswith("[ >"))

        # 4. Switch to Light theme and hover
        app.apply_theme("light")
        self.assertEqual(app.active_palette["display_name"], "Light")
        for cat_k, btn in app.cat_buttons.items():
            btn.event_generate("<Enter>")
            btn.event_generate("<Leave>")
            self.assertEqual(btn.cget("border_width"), 0)
            self.assertEqual(btn.cget("border_color"), "#cbd5e1")
            if cat_k == app.current_category:
                self.assertEqual(btn.cget("text_color"), "#0284c7")  # Light accent
            else:
                self.assertEqual(btn.cget("text_color"), "#334155")  # Light secondary text

        # 5. Clear completed button
        app.apply_theme("dark")
        app.btn_clear.event_generate("<Enter>")
        app.btn_clear.event_generate("<Leave>")
        self.assertEqual(app.btn_clear.cget("border_width"), 0)
        self.assertEqual(app.btn_clear.cget("text_color"), "#a0a5b5")

        app._on_close()

    def test_15_metadata_cleanup_on_completion_and_remove(self):
        """Verify .dm_meta.json is cleanly deleted on task completion and task removal."""
        custom_name = "test_meta_cleanup.bin"
        task = DownloadTask(
            url=self.server_url,
            save_path=self.test_dir,
            filename=custom_name,
            total_bytes=len(TEST_DATA),
            supports_range=True,
            num_connections=4
        )
        task.save_meta()
        self.assertTrue(os.path.exists(task.meta_file_path))

        # Test download to completion cleans up meta
        completed_event = threading.Event()
        def on_complete(t):
            completed_event.set()

        downloader = SegmentDownloader(task, on_complete=on_complete)
        downloader.start()
        self.assertTrue(completed_event.wait(timeout=10.0))

        # Check meta file is deleted
        self.assertFalse(os.path.exists(task.meta_file_path))

        # Test task removal cleans up meta
        qm = QueueManager(data_dir=os.path.join(self.test_dir, "qm_data_test"))
        t2 = qm.create_and_add_task(
            url=self.server_url,
            save_path=self.test_dir,
            filename="test_remove_cleanup.bin",
            auto_start=False
        )
        t2.save_meta()
        self.assertTrue(os.path.exists(t2.meta_file_path))

        qm.remove_task(t2.task_id)
        self.assertFalse(os.path.exists(t2.meta_file_path))
        qm.close()

    def test_16_custom_filename_preservation(self):
        """Verify custom filename specified by user is preserved throughout lifecycle."""
        qm = QueueManager(data_dir=os.path.join(self.test_dir, "qm_data_test2"))
        custom_name = f"my_custom_override_name_{int(time.time()*1000)}.bin"
        t = qm.create_and_add_task(
            url=self.server_url,
            save_path=self.test_dir,
            filename=custom_name,
            auto_start=True
        )
        self.assertEqual(t.filename, custom_name)

        time.sleep(1.0)
        self.assertEqual(t.filename, custom_name)
        self.assertEqual(os.path.basename(t.full_output_path), custom_name)
        qm.remove_task(t.task_id)
        out_f = os.path.join(self.test_dir, custom_name)
        if os.path.exists(out_f):
            try:
                os.remove(out_f)
            except Exception:
                pass
        qm.close()


if __name__ == "__main__":
    unittest.main()
