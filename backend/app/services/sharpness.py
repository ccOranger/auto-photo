"""Sharpness / blur detection using Laplacian variance."""

from __future__ import annotations

import cv2
import numpy as np
from app.core.config import settings


def compute_sharpness(image: np.ndarray) -> float:
    """Compute Laplacian variance as a sharpness metric.

    Higher values = sharper. Returns the raw variance value.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def is_sharp(image: np.ndarray) -> bool:
    """Check if image is sharp enough (not blurry)."""
    variance = compute_sharpness(image)
    return variance >= settings.blur_threshold_laplacian
