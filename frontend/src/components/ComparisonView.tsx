import { useState, useEffect, useCallback, useRef } from "react";
import { mediumUrl } from "../api/client";
import type { PhotoInfo } from "../api/client";

interface Props {
  sessionId: string;
  photos: PhotoInfo[];
  onDecision: (photoId: string, decision: "keep" | "discard") => void;
  onRefresh: () => void;
}

export default function ComparisonView({ sessionId, photos, onDecision, onRefresh }: Props) {
  const undecided = photos.filter((p) => !p.user_decision);
  const [index, setIndex] = useState(0);
  const [sliderMode, setSliderMode] = useState(false);
  const [sliderPos, setSliderPos] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const left = undecided[index] ?? null;
  const right = undecided[index + 1] ?? null;

  const advance = useCallback(() => {
    setIndex((i) => i + 2);
    setSliderPos(50);
  }, []);

  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft" && left) {
        e.preventDefault();
        onDecision(left.id, "keep");
        advance();
      }
      if (e.key === "ArrowRight" && right) {
        e.preventDefault();
        onDecision(right.id, "keep");
        advance();
      }
      if (e.key === " " || e.key === "Space") {
        e.preventDefault();
        advance();
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        if (left && right) {
          const leftScore = left.score_overall ?? 0;
          const rightScore = right.score_overall ?? 0;
          if (leftScore < rightScore) onDecision(left.id, "discard");
          else onDecision(right.id, "discard");
        }
        advance();
      }
      if (e.key === "s" || e.key === "S") {
        setSliderMode((v) => !v);
      }
    },
    [left, right, onDecision, advance]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  useEffect(() => { setIndex(0); }, [photos.length]);

  // Slider drag handlers
  const handlePointerDown = useCallback(() => { dragging.current = true; }, []);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    setSliderPos(Math.max(5, Math.min(95, x)));
  }, []);

  const handlePointerUp = useCallback(() => { dragging.current = false; }, []);

  if (!left && !right) {
    return (
      <div className="no-compare-content">
        所有照片已筛选完毕。
        <button className="toolbar-btn" onClick={() => onRefresh()} style={{ marginLeft: 12 }}>
          刷新
        </button>
      </div>
    );
  }

  if (sliderMode && left && right) {
    return (
      <div
        className="slider-compare"
        ref={containerRef}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        {/* Right image (full background) */}
        <img className="slider-img slider-img-right" src={mediumUrl(sessionId, right.id)} alt={right.filename} />
        {/* Left image (clipped) */}
        <div className="slider-clip-left" style={{ width: `${sliderPos}%` }}>
          <img className="slider-img" src={mediumUrl(sessionId, left.id)} alt={left.filename} />
        </div>
        {/* Divider */}
        <div className="slider-divider" style={{ left: `${sliderPos}%` }} onPointerDown={handlePointerDown}>
          <div className="slider-handle">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="8,4 4,12 8,20" /><polyline points="16,4 20,12 16,20" />
            </svg>
          </div>
        </div>
        {/* Labels */}
        <div className="slider-label slider-label-left">A — {left.filename}</div>
        <div className="slider-label slider-label-right">B — {right.filename}</div>
        {/* Scores */}
        <div className="slider-scores slider-scores-left">
          <div className="score-chip">综合 <span>{left.score_overall?.toFixed(1) ?? "-"}</span></div>
        </div>
        <div className="slider-scores slider-scores-right">
          <div className="score-chip">综合 <span>{right.score_overall?.toFixed(1) ?? "-"}</span></div>
        </div>
        {/* Toggle button */}
        <button className="slider-toggle-btn" onClick={() => setSliderMode(false)} title="切换到并排模式 (S)">
          并排
        </button>
        <div className="compare-hint">
          <span><kbd>←</kbd> 保留左图</span>
          <span><kbd>→</kbd> 保留右图</span>
          <span><kbd>Space</kbd> 跳过</span>
          <span><kbd>Del</kbd> 淘汰低分</span>
          <span><kbd>S</kbd> 切换模式</span>
        </div>
      </div>
    );
  }

  return (
    <div className="compare-view">
      <ComparePane photo={left} sessionId={sessionId} side="left" />
      <ComparePane photo={right} sessionId={sessionId} side="right" />
      <button className="slider-toggle-btn" onClick={() => setSliderMode(true)} title="切换到滑动对比 (S)">
        滑动
      </button>
      <div className="compare-hint">
        <span><kbd>←</kbd> 保留左图</span>
        <span><kbd>→</kbd> 保留右图</span>
        <span><kbd>Space</kbd> 跳过</span>
        <span><kbd>Del</kbd> 淘汰低分</span>
        <span><kbd>S</kbd> 切换模式</span>
      </div>
    </div>
  );
}

function ComparePane({ photo, sessionId, side }: { photo: PhotoInfo | null; sessionId: string; side: string }) {
  if (!photo) {
    return (
      <div className="compare-pane">
        <span className="compare-label">Empty</span>
      </div>
    );
  }

  return (
    <div className="compare-pane" onClick={() => {}}>
      <span className="compare-label">
        {side === "left" ? "A" : "B"} — {photo.filename}
      </span>
      <img
        src={mediumUrl(sessionId, photo.id)}
        alt={photo.filename}
        loading="lazy"
      />
      {photo.score_overall != null && (
        <div className="compare-scores">
          <div className="score-chip">构图 <span>{photo.score_composition?.toFixed(1)}</span></div>
          <div className="score-chip">色彩 <span>{photo.score_color?.toFixed(1)}</span></div>
          <div className="score-chip">光影 <span>{photo.score_lighting?.toFixed(1)}</span></div>
          <div className="score-chip">综合 <span>{photo.score_overall.toFixed(1)}</span></div>
        </div>
      )}
    </div>
  );
}
