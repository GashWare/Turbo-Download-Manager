"""
Unit tests for BitTorrent engine, magnet parsing, Leech Only mode, and configuration options.
"""

import unittest
import os
import tempfile
import shutil
import libtorrent as lt

from core.models import DownloadTask, DownloadStatus, DownloadCategory, DownloadSettings
from core.prober import is_likely_torrent_url, probe_url
from core.queue_manager import QueueManager
from core.torrent_downloader import TorrentDownloader


class TestTorrentEngine(unittest.TestCase):
    """Tests for Torrent probing, models, queue manager, and libtorrent engine."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.qm = QueueManager(data_dir=os.path.join(self.test_dir, "qm_data"))

    def tearDown(self):
        self.qm.shutdown() if hasattr(self.qm, "shutdown") else None

    def test_torrent_url_detection(self):
        """Verify magnet and .torrent URL recognition."""
        magnet = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=Sintel.mp4"
        self.assertTrue(is_likely_torrent_url(magnet))

        torrent_url = "https://webtorrent.io/torrents/sintel.torrent"
        self.assertTrue(is_likely_torrent_url(torrent_url))

        non_torrent = "https://example.com/archive.zip"
        self.assertFalse(is_likely_torrent_url(non_torrent))

    def test_magnet_probing(self):
        """Verify probe_url correctly parses metadata from magnet link."""
        magnet = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=Sintel%20Movie"
        res = probe_url(magnet)
        self.assertTrue(res.is_torrent)
        self.assertEqual(res.category, DownloadCategory.TORRENT)
        self.assertIn("Sintel", res.filename)
        self.assertTrue(res.supports_range)

    def test_torrent_task_creation_and_leech_only_options(self):
        """Verify QueueManager creates a torrent task with Leech Only defaults."""
        magnet = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=TestTorrent"
        task = self.qm.create_and_add_task(
            url=magnet,
            save_path=self.test_dir,
            auto_start=False,
            is_torrent=True,
            leech_only=True,
            sequential_download=True,
            max_peers=75,
            download_limit_kbps=500,
            upload_limit_kbps=0
        )
        self.assertTrue(task.is_torrent)
        self.assertTrue(task.leech_only)
        self.assertTrue(task.sequential_download)
        self.assertEqual(task.max_peers, 75)
        self.assertEqual(task.download_limit_kbps, 500)
        self.assertEqual(task.upload_limit_kbps, 0)
        self.assertEqual(task.category, DownloadCategory.TORRENT)

        # Verify serialization
        data = task.to_dict()
        loaded = DownloadTask.from_dict(data)
        self.assertTrue(loaded.is_torrent)
        self.assertTrue(loaded.leech_only)
        self.assertTrue(loaded.sequential_download)
        self.assertEqual(loaded.max_peers, 75)

    def test_torrent_downloader_session_leech_settings(self):
        """Verify TorrentDownloader configures libtorrent session with Leech Only constraints."""
        magnet = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=TestTorrent"
        task = DownloadTask(
            url=magnet,
            save_path=self.test_dir,
            filename="TestTorrent",
            is_torrent=True,
            leech_only=True,
            sequential_download=True,
            max_peers=50,
            download_limit_kbps=1000
        )

        downloader = TorrentDownloader(task=task)
        ses = downloader._configure_session()
        settings = ses.get_settings()

        # Check that upload is strictly blocked in Leech Only mode
        self.assertEqual(settings["upload_rate_limit"], 1)
        self.assertEqual(settings["unchoke_slots_limit"], 0)
        self.assertEqual(settings["num_optimistic_unchoke_slots"], 0)
        self.assertEqual(settings["active_seeds"], 0)

        # Check download limit
        self.assertEqual(settings["download_rate_limit"], 1000 * 1024)

    def test_torrent_downloader_lifecycle(self):
        """Verify start, pause, and cancel on TorrentDownloader."""
        magnet = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=TestLifecycle"
        task = DownloadTask(
            url=magnet,
            save_path=self.test_dir,
            filename="TestLifecycle",
            is_torrent=True,
            leech_only=True
        )

        status_changes = []
        downloader = TorrentDownloader(
            task=task,
            on_status_change=lambda t: status_changes.append(t.status)
        )

        downloader.start()
        downloader.pause()
        self.assertEqual(task.status, DownloadStatus.PAUSED)

        downloader.cancel()
        self.assertEqual(task.status, DownloadStatus.CANCELLED)


class TestProtocolHandler(unittest.TestCase):
    """Tests for browser magnet protocol and .torrent file association handler."""

    def test_launch_command_and_icon(self):
        from core.protocol_handler import get_app_launch_command, get_icon_path
        cmd = get_app_launch_command()
        self.assertTrue(bool(cmd))
        self.assertIn("%1", cmd)

        icon = get_icon_path()
        self.assertTrue(bool(icon))

    def test_protocol_registration_lifecycle(self):
        from core.protocol_handler import (
            register_all_associations,
            is_magnet_protocol_registered,
            is_torrent_file_associated,
            unregister_all_associations
        )
        # Test registering all associations
        m_ok, t_ok = register_all_associations()
        if os.name == "nt":
            self.assertTrue(m_ok)
            self.assertTrue(t_ok)
            self.assertTrue(is_magnet_protocol_registered())
            self.assertTrue(is_torrent_file_associated())


if __name__ == "__main__":
    unittest.main()
