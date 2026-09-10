import { useState } from "react";
import { thumbUrl } from "../api/client";
import type { PhotoInfo, ClusterGroup } from "../api/client";

interface Props {
  sessionId: string;
  clusters: ClusterGroup[];
  onDecision: (photoId: string, decision: "keep" | "discard") => void;
}

export default function ClusterPanel({ sessionId, clusters, onDecision }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (cid: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(cid)) next.delete(cid);
      else next.add(cid);
      return next;
    });
  };

  if (clusters.length === 0) {
    return <div className="no-compare-content">暂无分组数据</div>;
  }

  return (
    <div className="cluster-panel">
      {clusters.map((cluster) => {
        const isOpen = expanded.has(cluster.cluster_id);

        return (
          <div key={cluster.cluster_id} className="cluster-group">
            <div className="cluster-header" onClick={() => toggle(cluster.cluster_id)}>
              <h3>
                {cluster.photos.length > 1
                  ? "连拍分组 #" + (cluster.cluster_id + 1)
                  : "单张 #" + (cluster.cluster_id + 1)}
                {" "}
                <span className="cluster-meta">
                  ({cluster.photos.length} 张)
                </span>
              </h3>
              <span className="cluster-meta">
                {isOpen ? "收起 ▲" : "展开 ▼"}
              </span>
            </div>
            {isOpen && (
              <div className="cluster-body">
                {cluster.photos.map((photo) => {
                  const isBest = photo.cluster_rank === 0;
                  const isKept = photo.user_decision === "keep";
                  const isDiscarded = photo.user_decision === "discard";
                  let cls = "cluster-photo";
                  if (isBest) cls += " best";
                  if (isKept) cls += " kept";
                  if (isDiscarded) cls += " discarded";

                  return (
                    <div key={photo.id} className={cls}>
                      <img
                        src={thumbUrl(sessionId, photo.id)}
                        alt={photo.filename}
                        loading="lazy"
                      />
                      <span className="cluster-photo-badge">
                        {isBest ? "★ 最佳 · " : "#" + ((photo.cluster_rank ?? 0) + 1) + " · "}
                        {photo.score_overall?.toFixed(1)}
                      </span>
                      <div
                        className="cluster-photo-actions"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          className={"card-action-btn keep-btn" + (isKept ? " active" : "")}
                          onClick={() => onDecision(photo.id, "keep")}
                        >
                          保留
                        </button>
                        <button
                          className={"card-action-btn discard-btn" + (isDiscarded ? " active" : "")}
                          onClick={() => onDecision(photo.id, "discard")}
                        >
                          淘汰
                        </button>
                      </div>
                      {isKept && (
                        <span className="cluster-decision-badge keep-badge">已保留</span>
                      )}
                      {isDiscarded && (
                        <span className="cluster-decision-badge discard-badge">已淘汰</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
