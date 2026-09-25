"""
System Tray Integration for Turbo Download Manager.
Enables running the application in the background (notification area)
to automatically receive and process downloads from browser extensions without stealing focus.
"""

from __future__ import annotations
import os
import sys
import threading
from typing import Optional, Callable
from PIL import Image

try:
    import pystray
    from pystray import MenuItem as item, Menu
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


class SystemTrayManager:
    """Manages the OS taskbar notification area / system tray icon."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_add_download: Optional[Callable[[], None]] = None,
        on_pause_all: Optional[Callable[[], None]] = None,
        on_resume_all: Optional[Callable[[], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        self.on_show = on_show
        self.on_add_download = on_add_download
        self.on_pause_all = on_pause_all
        self.on_resume_all = on_resume_all
        self.on_settings = on_settings
        self.on_exit = on_exit

        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self._icon is not None

    def _load_icon_image(self) -> Image.Image:
        """Loads application icon or falls back to a generated icon."""
        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        png_path = os.path.join(assets_dir, "app_icon.png")

        if os.path.exists(png_path):
            try:
                with Image.open(png_path) as img:
                    return img.copy()
            except Exception:
                pass

        # Create a clean fallback lightning icon
        img = Image.new("RGBA", (64, 64), color=(11, 17, 32, 255))
        return img

    def start(self) -> bool:
        """Starts the tray icon in a dedicated background thread."""
        if not PYSTRAY_AVAILABLE:
            return False

        if self._is_running and self._icon:
            return True

        try:
            image = self._load_icon_image()

            menu = Menu(
                item("⚡ Show Turbo DM", lambda icon, item: self._handle_show(), default=True),
                item("➕ Add Download...", lambda icon, item: self._handle_add()),
                Menu.SEPARATOR,
                item("⏸️ Pause All", lambda icon, item: self._handle_pause_all()),
                item("▶️ Resume All", lambda icon, item: self._handle_resume_all()),
                item("⚙️ Settings...", lambda icon, item: self._handle_settings()),
                Menu.SEPARATOR,
                item("🚪 Exit Turbo DM", lambda icon, item: self._handle_exit())
            )

            # Ensure Windows AppUserModelID is set
            if sys.platform == "win32":
                try:
                    import ctypes
                    myappid = "turbodm.downloadmanager.accelerator.2.0"
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except Exception:
                    pass

            self._icon = pystray.Icon(
                "Turbo Download Manager",
                image,
                "Turbo Download Manager",
                menu=menu
            )

            self._is_running = True
            self._thread = threading.Thread(target=self._run_icon, daemon=True, name="SystemTrayThread")
            self._thread.start()
            return True
        except Exception as e:
            self._is_running = False
            return False

    def _run_icon(self) -> None:
        try:
            if self._icon:
                self._icon.run()
        except Exception:
            pass

    def stop(self) -> None:
        """Stops and removes the tray icon from the system taskbar."""
        self._is_running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def notify(self, title: str, message: str) -> None:
        """Sends a notification balloon through the system tray."""
        if self._icon and self._is_running:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass

    def _handle_show(self) -> None:
        if self.on_show:
            self.on_show()

    def _handle_add(self) -> None:
        if self.on_add_download:
            self.on_add_download()

    def _handle_pause_all(self) -> None:
        if self.on_pause_all:
            self.on_pause_all()

    def _handle_resume_all(self) -> None:
        if self.on_resume_all:
            self.on_resume_all()

    def _handle_settings(self) -> None:
        if self.on_settings:
            self.on_settings()

    def _handle_exit(self) -> None:
        if self.on_exit:
            self.on_exit()
        else:
            self.stop()
            sys.exit(0)
