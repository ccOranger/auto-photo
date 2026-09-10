"""Pydantic data models for the API and internal state."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PhotoStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class TechnicalIssue(str, Enum):
    BLUR = "blur"
    OVEREXPOSED = "overexposed"
    UNDEREXPOSED = "underexposed"
    EYES_CLOSED = "eyes_closed"


class PhotoInfo(BaseModel):
    """Per-photo metadata returned to the frontend."""
    id: str
    path: str               # absolute path
    filename: str
    status: PhotoStatus = PhotoStatus.PENDING

    # Technical checks
    is_sharp: Optional[bool] = None
    sharpness_score: Optional[float] = None  # raw Laplacian variance for ranking
    is_exposed: Optional[bool] = None
    has_closed_eyes: Optional[bool] = None
    face_count: Optional[int] = None  # number of faces detected (for cluster ranking)
    technical_issues: list[TechnicalIssue] = Field(default_factory=list)
    # Whether eyes-closed is actually emotional (smile laugh kiss etc.)
    eyes_closed_is_emotional: Optional[bool] = None

    # Feature embedding for clustering (serialized as list)
    feature_vector: Optional[list[float]] = None

    # Cluster info
    cluster_id: Optional[int] = None
    cluster_rank: Optional[int] = None   # rank within cluster (0 = best)
    cluster_size: Optional[int] = None

    # Aesthetic scores (0-10)
    score_composition: Optional[float] = None
    score_color: Optional[float] = None
    score_lighting: Optional[float] = None
    score_overall: Optional[float] = None

    # User decision
    user_decision: Optional[str] = None  # "keep" | "discard" | None


class ScanRequest(BaseModel):
    folder_path: str


class ScanProgress(BaseModel):
    phase: str                      # "scanning" | "analyzing" | "clustering" | "scoring" | "done"
    total: int
    processed: int
    message: str


class ExportRequest(BaseModel):
    photo_ids: list[str]
    target_folder: str
    format: str = "json"            # "json" | "csv"


class ExportResponse(BaseModel):
    copied_count: int
    report_path: str
    errors: list[str] = Field(default_factory=list)


class ClusterGroup(BaseModel):
    cluster_id: int
    photos: list[PhotoInfo]
    best_index: int     # index into photos list
