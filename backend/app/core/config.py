"""Application configuration."""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Global settings for the photo screening tool."""

    # Paths
    models_cache_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
        / "models_cache"
    )

    # Image processing
    supported_extensions: tuple = (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".heic", ".heif")
    max_image_dimension: int = 2048  # resize long edge for feature extraction

    # Sharpness thresholds
    blur_threshold_laplacian: float = 100.0  # Laplacian variance threshold

    # Exposure thresholds
    overexposed_ratio: float = 0.05   # fraction of pixels clipped at 250+
    underexposed_ratio: float = 0.30  # fraction of pixels below 30

    # Eye detection
    eye_aspect_ratio_threshold: float = 0.2  # below this = eyes closed
    emotion_smile_threshold: float = 0.3     # mouth openness for smile detection

    # Clustering
    similarity_threshold: float = 0.85  # cosine similarity threshold for grouping

    # Aesthetic scoring
    aesthetic_model_name: str = "cafeai/cafe_aesthetic"

    # Worker — parallel image processing threads (CPU-bound)
    # Default: half of CPU cores, clamped to [2, 6] to avoid memory pressure
    max_concurrent_tasks: int = field(
        default_factory=lambda: max(2, min(os.cpu_count() // 2 or 2, 6))
    )

    # Session management
    max_sessions_in_memory: int = 10  # LRU evict oldest sessions beyond this


settings = Settings()
