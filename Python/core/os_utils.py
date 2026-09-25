"""
Cross-Platform OS Utilities and System Integration.
Handles OS detection (Windows, Linux distros, macOS), native file reveal in File Manager,
and cross-platform desktop audio/notifications.
"""

from __future__ import annotations
import sys
import os
import shutil
import subprocess
from typing import Optional


class OSUtils:
    """Platform-agnostic helper for system operations."""

    @staticmethod
    def get_os_type() -> str:
        """Returns 'windows', 'linux', or 'macos'."""
        if sys.platform == "win32":
            return "windows"
        elif sys.platform == "darwin":
            return "macos"
        elif sys.platform.startswith("linux"):
            return "linux"
        return "other"

    @staticmethod
    def get_default_download_dir() -> str:
        """Returns the user's default Downloads directory across Windows, Linux, and macOS."""
        user_home = os.path.expanduser("~")
        downloads = os.path.join(user_home, "Downloads")
        
        # On Linux, also check xdg-user-dir if available
        if sys.platform.startswith("linux") and not os.path.exists(downloads):
            try:
                res = subprocess.check_output(["xdg-user-dir", "DOWNLOAD"], text=True).strip()
                if res and os.path.isdir(res):
                    return res
            except Exception:
                pass

        return downloads

    @staticmethod
    def open_file(file_path: str) -> bool:
        """Opens a file with its default system associated application."""
        if not os.path.exists(file_path):
            return False

        try:
            if sys.platform == "win32":
                os.startfile(file_path)
                return True
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
                return True
            else:
                subprocess.Popen(["xdg-open", file_path])
                return True
        except Exception:
            return False

    @staticmethod
    def open_folder(folder_path: str) -> bool:
        """Opens a folder in the native file manager (Windows Explorer, Nautilus, Dolphin, Finder, etc.)."""
        if not folder_path:
            folder_path = OSUtils.get_default_download_dir()

        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            folder_path = os.path.dirname(folder_path)
        if not os.path.exists(folder_path):
            folder_path = OSUtils.get_default_download_dir()

        try:
            if sys.platform == "win32":
                norm = os.path.normpath(folder_path)
                subprocess.Popen(f'explorer.exe "{norm}"')
                return True
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
                return True
            else:
                # Linux: try xdg-open first, then specific file managers
                for fm in ["xdg-open", "nautilus", "dolphin", "thunar", "pcmanfm", "nemo", "caja"]:
                    if shutil.which(fm):
                        subprocess.Popen([fm, folder_path])
                        return True
                return False
        except Exception:
            return False

    @staticmethod
    def reveal_in_folder(file_path: str) -> bool:
        """Opens the file manager and selects/highlights the specified file."""
        if not file_path:
            return OSUtils.open_folder(OSUtils.get_default_download_dir())

        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            # Fallback to parent directory if file is missing
            parent = os.path.dirname(abs_path) or OSUtils.get_default_download_dir()
            return OSUtils.open_folder(parent)

        try:
            if sys.platform == "win32":
                norm_path = os.path.normpath(abs_path)
                # Windows Explorer requires unquoted /select, followed by quoted path
                subprocess.Popen(f'explorer.exe /select,"{norm_path}"')
                return True
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", abs_path])
                return True
            else:
                folder = os.path.dirname(abs_path)
                if shutil.which("nautilus"):
                    subprocess.Popen(["nautilus", "--select", abs_path])
                    return True
                elif shutil.which("dolphin"):
                    subprocess.Popen(["dolphin", "--select", abs_path])
                    return True
                elif shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", folder])
                    return True
                return False
        except Exception:
            return OSUtils.open_folder(os.path.dirname(abs_path))

    @staticmethod
    def play_completion_alert() -> None:
        """Plays a completion chime/sound cross-platform."""
        try:
            if sys.platform == "win32":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
            elif sys.platform.startswith("linux"):
                # Try paplay (PulseAudio/PipeWire), aplay (ALSA), or terminal bell
                if shutil.which("paplay") and os.path.exists("/usr/share/sounds/freedesktop/stereo/complete.oga"):
                    subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"])
                elif shutil.which("canberra-gtk-play"):
                    subprocess.Popen(["canberra-gtk-play", "-i", "complete"])
                else:
                    print("\a", end="", flush=True)  # Standard terminal bell
        except Exception:
            pass

    @staticmethod
    def show_desktop_notification(title: str, message: str) -> None:
        """Displays a native desktop notification."""
        try:
            if sys.platform.startswith("linux") and shutil.which("notify-send"):
                subprocess.Popen(["notify-send", title, message, "-a", "Turbo Downloader"])
            elif sys.platform == "darwin":
                apple_script = f'display notification "{message}" with title "{title}"'
                subprocess.Popen(["osascript", "-e", apple_script])
        except Exception:
            pass
