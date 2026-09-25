"""
New Download Modal Dialog.
Provides URL inspection, filename detection, connection thread tuning,
folder selection, and checksum configuration with high-DPI responsive layout.
"""

from __future__ import annotations
import os
import threading
from typing import Optional, Callable
import customtkinter as ctk
from tkinter import filedialog
import pyperclip

from core.prober import probe_url, ProbeResult, is_likely_media_streaming_url, is_likely_torrent_url
from core.models import DownloadCategory, DownloadSettings
from gui.themes import get_theme


def format_bytes(size_bytes: float) -> str:
    if size_bytes <= 0:
        return "Unknown size"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


class AddDownloadDialog(ctk.CTkToplevel):
    """Modal dialog for creating and configuring new download tasks."""

    VIDEO_QUALITIES = [
        "Best Available (Auto)",
        "2160p (4K UHD)",
        "1440p (2K QHD)",
        "1080p (Full HD)",
        "720p (HD)",
        "480p (SD)",
        "360p (Fast)"
    ]

    VIDEO_FORMATS = [
        "MP4 (Universal)",
        "MKV (Matroska)",
        "WEBM (Web)"
    ]

    AUDIO_FORMATS = [
        "MP3 (High Quality 320k)",
        "M4A (AAC Audio)",
        "AAC",
        "WAV",
        "FLAC",
        "OPUS"
    ]

    def __init__(
        self,
        parent,
        settings: DownloadSettings,
        on_add: Callable[[dict], None],
        initial_url: str = ""
    ):
        super().__init__(parent)
        self.settings = settings
        self.on_add = on_add
        self.initial_url = initial_url
        self.probe_result: Optional[ProbeResult] = None
        self.palette = get_theme(settings.theme)
        self._deactivate_windows_window_header_manipulation = True

        self.title("Add New Download")
        self.geometry("680x700")
        self.minsize(600, 600)
        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 680) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 700) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()

        # If initial URL provided or clipboard has URL, populate
        if initial_url:
            self.entry_url.insert(0, initial_url)
            self._start_probe(initial_url)
        else:
            self._check_clipboard()

    def _build_ui(self) -> None:
        p = self.palette

        # 1. TOP TITLE BANNER (Always at the top)
        title_frame = ctk.CTkFrame(self, fg_color=p["toolbar_bg"], corner_radius=0, height=50)
        title_frame.pack(side="top", fill="x")

        title_label = ctk.CTkLabel(
            title_frame,
            text="⚡ Add New Download",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=p["accent"]
        )
        title_label.pack(side="left", padx=20, pady=12)

        # 2. BOTTOM ACTION BUTTONS (Always anchored to the bottom)
        btn_frame = ctk.CTkFrame(self, fg_color=p["toolbar_bg"], corner_radius=0, height=60)
        btn_frame.pack(side="bottom", fill="x")

        self.btn_start = ctk.CTkButton(
            btn_frame,
            text="⚡ Download Now",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=p["accent"],
            hover_color=p["accent_hover"],
            text_color=p.get("accent_text", "#ffffff"),
            height=38,
            width=140,
            command=lambda: self._submit(auto_start=True)
        )
        self.btn_start.pack(side="right", padx=(10, 20), pady=12)

        self.btn_queue = ctk.CTkButton(
            btn_frame,
            text="Add to Queue (Paused)",
            font=ctk.CTkFont(size=13),
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            height=38,
            command=lambda: self._submit(auto_start=False)
        )
        self.btn_queue.pack(side="right", padx=10, pady=12)

        self.btn_cancel_dlg = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=p["btn_hover"],
            text_color=p["text_secondary"],
            height=38,
            width=80,
            command=self.destroy
        )
        self.btn_cancel_dlg.pack(side="left", padx=20, pady=12)

        # 3. CENTER SCROLLABLE/EXPANDING CONTENT FORM
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(side="top", fill="both", expand=True, padx=20, pady=12)
        form_frame.grid_columnconfigure(0, weight=1)

        # Row 1: URL / Magnet / Torrent Input
        lbl_url = ctk.CTkLabel(form_frame, text="Download URL, Magnet Link, or .torrent:", font=ctk.CTkFont(weight="bold"))
        lbl_url.pack(anchor="w", pady=(0, 2))

        url_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        url_row.pack(fill="x", pady=(0, 6))

        self.entry_url = ctk.CTkEntry(url_row, placeholder_text="https://example.com/file.zip or magnet:?xt=urn:btih:...", height=35)
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_url.bind("<KeyRelease>", self._on_url_typed)

        self.btn_open_torrent = ctk.CTkButton(
            url_row,
            text="📁 .torrent",
            width=70,
            height=35,
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            command=self._browse_torrent_file
        )
        self.btn_open_torrent.pack(side="left", padx=(0, 6))

        self.btn_probe = ctk.CTkButton(
            url_row,
            text="Probe",
            width=70,
            height=35,
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            command=lambda: self._start_probe(self.entry_url.get().strip())
        )
        self.btn_probe.pack(side="right")

        # Probe status badge & detection info
        self.lbl_probe_status = ctk.CTkLabel(
            form_frame,
            text="Enter a URL, Magnet URI, or choose a .torrent file to inspect...",
            font=ctk.CTkFont(size=11),
            text_color="#90a4ae",
            anchor="w"
        )
        self.lbl_probe_status.pack(anchor="w", pady=(0, 8))

        # Dynamic YouTube / Media Streaming Configuration Card
        self.media_config_frame = ctk.CTkFrame(form_frame, fg_color=p["card_bg"], corner_radius=8)
        self._build_media_config_ui()
        self._media_visible = False

        # Dynamic BitTorrent / P2P Configuration Card
        self.torrent_config_frame = ctk.CTkFrame(form_frame, fg_color=p["card_bg"], corner_radius=8)
        self._build_torrent_config_ui()
        self._torrent_visible = False

        # Row 2: Filename
        lbl_fname = ctk.CTkLabel(form_frame, text="File Name:", font=ctk.CTkFont(weight="bold"))
        lbl_fname.pack(anchor="w", pady=(0, 2))

        self.entry_filename = ctk.CTkEntry(form_frame, placeholder_text="filename.ext", height=32)
        self.entry_filename.pack(fill="x", pady=(0, 8))

        # Row 3: Save Path
        lbl_path = ctk.CTkLabel(form_frame, text="Save Folder:", font=ctk.CTkFont(weight="bold"))
        lbl_path.pack(anchor="w", pady=(0, 2))

        path_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        path_row.pack(fill="x", pady=(0, 8))

        self.entry_path = ctk.CTkEntry(path_row, height=32)
        self.entry_path.insert(0, self.settings.default_save_dir)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(
            path_row,
            text="Browse...",
            width=80,
            height=32,
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            command=self._browse_folder
        )
        btn_browse.pack(side="right")

        # Row 4: Connections & Checksum Settings Box
        opt_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        opt_frame.pack(fill="x", pady=(2, 0))
        opt_frame.grid_columnconfigure(0, weight=1)
        opt_frame.grid_columnconfigure(1, weight=1)

        # Connections Slider Box
        conn_box = ctk.CTkFrame(opt_frame, fg_color=p["card_bg"], corner_radius=8)
        conn_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=2)

        self.lbl_conns = ctk.CTkLabel(
            conn_box,
            text=f"Connections: {self.settings.default_connections_per_task} threads",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_conns.pack(anchor="w", padx=10, pady=(8, 0))

        self.slider_conns = ctk.CTkSlider(
            conn_box,
            from_=1,
            to=32,
            number_of_steps=31,
            command=self._on_conns_changed
        )
        self.slider_conns.set(self.settings.default_connections_per_task)
        self.slider_conns.pack(fill="x", padx=10, pady=(4, 8))

        # Checksum Box
        hash_box = ctk.CTkFrame(opt_frame, fg_color=p["card_bg"], corner_radius=8)
        hash_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=2)

        lbl_hash = ctk.CTkLabel(hash_box, text="Checksum (Optional):", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_hash.pack(anchor="w", padx=10, pady=(8, 0))

        hash_inputs = ctk.CTkFrame(hash_box, fg_color="transparent")
        hash_inputs.pack(fill="x", padx=10, pady=(4, 8))

        self.combo_algo = ctk.CTkComboBox(hash_inputs, values=["SHA256", "MD5", "SHA1"], width=90, height=26)
        self.combo_algo.set("SHA256")
        self.combo_algo.pack(side="left", padx=(0, 6))

        self.entry_hash = ctk.CTkEntry(hash_inputs, placeholder_text="Expected Hash", height=26)
        self.entry_hash.pack(side="left", fill="x", expand=True)

    def _build_media_config_ui(self) -> None:
        p = self.palette

        # Header with icon and info
        top_media_row = ctk.CTkFrame(self.media_config_frame, fg_color="transparent")
        top_media_row.pack(fill="x", padx=12, pady=(10, 6))

        self.lbl_media_title = ctk.CTkLabel(
            top_media_row,
            text="🎬 YouTube & Media Stream Options",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=p["accent"]
        )
        self.lbl_media_title.pack(side="left")

        # Mode Selector: Video + Audio vs Audio Only
        self.seg_media_mode = ctk.CTkSegmentedButton(
            self.media_config_frame,
            values=["🎬 Video + Audio", "🎵 Audio Only"],
            command=self._on_media_mode_changed,
            height=28
        )
        self.seg_media_mode.set("🎬 Video + Audio")
        self.seg_media_mode.pack(fill="x", padx=12, pady=(0, 8))

        # Media Quality & Format Dropdowns Grid
        self.media_dropdown_frame = ctk.CTkFrame(self.media_config_frame, fg_color="transparent")
        self.media_dropdown_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.media_dropdown_frame.grid_columnconfigure(0, weight=1)
        self.media_dropdown_frame.grid_columnconfigure(1, weight=1)

        # Video Quality Column
        self.lbl_quality = ctk.CTkLabel(
            self.media_dropdown_frame,
            text="Video Quality:",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_quality.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 2))

        self.combo_quality = ctk.CTkComboBox(
            self.media_dropdown_frame,
            values=self.VIDEO_QUALITIES,
            height=28
        )
        self.combo_quality.set("Best Available (Auto)")
        self.combo_quality.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        # Output Format Column
        self.lbl_format = ctk.CTkLabel(
            self.media_dropdown_frame,
            text="Output Format:",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_format.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=(0, 2))

        self.combo_format = ctk.CTkComboBox(
            self.media_dropdown_frame,
            values=self.VIDEO_FORMATS,
            height=28,
            command=self._on_format_changed
        )
        self.combo_format.set("MP4 (Universal)")
        self.combo_format.grid(row=1, column=1, sticky="ew", padx=(6, 0))

    def _build_torrent_config_ui(self) -> None:
        p = self.palette

        # Header
        top_torrent_row = ctk.CTkFrame(self.torrent_config_frame, fg_color="transparent")
        top_torrent_row.pack(fill="x", padx=12, pady=(10, 6))

        lbl_torrent_title = ctk.CTkLabel(
            top_torrent_row,
            text="🧲 BitTorrent & P2P Options",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=p["accent"]
        )
        lbl_torrent_title.pack(side="left")

        # Row 1: Leech Only and Sequential Download Checkboxes
        chk_row1 = ctk.CTkFrame(self.torrent_config_frame, fg_color="transparent")
        chk_row1.pack(fill="x", padx=12, pady=(0, 6))

        self.chk_leech_only = ctk.CTkCheckBox(
            chk_row1,
            text="🛡️ Leech Only (Zero upload / Stop on complete)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=p["text_primary"],
            command=self._on_leech_only_toggled
        )
        self.chk_leech_only.select()  # Checked by default as requested
        self.chk_leech_only.pack(side="left", padx=(0, 16))

        self.chk_sequential = ctk.CTkCheckBox(
            chk_row1,
            text="🎬 Sequential Download (Stream piece order)",
            font=ctk.CTkFont(size=12),
            text_color=p["text_primary"]
        )
        self.chk_sequential.pack(side="left")

        # Row 2: DHT Checkbox & Max Peers
        row2 = ctk.CTkFrame(self.torrent_config_frame, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 6))

        self.chk_dht = ctk.CTkCheckBox(
            row2,
            text="🌐 Enable DHT, PeX & LSD (Trackerless)",
            font=ctk.CTkFont(size=12),
            text_color=p["text_primary"]
        )
        self.chk_dht.select()
        self.chk_dht.pack(side="left", padx=(0, 20))

        lbl_peers = ctk.CTkLabel(row2, text="Max Peers:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_peers.pack(side="left", padx=(0, 6))

        self.entry_max_peers = ctk.CTkEntry(row2, width=65, height=26)
        self.entry_max_peers.insert(0, str(getattr(self.settings, "torrent_max_peers_default", 100)))
        self.entry_max_peers.pack(side="left")

        # Row 3: Bandwidth Limits (Download & Upload Limits)
        limits_row = ctk.CTkFrame(self.torrent_config_frame, fg_color="transparent")
        limits_row.pack(fill="x", padx=12, pady=(0, 10))
        limits_row.grid_columnconfigure(0, weight=1)
        limits_row.grid_columnconfigure(1, weight=1)

        # Download Limit
        lbl_dl_limit = ctk.CTkLabel(limits_row, text="Download Limit (KB/s, 0=unlimited):", font=ctk.CTkFont(size=11))
        lbl_dl_limit.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 2))

        self.entry_dl_limit = ctk.CTkEntry(limits_row, height=26)
        self.entry_dl_limit.insert(0, "0")
        self.entry_dl_limit.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        # Upload Limit
        self.lbl_up_limit = ctk.CTkLabel(limits_row, text="Upload Limit (Disabled by Leech Only):", font=ctk.CTkFont(size=11), text_color="#90a4ae")
        self.lbl_up_limit.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=(0, 2))

        self.entry_up_limit = ctk.CTkEntry(limits_row, height=26, state="disabled")
        self.entry_up_limit.insert(0, "0")
        self.entry_up_limit.grid(row=1, column=1, sticky="ew", padx=(6, 0))

    def _set_media_options_visible(self, visible: bool) -> None:
        if visible and not self._media_visible:
            if self._torrent_visible:
                self._set_torrent_options_visible(False)
            self.media_config_frame.pack(after=self.lbl_probe_status, fill="x", pady=(0, 10))
            self._media_visible = True
        elif not visible and self._media_visible:
            self.media_config_frame.pack_forget()
            self._media_visible = False

    def _set_torrent_options_visible(self, visible: bool) -> None:
        if visible and not self._torrent_visible:
            if self._media_visible:
                self._set_media_options_visible(False)
            self.torrent_config_frame.pack(after=self.lbl_probe_status, fill="x", pady=(0, 10))
            self._torrent_visible = True
        elif not visible and self._torrent_visible:
            self.torrent_config_frame.pack_forget()
            self._torrent_visible = False

    def _on_leech_only_toggled(self) -> None:
        if self.chk_leech_only.get() == 1:
            self.lbl_up_limit.configure(text="Upload Limit (Disabled by Leech Only):", text_color="#90a4ae")
            self.entry_up_limit.configure(state="normal")
            self.entry_up_limit.delete(0, "end")
            self.entry_up_limit.insert(0, "0")
            self.entry_up_limit.configure(state="disabled")
        else:
            self.lbl_up_limit.configure(text="Upload Limit (KB/s, 0=unlimited):", text_color=self.palette["text_primary"])
            self.entry_up_limit.configure(state="normal")

    def _browse_torrent_file(self) -> None:
        fpath = filedialog.askopenfilename(
            title="Select .torrent File",
            filetypes=[("BitTorrent Files", "*.torrent"), ("All Files", "*.*")]
        )
        if fpath:
            self.entry_url.delete(0, "end")
            self.entry_url.insert(0, fpath)
            self._set_torrent_options_visible(True)
            self._start_probe(fpath)

    def _on_media_mode_changed(self, mode: str) -> None:
        if mode == "🎵 Audio Only":
            self.lbl_quality.configure(text="Audio Quality:", text_color="#90a4ae")
            self.combo_quality.configure(state="disabled")
            self.combo_format.configure(values=self.AUDIO_FORMATS)
            self.combo_format.set("MP3 (High Quality 320k)")
            self._update_filename_extension("mp3")
        else:
            self.lbl_quality.configure(text="Video Quality:", text_color=self.palette["text_primary"])
            self.combo_quality.configure(state="normal")
            self.combo_format.configure(values=self.VIDEO_FORMATS)
            self.combo_format.set("MP4 (Universal)")
            self._update_filename_extension("mp4")

    def _on_format_changed(self, choice: str) -> None:
        choice_clean = choice.lower()
        for ext in ("mp4", "mkv", "webm", "mp3", "m4a", "aac", "wav", "flac", "opus"):
            if ext in choice_clean:
                self._update_filename_extension(ext)
                break

    def _update_filename_extension(self, new_ext: str) -> None:
        curr_name = self.entry_filename.get().strip()
        if not curr_name:
            return
        base, _ = os.path.splitext(curr_name)
        if base:
            self.entry_filename.delete(0, "end")
            self.entry_filename.insert(0, f"{base}.{new_ext}")

    def _check_clipboard(self) -> None:
        try:
            clip = pyperclip.paste()
            if clip and (clip.startswith(("http://", "https://", "magnet:")) or clip.endswith(".torrent")):
                self.entry_url.insert(0, clip.strip())
                self._start_probe(clip.strip())
        except Exception:
            pass

    def _on_url_typed(self, event=None) -> None:
        url = self.entry_url.get().strip()
        if is_likely_torrent_url(url):
            self._set_torrent_options_visible(True)
            self.lbl_probe_status.configure(
                text="🧲 BitTorrent stream / Magnet link detected (Leech Only & P2P Acceleration available)",
                text_color="#00b4d8"
            )
        elif is_likely_media_streaming_url(url):
            self._set_media_options_visible(True)
            url_lower = url.lower()
            if any(d in url_lower for d in ("facebook.com", "fb.watch", "fb.com", "fb.gg")):
                platform_label = "Facebook Video / Reel"
            elif any(d in url_lower for d in ("instagram.com", "threads.net")):
                platform_label = "Instagram Reel / Video"
            elif any(d in url_lower for d in ("tiktok.com",)):
                platform_label = "TikTok Video"
            elif any(d in url_lower for d in ("youtube.com", "youtu.be")):
                platform_label = "YouTube Video / Short"
            else:
                platform_label = "Streaming Video / Audio"

            if hasattr(self, "lbl_media_title"):
                self.lbl_media_title.configure(text=f"🎬 {platform_label} Options")

            self.lbl_probe_status.configure(
                text=f"✨ Optimal {platform_label} Turbo settings applied (16 Parallel Fragment Workers, Direct MP4/MP3)",
                text_color="#00b4d8"
            )
            if hasattr(self, "slider_conns"):
                self.slider_conns.set(16)
                self.lbl_conns.configure(text=f"Connections: 16 threads (Turbo {platform_label} Acceleration)")
        else:
            if not (self.probe_result and (self.probe_result.is_media_stream or self.probe_result.is_torrent)):
                self._set_media_options_visible(False)
                self._set_torrent_options_visible(False)

        if len(url) > 5:
            self._start_probe(url)

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.entry_path.get())
        if folder:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, folder)

    def _on_conns_changed(self, val) -> None:
        int_val = int(val)
        self.lbl_conns.configure(text=f"Connections: {int_val} threads")

    def _start_probe(self, url: str) -> None:
        if is_likely_torrent_url(url):
            self._set_torrent_options_visible(True)
            self.lbl_probe_status.configure(
                text="🔍 Probing BitTorrent metadata & swarm...",
                text_color="#f39c12"
            )
        elif is_likely_media_streaming_url(url):
            self._set_media_options_visible(True)
            url_lower = url.lower()
            plat = "Facebook Reel/Video" if any(d in url_lower for d in ("facebook.com", "fb.watch", "fb.com")) else "media stream"
            self.lbl_probe_status.configure(
                text=f"🔍 Probing {plat} metadata & formats...",
                text_color="#f39c12"
            )
        else:
            self.lbl_probe_status.configure(
                text="🔍 Probing URL and server capabilities...",
                text_color="#f39c12"
            )
        threading.Thread(target=self._probe_thread, args=(url,), daemon=True).start()

    def _probe_thread(self, url: str) -> None:
        try:
            res = probe_url(url)
            self.probe_result = res
            self.after(0, self._apply_probe, res)
        except Exception:
            pass

    def _apply_probe(self, res: ProbeResult) -> None:
        if not self.entry_filename.get():
            self.entry_filename.insert(0, res.filename)

        if res.is_torrent:
            self._set_torrent_options_visible(True)
            size_txt = f" • Size: {format_bytes(res.total_bytes)}" if res.total_bytes > 0 else ""
            self.lbl_probe_status.configure(
                text=f"🧲 BitTorrent Swarm Ready{size_txt} • Leech Only Active",
                text_color="#2ec4b6"
            )
            return

        if res.is_media_stream:
            self._set_media_options_visible(True)
            url_lower = res.url.lower()
            if any(d in url_lower for d in ("facebook.com", "fb.watch", "fb.com", "fb.gg")):
                platform_label = "Facebook Video / Reel"
            elif any(d in url_lower for d in ("instagram.com", "threads.net")):
                platform_label = "Instagram Reel / Video"
            elif any(d in url_lower for d in ("tiktok.com",)):
                platform_label = "TikTok Video"
            elif any(d in url_lower for d in ("youtube.com", "youtu.be")):
                platform_label = "YouTube Video / Short"
            else:
                platform_label = "Streaming Media"

            if hasattr(self, "lbl_media_title"):
                self.lbl_media_title.configure(text=f"🎬 {platform_label} Options")

            size_txt = f" • Estimated Size: {format_bytes(res.total_bytes)}" if res.total_bytes > 0 else ""
            self.lbl_probe_status.configure(
                text=f"✨ {platform_label} Ready{size_txt} (Turbo Acceleration Active)",
                text_color="#2ec4b6"
            )
            if hasattr(self, "slider_conns"):
                self.slider_conns.set(16)
                self.lbl_conns.configure(text=f"Connections: 16 threads (Turbo {platform_label} Acceleration)")
            return

        range_text = "⚡ Multipart Acceleration Enabled" if res.supports_range else "Single Stream (Range not supported)"
        size_text = format_bytes(res.total_bytes)

        status_info = f"✓ Size: {size_text} • {range_text}"
        self.lbl_probe_status.configure(
            text=status_info,
            text_color="#2ec4b6" if res.supports_range else "#f39c12"
        )

    def _submit(self, auto_start: bool = True) -> None:
        url = self.entry_url.get().strip()
        if not url:
            self.lbl_probe_status.configure(text="Please enter a valid URL, Magnet link, or .torrent file", text_color="#e63946")
            return

        filename = self.entry_filename.get().strip()
        save_path = self.entry_path.get().strip() or self.settings.default_save_dir
        conns = int(self.slider_conns.get()) if hasattr(self, "slider_conns") else self.settings.default_connections_per_task
        expected_hash = self.entry_hash.get().strip() if hasattr(self, "entry_hash") else None
        if not expected_hash:
            expected_hash = None
        algo = self.combo_algo.get().lower() if (expected_hash and hasattr(self, "combo_algo")) else None

        # Media options extraction
        audio_only = False
        media_quality = "best"
        media_format = "mp4"

        if self._media_visible:
            mode_val = self.seg_media_mode.get()
            audio_only = (mode_val == "🎵 Audio Only")
            quality_val = self.combo_quality.get()
            if "2160p" in quality_val:
                media_quality = "2160p"
            elif "1440p" in quality_val:
                media_quality = "1440p"
            elif "1080p" in quality_val:
                media_quality = "1080p"
            elif "720p" in quality_val:
                media_quality = "720p"
            elif "480p" in quality_val:
                media_quality = "480p"
            elif "360p" in quality_val:
                media_quality = "360p"
            else:
                media_quality = "best"

            format_val = self.combo_format.get().lower()
            for candidate in ("mp4", "mkv", "webm", "mp3", "m4a", "aac", "wav", "flac", "opus"):
                if candidate in format_val:
                    media_format = candidate
                    break

        # Torrent options extraction
        is_torrent = self._torrent_visible or (self.probe_result and self.probe_result.is_torrent) or is_likely_torrent_url(url)
        leech_only = True
        sequential_download = False
        max_peers = 100
        download_limit_kbps = 0
        upload_limit_kbps = 0
        dht_enabled = True

        if self._torrent_visible:
            leech_only = bool(self.chk_leech_only.get())
            sequential_download = bool(self.chk_sequential.get())
            dht_enabled = bool(self.chk_dht.get())
            try:
                max_peers = int(self.entry_max_peers.get() or 100)
            except Exception:
                max_peers = 100
            try:
                download_limit_kbps = int(self.entry_dl_limit.get() or 0)
            except Exception:
                download_limit_kbps = 0
            if not leech_only:
                try:
                    upload_limit_kbps = int(self.entry_up_limit.get() or 0)
                except Exception:
                    upload_limit_kbps = 0
            else:
                upload_limit_kbps = 0

        data = {
            "url": url,
            "filename": filename or (self.probe_result.filename if self.probe_result else ""),
            "save_path": save_path,
            "num_connections": conns,
            "expected_checksum": expected_hash,
            "checksum_algo": algo,
            "auto_start": auto_start,
            "total_bytes": self.probe_result.total_bytes if self.probe_result else None,
            "supports_range": self.probe_result.supports_range if self.probe_result else None,
            "etag": self.probe_result.etag if self.probe_result else None,
            "last_modified": self.probe_result.last_modified if self.probe_result else None,
            "category": self.probe_result.category if self.probe_result else None,
            "is_media_stream": self.probe_result.is_media_stream if self.probe_result else None,
            "audio_only": audio_only,
            "media_quality": media_quality,
            "media_format": media_format,
            "is_torrent": is_torrent,
            "leech_only": leech_only,
            "sequential_download": sequential_download,
            "max_peers": max_peers,
            "download_limit_kbps": download_limit_kbps,
            "upload_limit_kbps": upload_limit_kbps,
            "dht_enabled": dht_enabled,
            "torrent_info_hash": self.probe_result.torrent_info_hash if self.probe_result else None,
        }

        try:
            self.on_add(data)
            self.destroy()
        except Exception as e:
            self.lbl_probe_status.configure(text=f"Error adding download: {e}", text_color="#e63946")

