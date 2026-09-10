"""Folder scanner: discover image files recursively."""

from __future__ import annotations

import os
from pathlib import Path
from app.core.config import settings


def scan_folder(folder_path: str) -> list[str]:
    """Recursively find all image files in a folder.

    Returns a sorted list of absolute paths.
    """
    root = Path(folder_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a valid directory: {folder_path}")

    images: list[str] = []
    for entry in root.rglob("*"):
        if entry.is_file() and entry.suffix.lower() in settings.supported_extensions:
            images.append(str(entry))

    # Natural sort
    images.sort(key=lambda p: (
        os.path.dirname(p),
        _natural_key(os.path.basename(p)),
    ))
    return images


def _natural_key(text: str) -> list:
    """Natural sort key: split into text/int chunks."""
    import re
    def convert(chunk: str):
        return int(chunk) if chunk.isdigit() else chunk.lower()
    return [convert(c) for c in re.split(r"(\d+)", text)]
