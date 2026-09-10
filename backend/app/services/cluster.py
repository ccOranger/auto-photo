""" Similar photo clustering using cosine similarity on DINOv2 features.

Groups burst/continuous shots into clusters, ranks photos within each cluster
using a composite quality score (sharpness + exposure + face presence).
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.core.config import settings


def cluster_photos(
    features: dict[str, list[float]],
    ids: list[str],
    quality_data: dict[str, dict] | None = None,
) -> dict[str, tuple[int, int, int]]:
    """Cluster photos by feature similarity with quality-aware ranking.

    Args:
        features: {photo_id: feature_vector (list of floats)}
        ids: ordered list of photo ids
        quality_data: optional {photo_id: {sharpness: float, is_exposed: bool, face_count: int}}

    Returns:
        {photo_id: (cluster_id, rank_in_cluster, cluster_size)}
    """
    if len(ids) == 0:
        return {}

    # Build feature matrix
    feature_matrix = np.array([features[pid] for pid in ids], dtype=np.float32)

    # Compute pairwise cosine similarity
    sim_matrix = cosine_similarity(feature_matrix)

    # Greedy clustering: group if similarity above threshold
    n = len(ids)
    visited = [False] * n
    clusters: list[list[int]] = []  # each cluster is list of indices

    for i in range(n):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if not visited[j] and sim_matrix[i, j] >= settings.similarity_threshold:
                cluster.append(j)
                visited[j] = True
        clusters.append(cluster)

    # Within each cluster, compute a composite quality score for ranking.
    result: dict[str, tuple[int, int, int]] = {}

    for cid, cluster_indices in enumerate(clusters):
        c_size = len(cluster_indices)
        scores = []
        for idx in cluster_indices:
            pid = ids[idx]

            if quality_data and pid in quality_data:
                qd = quality_data[pid]

                # Sharpness component (normalized Laplacian variance)
                sharpness = qd.get("sharpness", 0)
                # Normalize: typical range 50-5000, cap at 5000
                sharp_score = min(sharpness / 5000.0, 1.0)

                # Exposure component: good exposure = 1.0, issues = 0.0
                exposure_score = 1.0 if qd.get("is_exposed", True) else 0.3

                # Face presence: photos with faces often more valuable
                face_count = qd.get("face_count", 0)
                face_score = min(face_count * 0.2, 0.5) if face_count else 0.0

                # Position bonus: earlier shots in burst slightly preferred
                pos_bonus = 0.02 * (1.0 - idx / max(n, 1))

                # Composite score (weighted)
                quality = (
                    sharp_score * 0.45
                    + exposure_score * 0.30
                    + face_score * 0.20
                    + pos_bonus * 0.05
                )
            else:
                # Fallback: feature vector norm (legacy behavior)
                vec = feature_matrix[idx]
                quality = float(np.linalg.norm(vec))
                pos_bonus = 0.02 * (1.0 - idx / max(n, 1))
                quality += pos_bonus

            scores.append(quality)

        # Sort by score descending for ranking
        ranked = sorted(
            zip(cluster_indices, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        for rank, (idx, _score) in enumerate(ranked):
            pid = ids[idx]
            result[pid] = (cid, rank, c_size)

    return result
