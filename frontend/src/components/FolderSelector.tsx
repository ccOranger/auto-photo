import { useState, useEffect } from "react";
import { listSessions, restoreSession, deleteSession } from "../api/client";
import type { SavedSession } from "../api/client";

interface Props {
  onStart: (folderPath: string) => void;
  onRestore: (sessionId: string, folderPath: string) => void;
}

export default function FolderSelector({ onStart, onRestore }: Props) {
  const [folderPath, setFolderPath] = useState("");
  const [browsing, setBrowsing] = useState(false);
  const [sessions, setSessions] = useState<SavedSession[]>([]);

  useEffect(() => {
    listSessions().then(setSessions).catch(() => {});
  }, []);

  const handleBrowse = async () => {
    setBrowsing(true);
    try {
      const res = await fetch("/api/browse-folder");
      const data = await res.json();
      if (data.path) {
        setFolderPath(data.path);
      }
    } catch (e) {
      console.error("Browse failed:", e);
    } finally {
      setBrowsing(false);
    }
  };

  const handleSubmit = () => {
    const trimmed = folderPath.trim();
    if (trimmed) onStart(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit();
  };

  const handleRestore = async (sid: string) => {
    try {
      await restoreSession(sid);
      const s = sessions.find((s) => s.session_id === sid);
      if (s) onRestore(sid, s.folder_path);
    } catch (e) {
      console.error("Restore failed:", e);
    }
  };

  const handleDelete = async (sid: string) => {
    try {
      await deleteSession(sid);
      setSessions((prev) => prev.filter((s) => s.session_id !== sid));
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  const formatDate = (iso: string) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString("zh-CN") + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
  };

  const folderName = (p: string) => {
    const parts = p.replace(/[\\/]+$/, "").split(/[\\/]/);
    return parts[parts.length - 1] || p;
  };

  return (
    <div className="folder-selector">
      <h2>选择照片文件夹开始筛选</h2>
      <p>
        AI 将自动检测模糊、过曝、欠曝、闭眼等技术问题；
        提取图像特征进行相似照片分组；
        并基于构图、色彩、光影给出审美评分。
      </p>
      <div className="folder-input-row">
        <button
          className="browse-btn"
          onClick={handleBrowse}
          disabled={browsing}
        >
          {browsing ? "选择中..." : "选择文件夹"}
        </button>
        <input
          type="text"
          placeholder="或手动输入文件夹路径，如 D:\Photos\2024"
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          className="start-btn"
          onClick={handleSubmit}
          disabled={!folderPath.trim()}
        >
          开始分析
        </button>
      </div>

      {sessions.length > 0 && (
        <div className="saved-sessions">
          <h3>历史会话</h3>
          <ul className="session-list">
            {sessions.map((s) => (
              <li key={s.session_id} className="session-item">
                <div className="session-info">
                  <span className="session-folder">{folderName(s.folder_path)}</span>
                  <span className="session-meta">
                    {s.total} 张 · {s.keepers} 已保留 · {formatDate(s.created_at)}
                  </span>
                </div>
                <div className="session-actions">
                  <button className="restore-btn" onClick={() => handleRestore(s.session_id)}>恢复</button>
                  <button className="session-delete-btn" onClick={() => handleDelete(s.session_id)}>删除</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
