"""Aesthetic scoring service.

Uses enhanced heuristic scoring:
  - Composition: edge density + rule-of-thirds saliency analysis
  - Color: saturation variance + hue harmony (complementary/analogous)
  - Lighting: brightness entropy + contrast quality + dynamic range

Falls back gracefully; does not require network or GPU.
"""

from __future__ import annotations

import logging
import numpy as np
import cv2

logger = logging.getLogger(__name__)


def score_aesthetics(image_path: str) -> dict:
    """Score an image for aesthetic quality using enhanced heuristics.

    Returns dict with keys: composition, color, lighting, overall (all 0-10 scale).
    """
    from app.services.image_utils import imread

    img = imread(image_path)
    if img is None:
        return {"composition": 5.0, "color": 5.0, "lighting": 5.0, "overall": 5.0}

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # ── Composition: edge density + rule-of-thirds ──────────────────────

    # Base: edge density
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.count_nonzero(edges) / max(edges.size, 1)
    base_composition = min(10.0, edge_density * 80 + 3.0)

    # Rule-of-thirds: check if salient content aligns with 1/3 grid lines
    thirds_score = _score_rule_of_thirds(edges, h, w)

    composition = base_composition * 0.6 + thirds_score * 0.4

    # ── Color: saturation variance + hue harmony ────────────────────────

    saturation = hsv[:, :, 1]
    sat_score = min(10.0, float(np.std(saturation)) / 8.0 + 4.0)

    harmony_score = _score_color_harmony(hsv)

    color_score = sat_score * 0.5 + harmony_score * 0.5

    # ── Lighting: entropy + contrast + dynamic range ────────────────────

    brightness = hsv[:, :, 2]
    hist = cv2.calcHist([brightness], [0], None, [256], [0, 256])
    hist_norm = hist / max(hist.sum(), 1)
    ent = -float(np.sum(
        hist_norm[hist_norm > 0] * np.log2(hist_norm[hist_norm > 0] + 1e-10)
    ))
    entropy_score = min(10.0, ent / 0.8 + 3.0)

    contrast_score = _score_contrast(gray)

    lighting = entropy_score * 0.5 + contrast_score * 0.5

    # ── Overall (weighted) ──────────────────────────────────────────────

    overall = composition * 0.35 + color_score * 0.30 + lighting * 0.35

    return {
        "composition": round(min(10.0, composition), 2),
        "color": round(min(10.0, color_score), 2),
        "lighting": round(min(10.0, lighting), 2),
        "overall": round(min(10.0, overall), 2),
    }


# ── Helper functions ─────────────────────────────────────────────────────────


def _score_rule_of_thirds(edges: np.ndarray, h: int, w: int) -> float:
    """Score how well salient content aligns with rule-of-thirds grid."""
    edge_points = np.argwhere(edges > 0)
    if len(edge_points) < 50:
        return 5.0  # not enough structure to evaluate

    # 9-zone grid (3×3)
    zone_counts = np.zeros((3, 3), dtype=int)
    for r, c in edge_points:
        zr = min(int(r / h * 3), 2)
        zc = min(int(c / w * 3), 2)
        zone_counts[zr, zc] += 1

    total = zone_counts.sum()
    if total == 0:
        return 5.0

    zone_fracs = zone_counts / total

    # Rule-of-thirds intersections (4 power points at zone boundaries)
    # Weight the 4 corner-adjacent zones higher (they contain the power points)
    power_zones = [(0, 0), (0, 2), (2, 0), (2, 2)]
    center_zone = (1, 1)

    power_frac = sum(zone_fracs[z] for z in power_zones)
    center_frac = zone_fracs[center_zone]

    # Good composition: power zones have ~40-60% of content
    # Too centered: center_zone has >50% of content
    if 0.3 <= power_frac <= 0.65:
        thirds_bonus = 3.0
    elif power_frac < 0.2:
        thirds_bonus = 0.0
    else:
        thirds_bonus = 1.5

    # Penalize dead-center composition
    center_penalty = max(0, center_frac - 0.35) * 10

    return min(10.0, 5.0 + thirds_bonus - center_penalty)


def _score_color_harmony(hsv: np.ndarray) -> float:
    """Score color harmony based on hue distribution analysis."""
    hue = hsv[:, :, 0].astype(np.float32)  # OpenCV hue: 0-179
    sat = hsv[:, :, 1].astype(np.float32)

    # Only consider saturated pixels (ignore grayscale/low-saturation)
    mask = sat > 40
    if mask.sum() < 100:
        return 6.0  # mostly grayscale — neutral score

    hue_values = hue[mask].astype(int)

    # Build 36-bin hue histogram (5° per bin, OpenCV 0-179 → 0-35)
    hue_hist = np.zeros(36, dtype=np.float32)
    for h in hue_values:
        bin_idx = min(int(h / 5), 35)
        hue_hist[bin_idx] += 1

    if hue_hist.sum() < 10:
        return 6.0

    hue_hist = hue_hist / hue_hist.sum()

    # Smooth histogram and find dominant peaks
    kernel = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
    smoothed = np.convolve(hue_hist, kernel, mode="same")

    # Find peaks (local maxima above threshold)
    threshold = smoothed.max() * 0.3
    peaks = []
    for i in range(36):
        prev_val = smoothed[(i - 1) % 36]
        curr_val = smoothed[i]
        next_val = smoothed[(i + 1) % 36]
        if curr_val > threshold and curr_val >= prev_val and curr_val >= next_val:
            peaks.append(i)

    if len(peaks) <= 1:
        # Monochromatic — decent but not interesting
        return 6.5

    # Check angular distances between peak pairs
    harmony_points = 0
    for i in range(len(peaks)):
        for j in range(i + 1, len(peaks)):
            dist = abs(peaks[i] - peaks[j])
            dist = min(dist, 36 - dist)  # circular distance (max 18)
            # Analogous (~3 bins / 30°)
            if dist <= 4:
                harmony_points += 1
            # Complementary (~18 bins / 180°)
            elif dist >= 14:
                harmony_points += 2
            # Triadic (~12 bins / 120°)
            elif 10 <= dist <= 14:
                harmony_points += 1.5

    return min(10.0, 5.0 + harmony_points * 0.8)


def _score_contrast(gray: np.ndarray) -> float:
    """Score contrast quality using histogram spread and dynamic range."""
    mean_val = float(gray.mean())
    std_val = float(gray.std())

    # Good contrast: std ~50-70, mean ~100-160
    # Contrast score based on spread
    contrast = min(10.0, std_val / 7.0 + 3.0)

    # Dynamic range bonus
    p5 = float(np.percentile(gray, 5))
    p95 = float(np.percentile(gray, 95))
    dynamic_range = p95 - p5
    range_bonus = min(2.0, dynamic_range / 100.0)

    # Mean brightness penalty (too dark or too bright)
    if mean_val < 60 or mean_val > 200:
        brightness_penalty = 1.5
    elif mean_val < 80 or mean_val > 180:
        brightness_penalty = 0.5
    else:
        brightness_penalty = 0.0

    return max(1.0, min(10.0, contrast + range_bonus - brightness_penalty))
