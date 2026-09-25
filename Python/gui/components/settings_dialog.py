"""
Preferences and Settings Dialog.
Configures default storage path, concurrent limits, thread counts, and bandwidth limits with responsive layout.
"""

from __future__ import annotations
import os
from typing import Callable
import customtkinter as ctk
from tkinter import filedialog

from core.models import DownloadSettings
from core.protocol_handler import (
    register_magnet_protocol,
    unregister_magnet_protocol,
    is_magnet_protocol_registered,
    register_torrent_file_association,
    unregister_torrent_file_association,
    is_torrent_file_associated,
)
from gui.themes import get_theme, get_theme_display_names, normalize_theme_name, THEMES


class SettingsDialog(ctk.CTkToplevel):
    """Preferences modal window."""

    def __init__(self, parent, settings: DownloadSettings, on_save: Callable[[DownloadSettings], None]):
        super().__init__(parent)
        self.parent_app = parent
        self.settings = settings
        self.on_save = on_save
        self.initial_theme = getattr(settings, "theme", "dark")
        self.palette = get_theme(settings.theme)
        self._deactivate_windows_window_header_manipulation = True

        self.title("Settings & Preferences")
        self.geometry("580x740")
        self.minsize(520, 640)
        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)
        self.focus_force()
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 580) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 740) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", self._on_cancel)

    def _build_ui(self) -> None:
        p = self.palette

        # 1. Top Title
        self.header = ctk.CTkFrame(self, fg_color=p["toolbar_bg"], corner_radius=0, height=50)
        self.header.pack(side="top", fill="x")
        self.lbl_title = ctk.CTkLabel(
            self.header,
            text="⚙️ Preferences & Configuration",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=p["accent"]
        )
        self.lbl_title.pack(side="left", padx=20, pady=12)

        # 2. Bottom Action Buttons (Anchored to bottom)
        self.btn_frame = ctk.CTkFrame(self, fg_color=p["toolbar_bg"], corner_radius=0, height=55)
        self.btn_frame.pack(side="bottom", fill="x")

        import webbrowser
        self.btn_donate_settings = ctk.CTkButton(
            self.btn_frame,
            text="🍺 Buy me a beer",
            fg_color="transparent",
            hover_color=p["btn_hover"],
            text_color="#f59e0b",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=36,
            command=lambda: webbrowser.open("https://square.link/u/obDkxl6F")
        )
        self.btn_donate_settings.pack(side="left", padx=20, pady=10)

        self.btn_save = ctk.CTkButton(
            self.btn_frame,
            text="Save Preferences",
            fg_color=p["accent"],
            hover_color=p["accent_hover"],
            text_color=p.get("accent_text", "#ffffff"),
            font=ctk.CTkFont(weight="bold"),
            height=36,
            command=self._save
        )
        self.btn_save.pack(side="right", padx=20, pady=10)

        self.btn_cancel = ctk.CTkButton(
            self.btn_frame,
            text="Cancel",
            fg_color="transparent",
            hover_color=p["btn_hover"],
            text_color=p["text_secondary"],
            height=36,
            command=self._on_cancel
        )
        self.btn_cancel.pack(side="right", padx=10, pady=10)

        # 3. Center Form Content
        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.pack(side="top", fill="both", expand=True, padx=20, pady=12)
        form.grid_columnconfigure(1, weight=1)

        # Default Folder
        lbl_dir = ctk.CTkLabel(form, text="Default Download Folder:", font=ctk.CTkFont(weight="bold"))
        lbl_dir.grid(row=0, column=0, sticky="w", pady=(0, 4))

        dir_row = ctk.CTkFrame(form, fg_color="transparent")
        dir_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        dir_row.grid_columnconfigure(0, weight=1)

        self.entry_dir = ctk.CTkEntry(dir_row, height=32)
        self.entry_dir.insert(0, self.settings.default_save_dir)
        self.entry_dir.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.btn_browse = ctk.CTkButton(
            dir_row,
            text="Browse...",
            width=80,
            height=32,
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            command=self._browse_dir
        )
        self.btn_browse.grid(row=0, column=1)

        # Max Concurrent Downloads
        lbl_max = ctk.CTkLabel(form, text="Max Concurrent Active Downloads:", font=ctk.CTkFont(weight="bold"))
        lbl_max.grid(row=2, column=0, sticky="w", pady=(0, 4))

        self.slider_max = ctk.CTkSlider(form, from_=1, to=10, number_of_steps=9, command=self._on_max_changed)
        self.slider_max.set(self.settings.max_concurrent_downloads)
        self.slider_max.grid(row=3, column=0, sticky="ew", padx=(0, 10), pady=(0, 10))

        self.lbl_max_val = ctk.CTkLabel(form, text=f"{self.settings.max_concurrent_downloads} downloads", width=90)
        self.lbl_max_val.grid(row=3, column=1, sticky="w")

        # Default Connections Per Task
        lbl_conn = ctk.CTkLabel(form, text="Default Parallel Acceleration Connections:", font=ctk.CTkFont(weight="bold"))
        lbl_conn.grid(row=4, column=0, sticky="w", pady=(0, 4))

        self.slider_conns = ctk.CTkSlider(form, from_=1, to=32, number_of_steps=31, command=self._on_conns_changed)
        self.slider_conns.set(self.settings.default_connections_per_task)
        self.slider_conns.grid(row=5, column=0, sticky="ew", padx=(0, 10), pady=(0, 10))

        self.lbl_conns_val = ctk.CTkLabel(form, text=f"{self.settings.default_connections_per_task} threads", width=90)
        self.lbl_conns_val.grid(row=5, column=1, sticky="w")

        # Clipboard Monitor Toggle
        self.switch_clip = ctk.CTkSwitch(
            form,
            text="Enable Automatic Clipboard URL Detection",
            font=ctk.CTkFont(weight="bold")
        )
        if self.settings.clipboard_monitoring:
            self.switch_clip.select()
        self.switch_clip.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Sound Alert Toggle
        self.switch_sound = ctk.CTkSwitch(
            form,
            text="Play Audio Alert on Download Completion",
            font=ctk.CTkFont(weight="bold")
        )
        if getattr(self.settings, "sound_notifications", True):
            self.switch_sound.select()
        self.switch_sound.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # System Tray & Background Card
        tray_box = ctk.CTkFrame(form, fg_color=p["card_bg"], corner_radius=8)
        tray_box.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        tray_top = ctk.CTkFrame(tray_box, fg_color="transparent")
        tray_top.pack(fill="x", padx=12, pady=(8, 4))

        lbl_tray_title = ctk.CTkLabel(
            tray_top,
            text="⚡ System Tray & Background Operation",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=p["accent"]
        )
        lbl_tray_title.pack(side="left")

        self.switch_close_tray = ctk.CTkSwitch(
            tray_box,
            text="Close to System Tray (Keep running in background)",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if getattr(self.settings, "close_to_tray", True):
            self.switch_close_tray.select()
        self.switch_close_tray.pack(anchor="w", padx=12, pady=(2, 4))

        self.switch_min_tray = ctk.CTkSwitch(
            tray_box,
            text="Minimize to System Tray notification area",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if getattr(self.settings, "minimize_to_tray", True):
            self.switch_min_tray.select()
        self.switch_min_tray.pack(anchor="w", padx=12, pady=(0, 4))

        self.switch_start_min = ctk.CTkSwitch(
            tray_box,
            text="Start app minimized directly in System Tray",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if getattr(self.settings, "start_minimized", False):
            self.switch_start_min.select()
        self.switch_start_min.pack(anchor="w", padx=12, pady=(0, 8))

        # Browser & System Protocol Association Card
        proto_box = ctk.CTkFrame(form, fg_color=p["card_bg"], corner_radius=8)
        proto_box.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        proto_top = ctk.CTkFrame(proto_box, fg_color="transparent")
        proto_top.pack(fill="x", padx=12, pady=(8, 4))

        lbl_proto_title = ctk.CTkLabel(
            proto_top,
            text="🌐 Browser & System Protocol Associations",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=p["accent"]
        )
        lbl_proto_title.pack(side="left")

        # Live status badge
        is_magnet_on = is_magnet_protocol_registered()
        self.lbl_proto_status = ctk.CTkLabel(
            proto_top,
            text="✓ Registered" if is_magnet_on else "○ Not Registered",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#2ec4b6" if is_magnet_on else "#90a4ae"
        )
        self.lbl_proto_status.pack(side="right")

        # Magnet Switch
        self.switch_magnet = ctk.CTkSwitch(
            proto_box,
            text="Associate Magnet Links (magnet:) with Browsers (Chrome, Edge, Firefox)",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if getattr(self.settings, "associate_magnet_protocol", True) or is_magnet_on:
            self.switch_magnet.select()
        self.switch_magnet.pack(anchor="w", padx=12, pady=(2, 4))

        # Torrent File Association Switch
        is_torrent_on = is_torrent_file_associated()
        self.switch_torrent = ctk.CTkSwitch(
            proto_box,
            text="Associate .torrent Files with Turbo Download Manager",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if getattr(self.settings, "associate_torrent_files", True) or is_torrent_on:
            self.switch_torrent.select()
        self.switch_torrent.pack(anchor="w", padx=12, pady=(0, 8))

        # Theme Selection
        lbl_theme = ctk.CTkLabel(form, text="Application Theme:", font=ctk.CTkFont(weight="bold"))
        lbl_theme.grid(row=10, column=0, sticky="w", pady=(0, 4))

        theme_displays = get_theme_display_names()
        self.combo_theme = ctk.CTkComboBox(
            form,
            values=theme_displays,
            width=160
        )
        current_theme_key = getattr(self.settings, "theme", "dark")
        matched_display = next((t["display_name"] for t in THEMES.values() if normalize_theme_name(t["display_name"]) == current_theme_key), "Dark")
        self.combo_theme.set(matched_display)
        self.combo_theme.grid(row=11, column=0, sticky="w")

    def _browse_dir(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.entry_dir.get())
        if folder:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, folder)

    def _on_max_changed(self, val) -> None:
        self.lbl_max_val.configure(text=f"{int(val)} downloads")

    def _on_conns_changed(self, val) -> None:
        self.lbl_conns_val.configure(text=f"{int(val)} threads")

    def _on_cancel(self, event=None) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _save(self) -> None:
        self.settings.default_save_dir = self.entry_dir.get().strip()
        self.settings.max_concurrent_downloads = int(self.slider_max.get())
        self.settings.default_connections_per_task = int(self.slider_conns.get())
        self.settings.clipboard_monitoring = bool(self.switch_clip.get())
        self.settings.sound_notifications = bool(self.switch_sound.get())
        self.settings.close_to_tray = bool(self.switch_close_tray.get())
        self.settings.minimize_to_tray = bool(self.switch_min_tray.get())
        self.settings.start_minimized = bool(self.switch_start_min.get())
        self.settings.theme = normalize_theme_name(self.combo_theme.get())

        # Protocol associations
        magnet_assoc = bool(self.switch_magnet.get())
        torrent_assoc = bool(self.switch_torrent.get())
        self.settings.associate_magnet_protocol = magnet_assoc
        self.settings.associate_torrent_files = torrent_assoc

        if magnet_assoc:
            register_magnet_protocol()
        else:
            unregister_magnet_protocol()

        if torrent_assoc:
            register_torrent_file_association()
        else:
            unregister_torrent_file_association()

        self.on_save(self.settings)
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
