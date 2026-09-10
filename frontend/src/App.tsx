import { useState, useCallback, useRef, useEffect } from "react";
import FolderSelector from "./components/FolderSelector";
import ProgressBar from "./components/ProgressBar";
import PhotoGrid from "./components/PhotoGrid";
import type { SortMode } from "./components/PhotoGrid";
import ComparisonView from "./components/ComparisonView";
import ClusterPanel from "./components/ClusterPanel";
import ExportPanel from "./components/ExportPanel";
import type { PhotoInfo, ClusterGroup, BatchAction } from "./api/client";
import {
  startScan, getProgress, getPhotos, getClusters, setDecision, autoDecide, batchDecide,
} from "./api/client";

type ViewMode = "grid" | "compare" | "clusters";

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [photos, setPhotos] = useState<PhotoInfo[]>([]);
  const [clusters, setClusters] = useState<ClusterGroup[]>([]);
  const [phase, setPhase] = useState<string>("idle");
  const [progress, setProgress] = useState({ total: 0, processed: 0, message: "" });
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [photosVersion, setPhotosVersion] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [sourceFolder, setSourceFolder] = useState<string>("");
  const [photoFilter, setPhotoFilter] = useState<"all" | "keep" | "discard">("all");
  const [sortMode, setSortMode] = useState<SortMode>("default");
  const [toast, setToast] = useState<string | null>(null);

  // Undo stack: { photoId, previousDecision }
  const undoStack = useRef<{ photoId: string; prev: string | null }[]>([]);

  const refreshPhotos = useCallback(async () => {
    if (!sessionId) return;
    const p = await getPhotos(sessionId);
    setPhotos(p);
    setPhotosVersion((v) => v + 1);
  }, [sessionId]);

  const refreshClusters = useCallback(async () => {
    if (!sessionId) return;
    const c = await getClusters(sessionId);
    setClusters(c);
  }, [sessionId]);
  const refreshPhotosWithId = useCallback(async (sid: string) => {
    const p = await getPhotos(sid);
    setPhotos(p);
    setPhotosVersion((v) => v + 1);
  }, []);

  const refreshClustersWithId = useCallback(async (sid: string) => {
    const c = await getClusters(sid);
    setClusters(c);
  }, []);

  const handleStartScan = useCallback(async (folderPath: string) => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setSourceFolder(folderPath);
    const { session_id } = await startScan(folderPath);
    setSessionId(session_id);
    setPhase("scanning");
    setViewMode("grid");

    // Poll progress
    const poll = setInterval(async () => {
      try {
        const p = await getProgress(session_id);
        setProgress({ total: p.total, processed: p.processed, message: p.message });
        if (p.phase === "done" || p.phase === "error") {
          clearInterval(poll);
          // Load photos BEFORE setting phase, so grid never shows empty
          await refreshPhotosWithId(session_id);
          await refreshClustersWithId(session_id);
          setPhase(p.phase);
        } else {
          setPhase(p.phase);
        }
      } catch (err) { console.error("Poll error:", err); }
    }, 500);
    pollRef.current = poll;
  }, [refreshPhotosWithId, refreshClustersWithId]);

  const handleRestoreSession = useCallback(async (sid: string, folderPath: string) => {
    setSourceFolder(folderPath);
    setSessionId(sid);
    await refreshPhotosWithId(sid);
    await refreshClustersWithId(sid);
    setPhase("done");
    setViewMode("grid");
  }, [refreshPhotosWithId, refreshClustersWithId]);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  }, []);

  const handleAutoDecide = useCallback(async () => {
    if (!sessionId) return;
    await autoDecide(sessionId);
    await refreshPhotos();
    await refreshClusters();
  }, [sessionId, refreshPhotos, refreshClusters]);

  const handleDecision = useCallback(async (photoId: string, decision: "keep" | "discard") => {
    if (!sessionId) return;
    // Save previous state for undo
    const prev = photos.find((p) => p.id === photoId)?.user_decision ?? null;
    undoStack.current.push({ photoId, prev });
    if (undoStack.current.length > 100) undoStack.current.shift();

    await setDecision(sessionId, photoId, decision);
    setPhotos((prevPhotos) =>
      prevPhotos.map((p) => (p.id === photoId ? { ...p, user_decision: decision } : p))
    );
    setPhotosVersion((v) => v + 1);
    setClusters((prev) =>
      prev.map((c) => ({
        ...c,
        photos: c.photos.map((p) =>
          p.id === photoId ? { ...p, user_decision: decision } : p
        ),
      }))
    );
  }, [sessionId, photos]);

  const handleUndo = useCallback(async () => {
    if (!sessionId || undoStack.current.length === 0) return;
    const last = undoStack.current.pop()!;
    const restoreTo = last.prev === null ? "clear" : last.prev;
    await setDecision(sessionId, last.photoId, restoreTo as "keep" | "discard" | "clear");
    await refreshPhotos();
    await refreshClusters();
    showToast("已撤销");
  }, [sessionId, refreshPhotos, refreshClusters, showToast]);

  const handleBatchDecide = useCallback(async (action: BatchAction) => {
    if (!sessionId) return;
    const result = await batchDecide(sessionId, action);
    await refreshPhotos();
    await refreshClusters();
    const labels: Record<string, string> = {
      "keep-best": "保留组内最佳",
      "discard-issues": "淘汰技术问题",
      "clear": "清除所有决策",
    };
    showToast(`${labels[action]}：${result.affected} 张已处理`);
  }, [sessionId, refreshPhotos, refreshClusters, showToast]);


  const isProcessing = phase !== "done" && phase !== "idle" && phase !== "error";

  // Global Ctrl+Z for undo
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        handleUndo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleUndo]);

  return (
    <>
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">Auto Photo</h1>
        <span className="app-subtitle">AI 照片审美筛选</span>
        <nav className="app-nav">
          <button
            className={`nav-btn ${viewMode === "grid" ? "active" : ""}`}
            onClick={() => setViewMode("grid")}
            disabled={!sessionId}
          >
            网格浏览
          </button>
          <button
            className={`nav-btn ${viewMode === "compare" ? "active" : ""}`}
            onClick={() => setViewMode("compare")}
            disabled={!sessionId || photos.length === 0}
          >
            对比模式
          </button>
          <button
            className={`nav-btn ${viewMode === "clusters" ? "active" : ""}`}
            onClick={() => { setViewMode("clusters"); refreshClusters(); }}
            disabled={!sessionId || photos.length === 0}
          >
            连拍分组
          </button>
        </nav>
      </header>

      <main className="app-main">
        {!sessionId && (
          <div className="welcome-screen">
            <FolderSelector onStart={handleStartScan} onRestore={handleRestoreSession} />
          </div>
        )}

        {isProcessing && (
          <ProgressBar
            phase={phase}
            total={progress.total}
            processed={progress.processed}
            message={progress.message}
          />
        )}

        {sessionId && phase === "done" && (
          <>
            {viewMode === "grid" && (
              <>
                <div className="toolbar-row">
                  <span className="toolbar-label">排序：</span>
                  {(["default", "score", "filename", "decision"] as SortMode[]).map((m) => (
                    <button
                      key={m}
                      className={`toolbar-btn${sortMode === m ? " active" : ""}`}
                      onClick={() => setSortMode(m)}
                    >
                      {m === "default" ? "默认" : m === "score" ? "评分" : m === "filename" ? "文件名" : "决策状态"}
                    </button>
                  ))}
                  <div className="toolbar-spacer" />
                  <button className="toolbar-btn batch-btn" onClick={() => handleBatchDecide("keep-best")}>
                    ★ 保留组内最佳
                  </button>
                  <button className="toolbar-btn batch-btn" onClick={() => handleBatchDecide("discard-issues")}>
                    ✗ 淘汰技术问题
                  </button>
                  <button className="toolbar-btn batch-btn" onClick={() => handleBatchDecide("clear")}>
                    ↻ 清除决策
                  </button>
                  <button className="toolbar-btn undo-btn" onClick={handleUndo} title="Ctrl+Z">
                    ↶ 撤销
                  </button>
                </div>
                <PhotoGrid
                  sessionId={sessionId}
                  photos={photos.filter((p) => photoFilter === "all" ? true : p.user_decision === photoFilter)}
                  onDecision={handleDecision}
                  sortMode={sortMode}
                />
              </>
            )}
            {viewMode === "compare" && (
              <ComparisonView
                sessionId={sessionId}
                photos={photos}
                onDecision={handleDecision}
                onRefresh={refreshPhotos}
              />
            )}
            {viewMode === "clusters" && (
              <ClusterPanel
                sessionId={sessionId}
                clusters={clusters}
                onDecision={handleDecision}
              />
            )}
          </>
        )}

        {sessionId && phase === "error" && (
          <div className="error-banner">
            分析过程出错。请刷新或重新开始。
            <button onClick={() => { setSessionId(null); setPhase("idle"); }}>重新开始</button>
          </div>
        )}
      </main>

      {sessionId && phase === "done" && (
        <footer className="app-footer">
          <div className="footer-stats">
            <span className="filter-buttons">
              <button className={"filter-btn" + (photoFilter === "all" ? " active" : "")} onClick={() => setPhotoFilter("all")}>全部 ({photos.length})</button>
              <button className={"filter-btn filter-keep" + (photoFilter === "keep" ? " active" : "")} onClick={() => setPhotoFilter("keep")}>已保留 ({photos.filter((p) => p.user_decision === "keep").length})</button>
              <button className={"filter-btn filter-discard" + (photoFilter === "discard" ? " active" : "")} onClick={() => setPhotoFilter("discard")}>已淘汰 ({photos.filter((p) => p.user_decision === "discard").length})</button>
            </span>
          </div>
          <div className="footer-center">
            <button className="auto-decide-btn" onClick={handleAutoDecide}>
              AI 推荐筛选
            </button>
          </div>
          <div className="footer-actions">
            <ExportPanel
              sessionId={sessionId}
              photoIds={photos.filter((p) => p.user_decision === "keep").map((p) => p.id)}
              sourceFolder={sourceFolder}
            />
          </div>
        </footer>
      )}
    </div>
    {toast && <div className="toast-notification">{toast}</div>}
    </>
  );
}

export default App;
