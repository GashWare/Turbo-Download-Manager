"""
Download Card Component for CustomTkinter GUI.
Renders an individual task with live animated progress, segment chunk visualizer,
speed indicators, and quick action controls.
"""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Optional, Dict, Any
import customtkinter as ctk
import pyperclip

from core.models import DownloadTask, DownloadStatus, DownloadCategory, format_eta
from core.os_utils import OSUtils
from gui.themes import get_theme
from gui.components.matrix_rain import MatrixButtonAnimator


def format_bytes(size_bytes: float) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


CATEGORY_ICONS = {
    DownloadCategory.TORRENT: "🧲",
    DownloadCategory.VIDEO: "🎬",
    DownloadCategory.AUDIO: "🎵",
    DownloadCategory.DOCUMENTS: "📄",
    DownloadCategory.COMPRESSED: "📦",
    DownloadCategory.PROGRAMS: "⚡",
    DownloadCategory.IMAGES: "🖼️",
    DownloadCategory.OTHER: "📁",
}

STATUS_COLOR_KEYS = {
    DownloadStatus.DOWNLOADING: "badge_downloading",
    DownloadStatus.CONNECTING: "badge_connecting",
    DownloadStatus.COMPLETED: "badge_completed",
    DownloadStatus.PAUSED: "badge_paused",
    DownloadStatus.ERROR: "badge_error",
    DownloadStatus.QUEUED: "badge_queued",
    DownloadStatus.CANCELLED: "badge_cancelled",
}


class SegmentCanvas(tk.Canvas):
    """Ultra-fast multi-segment block visualizer using in-place coordinate updates."""

    def __init__(self, master, height: int = 8, theme_palette: Optional[Dict[str, Any]] = None, **kwargs):
        self.palette = theme_palette or get_theme("dark")
        super().__init__(master, height=height, bg=self.palette["card_bg"], highlightthickness=0, **kwargs)
        self.status = DownloadStatus.QUEUED
        self.progress_pct = 0.0
        
        p = self.palette
        self._bg_rect = self.create_rectangle(0, 0, 1, height, fill=p["progress_bg"], outline="")
        self._fill_rect = self.create_rectangle(0, 0, 0, height, fill=p["progress_fill"], outline="")
        self._last_w = 0
        self._last_fill_w = -1
        self._last_color = None
        self.bind("<Configure>", self._on_configure)

    def set_theme(self, palette: Dict[str, Any]) -> None:
        self.palette = palette
        self.configure(bg=palette["card_bg"])
        self.itemconfig(self._bg_rect, fill=palette["progress_bg"])
        self._last_color = None
        self._update_fill()

    def _on_configure(self, event=None) -> None:
        w = event.width if event else self.winfo_width()
        h = event.height if event else (self.winfo_height() or 8)
        if w > 1:
            self._last_w = w
            self.coords(self._bg_rect, 0, 0, w, h)
            self._update_fill()

    def update_segments(self, task: DownloadTask) -> None:
        pct_rounded = round(task.progress_pct, 1)
        if task.status == self.status and pct_rounded == self.progress_pct:
            return
        self.status = task.status
        self.progress_pct = pct_rounded
        self._update_fill()

    def _update_fill(self) -> None:
        w = self._last_w if self._last_w > 1 else self.winfo_width()
        if w <= 1:
            return
        h = self.winfo_height() or 8
        filled_w = int(w * (self.progress_pct / 100.0))
        if filled_w != self._last_fill_w:
            self.coords(self._fill_rect, 0, 0, filled_w, h)
            self._last_fill_w = filled_w

        p = self.palette
        badge_key = STATUS_COLOR_KEYS.get(self.status, "badge_downloading")
        color = p.get(badge_key, p["progress_fill"])
        if color != self._last_color:
            self.itemconfig(self._fill_rect, fill=color)
            self._last_color = color

    def draw(self, force: bool = False) -> None:
        if force:
            self._last_fill_w = -1
            self._last_color = None
        self._update_fill()


class FlatLabel(tk.Label):
    """Lightweight label replacing compound CTkLabel for instant rendering."""
    def __init__(self, master=None, text="", text_color=None, fg_color=None, font=None, anchor="center", padx=0, pady=0, **kwargs):
        self._text_color = text_color or "#ffffff"
        self._fg_color = fg_color or (master["bg"] if master and hasattr(master, "__getitem__") and "bg" in master.keys() else "#1a1b1e")
        kwargs.pop("corner_radius", None)
        super().__init__(
            master,
            text=text,
            fg=self._text_color,
            bg=self._fg_color,
            font=font or ("Segoe UI", 10),
            anchor=anchor,
            padx=padx,
            pady=pady,
            **kwargs
        )

    def configure(self, **kwargs):
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            kwargs["fg"] = self._text_color
        if "fg_color" in kwargs:
            self._fg_color = kwargs.pop("fg_color")
            kwargs["bg"] = self._fg_color
        kwargs.pop("corner_radius", None)
        super().configure(**kwargs)

    def cget(self, key):
        if key == "text_color":
            return self._text_color
        if key == "fg_color":
            return self._fg_color
        return super().cget(key)


class FlatButton(tk.Button):
    """Ultra-fast flat button replacing heavy compound CTkButton for download cards."""
    def __init__(self, master=None, text="", fg_color=None, hover_color=None, text_color=None, font=None, command=None, padx=8, pady=2, **kwargs):
        self._fg_color = fg_color or "#2b2d35"
        self._hover_color = hover_color or "#383a45"
        self._text_color = text_color or "#ffffff"
        kwargs.pop("corner_radius", None)
        kwargs.pop("border_width", None)
        kwargs.pop("border_color", None)
        kwargs.pop("width", None)
        kwargs.pop("height", None)

        super().__init__(
            master,
            text=text,
            bg=self._fg_color,
            fg=self._text_color,
            activebackground=self._hover_color,
            activeforeground=self._text_color,
            relief="flat",
            bd=0,
            padx=padx,
            pady=pady,
            font=font or ("Segoe UI", 9, "bold"),
            command=command,
            cursor="hand2",
            **kwargs
        )
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        try:
            super().configure(bg=self._hover_color)
        except Exception:
            pass

    def _on_leave(self, event=None):
        try:
            super().configure(bg=self._fg_color)
        except Exception:
            pass

    def configure(self, **kwargs):
        if "fg_color" in kwargs:
            self._fg_color = kwargs.pop("fg_color")
            kwargs["bg"] = self._fg_color
        if "hover_color" in kwargs:
            self._hover_color = kwargs.pop("hover_color")
            kwargs["activebackground"] = self._hover_color
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            kwargs["fg"] = self._text_color
            kwargs["activeforeground"] = self._text_color
        kwargs.pop("corner_radius", None)
        kwargs.pop("border_width", None)
        kwargs.pop("border_color", None)
        kwargs.pop("width", None)
        kwargs.pop("height", None)
        super().configure(**kwargs)

    def cget(self, key):
        if key == "fg_color":
            return self._fg_color
        if key == "hover_color":
            return self._hover_color
        if key == "text_color":
            return self._text_color
        return super().cget(key)


class DownloadCard(tk.Frame):
    """High-performance interactive card representing a single download item."""

    def __init__(
        self,
        master,
        task: DownloadTask,
        on_pause_resume: Callable[[DownloadTask], None],
        on_cancel: Callable[[DownloadTask], None],
        on_details: Callable[[DownloadTask], None],
        on_redownload: Optional[Callable[[DownloadTask], None]] = None,
        theme_palette: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.palette = theme_palette or get_theme("dark")
        kwargs.pop("corner_radius", None)
        kwargs.pop("border_width", None)
        kwargs.pop("border_color", None)
        kwargs.pop("fg_color", None)
        super().__init__(
            master,
            bg=self.palette["card_bg"],
            highlightbackground=self.palette.get("card_border", "#2a2d36"),
            highlightcolor=self.palette.get("card_border", "#2a2d36"),
            highlightthickness=self.palette.get("card_border_width", 1),
            **kwargs
        )
        self.task = task
        self.on_pause_resume = on_pause_resume
        self.on_cancel = on_cancel
        self.on_details = on_details
        self.on_redownload = on_redownload

        # Cache variables to prevent widget re-configuration flickering
        self._last_filename: Optional[str] = None
        self._last_status: Optional[DownloadStatus] = None
        self._last_metrics_text: Optional[str] = None
        self._last_button_mode: Optional[str] = None
        self._context_menu_widget: Optional[tk.Menu] = None

        self._build_ui()
        self._setup_context_menu()
        self.update_task_view(task)

    def configure(self, **kwargs):
        if "fg_color" in kwargs:
            kwargs["bg"] = kwargs.pop("fg_color")
        if "border_color" in kwargs:
            kwargs["highlightbackground"] = kwargs.pop("border_color")
            kwargs["highlightcolor"] = kwargs["highlightbackground"]
        if "border_width" in kwargs:
            kwargs["highlightthickness"] = kwargs.pop("border_width")
        kwargs.pop("corner_radius", None)
        super().configure(**kwargs)

    def cget(self, key: str):
        if key == "fg_color":
            return self.cget("bg")
        if key == "border_color":
            return self.cget("highlightbackground")
        if key == "border_width":
            return self.cget("highlightthickness")
        return super().cget(key)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Category Icon
        cat_icon = CATEGORY_ICONS.get(self.task.category, "📁")
        self.icon_label = FlatLabel(
            self,
            text=cat_icon,
            font=("Segoe UI", 20),
            fg_color=self.palette["card_bg"],
            width=3
        )
        self.icon_label.grid(row=0, column=0, rowspan=3, padx=(12, 8), pady=12)

        # Header: Filename & Status Badge
        self.header_frame = tk.Frame(self, bg=self.palette["card_bg"])
        self.header_frame.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 2))
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.filename_label = FlatLabel(
            self.header_frame,
            text=self.task.filename or "Initializing...",
            font=("Segoe UI", 11, "bold"),
            fg_color=self.palette["card_bg"],
            text_color=self.palette["text_primary"],
            anchor="w"
        )
        self.filename_label.grid(row=0, column=0, sticky="w")

        badge_key = STATUS_COLOR_KEYS.get(self.task.status, "badge_downloading")
        self.status_badge = FlatLabel(
            self.header_frame,
            text=self.task.status.value,
            font=("Segoe UI", 8, "bold"),
            fg_color=self.palette.get(badge_key, "#555"),
            text_color="#ffffff",
            padx=8,
            pady=2
        )
        self.status_badge.grid(row=0, column=1, sticky="e")

        # Multi-Segment Progress Canvas (in-place coords update)
        self.segment_canvas = SegmentCanvas(self, height=8, theme_palette=self.palette)
        self.segment_canvas.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(4, 6))

        # Metrics Row: Size / Speed / ETA / Acceleration Info
        self.metrics_frame = tk.Frame(self, bg=self.palette["card_bg"])
        self.metrics_frame.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(0, 10))
        self.metrics_frame.grid_columnconfigure(0, weight=1)

        self.metrics_label = FlatLabel(
            self.metrics_frame,
            text="0 B / 0 B (0%) • 0 B/s • ETA: --:--",
            font=("Segoe UI", 9),
            text_color="#a0a5b5",
            fg_color=self.palette["card_bg"],
            anchor="w"
        )
        self.metrics_label.grid(row=0, column=0, sticky="w")

        # Action Buttons Container
        self.actions_frame = tk.Frame(self.metrics_frame, bg=self.palette["card_bg"])
        self.actions_frame.grid(row=0, column=1, sticky="e")

        # Action Button (Pause / Resume / Retry)
        self.btn_action = FlatButton(
            self.actions_frame,
            text="Pause",
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self._on_action_click
        )

        # Open File Button (Direct launch)
        self.btn_open_file = FlatButton(
            self.actions_frame,
            text="Open",
            fg_color="#2ec4b6",
            hover_color="#249c90",
            text_color="#0d1117",
            command=self._open_file
        )

        # Open Folder Button (Reveals file in system file explorer)
        self.btn_open_folder = FlatButton(
            self.actions_frame,
            text="Open Folder",
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self._open_folder
        )

        # Details Button
        self.btn_details = FlatButton(
            self.actions_frame,
            text="Details",
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=lambda: self.on_details(self.task)
        )

        # Cancel/Delete Button
        self.btn_cancel = FlatButton(
            self.actions_frame,
            text="✕",
            fg_color="#3a1c1c",
            hover_color="#5a2222",
            text_color="#ff6b6b",
            command=lambda: self.on_cancel(self.task)
        )

        # Only attach Matrix hover animations when matrix theme is enabled
        if self.palette.get("matrix_rain"):
            for btn in (self.btn_action, self.btn_open_file, self.btn_open_folder, self.btn_details, self.btn_cancel):
                MatrixButtonAnimator.attach(btn, app_ref=self)

    def apply_theme(self, palette: Dict[str, Any]) -> None:
        """Applies a new theme palette dynamically to the card and all its subcomponents."""
        self.palette = palette
        self._context_menu_widget = None  # Re-create with new colors on next right-click

        for b in (self.btn_details, self.btn_open_folder, self.btn_open_file, self.btn_cancel, self.btn_action):
            MatrixButtonAnimator.reset(b)

        self.configure(
            fg_color=palette["card_bg"],
            border_color=palette["card_border"],
            border_width=palette.get("card_border_width", 1)
        )
        self.header_frame.configure(bg=palette["card_bg"])
        self.metrics_frame.configure(bg=palette["card_bg"])
        self.actions_frame.configure(bg=palette["card_bg"])
        self.icon_label.configure(fg_color=palette["card_bg"], text_color=palette.get("text_primary", "#ffffff"))
        self.filename_label.configure(fg_color=palette["card_bg"], text_color=palette["text_primary"])
        self.metrics_label.configure(fg_color=palette["card_bg"], text_color=palette["text_secondary"])

        # Update action buttons colors and borders
        self.btn_details.configure(
            fg_color=palette["btn_bg"],
            hover_color=palette["btn_hover"],
            text_color=palette["btn_text"],
            border_width=palette.get("btn_border_width", 0),
            border_color=palette.get("btn_border_color", palette["btn_bg"])
        )
        self.btn_open_folder.configure(
            fg_color=palette["btn_bg"],
            hover_color=palette["btn_hover"],
            text_color=palette["btn_text"],
            border_width=palette.get("btn_border_width", 0),
            border_color=palette.get("btn_border_color", palette["btn_bg"])
        )
        self.btn_open_file.configure(
            fg_color=palette["btn_open_bg"],
            hover_color=palette["btn_open_hover"],
            text_color=palette["btn_open_text"],
            border_width=palette.get("btn_border_width", 0),
            border_color=palette.get("btn_border_color", palette["btn_bg"])
        )
        self.btn_cancel.configure(
            fg_color=palette["btn_cancel_bg"],
            hover_color=palette["btn_cancel_hover"],
            text_color=palette["btn_cancel_text"],
            border_width=palette.get("btn_border_width", 0),
            border_color=palette.get("btn_border_color", palette["btn_cancel_bg"])
        )

        # Update segment visualizer
        self.segment_canvas.set_theme(palette)

        # Reset button mode cache so button styles re-apply with new palette
        self._last_button_mode = None
        self._last_status = None
        self.update_task_view(self.task)

    def _update_button_layout(self, status: DownloadStatus) -> None:
        """Updates the action buttons visibility and text based on current status without redundant re-gridding."""
        if status == DownloadStatus.COMPLETED:
            mode = "COMPLETED"
        elif status in (DownloadStatus.PAUSED, DownloadStatus.QUEUED):
            mode = "PAUSED"
        elif status in (DownloadStatus.ERROR, DownloadStatus.CANCELLED):
            mode = "ERROR"
        else:
            mode = "RUNNING"

        if mode == self._last_button_mode:
            return
        self._last_button_mode = mode
        p = self.palette

        # Grid buttons based on mode
        if mode == "COMPLETED":
            self.btn_action.grid_remove()
            self.btn_open_file.grid(row=0, column=0, padx=3)
            self.btn_open_folder.grid(row=0, column=1, padx=3)
            self.btn_details.grid(row=0, column=2, padx=3)
            self.btn_cancel.grid(row=0, column=3, padx=(3, 0))
        elif mode == "PAUSED":
            self.btn_open_file.grid_remove()
            self.btn_action.grid(row=0, column=0, padx=3)
            self.btn_action.configure(
                text="Resume",
                fg_color=p["accent"],
                hover_color=p["accent_hover"],
                text_color=p["accent_text"],
                border_width=p.get("btn_border_width", 0),
                border_color=p.get("btn_border_color", p["btn_bg"])
            )
            self.btn_open_folder.grid(row=0, column=1, padx=3)
            self.btn_details.grid(row=0, column=2, padx=3)
            self.btn_cancel.grid(row=0, column=3, padx=(3, 0))
        elif mode == "ERROR":
            self.btn_open_file.grid_remove()
            self.btn_action.grid(row=0, column=0, padx=3)
            self.btn_action.configure(
                text="Retry",
                fg_color=p["btn_bg"],
                hover_color=p["btn_hover"],
                text_color=p["btn_text"],
                border_width=p.get("btn_border_width", 0),
                border_color=p.get("btn_border_color", p["btn_bg"])
            )
            self.btn_open_folder.grid(row=0, column=1, padx=3)
            self.btn_details.grid(row=0, column=2, padx=3)
            self.btn_cancel.grid(row=0, column=3, padx=(3, 0))
        else:  # RUNNING
            self.btn_open_file.grid_remove()
            self.btn_open_folder.grid_remove()
            self.btn_action.grid(row=0, column=0, padx=3)
            self.btn_action.configure(
                text="Pause",
                fg_color=p["btn_bg"],
                hover_color=p["btn_hover"],
                text_color=p["btn_text"],
                border_width=p.get("btn_border_width", 0),
                border_color=p.get("btn_border_color", p["btn_bg"])
            )
            self.btn_details.grid(row=0, column=1, padx=3)
            self.btn_cancel.grid(row=0, column=2, padx=(3, 0))

    def _on_action_click(self) -> None:
        if self.task.status in (DownloadStatus.ERROR, DownloadStatus.CANCELLED):
            if self.on_redownload:
                self.on_redownload(self.task)
            else:
                self.on_pause_resume(self.task)
        else:
            self.on_pause_resume(self.task)

    def update_task_view(self, task: DownloadTask) -> None:
        """Refreshes UI elements based on the latest task state using caching to prevent twitching."""
        self.task = task
        p = self.palette
        
        # 1. Update Filename if changed
        current_name = task.filename or "Initializing..."
        if current_name != self._last_filename:
            self.filename_label.configure(text=current_name)
            self._last_filename = current_name
        
        # 2. Update Status Badge if changed
        if task.status != self._last_status:
            badge_key = STATUS_COLOR_KEYS.get(task.status, "badge_queued")
            status_color = p.get(badge_key, "#555")
            self.status_badge.configure(text=task.status.value, fg_color=status_color)
            self._last_status = task.status

        # 3. Update Action Buttons layout
        self._update_button_layout(task.status)

        # 4. Construct Metrics text
        pct = task.progress_pct
        transferred = f"{format_bytes(task.downloaded_bytes)} / {format_bytes(task.total_bytes)}"
        speed_str = f"{format_bytes(task.speed_bytes_per_sec)}/s" if task.status == DownloadStatus.DOWNLOADING else ""
        eta_str = f"ETA: {format_eta(task.eta_seconds)}" if task.eta_seconds is not None else ""
        
        info_parts = [f"{transferred} ({pct:.1f}%)"]
        if speed_str:
            info_parts.append(speed_str)
        if eta_str:
            info_parts.append(eta_str)
        if task.is_torrent:
            if task.leech_only:
                info_parts.append("🛡️ Leech Only")
            else:
                info_parts.append(f"🧲 P2P (⬆ {format_bytes(task.upload_speed_bytes_per_sec)}/s)")
            if task.num_peers > 0 or task.num_seeds > 0:
                info_parts.append(f"S: {task.num_seeds} | P: {task.num_peers}")
        elif task.supports_range and task.num_connections > 1:
            info_parts.append(f"⚡ {task.num_connections} conns")
        elif task.is_media_stream:
            info_parts.append("★ Stream")

        if task.error_message:
            info_parts = [f"Error: {task.error_message}"]

        metrics_text = " • ".join(info_parts)
        if metrics_text != self._last_metrics_text:
            self.metrics_label.configure(text=metrics_text)
            self._last_metrics_text = metrics_text

        # 5. Update segment visualizer (internally cached)
        self.segment_canvas.update_segments(task)

    def _setup_context_menu(self) -> None:
        """Configures right-click popup context menu binding."""
        self.bind("<Button-3>", self._show_context_menu)
        for w in (self.icon_label, self.filename_label, self.metrics_label, self.segment_canvas):
            w.bind("<Button-3>", self._show_context_menu)

    def _get_context_menu(self) -> tk.Menu:
        if self._context_menu_widget is not None:
            return self._context_menu_widget
        p = self.palette
        menu = tk.Menu(
            self,
            tearoff=0,
            bg=p["card_bg"],
            fg=p["text_primary"],
            activebackground=p["accent"],
            activeforeground=p["accent_text"]
        )
        menu.add_command(label="▶ Resume / Start", command=lambda: self.on_pause_resume(self.task))
        menu.add_command(label="⏸ Pause", command=lambda: self.on_pause_resume(self.task))
        menu.add_command(label="🔄 Re-download from start", command=self._handle_redownload)
        menu.add_separator()
        menu.add_command(label="📂 Open File", command=self._open_file)
        menu.add_command(label="📁 Open Folder & Reveal", command=self._open_folder)
        menu.add_separator()
        menu.add_command(label="🔗 Copy Download Link", command=self._copy_link)
        menu.add_command(label="📋 Copy Output Path", command=self._copy_path)
        menu.add_separator()
        menu.add_command(label="📊 Task Inspector & Checksum", command=lambda: self.on_details(self.task))
        menu.add_separator()
        menu.add_command(label="✕ Delete Download", command=lambda: self.on_cancel(self.task))
        self._context_menu_widget = menu
        return menu

    @property
    def context_menu(self) -> tk.Menu:
        """Backward-compatible property for any tests or references expecting self.context_menu."""
        return self._get_context_menu()

    def _show_context_menu(self, event) -> None:
        menu = self._get_context_menu()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _handle_redownload(self) -> None:
        if self.on_redownload:
            self.on_redownload(self.task)

    def _copy_link(self) -> None:
        pyperclip.copy(self.task.url)

    def _copy_path(self) -> None:
        pyperclip.copy(self.task.full_output_path)

    def _open_folder(self) -> None:
        """Opens the folder in file explorer and highlights the file cross-platform."""
        path = self.task.full_output_path
        if not OSUtils.reveal_in_folder(path):
            OSUtils.open_folder(self.task.save_path)

    def _open_file(self) -> None:
        """Opens the downloaded file cross-platform."""
        path = self.task.full_output_path
        if not OSUtils.open_file(path):
            OSUtils.reveal_in_folder(path)

