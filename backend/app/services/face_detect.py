"""Face and eye detection using OpenCV Haar cascades + pixel analysis.

Detects faces, checks for closed eyes using eye-region pixel variance,
and detects smiles using mouth aspect ratio analysis.
Distinguishes emotional closures (kissing, laughing) from true eyelid closures.
"""

from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np

from app.core.config import settings

# OpenCV's built-in Haar cascade files
_face_cascade: cv2.CascadeClassifier | None = None
_eye_cascade: cv2.CascadeClassifier | None = None
_smile_cascade: cv2.CascadeClassifier | None = None

# Thresholds for pixel-based analysis
_EYE_VARIANCE_RATIO_THRESHOLD = 0.6  # ratio < this → eyes likely closed
_MOUTH_AR_THRESHOLD = 0.40  # mouth aspect ratio > this → open (laughing/speaking)


def _get_cascades():
    """Lazy-load Haar cascade classifiers."""
    global _face_cascade, _eye_cascade, _smile_cascade

    if _face_cascade is not None:
        return

    # In OpenCV 5, cascades were removed from cv2.data.
    # Try multiple paths; download if missing.
    import urllib.request, os

    cascade_dir = Path(__file__).resolve().parent.parent.parent / "models_cache" / "cascades"
    cascade_dir.mkdir(parents=True, exist_ok=True)

    cascades = {
        "face": ("haarcascade_frontalface_default.xml",
                 "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"),
        "eye": ("haarcascade_eye.xml",
                "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml"),
        "smile": ("haarcascade_smile.xml",
                  "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_smile.xml"),
    }

    for name, (fname, url) in cascades.items():
        fpath = cascade_dir / fname
        if not fpath.exists():
            try:
                print(f"Downloading {name} cascade...")
                urllib.request.urlretrieve(url, str(fpath))
            except Exception:
                print(f"Could not download {name} cascade; face detection will be skipped")
                fpath = None
        cascade_obj = cv2.CascadeClassifier(str(fpath)) if fpath and fpath.exists() else None
        if name == "face":
            _face_cascade = cascade_obj
        elif name == "eye":
            _eye_cascade = cascade_obj
        elif name == "smile":
            _smile_cascade = cascade_obj


def _check_eyes_closed_pixel(gray_face: np.ndarray, fh: int, fw: int) -> tuple[bool, int]:
    """Check if eyes are closed using pixel variance analysis.

    Examines the upper portion of the face where eyes are expected.
    Open eyes create high variance (pupil/iris/sclera contrast).
    Closed eyelids create low, uniform variance.

    Returns (is_closed, eyes_detected_count).
    """
    # Eye region: upper 25-50% of face, central 80% width
    eye_top = int(fh * 0.22)
    eye_bot = int(fh * 0.48)
    eye_left = int(fw * 0.10)
    eye_right = int(fw * 0.90)

    eye_region = gray_face[eye_top:eye_bot, eye_left:eye_right]
    if eye_region.size < 100:
        return False, 0

    # Overall variance of the eye region
    overall_var = float(eye_region.var())

    # Edge density in eye region (Sobel filter)
    sobel_x = cv2.Sobel(eye_region, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(eye_region, cv2.CV_64F, 0, 1, ksize=3)
    edge_magnitude = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
    edge_mean = float(edge_magnitude.mean())

    # Variance in upper half (eyelid area) vs full eye region
    half_h = eye_region.shape[0] // 2
    upper_var = float(eye_region[:half_h, :].var())
    lower_var = float(eye_region[half_h:, :].var())

    # Ratio: if upper is much less variable than lower, eyes likely closed
    var_ratio = upper_var / max(lower_var, 1.0)

    # Try Haar eye detection as secondary signal
    eyes_detected = 0
    if _eye_cascade is not None:
        eyes = _eye_cascade.detectMultiScale(
            eye_region, scaleFactor=1.1, minNeighbors=5, minSize=(15, 15)
        )
        eyes_detected = len(eyes)

    # Decision logic: combine pixel analysis with Haar results
    if eyes_detected >= 2:
        # Haar found both eyes → definitely open
        return False, eyes_detected
    elif eyes_detected == 1:
        # One eye detected → partially closed or side angle
        return False, eyes_detected
    else:
        # No eyes detected by Haar → use pixel analysis
        # Low edge magnitude + low variance ratio → closed
        if edge_mean < 15.0 and var_ratio < _EYE_VARIANCE_RATIO_THRESHOLD:
            return True, 0
        elif overall_var < 200.0 and edge_mean < 20.0:
            return True, 0
        else:
            return False, 0


def _check_mouth_open(gray_face: np.ndarray, fh: int, fw: int) -> bool:
    """Check if mouth is open (laughing, speaking) using aspect ratio.

    Returns True if mouth appears open (emotional expression).
    """
    # Mouth region: lower 35% of face
    mouth_top = int(fh * 0.65)
    mouth_region = gray_face[mouth_top:, :]
    if mouth_region.size < 50:
        return False

    # Edge detection to find mouth contours
    edges = cv2.Canny(mouth_region, 30, 100)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        # Fallback: use smile cascade
        if _smile_cascade is not None:
            smiles = _smile_cascade.detectMultiScale(
                mouth_region, scaleFactor=1.3, minNeighbors=15, minSize=(25, 25)
            )
            return len(smiles) > 0
        return False

    # Find the largest contour (likely the mouth)
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    if w < 10 or h < 3:
        return False

    # Aspect ratio: open mouth → taller relative to width
    ar = h / w
    return ar > _MOUTH_AR_THRESHOLD


def detect_face_eyes(image_bgr: np.ndarray) -> dict:
    """Run face/eye/smile detection and return analysis results.

    Returns a dict:
    {
        "faces_detected": int,
        "any_eyes_closed": bool,
        "is_emotional": bool,
        "details": [...per face...]
    }
    """
    _get_cascades()

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    # Equalize histogram for better detection
    gray_eq = cv2.equalizeHist(gray)

    faces = _face_cascade.detectMultiScale(
        gray_eq, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )

    faces_detected = len(faces)
    any_eyes_closed = False
    is_emotional = False
    details: list = []

    for i, (fx, fy, fw, fh) in enumerate(faces):
        face_roi = gray_eq[fy : fy + fh, fx : fx + fw]

        # ── Eye closure: pixel variance analysis ───────────────────
        both_closed, eyes_found = _check_eyes_closed_pixel(face_roi, fh, fw)

        # ── Smile / mouth: aspect ratio analysis ───────────────────
        mouth_open = _check_mouth_open(face_roi, fh, fw)

        # Emotional closure check:
        # Eyes closed + mouth open (laughing) = likely emotional moment
        emotional = both_closed and mouth_open

        detail = {
            "face_index": i,
            "eyes_detected": eyes_found,
            "both_closed": both_closed,
            "smile_detected": mouth_open,
            "is_emotional": emotional,
            "face_rect": [int(fx), int(fy), int(fw), int(fh)],
        }
        details.append(detail)

        if both_closed:
            any_eyes_closed = True
            if emotional:
                is_emotional = True

    return {
        "faces_detected": faces_detected,
        "any_eyes_closed": any_eyes_closed,
        "is_emotional": is_emotional,
        "details": details,
    }
