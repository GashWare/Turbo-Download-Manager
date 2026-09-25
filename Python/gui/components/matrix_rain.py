"""
Matrix Digital Rain Canvas Animation.
Renders high-quality cascading green digital rain with Katakana glyphs,
luminous leading heads, fading phosphorescent trails, and dynamic columns.
Accelerated via multi-threaded background worker and Pillow sprite blitting for 0% UI lag.
"""

from __future__ import annotations
import random
import threading
import time
import tkinter as tk
from typing import List, Dict, Any, Optional, Tuple
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk

# Authentic Matrix glyph set: Half-width Katakana, Latin, digits, math operators
MATRIX_CHARS = (
    "ｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇﾈﾊﾋﾎﾏﾐﾑﾒﾓﾔﾕﾗﾘﾜ"
    "0123456789"
    "ABCDEFZ"
    ":・.=*+-<>¦｜"
)

TRAIL_RGB_COLORS = [
    (255, 255, 255),  # 0: Leading glowing white head
    (212, 255, 212),  # 1: Very bright green-white
    (0, 255, 65),    # 2: Bright phosphor green
    (0, 224, 56),    # 3: Primary matrix green
    (0, 179, 44),    # 4: Mid green
    (0, 128, 32),    # 5: Dim green
    (0, 82, 20),     # 6: Dark green
    (0, 48, 12),     # 7: Fading tail green
]

BG_COLOR_RGB = (2, 11, 5)


class MatrixRainCanvas(tk.Canvas):
    """Threaded background canvas rendering high-quality Matrix digital rain without UI lag."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("bg", "#020b05")
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)

        self.char_width = 14
        self.char_height = 18

        # Load font & pre-render glyph sprites for lightning-fast memory blitting
        try:
            self._font = ImageFont.truetype("consola.ttf", 13)
        except Exception:
            try:
                self._font = ImageFont.truetype("cour.ttf", 13)
            except Exception:
                self._font = ImageFont.load_default()

        self._glyph_cache: Dict[Tuple[str, int], Image.Image] = {}
        self._init_glyph_cache()

        self._is_running = False
        self._stop_event = threading.Event()
        self._render_thread: Optional[threading.Thread] = None
        self._timer_id: Optional[str] = None

        self._target_w = 800
        self._target_h = 600
        self._shared_image: Optional[Image.Image] = None
        self._lock = threading.Lock()

        self._img_item: Optional[int] = None
        self._current_photo: Optional[ImageTk.PhotoImage] = None

        self.bind("<Configure>", self._on_resize)

    def _init_glyph_cache(self) -> None:
        """Pre-renders all characters in all 8 trail colors into reusable memory sprites."""
        for ch in MATRIX_CHARS:
            for c_idx, col in enumerate(TRAIL_RGB_COLORS):
                im = Image.new("RGB", (self.char_width, self.char_height), BG_COLOR_RGB)
                draw = ImageDraw.Draw(im)
                draw.text((1, 1), ch, fill=col, font=self._font)
                self._glyph_cache[(ch, c_idx)] = im

    def _on_resize(self, event=None) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 10 and h > 10:
            with self._lock:
                self._target_w = w
                self._target_h = h

    def start(self) -> None:
        """Starts the background rendering thread and UI flip loop."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()

        w = max(100, self.winfo_width())
        h = max(100, self.winfo_height())
        with self._lock:
            self._target_w = w
            self._target_h = h

        # Start worker thread
        self._render_thread = threading.Thread(target=self._worker_loop, daemon=True, name="MatrixRainRenderer")
        self._render_thread.start()

        # Start lightweight UI flip loop on main thread
        self._schedule_flip()

    def stop(self) -> None:
        """Stops the worker thread and cleans up canvas image."""
        self._is_running = False
        self._stop_event.set()

        if self._timer_id:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

        if self._render_thread and self._render_thread.is_alive():
            self._render_thread.join(timeout=0.15)
            self._render_thread = None

        self.delete("all")
        self._img_item = None
        self._current_photo = None
        with self._lock:
            self._shared_image = None

    def _worker_loop(self) -> None:
        """Background thread generating Matrix digital rain frames at ~30 FPS."""
        columns: List[Dict[str, Any]] = []
        last_w = 0
        last_h = 0

        while not self._stop_event.is_set():
            t_start = time.perf_counter()

            with self._lock:
                w = max(100, self._target_w)
                h = max(100, self._target_h)

            num_cols = max(5, w // self.char_width)
            max_rows = max(10, h // self.char_height + 4)

            # Re-init columns if dimensions resized significantly
            if abs(w - last_w) > 30 or abs(h - last_h) > 30:
                last_w = w
                last_h = h
                columns = []
                for c in range(num_cols):
                    col_x = c * self.char_width
                    speed = random.choice([1, 1, 2, 2, 3])
                    length = random.randint(10, min(36, max_rows + 5))
                    head_y = random.randint(-max_rows, max_rows)
                    chars = [random.choice(MATRIX_CHARS) for _ in range(length)]
                    columns.append({
                        "x": col_x,
                        "y": head_y,
                        "speed": speed,
                        "length": length,
                        "chars": chars,
                        "tick": 0,
                        "rate": random.choice([1, 1, 2])
                    })

            # Balance columns if width grew
            while len(columns) < num_cols:
                c = len(columns)
                col_x = c * self.char_width
                speed = random.choice([1, 1, 2, 2, 3])
                length = random.randint(10, min(36, max_rows + 5))
                head_y = random.randint(-max_rows, max_rows)
                chars = [random.choice(MATRIX_CHARS) for _ in range(length)]
                columns.append({
                    "x": col_x,
                    "y": head_y,
                    "speed": speed,
                    "length": length,
                    "chars": chars,
                    "tick": 0,
                    "rate": random.choice([1, 1, 2])
                })

            # Create frame buffer
            frame = Image.new("RGB", (w, h), BG_COLOR_RGB)

            for col in columns:
                col["tick"] += 1
                if col["tick"] >= col["rate"]:
                    col["tick"] = 0
                    col["y"] += col["speed"]

                    # Character mutation
                    if random.random() < 0.25:
                        idx = random.randint(0, col["length"] - 1)
                        col["chars"][idx] = random.choice(MATRIX_CHARS)

                    # Reset column trail
                    if col["y"] - col["length"] > max_rows:
                        col["y"] = random.randint(-20, -1)
                        col["speed"] = random.choice([1, 1, 2, 2, 3])
                        col["length"] = random.randint(10, min(36, max_rows + 5))
                        col["chars"] = [random.choice(MATRIX_CHARS) for _ in range(col["length"])]

                head_y = col["y"]
                col_x = col["x"]

                for i in range(col["length"]):
                    char_row = head_y - i
                    if 0 <= char_row <= max_rows + 1:
                        pixel_y = char_row * self.char_height
                        if pixel_y + self.char_height > h:
                            continue

                        # Color index by distance from head
                        if i == 0:
                            c_idx = 0
                        elif i == 1:
                            c_idx = 1
                        elif i < 6:
                            c_idx = 2
                        elif i < 12:
                            c_idx = 3
                        elif i < 18:
                            c_idx = 4
                        elif i < 24:
                            c_idx = 5
                        elif i < 30:
                            c_idx = 6
                        else:
                            c_idx = 7

                        ch = col["chars"][i % len(col["chars"])]
                        sprite = self._glyph_cache.get((ch, c_idx))
                        if sprite:
                            frame.paste(sprite, (col_x, pixel_y))

            # Store completed frame atomically
            with self._lock:
                self._shared_image = frame

            # Target ~30 FPS (33ms per frame)
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.005, 0.033 - elapsed)
            time.sleep(sleep_time)

    def _schedule_flip(self) -> None:
        if not self._is_running:
            return
        self._ui_flip()
        self._timer_id = self.after(33, self._schedule_flip)

    def _ui_flip(self) -> None:
        """Instantaneous main-thread frame presentation."""
        if not self._is_running or not self.winfo_exists():
            return

        frame = None
        with self._lock:
            if self._shared_image is not None:
                frame = self._shared_image

        if frame is None:
            return

        try:
            photo = ImageTk.PhotoImage(frame)
            if self._img_item is None:
                self._img_item = self.create_image(0, 0, image=photo, anchor="nw")
            else:
                self.itemconfig(self._img_item, image=photo)
            self._current_photo = photo
        except Exception:
            pass


class MatrixButtonAnimator:
    """Manages enhanced Matrix cyber glitch, decoder cascade, and phosphor glow hover animations on CTkButtons."""

    GLYPHS = "ｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇ0123456789:*+-<>#%&@$"
    PULSE_BRACKETS = [("[ > ", " < ]"), ("[ » ", " « ]"), ("{ > ", " < }"), ("[ ", " ]")]

    @classmethod
    def attach(cls, btn: ctk.CTkButton, app_ref=None) -> None:
        """Attaches enhanced Matrix hover animations to any CTkButton."""
        if getattr(btn, "_has_matrix_hover", False):
            return
        btn._has_matrix_hover = True
        btn._anim_ids = []
        btn._pulse_idx = 0
        btn._is_hovered = False

        def on_enter(event):
            palette = None
            if app_ref and hasattr(app_ref, "active_palette"):
                palette = app_ref.active_palette
            elif hasattr(btn, "_active_palette"):
                palette = btn._active_palette
            elif hasattr(btn, "palette"):
                palette = btn.palette
            
            if not palette or not palette.get("matrix_rain"):
                btn._is_hovered = False
                return

            btn._is_hovered = True
            cls._cancel(btn)
            raw_text = btn.cget("text")
            # Strip any previous cyber brackets if present
            for l_b, r_b in cls.PULSE_BRACKETS:
                if raw_text.startswith(l_b) and raw_text.endswith(r_b):
                    raw_text = raw_text[len(l_b):-len(r_b)]
            btn._orig_text = raw_text
            btn._orig_border_width = btn.cget("border_width")
            btn._orig_border_color = btn.cget("border_color")
            btn._orig_text_color = btn.cget("text_color")

            # Enhanced Phosphor Glow & Border
            btn.configure(
                border_width=2,
                border_color="#00ff41",
                text_color="#ffffff"
            )

            # High-intensity multi-stage cyber decode
            def frame1():
                if not btn.winfo_exists() or not getattr(btn, "_is_hovered", False):
                    return
                scrambled = "".join(random.choice(cls.GLYPHS) if c.strip() and random.random() < 0.85 else c for c in raw_text)
                btn.configure(text=f"[ ｦ {scrambled} ｱ ]")

            def frame2():
                if not btn.winfo_exists() or not getattr(btn, "_is_hovered", False):
                    return
                scrambled = "".join(random.choice(cls.GLYPHS) if c.strip() and random.random() < 0.50 else c for c in raw_text)
                btn.configure(text=f"[ > {scrambled} < ]")

            def frame3():
                if not btn.winfo_exists() or not getattr(btn, "_is_hovered", False):
                    return
                scrambled = "".join(random.choice(cls.GLYPHS) if c.strip() and random.random() < 0.20 else c for c in raw_text)
                btn.configure(text=f"[ » {scrambled} « ]")

            def frame4():
                if not btn.winfo_exists() or not getattr(btn, "_is_hovered", False):
                    return
                btn.configure(text=f"[ > {raw_text} < ]", text_color="#d4ffd4")
                # Start subtle continuous pulse while hovered
                schedule_pulse()

            def schedule_pulse():
                if not btn.winfo_exists() or not getattr(btn, "_is_hovered", False):
                    return
                btn._pulse_idx = (getattr(btn, "_pulse_idx", 0) + 1) % len(cls.PULSE_BRACKETS)
                l_b, r_b = cls.PULSE_BRACKETS[btn._pulse_idx]
                btn.configure(text=f"{l_b}{raw_text}{r_b}")
                btn._anim_ids.append(btn.after(280, schedule_pulse))

            frame1()
            btn._anim_ids.append(btn.after(30, frame2))
            btn._anim_ids.append(btn.after(65, frame3))
            btn._anim_ids.append(btn.after(100, frame4))

        def on_leave(event):
            if not getattr(btn, "_is_hovered", False):
                return
            btn._is_hovered = False
            cls._cancel(btn)
            if hasattr(btn, "_orig_text") and btn.winfo_exists():
                btn.configure(text=btn._orig_text)
            
            # Check theme for restoring styling
            palette = None
            if app_ref and hasattr(app_ref, "active_palette"):
                palette = app_ref.active_palette
            elif hasattr(btn, "_active_palette"):
                palette = btn._active_palette
            elif hasattr(btn, "palette"):
                palette = btn.palette

            if not btn.winfo_exists():
                return

            if palette and palette.get("matrix_rain"):
                btn.configure(
                    border_width=palette.get("btn_border_width", 1),
                    border_color=palette.get("btn_border_color", "#00ff41"),
                    text_color=getattr(btn, "_orig_text_color", palette.get("btn_text", palette.get("text_primary", "#00ff41")))
                )

        btn.bind("<Enter>", on_enter, add="+")
        btn.bind("<Leave>", on_leave, add="+")

    @classmethod
    def reset(cls, btn: ctk.CTkButton) -> None:
        """Stops any active hover animations and cleans up cached matrix styling."""
        cls._cancel(btn)
        btn._is_hovered = False
        if hasattr(btn, "_orig_text") and btn.winfo_exists():
            raw_text = getattr(btn, "_orig_text", btn.cget("text"))
            for l_b, r_b in cls.PULSE_BRACKETS:
                if raw_text.startswith(l_b) and raw_text.endswith(r_b):
                    raw_text = raw_text[len(l_b):-len(r_b)]
            btn.configure(text=raw_text)
        for attr in ("_orig_text", "_orig_text_color", "_orig_border_width", "_orig_border_color"):
            if hasattr(btn, attr):
                try:
                    delattr(btn, attr)
                except Exception:
                    pass

    @classmethod
    def _cancel(cls, btn: ctk.CTkButton) -> None:
        if hasattr(btn, "_anim_ids"):
            for aid in btn._anim_ids:
                try:
                    btn.after_cancel(aid)
                except Exception:
                    pass
            btn._anim_ids.clear()
