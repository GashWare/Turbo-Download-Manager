"""
Main GUI Application Window for Turbo Download Manager.
Built with CustomTkinter for a modern dark/light UI.
"""

from __future__ import annotations
import sys
import os
import time
import threading
import queue
from typing import Dict, Optional, List, Callable, Any
import customtkinter as ctk

# Ensure core and gui packages can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import DownloadTask, DownloadStatus, DownloadCategory, DownloadSettings
from core.queue_manager import QueueManager
from core.clipboard_monitor import ClipboardMonitor
from core.api_server import ApiServer
from core.os_utils import OSUtils
from gui.themes import get_theme, normalize_theme_name, get_theme_display_names, set_window_icon
from gui.tray_icon import SystemTrayManager, PYSTRAY_AVAILABLE
from gui.components.download_card import DownloadCard
from gui.components.add_dialog import AddDownloadDialog
from gui.components.batch_add_dialog import BatchAddDialog
from gui.components.details_dialog import DetailsDialog
from gui.components.settings_dialog import SettingsDialog
from gui.components.matrix_rain import MatrixRainCanvas, MatrixButtonAnimator


def format_bytes(size_bytes: float) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


class TurboDownloadApp(ctk.CTk):
    """Main Download Manager Application."""

    def __init__(self, initial_url: str = "", start_in_tray: bool = False):
        super().__init__()

        self.qm = QueueManager()
        self.settings = self.qm.settings
        self.active_palette = get_theme(self.settings.theme)
        self._deactivate_windows_window_header_manipulation = True
        self._force_exit = False

        # Apply appearance settings
        ctk.set_appearance_mode(self.active_palette["ctk_mode"])
        ctk.set_default_color_theme("blue")

        self.title("Turbo Download Manager - Accelerated Multi-Connection Engine")
        self.geometry("1020x680")
        self.minsize(850, 500)

        # Set Windows AppUserModelID for dedicated taskbar icon & grouping and boost GUI thread priority
        if sys.platform == "win32":
            try:
                import ctypes
                myappid = "turbodm.downloadmanager.accelerator.2.0"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass
            OSUtils.boost_gui_thread_priority()

        # Lower GIL switch interval to 1ms to ensure GUI event loop never starves behind worker threads
        try:
            sys.setswitchinterval(0.001)
        except Exception:
            pass

        self._set_app_icon()

        # App state
        self.current_category = "All"
        self.search_query = ""
        self.card_widgets: Dict[str, DownloadCard] = {}
        self.detected_clipboard_url: Optional[str] = None

        self._build_layout()
        self.apply_theme(self.settings.theme)

        # Start Clipboard Monitor if enabled
        self.clipboard_monitor = ClipboardMonitor(on_url_detected=self._on_clipboard_url)
        if self.settings.clipboard_monitoring:
            self.clipboard_monitor.start()

        # Thread-safe UI event queue for background workers
        self._ui_event_queue = queue.Queue()
        self._check_ui_queue()

        # Subscribe to QueueManager events
        self.qm.add_listener(self._on_queue_event)

        # Embedded API Server for browser extensions and external IPC
        self.api_server = ApiServer(
            port=9669,
            on_add_download=self._on_api_add_download,
            status_callback=self._get_api_status
        )
        self.api_server.start()

        # System Tray Notification Area Manager
        self.tray_manager = SystemTrayManager(
            on_show=lambda: self.run_on_ui_thread(self._show_from_tray),
            on_add_download=lambda: self.run_on_ui_thread(self._tray_add_download),
            on_pause_all=lambda: self.run_on_ui_thread(self._tray_pause_all),
            on_resume_all=lambda: self.run_on_ui_thread(self._tray_resume_all),
            on_clear_inactive=lambda: self.run_on_ui_thread(self._clear_inactive_downloads),
            on_clear_all=lambda: self.run_on_ui_thread(self._clear_all_downloads),
            on_settings=lambda: self.run_on_ui_thread(self._tray_settings),
            on_exit=lambda: self.run_on_ui_thread(self._exit_application),
        )
        if PYSTRAY_AVAILABLE:
            self.tray_manager.start()

        # Refresh UI initial list
        self._refresh_downloads_list()

        # Handle starting minimized / directly to tray
        should_start_in_tray = start_in_tray or getattr(self.settings, "start_minimized", False)
        if should_start_in_tray:
            self.withdraw()

        # If initial URL provided (e.g. from browser protocol click or CLI), pop up Add dialog
        if initial_url:
            self.after(300, lambda: self._open_add_dialog(initial_url=initial_url))

        # Periodic UI Tick loop (200ms)
        self.after(200, self._ui_tick)

        # Window event handlers
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_window_unmap)

    def _set_app_icon(self) -> None:
        """Sets window titlebar, taskbar, and alt-tab icon across Windows and Linux."""
        set_window_icon(self)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ==========================================
        # TOP TOOLBAR
        # ==========================================
        self.toolbar = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#181a20")
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.toolbar.grid_columnconfigure(6, weight=1)

        # Add URL Button
        self.btn_add = ctk.CTkButton(
            self.toolbar,
            text="+ Add URL",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#00b4d8",
            hover_color="#0096c7",
            height=36,
            command=self._open_add_dialog
        )
        self.btn_add.grid(row=0, column=0, padx=(15, 6), pady=12)

        # Batch Add URLs Button
        self.btn_batch = ctk.CTkButton(
            self.toolbar,
            text="📋 Batch URLs",
            font=ctk.CTkFont(size=13),
            fg_color="#2b2d35",
            hover_color="#383a45",
            height=36,
            command=self._open_batch_dialog
        )
        self.btn_batch.grid(row=0, column=1, padx=4, pady=12)

        # Resume All Button
        self.btn_resume_all = ctk.CTkButton(
            self.toolbar,
            text="▶ Resume All",
            width=95,
            height=36,
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self.qm.resume_all
        )
        self.btn_resume_all.grid(row=0, column=2, padx=4, pady=12)

        # Pause All Button
        self.btn_pause_all = ctk.CTkButton(
            self.toolbar,
            text="⏸ Pause All",
            width=95,
            height=36,
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self.qm.pause_all
        )
        self.btn_pause_all.grid(row=0, column=3, padx=4, pady=12)

        # Clear All Button in Toolbar
        self.btn_clear_toolbar = ctk.CTkButton(
            self.toolbar,
            text="🗑️ Clear All",
            width=95,
            height=36,
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self._clear_all_downloads
        )
        self.btn_clear_toolbar.grid(row=0, column=4, padx=4, pady=12)

        # Speed Limiter Selector
        self.lbl_limit = ctk.CTkLabel(self.toolbar, text="Speed Limit:", font=ctk.CTkFont(size=12), text_color="#a0a5b5")
        self.lbl_limit.grid(row=0, column=5, padx=(12, 4), pady=12)

        self.combo_speed_limit = ctk.CTkComboBox(
            self.toolbar,
            values=["Unlimited", "500 KB/s", "1 MB/s", "2 MB/s", "5 MB/s", "10 MB/s", "20 MB/s"],
            width=115,
            height=32,
            command=self._on_speed_limit_changed
        )
        self.combo_speed_limit.set("Unlimited")
        self.combo_speed_limit.grid(row=0, column=6, sticky="w", padx=(0, 8), pady=12)

        # Search Bar
        self.entry_search = ctk.CTkEntry(
            self.toolbar,
            placeholder_text="🔍 Search downloads...",
            width=200,
            height=34
        )
        self.entry_search.grid(row=0, column=7, padx=8, pady=12)
        self.entry_search.bind("<KeyRelease>", self._on_search_changed)

        # Settings Button
        self.btn_settings = ctk.CTkButton(
            self.toolbar,
            text="⚙️",
            width=40,
            height=36,
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self._open_settings_dialog
        )
        self.btn_settings.grid(row=0, column=8, padx=(4, 15), pady=12)

        # ==========================================
        # LEFT SIDEBAR (Categories / Filters)
        # ==========================================
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#121316")
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Logo / Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="⚡ TURBO DL",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#00b4d8"
        )
        self.logo_label.pack(pady=(20, 15), padx=15, anchor="w")

        # Category Buttons
        self.cat_buttons: Dict[str, ctk.CTkButton] = {}
        categories = [
            ("All", "📥 All Downloads"),
            ("Downloading", "⏳ Downloading"),
            ("Completed", "✅ Completed"),
            ("Paused", "⏸️ Paused"),
            ("Torrents", "🧲 Torrents"),
            ("Video", "🎬 Video"),
            ("Audio", "🎵 Audio"),
            ("Documents", "📄 Documents"),
            ("Compressed", "📦 Compressed"),
            ("Programs", "⚡ Programs"),
        ]

        for cat_key, cat_label in categories:
            btn = ctk.CTkButton(
                self.sidebar,
                text=cat_label,
                anchor="w",
                height=34,
                font=ctk.CTkFont(size=12),
                fg_color="#181a20" if cat_key == "All" else "transparent",
                hover_color="#22252e",
                command=lambda k=cat_key: self._set_category(k)
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.cat_buttons[cat_key] = btn

        # Action Buttons at sidebar bottom
        self.sidebar_actions = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_actions.pack(side="bottom", fill="x", padx=10, pady=(4, 15))

        self.btn_clear_inactive = ctk.CTkButton(
            self.sidebar_actions,
            text="🧹 Clear Finished / Failed",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color="#2b2d35",
            text_color="#a0a5b5",
            height=30,
            command=self._clear_inactive_downloads
        )
        self.btn_clear_inactive.pack(fill="x", pady=2)
        self.btn_clear = self.btn_clear_inactive

        self.btn_clear_all = ctk.CTkButton(
            self.sidebar_actions,
            text="🗑️ Clear All Tasks",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color="#2b2d35",
            text_color="#a0a5b5",
            height=30,
            command=self._clear_all_downloads
        )
        self.btn_clear_all.pack(fill="x", pady=2)

        # ==========================================
        # MAIN CONTENT AREA
        # ==========================================
        self.main_frame = ctk.CTkFrame(self, fg_color=self.active_palette["bg_main"], corner_radius=0)
        self.main_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Clipboard Detection Banner (Initially Hidden)
        self.banner_frame = ctk.CTkFrame(self.main_frame, fg_color=self.active_palette["card_bg"], corner_radius=8, height=45)
        self.banner_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.banner_frame.grid_remove()  # Hidden by default

        self.lbl_banner = ctk.CTkLabel(
            self.banner_frame,
            text="📋 Copied URL detected: ...",
            font=ctk.CTkFont(size=12),
            text_color=self.active_palette["accent"]
        )
        self.lbl_banner.pack(side="left", padx=15, pady=8)

        self.btn_banner_dl = ctk.CTkButton(
            self.banner_frame,
            text="Download",
            width=80,
            height=28,
            fg_color=self.active_palette["accent"],
            hover_color=self.active_palette["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._download_clipboard_url
        )
        self.btn_banner_dl.pack(side="right", padx=10, pady=8)

        self.btn_banner_dismiss = ctk.CTkButton(
            self.banner_frame,
            text="✕",
            width=30,
            height=28,
            fg_color="transparent",
            hover_color=self.active_palette["btn_hover"],
            command=self.banner_frame.grid_remove
        )
        self.btn_banner_dismiss.pack(side="right", padx=(0, 5), pady=8)

        # Scrollable Downloads Card Container
        self.scroll_cards = ctk.CTkScrollableFrame(self.main_frame, fg_color=self.active_palette["bg_main"], corner_radius=0)
        self.scroll_cards.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.scroll_cards.grid_columnconfigure(0, weight=1)

        # Matrix Digital Rain Animation Canvas inside scroll area
        self.matrix_rain = MatrixRainCanvas(self.scroll_cards, bg=self.active_palette["bg_main"], height=300)

        # Empty State Label
        self.lbl_empty = ctk.CTkLabel(
            self.scroll_cards,
            text="No downloads found.\nClick '+ Add URL' or copy a link to start downloading!",
            font=ctk.CTkFont(size=14),
            text_color="#6c757d"
        )

        # Attach Matrix hover animations to all interactive buttons
        for btn in (self.btn_add, self.btn_batch, self.btn_resume_all, self.btn_pause_all, self.btn_clear_toolbar, self.btn_settings, self.btn_clear_inactive, self.btn_clear_all, self.btn_banner_dl, self.btn_banner_dismiss):
            MatrixButtonAnimator.attach(btn, app_ref=self)
        for btn in self.cat_buttons.values():
            MatrixButtonAnimator.attach(btn, app_ref=self)

        # Dynamic viewport resize listeners for Matrix Digital Rain
        self.bind("<Configure>", self._update_matrix_rain_geometry, add="+")
        self.main_frame.bind("<Configure>", self._update_matrix_rain_geometry, add="+")

        # ==========================================
        # BOTTOM STATUS BAR
        # ==========================================
        self.statusbar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color="#121316")
        self.statusbar.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.lbl_total_speed = ctk.CTkLabel(
            self.statusbar,
            text="⚡ Total Speed: 0 B/s",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#00b4d8"
        )
        self.lbl_total_speed.pack(side="left", padx=15)

        self.lbl_active_info = ctk.CTkLabel(
            self.statusbar,
            text="Active: 0/5 • Total: 0",
            font=ctk.CTkFont(size=11),
            text_color="#a0a5b5"
        )
        self.lbl_active_info.pack(side="left", padx=10)

        self.lbl_status_msg = ctk.CTkLabel(
            self.statusbar,
            text="● Engine Ready",
            font=ctk.CTkFont(size=11),
            text_color="#a0a5b5",
            anchor="center"
        )
        self.lbl_status_msg.pack(side="left", fill="x", expand=True, padx=15)

        # Support / Buy Me a Beer Button
        import webbrowser
        self.btn_donate = ctk.CTkButton(
            self.statusbar,
            text="🍺 Buy me a beer",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=115,
            height=22,
            fg_color="transparent",
            hover_color="#2b2d35",
            text_color="#f59e0b",
            cursor="hand2",
            command=lambda: webbrowser.open("https://square.link/u/obDkxl6F")
        )
        self.btn_donate.pack(side="right", padx=(4, 15))

        self.lbl_clip_status = ctk.CTkLabel(
            self.statusbar,
            text="📋 Clipboard Monitor: Active" if self.settings.clipboard_monitoring else "📋 Clipboard Monitor: Off",
            font=ctk.CTkFont(size=11),
            text_color="#2ec4b6" if self.settings.clipboard_monitoring else "#a0a5b5"
        )
        self.lbl_clip_status.pack(side="right", padx=(10, 5))

    def apply_theme(self, theme_name: str) -> None:
        """Applies the specified theme to all main window widgets and active cards."""
        self.active_palette = get_theme(theme_name)
        p = self.active_palette
        if ctk.get_appearance_mode().lower() != p["ctk_mode"].lower():
            ctk.set_appearance_mode(p["ctk_mode"])

        # Reset any leftover matrix hover state on all buttons
        all_app_buttons = [
            self.btn_add, self.btn_batch, self.btn_resume_all, self.btn_pause_all,
            self.btn_clear_toolbar, self.btn_settings, self.btn_clear_inactive, self.btn_clear_all,
            self.btn_banner_dl, self.btn_banner_dismiss
        ] + list(self.cat_buttons.values())
        for b in all_app_buttons:
            MatrixButtonAnimator.reset(b)

        self.configure(fg_color=p["bg_main"])
        self.main_frame.configure(fg_color=p["bg_main"])
        self.toolbar.configure(fg_color=p["toolbar_bg"])
        self.btn_add.configure(
            fg_color=p["accent"],
            hover_color=p["accent_hover"],
            text_color=p.get("accent_text", "#ffffff"),
            border_width=p.get("btn_border_width", 0),
            border_color=p.get("btn_border_color", p["btn_bg"]),
        )
        for btn in (self.btn_batch, self.btn_resume_all, self.btn_pause_all, self.btn_clear_toolbar, self.btn_settings):
            btn.configure(
                fg_color=p["btn_bg"],
                hover_color=p["btn_hover"],
                text_color=p.get("btn_text", "#ffffff"),
                border_width=p.get("btn_border_width", 0),
                border_color=p.get("btn_border_color", p["btn_bg"]),
            )
        self.lbl_limit.configure(text_color=p["text_secondary"])
        self.combo_speed_limit.configure(
            fg_color=p["btn_bg"],
            text_color=p["btn_text"],
            button_color=p["btn_hover"],
            dropdown_fg_color=p["card_bg"],
            dropdown_text_color=p["text_primary"],
            border_color=p["card_border"],
            button_hover_color=p["btn_hover"]
        )
        self.entry_search.configure(
            fg_color=p["card_bg"],
            text_color=p["text_primary"],
            border_color=p["card_border"]
        )
        self.sidebar.configure(fg_color=p["sidebar_bg"])
        self.logo_label.configure(text_color=p["accent"])

        for cat_key, btn in self.cat_buttons.items():
            if cat_key == self.current_category:
                btn.configure(
                    fg_color=p["toolbar_bg"] if p["ctk_mode"] == "light" else p["card_bg"],
                    text_color=p["accent"],
                    hover_color=p["btn_hover"],
                    border_width=p.get("btn_border_width", 0),
                    border_color=p.get("btn_border_color", p["btn_bg"])
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=p["text_secondary"],
                    hover_color=p["btn_hover"],
                    border_width=p.get("btn_border_width", 0),
                    border_color=p.get("btn_border_color", p["btn_bg"])
                )

        for btn in (self.btn_clear_inactive, self.btn_clear_all):
            btn.configure(
                fg_color="transparent",
                text_color=p["text_secondary"],
                hover_color=p["btn_hover"],
                border_width=p.get("btn_border_width", 0),
                border_color=p.get("btn_border_color", p["btn_bg"])
            )
        self.banner_frame.configure(fg_color=p["card_bg"])
        self.lbl_banner.configure(text_color=p["accent"])
        self.btn_banner_dl.configure(
            fg_color=p["accent"],
            hover_color=p["accent_hover"],
            text_color=p.get("accent_text", "#ffffff"),
            border_width=p.get("btn_border_width", 0),
            border_color=p.get("btn_border_color", p["btn_bg"])
        )
        self.btn_banner_dismiss.configure(
            hover_color=p["btn_hover"],
            text_color=p["text_secondary"],
            border_width=p.get("btn_border_width", 0),
            border_color=p.get("btn_border_color", p["btn_bg"])
        )
        self.lbl_empty.configure(text_color=p["text_muted"])
        self.statusbar.configure(fg_color=p["sidebar_bg"])
        self.lbl_total_speed.configure(text_color=p["accent"])
        self.lbl_active_info.configure(text_color=p["text_secondary"])
        self.lbl_status_msg.configure(text_color=p["text_secondary"])
        self.lbl_clip_status.configure(
            text_color=p["completed_fill"] if self.settings.clipboard_monitoring else p["text_muted"]
        )

        # Handle Matrix digital rain animation
        if p.get("matrix_rain"):
            self.matrix_rain.configure(bg=p["bg_main"])
            self.scroll_cards.configure(fg_color=p["bg_main"])
        else:
            self.matrix_rain.stop()
            self.matrix_rain.pack_forget()
            self.scroll_cards.configure(fg_color=p["bg_main"])

        # Update all active cards
        for card in self.card_widgets.values():
            card.apply_theme(p)

        self._refresh_downloads_list()

    def _set_category(self, cat_key: str) -> None:
        """Filter downloads by category."""
        self.current_category = cat_key
        p = self.active_palette
        for k, btn in self.cat_buttons.items():
            if k == cat_key:
                btn.configure(
                    fg_color=p["toolbar_bg"] if p["ctk_mode"] == "light" else p["card_bg"],
                    text_color=p["accent"],
                    hover_color=p["btn_hover"],
                    border_width=p.get("btn_border_width", 0),
                    border_color=p.get("btn_border_color", p["btn_bg"])
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=p["text_secondary"],
                    hover_color=p["btn_hover"],
                    border_width=p.get("btn_border_width", 0),
                    border_color=p.get("btn_border_color", p["btn_bg"])
                )
        self._refresh_downloads_list()

    def _on_search_changed(self, event=None) -> None:
        self.search_query = self.entry_search.get().strip().lower()
        self._refresh_downloads_list()

    def _filter_task(self, task: DownloadTask) -> bool:
        """Determines if a task matches category and search filters."""
        if self.search_query:
            query_match = (
                self.search_query in (task.filename or "").lower() or
                self.search_query in task.url.lower()
            )
            if not query_match:
                return False

        if self.current_category == "All":
            return True
        elif self.current_category == "Downloading":
            return task.status in (DownloadStatus.DOWNLOADING, DownloadStatus.CONNECTING)
        elif self.current_category == "Completed":
            return task.status == DownloadStatus.COMPLETED
        elif self.current_category == "Paused":
            return task.status in (DownloadStatus.PAUSED, DownloadStatus.QUEUED, DownloadStatus.ERROR)
        else:
            return task.category.value.lower() == self.current_category.lower()

    def _schedule_refresh(self, delay_ms: int = 80) -> None:
        """Debounced UI refresh to prevent main thread saturation."""
        if hasattr(self, "_refresh_timer_id") and self._refresh_timer_id:
            try:
                self.after_cancel(self._refresh_timer_id)
            except Exception:
                pass
        self._refresh_timer_id = self.after(delay_ms, self._refresh_downloads_list)

    def _refresh_downloads_list(self) -> None:
        """Re-renders the download card list incrementally in slices without dropping Tkinter frames."""
        self._refresh_timer_id = None
        self._card_render_gen = getattr(self, "_card_render_gen", 0) + 1
        current_gen = self._card_render_gen

        # Unpack empty state label first
        self.lbl_empty.pack_forget()

        all_tasks = self.qm.get_all_tasks()
        # Sort newest first
        all_tasks.sort(key=lambda t: t.created_at, reverse=True)

        matching_tasks = [t for t in all_tasks if self._filter_task(t)]
        matching_ids = {t.task_id for t in matching_tasks}

        # Remove cards that no longer match or were deleted
        to_destroy = []
        for tid in list(self.card_widgets.keys()):
            if tid not in matching_ids:
                card = self.card_widgets.pop(tid, None)
                if card:
                    try:
                        card.pack_forget()
                    except Exception:
                        pass
                    to_destroy.append(card)

        if to_destroy:
            self._schedule_widget_destruction(to_destroy)

        # Collect new tasks to instantiate (skip re-updating existing cards to avoid redundant redraws)
        to_create = [task for task in matching_tasks if task.task_id not in self.card_widgets]

        if not matching_tasks:
            if not self.active_palette.get("matrix_rain"):
                self.lbl_empty.pack(side="top", pady=60)
            self._update_matrix_rain_geometry()
            return

        # Incrementally instantiate and pack new cards with a strict frame budget
        # to ensure the Tkinter main thread and OS message pump remain 100% responsive.
        if to_create:
            self.after(5, lambda: self._process_card_creation_queue(to_create, current_gen, chunk_size=1))
        else:
            self._update_matrix_rain_geometry()

    def _schedule_widget_destruction(self, widgets: list, chunk_size: int = 8) -> None:
        """Asynchronously destroys widget hierarchies in small slices so UI thread never drops frames."""
        if not widgets:
            return
        chunk = widgets[:chunk_size]
        rem = widgets[chunk_size:]
        for w in chunk:
            try:
                w.destroy()
            except Exception:
                pass
        if rem:
            self.after(10, lambda: self._schedule_widget_destruction(rem, chunk_size))

    def _process_card_creation_queue(self, remaining_tasks: list, generation: int, chunk_size: int = 1) -> None:
        if generation != getattr(self, "_card_render_gen", 0):
            return

        if not remaining_tasks:
            self._update_matrix_rain_geometry()
            return

        t_start = time.perf_counter()
        idx = 0
        while idx < len(remaining_tasks):
            task = remaining_tasks[idx]
            idx += 1
            if task.task_id not in self.card_widgets:
                card = DownloadCard(
                    self.scroll_cards,
                    task=task,
                    on_pause_resume=self._handle_pause_resume,
                    on_cancel=self._handle_cancel,
                    on_details=self._handle_details,
                    on_redownload=self._handle_redownload,
                    theme_palette=self.active_palette
                )
                card.pack(side="top", fill="x", pady=5, padx=5)
                self.card_widgets[task.task_id] = card

            # Enforce 8ms frame budget: max 1-2 cards per slice for 60 FPS fluidity
            if idx >= chunk_size or (time.perf_counter() - t_start) >= 0.008:
                break

        rest = remaining_tasks[idx:]
        if rest:
            self.after(16, lambda: self._process_card_creation_queue(rest, generation, chunk_size))
        else:
            self._update_matrix_rain_geometry()

    def _update_matrix_rain_geometry(self, event=None) -> None:
        """Dynamically expands matrix rain canvas height or sleeps it when downloads fill the viewport."""
        if not self.active_palette.get("matrix_rain"):
            self.matrix_rain.stop()
            self.matrix_rain.pack_forget()
            return
        try:
            viewport_h = self.main_frame.winfo_height()
            if viewport_h <= 10:
                viewport_h = max(500, self.winfo_height() - 110)

            cards_total_h = 0
            for card in self.card_widgets.values():
                if card.winfo_exists():
                    ch = card.winfo_height()
                    cards_total_h += ch if ch > 10 else 105

            needed_h = viewport_h - cards_total_h - 15
            if needed_h > 40:
                # Viewport has empty space under cards: expand canvas and run animation
                if abs(self.matrix_rain.winfo_height() - needed_h) > 10:
                    self.matrix_rain.configure(height=needed_h)
                if not self.matrix_rain.winfo_ismapped():
                    self.matrix_rain.configure(bg=self.active_palette["bg_main"])
                    self.matrix_rain.pack(side="top", fill="both", expand=True, padx=2, pady=4)
                self.matrix_rain.start()
            else:
                # Cards fill viewport: pause animation to save 100% background CPU/GPU
                self.matrix_rain.stop()
                self.matrix_rain.pack_forget()
        except Exception:
            pass

    def _ui_tick(self) -> None:
        """Periodic UI updates for live progress, speed metrics, animations, and counts."""
        try:
            stats = self.qm.get_stats()
            total_speed = stats["total_speed"]
            active_count = stats["active_count"]
            all_count = stats["total_count"]
            active_downloading = stats["active_downloading"]
            active_connecting = stats["active_connecting"]
            active_errors = stats["active_errors"]

            # Pulse animation on active transfer
            self._pulse_count = getattr(self, "_pulse_count", 0) + 1
            if active_count > 0 and total_speed > 0:
                pulse_icons = ["⚡", "✨", "⚡", "💫"]
                icon = pulse_icons[(self._pulse_count // 2) % len(pulse_icons)]
                self.lbl_total_speed.configure(
                    text=f"{icon} Total Speed: {format_bytes(total_speed)}/s",
                    text_color=self.active_palette["accent"]
                )
            else:
                self.lbl_total_speed.configure(
                    text=f"⚡ Total Speed: {format_bytes(total_speed)}/s",
                    text_color=self.active_palette["accent"]
                )

            max_dl = self.settings.max_concurrent_downloads
            max_dl_str = "∞" if max_dl <= 0 else str(max_dl)
            self.lbl_active_info.configure(text=f"Active: {active_count}/{max_dl_str} • Total: {all_count}")

            # Update center status bar message with active operation details
            if active_downloading:
                top_t = active_downloading[0]
                fname_str = (top_t.filename[:32] + "...") if len(top_t.filename) > 32 else (top_t.filename or "Downloading")
                if top_t.is_torrent:
                    leech_badge = " [Leech Only]" if top_t.leech_only else ""
                    self.lbl_status_msg.configure(
                        text=f"🧲 [P2P Torrent{leech_badge}] {fname_str} • {top_t.progress_pct:.1f}% ({format_bytes(top_t.speed_bytes_per_sec)}/s) • Seeds: {top_t.num_seeds} | Peers: {top_t.num_peers}",
                        text_color=self.active_palette["accent"]
                    )
                elif top_t.is_media_stream:
                    self.lbl_status_msg.configure(
                        text=f"🎬 [Adaptive Stream] {fname_str} • {top_t.progress_pct:.1f}% ({format_bytes(top_t.speed_bytes_per_sec)}/s)",
                        text_color=self.active_palette["accent"]
                    )
                else:
                    self.lbl_status_msg.configure(
                        text=f"⚡ [Multi-Thread] {fname_str} • {top_t.progress_pct:.1f}% ({format_bytes(top_t.speed_bytes_per_sec)}/s)",
                        text_color=self.active_palette["accent"]
                    )
            elif active_connecting:
                top_t = active_connecting[0]
                fname_str = (top_t.filename[:32] + "...") if len(top_t.filename) > 32 else (top_t.filename or "Connecting")
                if top_t.is_torrent:
                    self.lbl_status_msg.configure(
                        text=f"🧲 [BitTorrent Engine] Connecting to DHT swarm & resolving metadata for {fname_str}...",
                        text_color="#f39c12"
                    )
                elif top_t.is_media_stream:
                    self.lbl_status_msg.configure(
                        text=f"🔍 [YouTube Engine] Probing stream & resolving JS challenges for {fname_str}...",
                        text_color="#f39c12"
                    )
                else:
                    self.lbl_status_msg.configure(
                        text=f"🌐 Connecting & allocating parallel segments for {fname_str}...",
                        text_color="#f39c12"
                    )
            elif active_errors:
                top_err = active_errors[0]
                err_txt = top_err.error_message or "Error occurred"
                if len(err_txt) > 45:
                    err_txt = err_txt[:42] + "..."
                self.lbl_status_msg.configure(
                    text=f"⚠️ {top_err.filename or 'Task'}: {err_txt}",
                    text_color="#e63946"
                )
            else:
                self.lbl_status_msg.configure(
                    text="● Engine Ready • Standing by for downloads",
                    text_color=self.active_palette.get("text_muted", "#6c757d")
                )

            # Update only active download cards to keep Tkinter event loop 100% smooth and responsive
            for task in (active_downloading + active_connecting):
                if task.task_id in self.card_widgets:
                    self.card_widgets[task.task_id].update_task_view(task)

            self.after(250, self._ui_tick)
        except Exception:
            pass

    def run_on_ui_thread(self, callback: Callable, *args, **kwargs) -> None:
        """Thread-safe enqueueing of UI operations from any background worker thread."""
        self._ui_event_queue.put((callback, args, kwargs))

    def _check_ui_queue(self) -> None:
        """Drains the thread-safe queue on the main UI thread with a strict frame time budget."""
        try:
            t_start = time.perf_counter()
            while not self._ui_event_queue.empty() and (time.perf_counter() - t_start < 0.008):
                cb, args, kwargs = self._ui_event_queue.get_nowait()
                try:
                    cb(*args, **kwargs)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if not getattr(self, "_force_exit", False):
                try:
                    self.after(16, self._check_ui_queue)
                except Exception:
                    pass

    def _on_queue_event(self, event: str, task: Optional[DownloadTask] = None) -> None:
        """Handles background events from QueueManager on UI thread."""
        if event == "progress":
            return  # Handled smoothly by periodic _ui_tick! Prevents Tkinter mainloop saturation.

        def apply_event():
            if event in ("task_added", "task_removed"):
                self._schedule_refresh(delay_ms=80)
            elif event in ("status_changed", "error"):
                if task and task.task_id in self.card_widgets:
                    self.card_widgets[task.task_id].update_task_view(task)
            elif event == "completed":
                if task and task.task_id in self.card_widgets:
                    self.card_widgets[task.task_id].update_task_view(task)
                if task and hasattr(self, "tray_manager") and self.tray_manager and self.tray_manager.is_running:
                    self.tray_manager.notify(
                        "Download Completed",
                        f"Finished: {task.filename}"
                    )

        self.run_on_ui_thread(apply_event)

    def _handle_pause_resume(self, task: DownloadTask) -> None:
        if task.status == DownloadStatus.DOWNLOADING:
            self.qm.pause_task(task.task_id)
        else:
            self.qm.start_task(task.task_id)

    def _handle_cancel(self, task: DownloadTask) -> None:
        self.qm.remove_task(task.task_id)
        self._refresh_downloads_list()

    def _handle_redownload(self, task: DownloadTask) -> None:
        self.qm.redownload_task(task.task_id)
        self._refresh_downloads_list()

    def _handle_details(self, task: DownloadTask) -> None:
        DetailsDialog(self, task)

    def _open_add_dialog(self, initial_url: str = "") -> None:
        AddDownloadDialog(self, self.settings, on_add=self._on_download_added, initial_url=initial_url)

    def _open_batch_dialog(self) -> None:
        BatchAddDialog(self, self.settings, on_batch_add=self._on_batch_added)

    def _on_download_added(self, data: dict) -> None:
        self._set_category("All")
        self.qm.create_and_add_task(
            url=data["url"],
            filename=data.get("filename"),
            save_path=data.get("save_path"),
            num_connections=data.get("num_connections"),
            expected_checksum=data.get("expected_checksum"),
            checksum_algo=data.get("checksum_algo"),
            auto_start=data.get("auto_start", True),
            total_bytes=data.get("total_bytes"),
            supports_range=data.get("supports_range"),
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
            category=data.get("category"),
            is_media_stream=data.get("is_media_stream"),
            media_quality=data.get("media_quality", "best"),
            media_format=data.get("media_format", "mp4"),
            audio_only=data.get("audio_only", False),
            is_torrent=data.get("is_torrent", False),
            leech_only=data.get("leech_only", True),
            sequential_download=data.get("sequential_download", False),
            max_peers=data.get("max_peers", 100),
            download_limit_kbps=data.get("download_limit_kbps", 0),
            upload_limit_kbps=data.get("upload_limit_kbps", 0),
            dht_enabled=data.get("dht_enabled", True),
            torrent_info_hash=data.get("torrent_info_hash")
        )
        self._refresh_downloads_list()

    def _on_batch_added(self, data: dict) -> None:
        urls = data.get("urls", [])
        save_path = data.get("save_path")
        conns = data.get("num_connections")
        auto_start = data.get("auto_start", True)

        self.qm.create_and_add_batch_tasks(
            urls=urls,
            save_path=save_path,
            num_connections=conns,
            auto_start=auto_start
        )
        self._refresh_downloads_list()

    def _open_settings_dialog(self) -> None:
        SettingsDialog(self, self.settings, on_save=self._on_settings_saved)

    def _on_settings_saved(self, new_settings: DownloadSettings) -> None:
        self.settings = new_settings
        self.qm.settings = new_settings
        self.qm.config_path = os.path.join(self.qm.data_dir, "settings.json")
        self.settings.save(self.qm.config_path)

        # Apply theme dynamically
        self.apply_theme(self.settings.theme)

        # Update clipboard monitor
        if self.settings.clipboard_monitoring:
            self.clipboard_monitor.start()
            self.lbl_clip_status.configure(text="📋 Clipboard Monitor: Active", text_color=self.active_palette["completed_fill"])
        else:
            self.clipboard_monitor.stop()
            self.lbl_clip_status.configure(text="📋 Clipboard Monitor: Off", text_color=self.active_palette["text_muted"])

    def _on_speed_limit_changed(self, choice: str) -> None:
        limit_map = {
            "Unlimited": 0,
            "500 KB/s": 500 * 1024,
            "1 MB/s": 1024 * 1024,
            "2 MB/s": 2 * 1024 * 1024,
            "5 MB/s": 5 * 1024 * 1024,
            "10 MB/s": 10 * 1024 * 1024,
            "20 MB/s": 20 * 1024 * 1024,
        }
        limit_bytes = limit_map.get(choice, 0)
        self.qm.set_speed_limit(limit_bytes)

    def _clear_completed(self) -> None:
        self.qm.clear_completed()
        self._refresh_downloads_list()

    def _clear_inactive_downloads(self) -> None:
        """Removes all finished (completed), failed (error), and cancelled tasks."""
        self.qm.clear_inactive()
        self._refresh_downloads_list()

    def _clear_all_downloads(self) -> None:
        """Removes all tasks from the download queue with instantaneous UI response."""
        self._card_render_gen = getattr(self, "_card_render_gen", 0) + 1
        old_cards = list(self.card_widgets.values())
        self.card_widgets.clear()
        for card in old_cards:
            try:
                card.pack_forget()
            except Exception:
                pass
        if old_cards:
            self._schedule_widget_destruction(old_cards)
        self.qm.clear_all()
        self._refresh_downloads_list()

    def _on_clipboard_url(self, url: str) -> None:
        """Callback when clipboard monitor detects a new downloadable link."""
        self.detected_clipboard_url = url
        short_url = url if len(url) < 60 else url[:57] + "..."

        def show_banner():
            self.lbl_banner.configure(text=f"📋 Detected link: {short_url}")
            self.banner_frame.grid()

        self.run_on_ui_thread(show_banner)

    def _download_clipboard_url(self) -> None:
        self.banner_frame.grid_remove()
        if self.detected_clipboard_url:
            self._open_add_dialog(initial_url=self.detected_clipboard_url)

    def _on_api_add_download(self, data: dict) -> None:
        """Handles download request sent from browser extension or CLI via HTTP API."""
        items = data.get("items", [])
        subfolder = data.get("subfolder", "").strip()
        save_path = data.get("save_path", "").strip()

        # Determine target save directory
        target_dir = self.settings.default_save_dir
        if save_path:
            target_dir = save_path
        elif subfolder:
            # Clean subfolder name of illegal filesystem characters
            cleaned_subfolder = "".join(c for c in subfolder if c not in r'<>:"/\|?*').strip()
            if cleaned_subfolder:
                target_dir = os.path.join(self.settings.default_save_dir, cleaned_subfolder)

        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            pass

        auto_start = data.get("auto_start", True)
        audio_only = data.get("audio_only", False)
        format_id = data.get("format_id", "")

        def async_worker():
            if items and isinstance(items, list):
                # Batch / Playlist download - process smoothly without blocking UI
                added_count = 0
                valid_items = [it for it in items if (it.get("url", "").strip() if isinstance(it, dict) else str(it).strip())]
                total_items = len(valid_items)
                for idx, item in enumerate(valid_items):
                    item_url = item.get("url", "").strip() if isinstance(item, dict) else str(item).strip()
                    item_name = item.get("filename", "") if isinstance(item, dict) else None
                    item_audio = item.get("audio_only", audio_only) if isinstance(item, dict) else audio_only
                    is_media = "youtube.com" in item_url.lower() or "youtu.be" in item_url.lower() or item_audio

                    fallback_name = item_name or f"Track_{added_count + 1}.{'mp3' if item_audio else 'mp4'}"
                    is_last = (idx == total_items - 1)
                    self.qm.create_and_add_task(
                        url=item_url,
                        filename=fallback_name,
                        save_path=target_dir,
                        num_connections=min(self.settings.default_connections_per_task, 8),
                        audio_only=item_audio,
                        media_format="mp3" if item_audio else "mp4",
                        is_media_stream=is_media,
                        total_bytes=0 if is_media else None,
                        supports_range=True if is_media else None,
                        category=DownloadCategory.AUDIO if item_audio else DownloadCategory.VIDEO,
                        auto_start=auto_start,
                        notify=is_last
                    )
                    added_count += 1

                self.run_on_ui_thread(self._schedule_refresh)
                if hasattr(self, "tray_manager") and self.tray_manager and self.tray_manager.is_running:
                    playlist_title = data.get("playlist_title") or subfolder or "Playlist"
                    self.tray_manager.notify(
                        "Playlist Download Started",
                        f"Queued {added_count} tracks from '{playlist_title}' into '{os.path.basename(target_dir)}'"
                    )
                return

            # Single download fallback
            url = data.get("url", "").strip()
            if not url:
                return
            custom_name = data.get("filename", "") or None
            is_media = "youtube.com" in url.lower() or "youtu.be" in url.lower() or audio_only

            if auto_start:
                task = self.qm.create_and_add_task(
                    url=url,
                    filename=custom_name,
                    save_path=target_dir,
                    num_connections=self.settings.default_connections_per_task,
                    audio_only=audio_only,
                    media_format="mp3" if audio_only else "mp4",
                    is_media_stream=is_media,
                    total_bytes=0 if is_media else None,
                    supports_range=True if is_media else None,
                    category=DownloadCategory.AUDIO if audio_only else (DownloadCategory.VIDEO if is_media else None),
                    auto_start=True
                )
                self.run_on_ui_thread(self._schedule_refresh)

                # Non-intrusive tray balloon notification so the user knows the download started in background
                if hasattr(self, "tray_manager") and self.tray_manager and self.tray_manager.is_running:
                    self.tray_manager.notify(
                        "Download Started",
                        f"Downloading in background: {task.filename or url[:45]}"
                    )
            else:
                self.run_on_ui_thread(lambda: (self._show_from_tray(), self._open_add_dialog(initial_url=url)))

        threading.Thread(target=async_worker, daemon=True, name="ApiAddDownloadWorker").start()

    def _get_api_status(self) -> dict:
        active_count = len(self.qm.get_active_tasks())
        all_count = len(self.qm.get_all_tasks())
        return {
            "active_downloads": active_count,
            "total_downloads": all_count
        }

    def _show_from_tray(self) -> None:
        """Restores and brings the main window to the front."""
        try:
            self.deiconify()
            self.state("normal")
            self.lift()
            self.attributes("-topmost", True)
            self.after(150, lambda: self.attributes("-topmost", False))
            self.focus_force()

            # On Windows, force foreground activation via Win32 API to bypass OS Foreground Lock
            if sys.platform == "win32":
                try:
                    import ctypes
                    hwnd = self.winfo_id()
                    root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2) or hwnd
                    ctypes.windll.user32.ShowWindow(root_hwnd, 9)  # SW_RESTORE = 9
                    ctypes.windll.user32.SetForegroundWindow(root_hwnd)
                except Exception:
                    pass
        except Exception:
            pass

    def _hide_to_tray(self) -> None:
        """Hides the window to the system notification area / tray."""
        try:
            self.withdraw()
            if hasattr(self, "tray_manager") and self.tray_manager and self.tray_manager.is_running:
                self.tray_manager.notify(
                    "Turbo Download Manager",
                    "App is running in the background. Browser downloads will start automatically."
                )
        except Exception:
            pass

    def _on_window_unmap(self, event) -> None:
        """Intercepts window minimize to withdraw to tray if enabled."""
        if event.widget == self and self.state() == "iconic":
            if getattr(self.settings, "minimize_to_tray", True):
                self.after(20, self.withdraw)

    def _tray_add_download(self) -> None:
        self._show_from_tray()
        self._open_add_dialog()

    def _tray_pause_all(self) -> None:
        for task in self.qm.get_active_tasks():
            self.qm.pause_task(task.task_id)
        self._refresh_downloads_list()

    def _tray_resume_all(self) -> None:
        for task in self.qm.get_all_tasks():
            if task.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
                self.qm.start_task(task.task_id)
        self._refresh_downloads_list()

    def _tray_settings(self) -> None:
        self._show_from_tray()
        self._open_settings_dialog()

    def _on_close(self) -> None:
        if getattr(self.settings, "close_to_tray", True) and not getattr(self, "_force_exit", False):
            self._hide_to_tray()
        else:
            self._exit_application()

    def _exit_application(self) -> None:
        self._force_exit = True
        if hasattr(self, "tray_manager") and self.tray_manager:
            self.tray_manager.stop()
        if hasattr(self, "api_server") and self.api_server:
            self.api_server.stop()
        if hasattr(self, "clipboard_monitor") and self.clipboard_monitor:
            self.clipboard_monitor.stop()
        if hasattr(self, "qm") and self.qm:
            self.qm.close()
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)


def main(initial_url: str = "", start_in_tray: bool = False):
    app = TurboDownloadApp(initial_url=initial_url, start_in_tray=start_in_tray)
    app.mainloop()


if __name__ == "__main__":
    main()
