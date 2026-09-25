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
    """Draws multi-segment block visualizer showing individual connection progress."""

    def __init__(self, master, height: int = 10, theme_palette: Optional[Dict[str, Any]] = None, **kwargs):
        self.palette = theme_palette or get_theme("dark")
        super().__init__(master, height=height, bg=self.palette["card_bg"], highlightthickness=0, **kwargs)
        self.segments = []
        self.total_bytes = 0
        self.status = DownloadStatus.QUEUED
        self.progress_pct = 0.0
        self._last_draw_key = None
        self.bind("<Configure>", lambda e: self.draw(force=True))

    def set_theme(self, palette: Dict[str, Any]) -> None:
        self.palette = palette
        self.configure(bg=palette["card_bg"])
        self.draw(force=True)

    def update_segments(self, task: DownloadTask) -> None:
        seg_snapshot = tuple((s.segment_id, s.downloaded_bytes, s.status) for s in task.segments) if task.segments else ()
        key = (task.status, task.total_bytes, round(task.progress_pct, 1), seg_snapshot)
        if key == self._last_draw_key:
            return
        self._last_draw_key = key
        self.segments = task.segments
        self.total_bytes = task.total_bytes
        self.status = task.status
        self.progress_pct = task.progress_pct
        self.draw()

    def draw(self, force: bool = False) -> None:
        if force:
            self._last_draw_key = None
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1:
            return

        p = self.palette
        badge_color = p.get(STATUS_COLOR_KEYS.get(self.status, "badge_downloading"), p["progress_fill"])

        # Single stream fallback or no segments
        if not self.segments or self.total_bytes <= 0:
            filled_w = int(w * (self.progress_pct / 100.0))
            self.create_rectangle(0, 0, filled_w, h, fill=badge_color, outline="")
            self.create_rectangle(filled_w, 0, w, h, fill=p["progress_bg"], outline="")
            return

        # Render individual segment slices
        x_offset = 0.0
        for seg in self.segments:
            seg_w = (seg.total_bytes / self.total_bytes) * w
            seg_pct = (seg.downloaded_bytes / max(1, seg.total_bytes))
            filled_seg_w = seg_w * seg_pct

            seg_x_start = x_offset
            seg_x_end = x_offset + seg_w

            # Background for this segment
            self.create_rectangle(seg_x_start, 0, seg_x_end, h, fill=p["progress_bg"], outline=p["card_bg"], width=1)

            # Filled portion
            if filled_seg_w > 0:
                color = p["completed_fill"] if seg.status == "COMPLETED" else p["progress_fill"] if seg.status == "DOWNLOADING" else p["paused_fill"]
                self.create_rectangle(seg_x_start, 0, seg_x_start + filled_seg_w, h, fill=color, outline="")

            x_offset += seg_w


class DownloadCard(ctk.CTkFrame):
    """Interactive card representing a single download item."""

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
        super().__init__(
            master,
            corner_radius=12,
            fg_color=self.palette["card_bg"],
            border_width=self.palette.get("card_border_width", 1),
            border_color=self.palette["card_border"],
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

        self._build_ui()
        self._setup_context_menu()
        self.update_task_view(task)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Category Icon
        cat_icon = CATEGORY_ICONS.get(self.task.category, "📁")
        self.icon_label = ctk.CTkLabel(
            self,
            text=cat_icon,
            font=ctk.CTkFont(size=26),
            width=50
        )
        self.icon_label.grid(row=0, column=0, rowspan=3, padx=(12, 8), pady=12)

        # Header: Filename & Status Badge
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 2))
        header_frame.grid_columnconfigure(0, weight=1)

        self.filename_label = ctk.CTkLabel(
            header_frame,
            text=self.task.filename or "Initializing...",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.filename_label.grid(row=0, column=0, sticky="w")

        badge_key = STATUS_COLOR_KEYS.get(self.task.status, "badge_downloading")
        self.status_badge = ctk.CTkLabel(
            header_frame,
            text=self.task.status.value,
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6,
            fg_color=self.palette.get(badge_key, "#555"),
            text_color="#ffffff",
            padx=8,
            pady=2
        )
        self.status_badge.grid(row=0, column=1, sticky="e")

        # Multi-Segment Progress Canvas
        self.segment_canvas = SegmentCanvas(self, height=8)
        self.segment_canvas.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(4, 6))

        # Metrics Row: Size / Speed / ETA / Acceleration Info
        metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        metrics_frame.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(0, 10))
        metrics_frame.grid_columnconfigure(0, weight=1)

        self.metrics_label = ctk.CTkLabel(
            metrics_frame,
            text="0 B / 0 B (0%) • 0 B/s • ETA: --:--",
            font=ctk.CTkFont(size=11),
            text_color="#a0a5b5",
            anchor="w"
        )
        self.metrics_label.grid(row=0, column=0, sticky="w")

        # Action Buttons Container
        self.actions_frame = ctk.CTkFrame(metrics_frame, fg_color="transparent")
        self.actions_frame.grid(row=0, column=1, sticky="e")

        # Action Button (Pause / Resume / Retry)
        self.btn_action = ctk.CTkButton(
            self.actions_frame,
            text="Pause",
            width=65,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self._on_action_click
        )

        # Open File Button (Direct launch)
        self.btn_open_file = ctk.CTkButton(
            self.actions_frame,
            text="Open",
            width=55,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2ec4b6",
            hover_color="#249c90",
            text_color="#0d1117",
            command=self._open_file
        )

        # Open Folder Button (Reveals file in system file explorer)
        self.btn_open_folder = ctk.CTkButton(
            self.actions_frame,
            text="Open Folder",
            width=82,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=self._open_folder
        )

        # Details Button
        self.btn_details = ctk.CTkButton(
            self.actions_frame,
            text="Details",
            width=58,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#2b2d35",
            hover_color="#383a45",
            command=lambda: self.on_details(self.task)
        )

        # Cancel/Delete Button
        self.btn_cancel = ctk.CTkButton(
            self.actions_frame,
            text="✕",
            width=28,
            height=26,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3a1c1c",
            hover_color="#5a2222",
            text_color="#ff6b6b",
            command=lambda: self.on_cancel(self.task)
        )

        for btn in (self.btn_action, self.btn_open_file, self.btn_open_folder, self.btn_details, self.btn_cancel):
            MatrixButtonAnimator.attach(btn, app_ref=self)

    def apply_theme(self, palette: Dict[str, Any]) -> None:
        """Applies a new theme palette dynamically to the card and all its subcomponents."""
        self.palette = palette

        for b in (self.btn_details, self.btn_open_folder, self.btn_open_file, self.btn_cancel, self.btn_action):
            MatrixButtonAnimator.reset(b)

        self.configure(
            fg_color=palette["card_bg"],
            border_color=palette["card_border"],
            border_width=palette.get("card_border_width", 1)
        )
        self.filename_label.configure(text_color=palette["text_primary"])
        self.metrics_label.configure(text_color=palette["text_secondary"])

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
        """Configures right-click popup context menu."""
        p = self.palette
        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            bg=p["card_bg"],
            fg=p["text_primary"],
            activebackground=p["accent"],
            activeforeground=p["accent_text"]
        )
        self.context_menu.add_command(label="▶ Resume / Start", command=lambda: self.on_pause_resume(self.task))
        self.context_menu.add_command(label="⏸ Pause", command=lambda: self.on_pause_resume(self.task))
        self.context_menu.add_command(label="🔄 Re-download from start", command=self._handle_redownload)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📂 Open File", command=self._open_file)
        self.context_menu.add_command(label="📁 Open Folder & Reveal", command=self._open_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔗 Copy Download Link", command=self._copy_link)
        self.context_menu.add_command(label="📋 Copy Output Path", command=self._copy_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📊 Task Inspector & Checksum", command=lambda: self.on_details(self.task))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✕ Delete Download", command=lambda: self.on_cancel(self.task))

        self.bind("<Button-3>", self._show_context_menu)
        for child in self.winfo_children():
            child.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event) -> None:
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

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

