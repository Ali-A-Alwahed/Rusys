# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Checksum / hashing utilities for Rusys."""
from __future__ import annotations

import hashlib
from typing import Optional

# Algorithms we expose in the UI, mirroring Rufus' MD5/SHA-1/SHA-256/SHA-512.
SUPPORTED_ALGOS = ("md5", "sha1", "sha256", "sha512")


def _new(algo: str) -> "hashlib._Hash":
    algo = algo.lower()
    if algo not in SUPPORTED_ALGOS:
        raise ValueError(f"Unsupported checksum algorithm: {algo}")
    return hashlib.new(algo)


def hash_file(
    path: str,
    algo: str = "sha256",
    chunk_size: int = 1 << 20,
    progress_cb=None,
    max_bytes: Optional[int] = None,
) -> str:
    """Return the hex digest of *path* using *algo*.

    If *progress_cb* is provided it is called with (bytes_read, total_bytes)
    where total_bytes may be None if the size is unknown.

    If *max_bytes* is provided, only the first *max_bytes* of the file are
    hashed.  This is essential when verifying a block device that is larger
    than the source image — the trailing bytes (usually zeros) would otherwise
    cause a digest mismatch.
    """
    import os

    h = _new(algo)
    total = None
    try:
        total = os.path.getsize(path)
    except OSError:
        total = None
    # When max_bytes is set, cap the reported total so progress bars are accurate
    if max_bytes is not None and total is not None and total > max_bytes:
        total = max_bytes
    read = 0
    with open(path, "rb") as fh:
        while True:
            to_read = chunk_size
            if max_bytes is not None:
                remaining = max_bytes - read
                if remaining <= 0:
                    break
                to_read = min(chunk_size, remaining)
            chunk = fh.read(to_read)
            if not chunk:
                break
            h.update(chunk)
            read += len(chunk)
            if progress_cb is not None:
                progress_cb(read, total)
            if max_bytes is not None and read >= max_bytes:
                break
    return h.hexdigest()


def hash_bytes(data: bytes, algo: str = "sha256") -> str:
    h = _new(algo)
    h.update(data)
    return h.hexdigest()


def verify_file(path: str, expected: str, algo: str = "sha256") -> bool:
    """Return True if the file's digest matches *expected* (case-insensitive)."""
    if not expected:
        return False
    return hash_file(path, algo).lower() == expected.strip().lower()
