import { useState, useEffect, useCallback, useRef } from "react";
import { thumbUrl } from "../api/client";
import type { PhotoInfo } from "../api/client";
import PhotoDetailModal from "./PhotoDetailModal";

export type SortMode = "default" | "score" | "filename" | "decision";

interface Props {
  sessionId: string;
  photos: PhotoInfo[];
  onDecision: (photoId: string, decision: "keep" | "discard") => void;
  sortMode?: SortMode;
}

export default function PhotoGrid({ sessionId, photos, onDecision, sortMode = "default" }: Props) {
  const [focusIndex, setFocusIndex] = useState(-1);
  const [detailPhoto, setDetailPhoto] = useState<PhotoInfo | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Sort photos based on mode
  const sortedPhotos = (() => {
    if (sortMode === "default") return photos;
    const arr = [...photos];
    switch (sortMode) {
      case "score":
        arr.sort((a, b) => (b.score_overall ?? 0) - (a.score_overall ?? 0));
        break;
      case "filename":
        arr.sort((a, b) => a.filename.localeCompare(b.filename));
        break;
      case "decision":
        arr.sort((a, b) => {
          const order = { keep: 0, discard: 2 };
          const av = a.user_decision ? (order[a.user_decision as "keep"] ?? 1) : 1;
          const bv = b.user_decision ? (order[b.user_decision as "keep"] ?? 1) : 1;
          return av - bv;
        });
        break;
    }
    return arr;
  })();

  // Calculate how many columns are currently displayed
  const getCols = useCallback(() => {
    if (!gridRef.current || sortedPhotos.length === 0) return 1;
    const gridWidth = gridRef.current.clientWidth;
    return Math.max(1, Math.floor((gridWidth + 6) / (220 + 6)));
  }, [sortedPhotos.length]);

  const scrollToCard = useCallback((idx: number) => {
    const card = cardRefs.current[idx];
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (sortedPhotos.length === 0) return;
      // Don't capture keys when detail modal is open
      if (detailPhoto) return;
      // Don't capture keys when an input/button is focused
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

      const cols = getCols();

      switch (e.key) {
        case "ArrowRight": {
          e.preventDefault();
          const next = focusIndex < sortedPhotos.length - 1 ? focusIndex + 1 : 0;
          setFocusIndex(next);
          scrollToCard(next);
          break;
        }
        case "ArrowLeft": {
          e.preventDefault();
          const prev = focusIndex > 0 ? focusIndex - 1 : sortedPhotos.length - 1;
          setFocusIndex(prev);
          scrollToCard(prev);
          break;
        }
        case "ArrowDown": {
          e.preventDefault();
          const down = Math.min(focusIndex + cols, sortedPhotos.length - 1);
          setFocusIndex(down);
          scrollToCard(down);
          break;
        }
        case "ArrowUp": {
          e.preventDefault();
          const up = Math.max(focusIndex - cols, 0);
          setFocusIndex(up);
          scrollToCard(up);
          break;
        }
        case "Enter": {
          if (focusIndex >= 0 && focusIndex < sortedPhotos.length) {
            e.preventDefault();
            setDetailPhoto(sortedPhotos[focusIndex]);
          }
          break;
        }
        case "k":
        case "K": {
          if (focusIndex >= 0 && focusIndex < sortedPhotos.length) {
            e.preventDefault();
            onDecision(sortedPhotos[focusIndex].id, "keep");
          }
          break;
        }
        case "d":
        case "D": {
          if (focusIndex >= 0 && focusIndex < sortedPhotos.length) {
            e.preventDefault();
            onDecision(sortedPhotos[focusIndex].id, "discard");
          }
          break;
        }
      }
    },
    [focusIndex, sortedPhotos, onDecision, getCols, scrollToCard, detailPhoto]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Reset focus when photo list changes
  useEffect(() => {
    if (focusIndex >= sortedPhotos.length) setFocusIndex(sortedPhotos.length - 1);
  }, [sortedPhotos.length, focusIndex]);

  if (sortedPhotos.length === 0) {
    return <div className="no-compare-content">暂无照片</div>;
  }

  // Get live version of detail photo from sorted list
  const liveDetailPhoto = detailPhoto
    ? sortedPhotos.find((p) => p.id === detailPhoto.id) ?? detailPhoto
    : null;

  return (
    <>
    {liveDetailPhoto && (
      <PhotoDetailModal
        photo={liveDetailPhoto}
        sessionId={sessionId}
        onClose={() => setDetailPhoto(null)}
        onDecision={(pid, dec) => {
          onDecision(pid, dec);
          // Update detail photo reference
          setDetailPhoto((prev) => prev && prev.id === pid ? { ...prev, user_decision: dec } : prev);
        }}
      />
    )}
    <div className="photo-grid" ref={gridRef}>
      {sortedPhotos.map((photo, idx) => {
        const isKept = photo.user_decision === "keep";
        const isDiscarded = photo.user_decision === "discard";
        const isFocused = idx === focusIndex;

        let cardClass = "photo-card";
        if (isKept) cardClass += " kept";
        if (isDiscarded) cardClass += " discarded";
        if (isFocused) cardClass += " focused";

        return (
          <div
            key={photo.id}
            ref={(el) => { cardRefs.current[idx] = el; }}
            className={cardClass}
            onClick={() => setFocusIndex(idx)}
            onDoubleClick={() => setDetailPhoto(photo)}
          >
            <img
              src={thumbUrl(sessionId, photo.id)}
              alt={photo.filename}
              loading="lazy"
            />
            {isKept && <span className="photo-card-decision keep-badge">已保留</span>}
            {isDiscarded && <span className="photo-card-decision discard-badge">已淘汰</span>}

            <div className="photo-card-overlay">
              <div className="photo-card-badges">
                {photo.technical_issues.map((issue) => (
                  <span key={issue} className="badge badge-issue">{issue}</span>
                ))}
                {photo.has_closed_eyes && photo.eyes_closed_is_emotional && (
                  <span className="badge badge-emotion">情感瞬间</span>
                )}
                {photo.cluster_size != null && photo.cluster_size > 1 && (
                  <span className="badge badge-cluster">
                    {photo.cluster_rank === 0 ? "★" : ""}连拍{photo.cluster_size}/{photo.cluster_rank! + 1}
                  </span>
                )}
                {photo.score_overall != null && (
                  <span className="badge badge-score">
                    {photo.score_overall.toFixed(1)}
                  </span>
                )}
              </div>
              <div className="photo-card-actions" onClick={(e) => e.stopPropagation()}>
                <button
                  className="card-action-btn keep-btn"
                  onClick={() => onDecision(photo.id, "keep")}
                >
                  保留
                </button>
                <button
                  className="card-action-btn discard-btn"
                  onClick={() => onDecision(photo.id, "discard")}
                >
                  淘汰
                </button>
              </div>
            </div>

            {isFocused && (
              <div className="photo-card-kbd-hint">
                <kbd>K</kbd> 保留 <kbd>D</kbd> 淘汰 <kbd>Enter</kbd> 详情 <kbd>↑↓←→</kbd> 导航
              </div>
            )}
          </div>
        );
      })}
    </div>
    </>
  );
}
