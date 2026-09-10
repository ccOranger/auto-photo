import { useEffect, useCallback } from "react";
import { mediumUrl } from "../api/client";
import type { PhotoInfo } from "../api/client";

interface Props {
  photo: PhotoInfo;
  sessionId: string;
  onClose: () => void;
  onDecision: (photoId: string, decision: "keep" | "discard") => void;
}

export default function PhotoDetailModal({ photo, sessionId, onClose, onDecision }: Props) {
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "k" || e.key === "K") onDecision(photo.id, "keep");
      if (e.key === "d" || e.key === "D") onDecision(photo.id, "discard");
    },
    [onClose, onDecision, photo.id]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  const isKept = photo.user_decision === "keep";
  const isDiscarded = photo.user_decision === "discard";

  const scoreBar = (label: string, value: number | null) => {
    if (value == null) return null;
    const pct = Math.min(value / 10, 1);
    const color = value >= 7 ? "#22c55e" : value >= 5 ? "#f59e0b" : "#ef4444";
    const r = 14;
    const circ = 2 * Math.PI * r;
    const offset = circ * (1 - pct);
    return (
      <div className="detail-score-row">
        <svg width="36" height="36" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
          <circle
            cx="18" cy="18" r={r} fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={circ} strokeDashoffset={offset}
            strokeLinecap="round" transform="rotate(-90 18 18)"
            style={{ transition: "stroke-dashoffset 0.6s ease" }}
          />
          <text x="18" y="18" textAnchor="middle" dominantBaseline="central"
            fill="#ccc" fontSize="9" fontWeight="600" fontFamily="system-ui">
            {value.toFixed(1)}
          </text>
        </svg>
        <span className="detail-score-label">{label}</span>
      </div>
    );
  };

  const issueLabel: Record<string, string> = {
    blur: "模糊",
    overexposed: "过曝",
    underexposed: "欠曝",
    eyes_closed: "闭眼",
  };

  return (
    <div className="detail-modal-overlay" onClick={onClose}>
      <div className="detail-modal" onClick={(e) => e.stopPropagation()}>
        <button className="detail-close-btn" onClick={onClose} title="关闭 (Esc)">×</button>

        <div className="detail-image-wrap">
          <img
            src={mediumUrl(sessionId, photo.id)}
            alt={photo.filename}
            className="detail-image"
          />
          <div className="detail-filename">{photo.filename}</div>
        </div>

        <div className="detail-info-panel">
          {/* Decision status */}
          <div className="detail-decision-row">
            <button
              className={"detail-decision-btn keep" + (isKept ? " active" : "")}
              onClick={() => onDecision(photo.id, "keep")}
            >
              ✓ 保留
            </button>
            <button
              className={"detail-decision-btn discard" + (isDiscarded ? " active" : "")}
              onClick={() => onDecision(photo.id, "discard")}
            >
              ✗ 淘汰
            </button>
            {photo.user_decision && (
              <button
                className="detail-decision-btn clear"
                onClick={() => onDecision(photo.id, "keep")}
                style={{ display: "none" }}
              >
                清除
              </button>
            )}
          </div>

          {/* Scores */}
          <div className="detail-section">
            <h3>审美评分</h3>
            {scoreBar("构图", photo.score_composition)}
            {scoreBar("色彩", photo.score_color)}
            {scoreBar("光影", photo.score_lighting)}
            {scoreBar("综合", photo.score_overall)}
          </div>

          {/* Technical */}
          <div className="detail-section">
            <h3>技术分析</h3>
            <div className="detail-tags">
              <span className={"detail-tag" + (photo.is_sharp ? " good" : " bad")}>
                {photo.is_sharp ? "✓ 清晰" : "✗ 模糊"}
              </span>
              <span className={"detail-tag" + (photo.is_exposed ? " good" : " bad")}>
                {photo.is_exposed ? "✓ 曝光正常" : "✗ 曝光异常"}
              </span>
              {photo.sharpness_score != null && (
                <span className="detail-tag neutral">
                  锐度 {photo.sharpness_score.toFixed(0)}
                </span>
              )}
            </div>
            {photo.technical_issues.length > 0 && (
              <div className="detail-issues">
                {photo.technical_issues.map((issue) => (
                  <span key={issue} className="detail-issue-badge">
                    {issueLabel[issue] || issue}
                  </span>
                ))}
              </div>
            )}
            {photo.has_closed_eyes && photo.eyes_closed_is_emotional && (
              <span className="detail-tag emotion">情感瞬间（闭眼）</span>
            )}
          </div>

          {/* Cluster */}
          {photo.cluster_size != null && photo.cluster_size > 1 && (
            <div className="detail-section">
              <h3>连拍分组</h3>
              <div className="detail-tags">
                <span className="detail-tag neutral">
                  组 #{(photo.cluster_id ?? 0) + 1}
                </span>
                <span className="detail-tag neutral">
                  排名 {(photo.cluster_rank ?? 0) + 1} / {photo.cluster_size}
                </span>
                {photo.cluster_rank === 0 && (
                  <span className="detail-tag good">★ 组内最佳</span>
                )}
              </div>
            </div>
          )}

          {/* Keyboard hints */}
          <div className="detail-kbd-hints">
            <kbd>K</kbd> 保留 <kbd>D</kbd> 淘汰 <kbd>Esc</kbd> 关闭
          </div>
        </div>
      </div>
    </div>
  );
}
