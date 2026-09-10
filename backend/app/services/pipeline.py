"""Photo screening pipeline: orchestrates the full analysis workflow.

Phases:
  1. SCAN      — scan folder, create PhotoInfo entries
  2. TECHNICAL — blur, exposure, face/eye checks (fast, per-image)
  3. FEATURES  — DINOv2 feature extraction (slow, per-image)
  4. CLUSTER   — similarity clustering on all features
  5. AESTHETIC — aesthetic scoring (per-image)
  6. DONE

Processing phases run sequentially via the event-loop executor to avoid
thread-safety issues with OpenCV / PyTorch C-extensions.  Each item yields
control back to the event loop so progress polls remain responsive.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings
from app.core.models import PhotoInfo, PhotoStatus, TechnicalIssue
from app.services import scanner, sharpness, exposure, face_detect
from app.services import feature_extract, cluster as cluster_svc, aesthetic
from app.services.image_utils import imread

logger = logging.getLogger(__name__)


# ── Sequential async execution infrastructure ─────────────────────────────


async def _run_sequential(
    fn: Callable[..., None],
    items: list[Any],
    on_done: Callable[[], None] | None = None,
) -> None:
    """Run *fn(item)* for every item sequentially, yielding between items.

    Each call is dispatched to the default executor (thread pool) so it
    doesn't block the event loop.  Only one task runs at a time to avoid
    thread-safety issues with OpenCV / PyTorch C-extensions.
    Exceptions from individual items are logged and skipped.
    """
    loop = asyncio.get_running_loop()
    for item in items:
        try:
            await loop.run_in_executor(None, fn, item)
        except Exception as e:
            logger.warning(f"Task error: {e}")
        if on_done is not None:
            on_done()
        # Yield to event loop so progress polls get served
        await asyncio.sleep(0)


# In-memory session store (per-scan)
_sessions: dict[str, dict[str, Any]] = {}

# Persistent session storage directory
_SESSIONS_DIR = settings.models_cache_dir / "sessions"


def _session_to_json(session: dict[str, Any]) -> dict:
    """Serialize a session dict to JSON-safe format.

    Skips feature_vector to keep file size small (~384 floats per photo).
    """
    photos_ser = {}
    for pid, photo in session["photos"].items():
        d = photo.model_dump()
        d.pop("feature_vector", None)  # drop large embedding
        # Convert enum values to strings
        d["status"] = d["status"].value if hasattr(d["status"], "value") else d["status"]
        d["technical_issues"] = [
            t.value if hasattr(t, "value") else t for t in d["technical_issues"]
        ]
        photos_ser[pid] = d

    return {
        "session_id": "",
        "folder_path": session["folder_path"],
        "phase": session["phase"],
        "photo_ids": session["photo_ids"],
        "photos": photos_ser,
        "total": session["progress"]["total"],
        "created_at": session.get("created_at", datetime.now().isoformat()),
    }


def _json_to_session(data: dict) -> dict:
    """Deserialize a JSON dict back into an in-memory session."""
    photos: dict[str, PhotoInfo] = {}
    for pid, pd in data["photos"].items():
        pd["id"] = pid
        photos[pid] = PhotoInfo(**pd)

    return {
        "folder_path": data["folder_path"],
        "photos": photos,
        "photo_ids": data["photo_ids"],
        "phase": data["phase"],
        "progress": {"total": data.get("total", len(data["photo_ids"])), "processed": data.get("total", 0)},
        "message": "分析完成",
        "error": None,
        "created_at": data.get("created_at", ""),
    }


def save_session_to_disk(session_id: str) -> str | None:
    """Persist a completed session to a JSON file. Returns the file path."""
    session = _sessions.get(session_id)
    if not session:
        return None

    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    data = _session_to_json(session)
    data["session_id"] = session_id

    fpath = _SESSIONS_DIR / f"{session_id}.json"
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Session {session_id} saved to {fpath}")
        return str(fpath)
    except Exception as e:
        logger.warning(f"Failed to save session {session_id}: {e}")
        return None


def load_session_from_disk(session_id: str) -> bool:
    """Load a previously saved session into memory. Returns True on success."""
    fpath = _SESSIONS_DIR / f"{session_id}.json"
    if not fpath.exists():
        return False

    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        session = _json_to_session(data)
        _sessions[session_id] = session
        logger.info(f"Session {session_id} restored from disk")
        return True
    except Exception as e:
        logger.warning(f"Failed to load session {session_id}: {e}")
        return False


def list_saved_sessions() -> list[dict]:
    """List all persisted sessions with summary info."""
    if not _SESSIONS_DIR.exists():
        return []

    results = []
    for fpath in sorted(_SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            total = data.get("total", len(data.get("photo_ids", [])))
            keepers = sum(
                1 for pd in data["photos"].values()
                if pd.get("user_decision") == "keep"
            )
            results.append({
                "session_id": data.get("session_id", fpath.stem),
                "folder_path": data.get("folder_path", ""),
                "phase": data.get("phase", "done"),
                "total": total,
                "keepers": keepers,
                "created_at": data.get("created_at", ""),
            })
        except Exception:
            continue
    return results


def create_session(folder_path: str) -> str:
    """Create a new scan session, return session_id."""
    session_id = str(uuid.uuid4())[:8]
    _sessions[session_id] = {
        "folder_path": folder_path,
        "photos": {},        # photo_id -> PhotoInfo
        "photo_ids": [],     # ordered list
        "phase": "created",
        "progress": {"total": 0, "processed": 0},
        "error": None,
        "created_at": datetime.now().isoformat(),
    }

    # LRU eviction: keep memory bounded
    _evict_old_sessions()

    return session_id


def _evict_old_sessions() -> None:
    """Evict oldest completed sessions if we exceed max_sessions_in_memory.

    Saves evicted sessions to disk before removing from memory.
    """
    max_sessions = settings.max_sessions_in_memory
    if len(_sessions) <= max_sessions:
        return

    # Sort by created_at, oldest first; prefer evicting 'done' sessions
    candidates = sorted(
        _sessions.items(),
        key=lambda item: item[1].get("created_at", ""),
    )

    for sid, session in candidates:
        if len(_sessions) <= max_sessions:
            break
        # Save to disk before eviction (if completed)
        if session.get("phase") == "done":
            try:
                save_session_to_disk(sid)
            except Exception:
                pass
        _sessions.pop(sid, None)
        logger.info(f"Evicted session {sid} from memory (LRU)")



def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def get_photos(session_id: str) -> list[PhotoInfo]:
    session = _sessions.get(session_id)
    if not session:
        return []
    return [session["photos"][pid] for pid in session["photo_ids"]]


def get_progress(session_id: str) -> dict:
    session = _sessions.get(session_id)
    if not session:
        return {"phase": "unknown", "total": 0, "processed": 0, "message": ""}
    p = session["progress"]
    return {
        "phase": session["phase"],
        "total": p["total"],
        "processed": p["processed"],
        "message": session.get("message", ""),
        "error": session.get("error"),
    }


async def run_pipeline(session_id: str):
    """Run the full pipeline asynchronously."""
    session = _sessions.get(session_id)
    if not session:
        logger.warning(f"Session {session_id} not found for pipeline")
        return

    try:
        logger.info(f"Pipeline {session_id}: starting scan phase")
        await _phase_scan(session_id)
        logger.info(f"Pipeline {session_id}: scan done, {len(session['photo_ids'])} photos")
        await _phase_technical(session_id)
        logger.info(f"Pipeline {session_id}: technical done")
        await _phase_features(session_id)
        logger.info(f"Pipeline {session_id}: features done")
        await _phase_cluster(session_id)
        logger.info(f"Pipeline {session_id}: cluster done")
        await _phase_aesthetic(session_id)
        logger.info(f"Pipeline {session_id}: aesthetic done")

        session["phase"] = "done"
        session["message"] = "分析完成"
        logger.info(f"Pipeline {session_id}: all done")

        # Auto-persist completed session
        save_session_to_disk(session_id)

    except Exception as e:
        logger.exception(f"Pipeline failed for session {session_id}")
        session["phase"] = "error"
        session["error"] = str(e)


async def _phase_scan(session_id: str):
    session = _sessions[session_id]
    session["phase"] = "scanning"
    session["message"] = "正在扫描文件夹..."

    folder = session["folder_path"]
    paths = scanner.scan_folder(folder)
    photo_ids = []

    for path in paths:
        pid = str(uuid.uuid4())[:8]
        photo_ids.append(pid)
        session["photos"][pid] = PhotoInfo(
            id=pid,
            path=path,
            filename=Path(path).name,
            status=PhotoStatus.PENDING,
        )

    session["photo_ids"] = photo_ids
    session["progress"]["total"] = len(photo_ids)
    session["progress"]["processed"] = 0
    await asyncio.sleep(0)


async def _phase_technical(session_id: str):
    session = _sessions[session_id]
    session["phase"] = "analyzing"
    session["message"] = "正在分析技术质量..."

    # Collect only pending photos
    pending_ids = [
        pid for pid in session["photo_ids"]
        if session["photos"][pid].status == PhotoStatus.PENDING
    ]

    progress_lock = threading.Lock()

    def _process_technical(pid: str) -> None:
        """Per-image technical analysis (runs in executor thread)."""
        photo: PhotoInfo = session["photos"][pid]
        photo.status = PhotoStatus.PROCESSING
        try:
            img = imread(photo.path)
            if img is None:
                photo.technical_issues.append(TechnicalIssue.BLUR)
                photo.status = PhotoStatus.ERROR
                return

            # 1. Sharpness
            raw_sharpness = sharpness.compute_sharpness(img)
            photo.sharpness_score = raw_sharpness
            photo.is_sharp = raw_sharpness >= settings.blur_threshold_laplacian
            if not photo.is_sharp:
                photo.technical_issues.append(TechnicalIssue.BLUR)

            # 2. Exposure
            ok, over, under, _ = exposure.check_exposure(img)
            photo.is_exposed = ok
            if over:
                photo.technical_issues.append(TechnicalIssue.OVEREXPOSED)
            if under:
                photo.technical_issues.append(TechnicalIssue.UNDEREXPOSED)

            # 3. Face / Eye detection
            try:
                face_result = face_detect.detect_face_eyes(img)
                photo.has_closed_eyes = face_result["any_eyes_closed"]
                photo.eyes_closed_is_emotional = face_result["is_emotional"]
                photo.face_count = face_result["faces_detected"]
                if photo.has_closed_eyes and not photo.eyes_closed_is_emotional:
                    photo.technical_issues.append(TechnicalIssue.EYES_CLOSED)
            except Exception:
                logger.debug(f"Face detection skipped for {photo.filename}")

            photo.status = PhotoStatus.DONE
        except Exception as e:
            logger.warning(f"Technical analysis failed for {photo.filename}: {e}")
            photo.status = PhotoStatus.ERROR

    def _on_done() -> None:
        with progress_lock:
            session["progress"]["processed"] += 1

    await _run_sequential(_process_technical, pending_ids, on_done=_on_done)


async def _phase_features(session_id: str):
    session = _sessions[session_id]
    session["phase"] = "features"
    session["message"] = "正在提取图像特征 (DINOv2)..."
    session["progress"]["processed"] = 0

    # Only process photos that passed technical analysis
    valid_ids = [
        pid for pid in session["photo_ids"]
        if session["photos"][pid].status != PhotoStatus.ERROR
    ]

    progress_lock = threading.Lock()

    def _extract_features(pid: str) -> None:
        """Per-image DINOv2 feature extraction (runs in executor thread)."""
        photo: PhotoInfo = session["photos"][pid]
        try:
            vec = feature_extract.extract_features(photo.path)
            photo.feature_vector = vec
        except Exception as e:
            logger.warning(f"Feature extraction failed for {photo.filename}: {e}")
            photo.status = PhotoStatus.ERROR

    def _on_done() -> None:
        with progress_lock:
            session["progress"]["processed"] += 1

    await _run_sequential(_extract_features, valid_ids, on_done=_on_done)


async def _phase_cluster(session_id: str):
    session = _sessions[session_id]
    session["phase"] = "clustering"
    session["message"] = "正在聚类相似照片..."

    # Gather photos with valid features
    valid = {}
    valid_ids = []
    quality_data: dict[str, dict] = {}
    for pid in session["photo_ids"]:
        photo: PhotoInfo = session["photos"][pid]
        if photo.feature_vector is not None:
            valid[pid] = photo.feature_vector
            valid_ids.append(pid)
            quality_data[pid] = {
                "sharpness": photo.sharpness_score or 0,
                "is_exposed": photo.is_exposed if photo.is_exposed is not None else True,
                "face_count": photo.face_count or 0,
            }

    if len(valid) >= 2:
        clusters = cluster_svc.cluster_photos(valid, valid_ids, quality_data)
        for pid, (cid, rank, size) in clusters.items():
            photo: PhotoInfo = session["photos"][pid]
            photo.cluster_id = cid
            photo.cluster_rank = rank
            photo.cluster_size = size

    # Single-item clusters: mark as cluster of 1
    for pid in session["photo_ids"]:
        photo: PhotoInfo = session["photos"][pid]
        if photo.cluster_id is None and photo.feature_vector is not None:
            # Assign a unique cluster
            max_cid = max(
                (p.cluster_id for p in session["photos"].values() if p.cluster_id is not None),
                default=-1,
            )
            photo.cluster_id = max_cid + 1
            photo.cluster_rank = 0
            photo.cluster_size = 1

    await asyncio.sleep(0)


async def _phase_aesthetic(session_id: str):
    session = _sessions[session_id]
    session["phase"] = "scoring"
    session["message"] = "正在美学评分..."
    session["progress"]["processed"] = 0

    valid_ids = [
        pid for pid in session["photo_ids"]
        if session["photos"][pid].status != PhotoStatus.ERROR
    ]

    progress_lock = threading.Lock()

    def _score_aesthetic(pid: str) -> None:
        """Per-image aesthetic scoring (runs in executor thread)."""
        photo: PhotoInfo = session["photos"][pid]
        try:
            scores = aesthetic.score_aesthetics(photo.path)
            photo.score_composition = scores["composition"]
            photo.score_color = scores["color"]
            photo.score_lighting = scores["lighting"]
            photo.score_overall = scores["overall"]
        except Exception as e:
            logger.warning(f"Aesthetic scoring failed for {photo.filename}: {e}")

    def _on_done() -> None:
        with progress_lock:
            session["progress"]["processed"] += 1

    await _run_sequential(_score_aesthetic, valid_ids, on_done=_on_done)
