"""
Batch Add Downloads Modal Dialog.
Enables pasting multiple download links and bulk adding them to the download queue.
"""

from __future__ import annotations
import os
from typing import List, Callable
import customtkinter as ctk
from tkinter import filedialog
import pyperclip

from core.models import DownloadSettings
from gui.themes import get_theme


class BatchAddDialog(ctk.CTkToplevel):
    """Modal dialog for pasting multiple URLs and bulk queueing."""

    def __init__(self, parent, settings: DownloadSettings, on_batch_add: Callable[[dict], None]):
        super().__init__(parent)
        self.settings = settings
        self.on_batch_add = on_batch_add
        self.palette = get_theme(settings.theme)
        self._deactivate_windows_window_header_manipulation = True

        self.title("Batch Add URLs")
        self.geometry("640x520")
        self.resizable(False, False)
        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 640) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 520) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()

    def _build_ui(self) -> None:
        p = self.palette
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color=p["toolbar_bg"], corner_radius=0, height=55)
        header.grid(row=0, column=0, sticky="ew")
        lbl_title = ctk.CTkLabel(
            header,
            text="📋 Batch Add Downloads",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=p["accent"]
        )
        lbl_title.pack(side="left", padx=20, pady=12)

        # Form Content
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=1, column=0, sticky="nsew", padx=20, pady=12)
        form.grid_columnconfigure(1, weight=1)

        # URLs text area
        lbl_urls = ctk.CTkLabel(form, text="Enter download URLs (one per line):", font=ctk.CTkFont(weight="bold"))
        lbl_urls.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.textbox_urls = ctk.CTkTextbox(form, height=180, font=ctk.CTkFont(family="Consolas", size=11))
        self.textbox_urls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Paste from clipboard button
        btn_paste = ctk.CTkButton(
            form,
            text="Paste Clipboard Content",
            width=160,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            command=self._paste_clipboard
        )
        btn_paste.grid(row=2, column=0, sticky="w", pady=(0, 10))

        # Save Folder
        lbl_path = ctk.CTkLabel(form, text="Save Folder:", font=ctk.CTkFont(weight="bold"))
        lbl_path.grid(row=3, column=0, sticky="w", pady=(0, 4))

        path_row = ctk.CTkFrame(form, fg_color="transparent")
        path_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        path_row.grid_columnconfigure(0, weight=1)

        self.entry_path = ctk.CTkEntry(path_row, height=32)
        self.entry_path.insert(0, self.settings.default_save_dir)
        self.entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 8))

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
        btn_browse.grid(row=0, column=1)

        # Connections slider
        lbl_conn = ctk.CTkLabel(form, text="Connections per Download:", font=ctk.CTkFont(weight="bold"))
        lbl_conn.grid(row=5, column=0, sticky="w", pady=(0, 4))

        conn_row = ctk.CTkFrame(form, fg_color="transparent")
        conn_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        conn_row.grid_columnconfigure(0, weight=1)

        self.slider_conns = ctk.CTkSlider(conn_row, from_=1, to=32, number_of_steps=31, command=self._on_conns_changed)
        self.slider_conns.set(self.settings.default_connections_per_task)
        self.slider_conns.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.lbl_conns = ctk.CTkLabel(conn_row, text=f"{self.settings.default_connections_per_task} threads", width=80)
        self.lbl_conns.grid(row=0, column=1, sticky="w")

        # Bottom Buttons
        btn_frame = ctk.CTkFrame(self, fg_color=p["toolbar_bg"], corner_radius=0, height=50)
        btn_frame.grid(row=2, column=0, sticky="ew")

        btn_start_all = ctk.CTkButton(
            btn_frame,
            text="⚡ Download All",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=p["accent"],
            hover_color=p["accent_hover"],
            text_color=p.get("accent_text", "#ffffff"),
            height=36,
            command=lambda: self._submit(auto_start=True)
        )
        btn_start_all.pack(side="right", padx=20, pady=10)

        btn_queue_all = ctk.CTkButton(
            btn_frame,
            text="Add Paused",
            height=36,
            fg_color=p["btn_bg"],
            hover_color=p["btn_hover"],
            text_color=p["btn_text"],
            command=lambda: self._submit(auto_start=False)
        )
        btn_queue_all.pack(side="right", padx=10, pady=10)

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            height=36,
            fg_color="transparent",
            hover_color=p["btn_hover"],
            text_color=p["text_secondary"],
            command=self.destroy
        )
        btn_cancel.pack(side="left", padx=20, pady=10)

    def _paste_clipboard(self) -> None:
        try:
            content = pyperclip.paste()
            if content:
                self.textbox_urls.insert("end", content.strip() + "\n")
        except Exception:
            pass

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.entry_path.get())
        if folder:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, folder)

    def _on_conns_changed(self, val) -> None:
        self.lbl_conns.configure(text=f"{int(val)} threads")

    def _submit(self, auto_start: bool = True) -> None:
        raw_text = self.textbox_urls.get("1.0", "end")
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        valid_urls = [u for u in lines if u.startswith(("http://", "https://"))]

        if not valid_urls:
            return

        data = {
            "urls": valid_urls,
            "save_path": self.entry_path.get().strip() or self.settings.default_save_dir,
            "num_connections": int(self.slider_conns.get()),
            "auto_start": auto_start
        }
        self.on_batch_add(data)
        self.destroy()
