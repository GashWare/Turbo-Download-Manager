"""
Token-bucket bandwidth rate limiter for throttling downloads.
"""

import time
import threading


class RateLimiter:
    """
    Thread-safe Token Bucket Rate Limiter.
    Allows controlling total bandwidth (bytes per second).
    """

    def __init__(self, max_bytes_per_sec: int = 0):
        """
        :param max_bytes_per_sec: Max allowed throughput in bytes/sec. 0 means unlimited.
        """
        self.max_bytes_per_sec = max_bytes_per_sec
        self.lock = threading.Lock()
        self.tokens = float(max_bytes_per_sec) if max_bytes_per_sec > 0 else float("inf")
        self.last_update = time.monotonic()

    def set_limit(self, max_bytes_per_sec: int) -> None:
        """Update speed limit dynamically."""
        with self.lock:
            self.max_bytes_per_sec = max_bytes_per_sec
            if max_bytes_per_sec <= 0:
                self.tokens = float("inf")
            else:
                self.tokens = min(self.tokens, float(max_bytes_per_sec))
            self.last_update = time.monotonic()

    def acquire(self, num_bytes: int) -> None:
        """
        Blocks until enough tokens are available to send/receive `num_bytes`.
        """
        if self.max_bytes_per_sec <= 0:
            return  # Unlimited

        while num_bytes > 0:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now

                # Add new tokens based on elapsed time
                self.tokens = min(
                    float(self.max_bytes_per_sec),
                    self.tokens + elapsed * self.max_bytes_per_sec
                )

                if self.tokens >= num_bytes:
                    self.tokens -= num_bytes
                    return
                elif self.tokens > 0:
                    # Partially consume tokens
                    consumed = int(self.tokens)
                    self.tokens -= consumed
                    num_bytes -= consumed
                    # Calculate sleep for the remainder
                    needed = num_bytes
                    sleep_time = needed / self.max_bytes_per_sec
                else:
                    sleep_time = num_bytes / self.max_bytes_per_sec

            # Sleep outside lock
            if sleep_time > 0:
                time.sleep(min(sleep_time, 0.1))
