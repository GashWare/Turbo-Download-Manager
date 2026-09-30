"""
File checksum calculation and integrity verification module.
"""

import hashlib
import os
from typing import Optional, Callable


def calculate_file_hash(
    file_path: str,
    algorithm: str = "sha256",
    chunk_size: int = 65536,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> str:
    """
    Calculates the cryptographic hash of a file with progress reporting.
    Supported algorithms: md5, sha1, sha256, sha512.
    """
    algo = algorithm.lower().strip()
    if algo == "md5":
        hasher = hashlib.md5()
    elif algo == "sha1":
        hasher = hashlib.sha1()
    elif algo == "sha512":
        hasher = hashlib.sha512()
    else:
        hasher = hashlib.sha256()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    total_size = os.path.getsize(file_path)
    processed = 0

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            processed += len(chunk)
            if progress_callback:
                progress_callback(processed, total_size)

    return hasher.hexdigest()


def verify_file_checksum(file_path: str, expected_hash: str, algorithm: str = "sha256") -> bool:
    """Verifies that a file matches an expected hash."""
    computed = calculate_file_hash(file_path, algorithm=algorithm)
    return computed.lower().strip() == expected_hash.lower().strip()
