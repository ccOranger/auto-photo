"""Exposure analysis: detect over/underexposure."""

from __future__ import annotations

import cv2
import numpy as np
from app.core.config import settings


def check_exposure(image: np.ndarray) -> tuple[bool, bool, dict]:
    """Check for overexposure and underexposure.

    Returns (is_ok, is_over, is_under, stats).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    total = gray.size

    over_mask = gray >= 250
    under_mask = gray <= 30

    over_ratio = float(np.count_nonzero(over_mask)) / total
    under_ratio = float(np.count_nonzero(under_mask)) / total

    is_over = over_ratio > settings.overexposed_ratio
    is_under = under_ratio > settings.underexposed_ratio
    is_ok = not is_over and not is_under

    stats = {
        "overexposed_ratio": over_ratio,
        "underexposed_ratio": under_ratio,
        "mean_brightness": float(gray.mean()),
    }
    return is_ok, is_over, is_under, stats
