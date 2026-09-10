"""API routes for the photo screening tool."""

from __future__ import annotations

import asyncio
import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from app.core.models import (
    PhotoInfo, ScanRequest, ScanProgress, ExportRequest, ExportResponse,
    ClusterGroup, PhotoStatus,
)
from app.services import pipeline

router = APIRouter()


# ── Scan ──────────────────────────────────────────────────────────────────────

@router.post("/scan", response_model=dict)
async def start_scan(req: ScanRequest, bg: BackgroundTasks):
    """Start scanning a folder. Returns a session_id for tracking."""
    folder = Path(req.folder_path).resolve()
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail="Invalid folder path")

    session_id = pipeline.create_session(str(folder))
    bg.add_task(pipeline.run_pipeline, session_id)

    return {"session_id": session_id, "message": "扫描已开始"}


# ── Progress ──────────────────────────────────────────────────────────────────

@router.get("/progress/{session_id}", response_model=ScanProgress)
async def get_progress(session_id: str):
    """Get current pipeline progress."""
    info = pipeline.get_progress(session_id)
    if info["phase"] == "unknown":
        raise HTTPException(status_code=404, detail="Session not found")
    return ScanProgress(**info)


# ── Photos ─────────────────────────────────────────────────────────────────────

@router.get("/photos/{session_id}", response_model=list[PhotoInfo])
async def list_photos(
    session_id: str,
    cluster_id: Optional[int] = Query(None),
    only_issues: bool = Query(False),
    only_keepers: bool = Query(False),
):
    """List all photos in a session with optional filters."""
    photos = pipeline.get_photos(session_id)
    if not photos:
        raise HTTPException(status_code=404, detail="Session not found")

    if cluster_id is not None:
        photos = [p for p in photos if p.cluster_id == cluster_id]
    if only_issues:
        photos = [p for p in photos if p.technical_issues]
    if only_keepers:
        photos = [p for p in photos if p.user_decision == "keep"]

    return photos


@router.get("/photos/{session_id}/{photo_id}/image")
async def serve_image(session_id: str, photo_id: str):
    """Serve the actual image file."""
    session = pipeline.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    photo = session["photos"].get(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    path = photo.path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(path, media_type="image/jpeg")


@router.put("/photos/{session_id}/{photo_id}/decision")
async def set_decision(session_id: str, photo_id: str, decision: str = Query(...)):
    """Set user decision: keep, discard, or clear."""
    if decision not in ("keep", "discard", "clear"):
        raise HTTPException(status_code=400, detail="Decision must be 'keep', 'discard', or 'clear'")

    session = pipeline.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    photo = session["photos"].get(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo.user_decision = None if decision == "clear" else decision
    return {"ok": True}


# ── Clusters ───────────────────────────────────────────────────────────────────

@router.get("/clusters/{session_id}", response_model=list[ClusterGroup])
async def list_clusters(session_id: str):
    """Get all photo clusters for a session."""
    photos = pipeline.get_photos(session_id)
    if not photos:
        raise HTTPException(status_code=404, detail="Session not found")

    # Group by cluster_id
    clusters: dict[int, list[PhotoInfo]] = {}
    for p in photos:
        if p.cluster_id is not None:
            clusters.setdefault(p.cluster_id, []).append(p)

    result = []
    for cid, cphotos in clusters.items():
        cphotos.sort(key=lambda x: x.cluster_rank or 0)
        best_idx = next(
            (i for i, p in enumerate(cphotos) if p.cluster_rank == 0), 0
        )
        result.append(ClusterGroup(
            cluster_id=cid,
            photos=cphotos,
            best_index=best_idx,
        ))

    # Sort clusters: multi-photo clusters first (most interesting)
    result.sort(key=lambda c: (-c.photos[0].cluster_size if c.photos else 0, c.cluster_id))
    return result


# ── Export ─────────────────────────────────────────────────────────────────────

@router.post("/export/{session_id}", response_model=ExportResponse)
async def export_results(session_id: str, req: ExportRequest):
    """Export selected photos to target folder with report."""
    session = pipeline.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    target = Path(req.target_folder).resolve()
    target.mkdir(parents=True, exist_ok=True)

    copied = 0
    errors: list[str] = []
    report_rows: list[dict] = []

    for pid in req.photo_ids:
        photo = session["photos"].get(pid)
        if not photo:
            errors.append(f"Photo {pid} not found")
            continue

        src = Path(photo.path)
        if not src.exists():
            errors.append(f"Source file not found: {photo.path}")
            continue

        dst = target / src.name
        # Avoid overwrite: append number if exists
        if dst.exists():
            stem, suffix = dst.stem, dst.suffix
            counter = 1
            while dst.exists():
                dst = target / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            shutil.copy2(str(src), str(dst))
            copied += 1
        except Exception as e:
            errors.append(f"Copy failed for {photo.filename}: {e}")
            continue

        report_rows.append({
            "filename": photo.filename,
            "original_path": photo.path,
            "score_overall": photo.score_overall,
            "score_composition": photo.score_composition,
            "score_color": photo.score_color,
            "score_lighting": photo.score_lighting,
            "cluster_id": photo.cluster_id,
            "cluster_rank": photo.cluster_rank,
        })

    # Write report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if req.format == "csv":
        report_path = str(target / f"筛选报告_{ts}.csv")
        with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
            if report_rows:
                writer = csv.DictWriter(f, fieldnames=report_rows[0].keys())
                writer.writeheader()
                writer.writerows(report_rows)
    else:
        report_path = str(target / f"筛选报告_{ts}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_rows, f, ensure_ascii=False, indent=2)

    return ExportResponse(
        copied_count=copied,
        report_path=report_path,
        errors=errors,
    )


# ── Folders ────────────────────────────────────────────────────────────────────

@router.get("/thumbs/{session_id}/{photo_id}")
async def serve_thumbnail(
    session_id: str,
    photo_id: str,
    size: int = Query(400, ge=100, le=2000),
):
    """Serve a thumbnail version of the photo (cached on disk).

    Use ?size=1200 for medium-resolution (comparison view).
    """
    session = pipeline.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    photo = session["photos"].get(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    from app.services.image_utils import get_or_create_thumbnail
    # Use different cache key for different sizes
    cache_key = f"{photo_id}_s{size}" if size != 400 else photo_id
    thumb_path = get_or_create_thumbnail(session_id, cache_key, photo.path, max_dim=size)
    if thumb_path is None:
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(thumb_path, media_type="image/jpeg")


# ── Folder Dialog ─────────────────────────────────────────────────────────────

@router.get("/browse-folder")
async def browse_folder():
    """Open a native folder picker dialog and return the selected path."""
    import subprocess, os

    ps_script = """
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择照片文件夹'
$dialog.RootFolder = 'MyComputer'
$result = $dialog.ShowDialog()
if ($result -eq 'OK') { $dialog.SelectedPath } else { '' }
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        selected = proc.stdout.strip()
        if selected:
            return {"path": selected}
        return {"path": ""}
    except Exception as e:
        return {"path": "", "error": str(e)}


# ── Saved Sessions ────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions():
    """List all previously saved sessions."""
    return pipeline.list_saved_sessions()


@router.post("/sessions/{session_id}/restore")
async def restore_session(session_id: str):
    """Restore a saved session into memory."""
    # Already in memory?
    if pipeline.get_session(session_id):
        return {"session_id": session_id, "message": "already in memory"}

    if pipeline.load_session_from_disk(session_id):
        return {"session_id": session_id, "message": "restored"}

    raise HTTPException(status_code=404, detail="Saved session not found")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a saved session file and its thumbnail cache."""
    fpath = pipeline._SESSIONS_DIR / f"{session_id}.json"
    if fpath.exists():
        fpath.unlink()
    # Remove from memory
    pipeline._sessions.pop(session_id, None)
    # Clean up thumbnail cache
    from app.services.image_utils import invalidate_thumbnail_cache
    invalidate_thumbnail_cache(session_id)
    return {"ok": True}


# ── Auto Decide ────────────────────────────────────────────────────────────────

@router.post("/auto-decide/{session_id}")
async def auto_decide(session_id: str):
    """AI-recommended decisions: discard technical failures, keep cluster best.

    Rules:
      1. Photos with technical issues  → discard (unless emotional moment)
      2. In each cluster, the best photo (rank 0) → keep, others → discard
      3. Already-decided photos are NOT overridden
    """
    session = pipeline.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    decided = 0
    skipped = 0

    # Pass 1: discard technical failures
    for pid in session["photo_ids"]:
        photo = session["photos"][pid]
        if photo.user_decision is not None:
            skipped += 1
            continue
        if photo.technical_issues and not (
            photo.has_closed_eyes and photo.eyes_closed_is_emotional
        ):
            photo.user_decision = "discard"
            decided += 1

    # Pass 2: cluster best → keep, rest → discard
    clusters: dict[int, list[str]] = {}
    for pid in session["photo_ids"]:
        photo = session["photos"][pid]
        if photo.cluster_id is not None and photo.cluster_size and photo.cluster_size > 1:
            clusters.setdefault(photo.cluster_id, []).append(pid)

    for cid, pids in clusters.items():
        # Sort by rank (0 = best)
        pids.sort(key=lambda p: session["photos"][p].cluster_rank or 0)
        for i, pid in enumerate(pids):
            photo = session["photos"][pid]
            if photo.user_decision is not None:
                continue
            if i == 0:
                photo.user_decision = "keep"
            else:
                photo.user_decision = "discard"
            decided += 1

    # Save updated decisions
    pipeline.save_session_to_disk(session_id)

    return {"decided": decided, "skipped": skipped}


# ── Batch Decide ─────────────────────────────────────────────────────────────

@router.post("/batch-decide/{session_id}/{action}")
async def batch_decide(session_id: str, action: str):
    """Batch decision operations.

    Actions:
      - keep-best: keep cluster rank-0 photos
      - discard-issues: discard all photos with technical issues
      - clear: clear all user decisions
    """
    session = pipeline.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    affected = 0

    if action == "keep-best":
        for pid in session["photo_ids"]:
            photo = session["photos"][pid]
            if photo.cluster_rank == 0 and photo.cluster_size and photo.cluster_size > 1:
                photo.user_decision = "keep"
                affected += 1

    elif action == "discard-issues":
        for pid in session["photo_ids"]:
            photo = session["photos"][pid]
            if photo.technical_issues and not (
                photo.has_closed_eyes and photo.eyes_closed_is_emotional
            ):
                photo.user_decision = "discard"
                affected += 1

    elif action == "clear":
        for pid in session["photo_ids"]:
            photo = session["photos"][pid]
            if photo.user_decision is not None:
                photo.user_decision = None
                affected += 1

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    pipeline.save_session_to_disk(session_id)
    return {"affected": affected, "action": action}
