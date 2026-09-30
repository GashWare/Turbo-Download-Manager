import sys
import os
import customtkinter
from cx_Freeze import setup, Executable

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ctk_path = os.path.dirname(customtkinter.__file__)
assets_path = os.path.join(ctk_path, "assets")
gui_assets = os.path.join(BASE_DIR, "gui", "assets")

include_files = []
if os.path.exists(gui_assets):
    include_files.append((gui_assets, "gui/assets"))

if os.path.exists(assets_path):
    include_files.append((assets_path, "lib/customtkinter/assets"))
    include_files.append((assets_path, "customtkinter/assets"))

build_exe_options = {
    "packages": [
        "os", "sys", "threading", "queue", "time", "json", "urllib", "subprocess", "shutil",
        "hashlib", "re", "math", "dataclasses", "datetime", "uuid", "typing",
        "customtkinter", "tkinter", "requests", "rich", "pyperclip", "yt_dlp", "darkdetect", "PIL", "pystray"
    ],
    "includes": [
        "core", "gui", "cli"
    ],
    "include_files": include_files,
    "excludes": [
        "matplotlib", "torch", "scipy", "pandas", "numpy", "transformers", "PyQt6", "cv2"
    ],
    "optimize": 1,
}

shortcut_table = [
    (
        "DesktopShortcut",
        "DesktopFolder",
        "Turbo Download Manager",
        "TARGETDIR",
        "[TARGETDIR]TurboDownloadManager.exe",
        None,
        "Turbo Download Manager - Accelerated Multi-Connection Engine",
        None,
        None,
        None,
        None,
        "TARGETDIR",
    ),
    (
        "ProgramMenuShortcut",
        "ProgramMenuFolder",
        "Turbo Download Manager",
        "TARGETDIR",
        "[TARGETDIR]TurboDownloadManager.exe",
        None,
        "Turbo Download Manager - Accelerated Multi-Connection Engine",
        None,
        None,
        None,
        None,
        "TARGETDIR",
    ),
]

bdist_msi_options = {
    "add_to_path": True,
    "initial_target_dir": r"[ProgramFilesFolder]\Turbo Download Manager",
    "data": {"Shortcut": shortcut_table},
    "upgrade_code": "{B5E3971C-64D0-42FA-99DF-41BC95893F71}",
}

base_gui = "gui" if sys.platform == "win32" else None
icon_file = os.path.join(gui_assets, "app_icon.ico") if os.path.exists(os.path.join(gui_assets, "app_icon.ico")) else None
main_script = os.path.join(BASE_DIR, "main.py")

executables = [
    Executable(
        main_script,
        base=base_gui,
        target_name="TurboDownloadManager.exe",
        icon=icon_file,
        shortcut_name="Turbo Download Manager",
        shortcut_dir="DesktopFolder",
    ),
    Executable(
        main_script,
        base=None,
        target_name="turbo-cli.exe",
        icon=icon_file,
        shortcut_name="Turbo DM CLI",
        shortcut_dir="ProgramMenuFolder",
    ),
]

setup(
    name="Turbo Download Manager",
    version="2.0.0",
    author="Turbo DM Team",
    description="Accelerated Multi-Connection Download Engine",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)