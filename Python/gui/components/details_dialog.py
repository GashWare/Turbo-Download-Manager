"""
Task Details Inspector Dialog.
Shows deep metadata, connection chunk breakdown, and file checksum tools.
"""

from __future__ import annotations
import os
import threading
from typing import Optional
import customtkinter as ctk
import pyperclip

from core.models import DownloadTask, DownloadStatus, format_eta
from core.checksum import calculate_file_hash
from gui.themes import get_theme


def format_bytes(size_bytes: float) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


class DetailsDialog(ctk.CTkToplevel):
    """Detailed metadata and segment connection inspector modal."""

    def __init__(self, parent, task: DownloadTask):
        super().__init__(parent)
        self.task = task
        self.palette = parent.active_palette if hasattr(parent, "active_palette") else get_theme("dark")
        self._deactivate_windows_window_header_manipulation = True

        self.title(f"Task Details - {task.filename or task.task_id}")
        self.geometry("700x580")
        self.resizable(True, True)
        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)
        self.focus_force()

        self._build_ui()
        self._refresh_timer()

    def _build_ui(self) -> None:
        p = self.palette
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color=p["toolbar_bg"], corner_radius=0, height=50)
        header.grid(row=0, column=0, sticky="ew")
        lbl_title = ctk.CTkLabel(
            header,
            text=f"📊 Task Inspector: {self.task.filename}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=p["accent"]
        )
        lbl_title.pack(side="left", padx=20, pady=12)

        # Tabview for Overview / Segments / Checksum
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        self.tab_overview = self.tabview.add("General Overview")
        self.tab_segments = self.tabview.add("Active Segments")
        self.tab_checksum = self.tabview.add("Checksum & Integrity")

        self._build_overview_tab()
        self._build_segments_tab()
        self._build_checksum_tab()

        # Bottom Close Button
        btn_close = ctk.CTkButton(
            self,
            text="Close",
            width=100,
            height=32,
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            command=self.destroy
        )
        btn_close.grid(row=2, column=0, pady=(0, 12))

    def _build_overview_tab(self) -> None:
        tab = self.tab_overview
        tab.grid_columnconfigure(1, weight=1)

        rows = [
            ("Task ID:", self.task.task_id),
            ("URL / Magnet:", self.task.url),
            ("Save Location:", self.task.full_output_path),
            ("Status:", self.task.status.value),
            ("Total Size:", format_bytes(self.task.total_bytes)),
            ("Downloaded:", f"{format_bytes(self.task.downloaded_bytes)} ({self.task.progress_pct:.2f}%)"),
            ("Download Speed:", f"{format_bytes(self.task.speed_bytes_per_sec)}/s"),
            ("Upload Speed:", f"{format_bytes(self.task.upload_speed_bytes_per_sec)}/s" if self.task.is_torrent else "N/A"),
            ("Uploaded Total:", format_bytes(self.task.uploaded_bytes) if self.task.is_torrent else "N/A"),
            ("ETA:", format_eta(self.task.eta_seconds) if self.task.eta_seconds is not None else "N/A"),
            ("P2P Swarm:", f"Seeds: {self.task.num_seeds} | Peers: {self.task.num_peers}" if self.task.is_torrent else ("Multi-Segment Threads" if self.task.supports_range else "Single stream")),
            ("Mode:", "🛡️ Leech Only (Upload Disabled)" if (self.task.is_torrent and self.task.leech_only) else ("🧲 P2P Swarm" if self.task.is_torrent else ("Adaptive Media" if self.task.is_media_stream else "Standard Download"))),
            ("Info Hash:", self.task.torrent_info_hash or (self.task.etag or "N/A")),
            ("Category:", self.task.category.value),
        ]

        self.overview_labels = {}
        for idx, (k, v) in enumerate(rows):
            lbl_k = ctk.CTkLabel(tab, text=k, font=ctk.CTkFont(size=12, weight="bold"), text_color="#a0a5b5", anchor="w")
            lbl_k.grid(row=idx, column=0, sticky="w", padx=10, pady=4)

            lbl_v = ctk.CTkLabel(tab, text=str(v), font=ctk.CTkFont(size=12), anchor="w")
            lbl_v.grid(row=idx, column=1, sticky="w", padx=10, pady=4)
            self.overview_labels[k] = lbl_v

    def _build_segments_tab(self) -> None:
        tab = self.tab_segments
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        p = self.palette
        self.scroll_segments = ctk.CTkScrollableFrame(tab, fg_color=p["card_bg"], corner_radius=8)
        self.scroll_segments.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.scroll_segments.grid_columnconfigure(1, weight=1)

        self.segment_widgets = []
        self._update_segments_list()

    def _update_segments_list(self) -> None:
        p = self.palette
        for w in self.scroll_segments.winfo_children():
            w.destroy()

        if self.task.is_torrent:
            torrent_box = ctk.CTkFrame(self.scroll_segments, fg_color=p["btn_bg"], corner_radius=8)
            torrent_box.pack(fill="x", pady=8, padx=8)

            ctk.CTkLabel(
                torrent_box,
                text="🧲 BitTorrent Swarm Engine (libtorrent)",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=p["accent"]
            ).pack(anchor="w", padx=12, pady=(10, 4))

            leech_str = "🛡️ Active (Zero upload / Stops on completion)" if self.task.leech_only else "Inactive (Seeding allowed)"
            seq_str = "Enabled (Linear piece order for streaming)" if self.task.sequential_download else "Standard (Rarest first piece picking)"
            dht_str = "Enabled" if self.task.dht_enabled else "Disabled"

            info_text = (
                f"• Leech Only Mode: {leech_str}\n"
                f"• Sequential Piece Order: {seq_str}\n"
                f"• Distributed Hash Table (DHT): {dht_str}\n"
                f"• Swarm Stats: {self.task.num_seeds} Connected Seeds • {self.task.num_peers} Connected Peers\n"
                f"• Max Peers Limit: {self.task.max_peers}\n"
                f"• Download Speed: {format_bytes(self.task.speed_bytes_per_sec)}/s\n"
                f"• Upload Speed: {format_bytes(self.task.upload_speed_bytes_per_sec)}/s (Total Uploaded: {format_bytes(self.task.uploaded_bytes)})\n"
                f"• Progress: {format_bytes(self.task.downloaded_bytes)} / {format_bytes(self.task.total_bytes)} ({self.task.progress_pct:.2f}%)\n"
                f"• Status: {self.task.status.value}"
            )
            ctk.CTkLabel(
                torrent_box,
                text=info_text,
                font=ctk.CTkFont(size=11),
                text_color=p["text_primary"],
                justify="left"
            ).pack(anchor="w", padx=12, pady=(0, 10))
            return

        if self.task.is_media_stream:
            stream_box = ctk.CTkFrame(self.scroll_segments, fg_color=p["btn_bg"], corner_radius=8)
            stream_box.pack(fill="x", pady=8, padx=8)
            stream_box.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                stream_box,
                text="🎬 Adaptive Media Stream Engine",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=p["accent"]
            ).pack(anchor="w", padx=12, pady=(10, 4))

            info_text = (
                f"• Engine: yt-dlp with Node.js JavaScript Solver\n"
                f"• Stream Protocol: Adaptive DASH / HLS Multi-Fragment Pipeline\n"
                f"• Target Container: MP4 (H.264 Video + AAC Audio Stream Auto-Merge)\n"
                f"• Current Speed: {format_bytes(self.task.speed_bytes_per_sec)}/s\n"
                f"• Transferred: {format_bytes(self.task.downloaded_bytes)} ({self.task.progress_pct:.1f}%)\n"
                f"• Status: {self.task.status.value}"
            )
            ctk.CTkLabel(
                stream_box,
                text=info_text,
                font=ctk.CTkFont(size=11),
                text_color=p["text_primary"],
                justify="left"
            ).pack(anchor="w", padx=12, pady=(0, 10))
            return

        if not self.task.segments:
            lbl = ctk.CTkLabel(
                self.scroll_segments,
                text="Single connection stream download (server does not support multi-range chunks).",
                text_color=p["text_secondary"]
            )
            lbl.pack(pady=20)
            return

        for seg in self.task.segments:
            seg_frame = ctk.CTkFrame(self.scroll_segments, fg_color=p["btn_bg"], corner_radius=6)
            seg_frame.pack(fill="x", pady=4, padx=4)
            seg_frame.grid_columnconfigure(1, weight=1)

            lbl_id = ctk.CTkLabel(seg_frame, text=f"Conn #{seg.segment_id + 1}", font=ctk.CTkFont(weight="bold", size=12), width=70, text_color=p["text_primary"])
            lbl_id.grid(row=0, column=0, padx=8, pady=6)

            prog = ctk.CTkProgressBar(seg_frame, height=10, progress_color=p["progress_fill"])
            prog.set(seg.progress_pct / 100.0)
            prog.grid(row=0, column=1, sticky="ew", padx=8, pady=6)

            info = f"{format_bytes(seg.downloaded_bytes)}/{format_bytes(seg.total_bytes)} ({seg.progress_pct:.0f}%) • [{seg.status}]"
            lbl_info = ctk.CTkLabel(seg_frame, text=info, font=ctk.CTkFont(size=11), text_color=p["text_secondary"])
            lbl_info.grid(row=0, column=2, padx=8, pady=6)

    def _build_checksum_tab(self) -> None:
        p = self.palette
        tab = self.tab_checksum
        tab.grid_columnconfigure(1, weight=1)

        lbl_desc = ctk.CTkLabel(
            tab,
            text="Verify the downloaded file integrity using SHA256 or MD5 hashes.",
            text_color=p["text_secondary"],
            anchor="w"
        )
        lbl_desc.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 15))

        # Checksum calculation UI
        lbl_calc = ctk.CTkLabel(tab, text="Algorithm:", font=ctk.CTkFont(weight="bold"))
        lbl_calc.grid(row=1, column=0, sticky="w", padx=10, pady=5)

        self.combo_hash = ctk.CTkComboBox(tab, values=["SHA256", "MD5", "SHA1"])
        self.combo_hash.set("SHA256")
        self.combo_hash.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        self.btn_compute_hash = ctk.CTkButton(
            tab,
            text="Calculate Hash",
            fg_color=p["accent"],
            hover_color=p["accent_hover"],
            text_color=p.get("accent_text", "#ffffff"),
            command=self._compute_hash
        )
        self.btn_compute_hash.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

        self.entry_computed_hash = ctk.CTkEntry(tab, placeholder_text="Computed hash will appear here...", height=35)
        self.entry_computed_hash.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        self.lbl_hash_match = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_hash_match.grid(row=4, column=0, columnspan=2, padx=10, pady=5)

    def _compute_hash(self) -> None:
        path = self.task.full_output_path
        if not os.path.exists(path):
            self.lbl_hash_match.configure(text="File does not exist yet (download incomplete).", text_color="#e63946")
            return

        algo = self.combo_hash.get().lower()
        self.btn_compute_hash.configure(state="disabled", text="Calculating...")
        
        def worker():
            try:
                res = calculate_file_hash(path, algorithm=algo)
                self.after(0, lambda: self._on_hash_computed(res))
            except Exception as e:
                self.after(0, lambda: self.lbl_hash_match.configure(text=f"Error: {e}", text_color="#e63946"))
            finally:
                self.after(0, lambda: self.btn_compute_hash.configure(state="normal", text="Calculate Hash"))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_hash_computed(self, hash_val: str) -> None:
        self.entry_computed_hash.delete(0, "end")
        self.entry_computed_hash.insert(0, hash_val)
        
        if self.task.expected_checksum:
            if hash_val.lower().strip() == self.task.expected_checksum.lower().strip():
                self.lbl_hash_match.configure(text="✓ Checksum Matches Expected Hash!", text_color="#2ec4b6")
            else:
                self.lbl_hash_match.configure(text="✗ Checksum Mismatch!", text_color="#e63946")
        else:
            self.lbl_hash_match.configure(text="✓ Hash successfully calculated (copied to clipboard)", text_color="#2ec4b6")
            pyperclip.copy(hash_val)

    def _refresh_timer(self) -> None:
        """Periodic UI refresh when task is actively downloading."""
        try:
            if not self.winfo_exists():
                return
            if self.task.status == DownloadStatus.DOWNLOADING:
                # Update overview fields
                if "Downloaded:" in self.overview_labels:
                    self.overview_labels["Downloaded:"].configure(
                        text=f"{format_bytes(self.task.downloaded_bytes)} ({self.task.progress_pct:.2f}%)"
                    )
                if "Current Speed:" in self.overview_labels:
                    self.overview_labels["Current Speed:"].configure(
                        text=f"{format_bytes(self.task.speed_bytes_per_sec)}/s"
                    )
                if "Status:" in self.overview_labels:
                    self.overview_labels["Status:"].configure(text=self.task.status.value)
                if "ETA:" in self.overview_labels:
                    self.overview_labels["ETA:"].configure(
                        text=format_eta(self.task.eta_seconds) if self.task.eta_seconds is not None else "N/A"
                    )
                
                # Update segments tab
                if self.tabview.get() == "Active Segments":
                    self._update_segments_list()

            self.after(500, self._refresh_timer)
        except Exception:
            pass
