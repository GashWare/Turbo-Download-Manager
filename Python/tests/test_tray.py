"""
Unit tests for System Tray Integration and Background Operation.
"""

import unittest
import os
import sys

# Ensure core and gui packages can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import DownloadSettings
from gui.tray_icon import SystemTrayManager, PYSTRAY_AVAILABLE


class TestSystemTray(unittest.TestCase):
    """Tests for system tray manager and background configuration."""

    def test_settings_tray_defaults_and_serialization(self):
        """Verify default settings for tray integration and dict serialization."""
        settings = DownloadSettings()
        self.assertTrue(settings.close_to_tray)
        self.assertTrue(settings.minimize_to_tray)
        self.assertFalse(settings.start_minimized)

        d = settings.to_dict()
        self.assertIn("close_to_tray", d)
        self.assertIn("minimize_to_tray", d)
        self.assertIn("start_minimized", d)

        restored = DownloadSettings.from_dict(d)
        self.assertEqual(restored.close_to_tray, settings.close_to_tray)
        self.assertEqual(restored.minimize_to_tray, settings.minimize_to_tray)
        self.assertEqual(restored.start_minimized, settings.start_minimized)

    def test_tray_manager_callbacks_and_lifecycle(self):
        """Verify SystemTrayManager triggers bound callbacks cleanly."""
        show_called = []
        add_called = []
        pause_called = []
        resume_called = []
        settings_called = []

        tray = SystemTrayManager(
            on_show=lambda: show_called.append(True),
            on_add_download=lambda: add_called.append(True),
            on_pause_all=lambda: pause_called.append(True),
            on_resume_all=lambda: resume_called.append(True),
            on_settings=lambda: settings_called.append(True),
            on_exit=lambda: None
        )

        tray._handle_show()
        self.assertEqual(len(show_called), 1)

        tray._handle_add()
        self.assertEqual(len(add_called), 1)

        tray._handle_pause_all()
        self.assertEqual(len(pause_called), 1)

        tray._handle_resume_all()
        self.assertEqual(len(resume_called), 1)

        tray._handle_settings()
        self.assertEqual(len(settings_called), 1)

        icon_img = tray._load_icon_image()
        self.assertIsNotNone(icon_img)


if __name__ == "__main__":
    unittest.main()
