"""
Background Clipboard Monitor.
Listens for URL copies to provide seamless quick-download popups/suggestions.
"""

from __future__ import annotations
import re
import time
import threading
from typing import Optional, Callable, Set
import pyperclip

URL_REGEX = re.compile(
    r"^(?:http|https)://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$", re.IGNORECASE
)


class ClipboardMonitor:
    """Monitors system clipboard for downloadable URLs in a background thread."""

    def __init__(self, on_url_detected: Callable[[str], None], poll_interval: float = 0.8):
        self.on_url_detected = on_url_detected
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._seen_urls: Set[str] = set()
        self._last_clip_content = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ClipboardMonitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _loop(self) -> None:
        try:
            self._last_clip_content = pyperclip.paste() or ""
        except Exception:
            pass

        while not self._stop_event.is_set():
            try:
                content = pyperclip.paste()
                if content and content != self._last_clip_content:
                    self._last_clip_content = content
                    cleaned = content.strip()
                    if URL_REGEX.match(cleaned) and cleaned not in self._seen_urls:
                        self._seen_urls.add(cleaned)
                        self.on_url_detected(cleaned)
            except Exception:
                pass

            time.sleep(self.poll_interval)
