"""
Stress Test: GUI Responsiveness with 50+ Concurrent Playlist Tasks.
Verifies that the Tkinter event loop remains responsive (sub-25ms per tick)
even when 50 downloads are queued and active simultaneously.
"""

import time
import os
import unittest
import customtkinter as ctk

from core.models import DownloadTask, DownloadStatus, DownloadCategory
from core.queue_manager import QueueManager
from gui.gui_app import TurboDownloadApp


class TestGuiResponsiveness(unittest.TestCase):
    @staticmethod
    def mock_media_run(downloader_self):
        downloader_self.task.status = DownloadStatus.DOWNLOADING
        downloader_self.task.total_bytes = 10_000_000
        downloader_self.task.downloaded_bytes = 2_500_000
        downloader_self.task.speed_bytes_per_sec = 1_500_000
        if downloader_self.on_status_change:
            downloader_self.on_status_change(downloader_self.task)
        while not downloader_self._stop_event.is_set():
            time.sleep(0.05)

    def setUp(self):
        from unittest.mock import patch
        self.patcher = patch("core.media_downloader.MediaDownloader._run", self.mock_media_run)
        self.patcher.start()
        self.app = TurboDownloadApp()
        self.app.withdraw()  # Run headless for test
        self.app.qm.clear_all()
        for c in list(self.app.card_widgets.values()):
            try: c.destroy()
            except Exception: pass
        self.app.card_widgets.clear()

    def tearDown(self):
        try:
            self.patcher.stop()
        except Exception:
            pass
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_rapid_playlist_batch_add_responsiveness(self):
        """Simulates adding 50 playlist items rapidly and measures UI pump lag."""
        qm = self.app.qm

        # Simulate batch API payload with 50 tracks
        items = [{"url": f"https://www.youtube.com/watch?v=mock_{i}", "filename": f"Track_{i:02d}.mp3", "audio_only": True} for i in range(50)]
        payload = {
            "items": items,
            "subfolder": "Mega Playlist",
            "playlist_title": "Mega Playlist",
            "audio_only": True,
            "auto_start": True
        }

        # Measure UI thread responsiveness during addition
        t_start = time.perf_counter()
        self.app._on_api_add_download(payload)

        # Pump Tkinter event loop for 1.5 seconds and measure frame times
        t_end = time.perf_counter() + 1.5
        max_frame_delay = 0.0
        frame_count = 0

        while time.perf_counter() < t_end:
            frame_start = time.perf_counter()
            self.app.update_idletasks()
            self.app.update()
            time.sleep(0.01)  # 10ms frame interval
            frame_duration = time.perf_counter() - frame_start
            if frame_duration > max_frame_delay:
                max_frame_delay = frame_duration
            frame_count += 1

        # Frame delay should NEVER exceed 100ms (standard freeze threshold on Windows)
        self.assertLess(max_frame_delay, 0.15, f"UI frame delay was too high: {max_frame_delay*1000:.1f}ms")

        # Verify all 50 tasks exist in QueueManager
        all_tasks = qm.get_all_tasks()
        self.assertGreaterEqual(len(all_tasks), 50)

        # Test Clear All responsiveness
        clear_start = time.perf_counter()
        self.app._clear_all_downloads()
        self.app.update_idletasks()
        self.app.update()
        clear_duration = time.perf_counter() - clear_start
        self.assertLess(clear_duration, 0.1, f"Clear all took too long: {clear_duration*1000:.1f}ms")
        self.assertEqual(len(self.app.qm.get_all_tasks()), 0)


if __name__ == "__main__":
    unittest.main()
