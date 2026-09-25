"""
Browser and System Protocol Handler Registration.
Associates 'magnet:' URI scheme and '.torrent' file extensions with Turbo Download Manager
across Windows (Registry HKCU) and Linux (XDG / FreeDesktop .desktop).
"""

from __future__ import annotations
import sys
import os
import shutil
import subprocess
from typing import Tuple


def get_app_launch_command() -> str:
    """Constructs the exact executable invocation string for protocol association."""
    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        return f'"{exe_path}" "%1"'

    # When running as Python script from source
    py_dir = os.path.dirname(sys.executable)
    pyw_path = os.path.join(py_dir, "pythonw.exe")
    python_exe = pyw_path if os.path.exists(pyw_path) else sys.executable

    # Resolve main.py path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_py = os.path.join(base_dir, "main.py")

    return f'"{python_exe}" "{main_py}" "%1"'


def get_icon_path() -> str:
    """Returns icon path if available or falls back to executable."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ico = os.path.join(base_dir, "assets", "icon.ico")
    if os.path.exists(ico):
        return ico
    return sys.executable


# ==============================================================================
# WINDOWS REGISTRY IMPLEMENTATION (HKCU - No Administrator privileges needed)
# ==============================================================================

def _win_register_magnet() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        cmd = get_app_launch_command()
        icon = get_icon_path()

        # 1. Register magnet protocol in HKCU\Software\Classes\magnet
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\magnet") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:BitTorrent Magnet Link")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\magnet\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{icon}",0')

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\magnet\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)

        # 2. Register turbodm custom protocol in HKCU\Software\Classes\turbodm
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\turbodm") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Turbo Download Manager Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\turbodm\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{icon}",0')

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\turbodm\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)

        return True
    except Exception:
        return False


def _win_unregister_magnet() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        # Helper to recursively delete subkeys
        def delete_key_tree(root, subkey):
            try:
                with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                    while True:
                        try:
                            child = winreg.EnumKey(key, 0)
                            delete_key_tree(root, f"{subkey}\\{child}")
                        except OSError:
                            break
                winreg.DeleteKey(root, subkey)
            except Exception:
                pass

        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\magnet")
        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\turbodm")
        return True
    except Exception:
        return False


def _win_is_magnet_registered() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\magnet\shell\open\command") as key:
            val, _ = winreg.QueryValueEx(key, "")
            cmd = get_app_launch_command()
            return bool(val and ("main.py" in val or "python" in val.lower() or "turbodownload" in val.lower()))
    except Exception:
        return False


def _win_register_torrent() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        cmd = get_app_launch_command()
        icon = get_icon_path()

        # 1. Register .torrent extension -> ProgID
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.torrent") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "TurboDownloadManager.torrent")

        # 2. Register ProgID handler
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\TurboDownloadManager.torrent") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "BitTorrent File")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\TurboDownloadManager.torrent\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{icon}",0')

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\TurboDownloadManager.torrent\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)

        return True
    except Exception:
        return False


def _win_unregister_torrent() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        def delete_key_tree(root, subkey):
            try:
                with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                    while True:
                        try:
                            child = winreg.EnumKey(key, 0)
                            delete_key_tree(root, f"{subkey}\\{child}")
                        except OSError:
                            break
                winreg.DeleteKey(root, subkey)
            except Exception:
                pass

        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\TurboDownloadManager.torrent")
        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\.torrent")
        return True
    except Exception:
        return False


def _win_is_torrent_registered() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\TurboDownloadManager.torrent\shell\open\command") as key:
            val, _ = winreg.QueryValueEx(key, "")
            return bool(val)
    except Exception:
        return False


# ==============================================================================
# LINUX XDG / FREEDESKTOP IMPLEMENTATION
# ==============================================================================

def _linux_register() -> bool:
    if sys.platform == "win32":
        return False
    try:
        app_dir = os.path.expanduser("~/.local/share/applications")
        os.makedirs(app_dir, exist_ok=True)
        desktop_file = os.path.join(app_dir, "turbo-download-manager.desktop")

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_py = os.path.join(base_dir, "main.py")

        content = f"""[Desktop Entry]
Name=Turbo Download Manager
Comment=High-Performance Accelerated Download Manager
Exec={sys.executable} "{main_py}" %U
Icon=download
Terminal=false
Type=Application
Categories=Network;FileTransfer;P2P;
MimeType=x-scheme-handler/magnet;application/x-bittorrent;
"""
        with open(desktop_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Update MIME database
        subprocess.run(["xdg-mime", "default", "turbo-download-manager.desktop", "x-scheme-handler/magnet"], check=False)
        subprocess.run(["xdg-mime", "default", "turbo-download-manager.desktop", "application/x-bittorrent"], check=False)
        subprocess.run(["update-desktop-database", app_dir], check=False)
        return True
    except Exception:
        return False


def _linux_unregister() -> bool:
    if sys.platform == "win32":
        return False
    try:
        desktop_file = os.path.expanduser("~/.local/share/applications/turbo-download-manager.desktop")
        if os.path.exists(desktop_file):
            os.remove(desktop_file)
        return True
    except Exception:
        return False


def _linux_is_registered() -> bool:
    if sys.platform == "win32":
        return False
    desktop_file = os.path.expanduser("~/.local/share/applications/turbo-download-manager.desktop")
    return os.path.exists(desktop_file)


# ==============================================================================
# UNIFIED PUBLIC API
# ==============================================================================

def register_magnet_protocol() -> bool:
    """Registers the 'magnet:' URI scheme to launch Turbo Download Manager from browsers."""
    if sys.platform == "win32":
        return _win_register_magnet()
    else:
        return _linux_register()


def unregister_magnet_protocol() -> bool:
    """Unregisters the 'magnet:' URI scheme handler."""
    if sys.platform == "win32":
        return _win_unregister_magnet()
    else:
        return _linux_unregister()


def is_magnet_protocol_registered() -> bool:
    """Checks if 'magnet:' protocol is currently associated with Turbo Download Manager."""
    if sys.platform == "win32":
        return _win_is_magnet_registered()
    else:
        return _linux_is_registered()


def register_torrent_file_association() -> bool:
    """Registers '.torrent' file extension association."""
    if sys.platform == "win32":
        return _win_register_torrent()
    else:
        return _linux_register()


def unregister_torrent_file_association() -> bool:
    """Unregisters '.torrent' file extension association."""
    if sys.platform == "win32":
        return _win_unregister_torrent()
    else:
        return _linux_unregister()


def is_torrent_file_associated() -> bool:
    """Checks if '.torrent' files are associated with Turbo Download Manager."""
    if sys.platform == "win32":
        return _win_is_torrent_registered()
    else:
        return _linux_is_registered()


def register_all_associations() -> Tuple[bool, bool]:
    """Registers both magnet protocol and .torrent file associations."""
    m_ok = register_magnet_protocol()
    t_ok = register_torrent_file_association()
    return m_ok, t_ok


def unregister_all_associations() -> Tuple[bool, bool]:
    """Unregisters both magnet protocol and .torrent file associations."""
    m_ok = unregister_magnet_protocol()
    t_ok = unregister_torrent_file_association()
    return m_ok, t_ok
