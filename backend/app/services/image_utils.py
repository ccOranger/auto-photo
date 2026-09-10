"""Image I/O utilities with Unicode path support.

OpenCV's cv2.imread cannot handle non-ASCII paths on Windows.
Use np.fromfile + cv2.imdecode as a drop-in replacement.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.config import settings


def imread(path: str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """Read an image from a path with full Unicode support."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, flags)
    except Exception:
        return None


# ── Thumbnail cache ────────────────────────────────────────────────────────────

_THUMB_DIR = settings.models_cache_dir / "thumbnails"


def get_or_create_thumbnail(
    session_id: str,
    photo_id: str,
    source_path: str,
    max_dim: int = 400,
    quality: int = 75,
) -> str | None:
    """Return cached thumbnail path, generating it on first access.

    Returns the absolute path to the JPEG thumbnail, or None on failure.
    """
    cache_dir = _THUMB_DIR / session_id
    thumb_path = cache_dir / f"{photo_id}.jpg"

    # Serve from cache if it already exists
    if thumb_path.exists():
        return str(thumb_path)

    # Generate thumbnail
    img = imread(source_path)
    if img is None:
        return None

    h, w = img.shape[:2]
    scale = max_dim / max(h, w, 1)
    if scale < 1.0:
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    cache_dir.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return None

    # Write with Unicode-safe path handling
    try:
        with open(str(thumb_path), "wb") as f:
            f.write(buf.tobytes())
    except Exception:
        return None

    return str(thumb_path)


def invalidate_thumbnail_cache(session_id: str) -> None:
    """Remove all cached thumbnails for a session."""
    cache_dir = _THUMB_DIR / session_id
    if cache_dir.exists():
        for f in cache_dir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            cache_dir.rmdir()
        except OSError:
            pass
