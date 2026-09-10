import { useState, useEffect } from "react";
import { exportResults } from "../api/client";

interface Props {
  sessionId: string;
  photoIds: string[];
  sourceFolder: string;
}

function defaultTarget(sourceFolder: string): string {
  if (!sourceFolder) return "";
  const now = new Date();
  const ts = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
    "_",
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0"),
  ].join("");
  return sourceFolder.replace(/[\\/]$/, "") + "/筛选结果_" + ts;
}

export default function ExportPanel({ sessionId, photoIds, sourceFolder }: Props) {
  const [targetFolder, setTargetFolder] = useState(() => defaultTarget(sourceFolder));
  const [format, setFormat] = useState("json");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (sourceFolder) {
      setTargetFolder(defaultTarget(sourceFolder));
    }
  }, [sourceFolder]);

  const handleBrowse = async () => {
    try {
      const res = await fetch("/api/browse-folder");
      const data = await res.json();
      if (data.path) setTargetFolder(data.path);
    } catch { /* ignore */ }
  };

  const handleExport = async () => {
    if (!targetFolder.trim() || photoIds.length === 0) return;
    setStatus("导出中...");
    try {
      const result = await exportResults(sessionId, photoIds, targetFolder.trim(), format);
      setStatus("完成：" + result.copied_count + " 张已复制。报告：" + result.report_path);
    } catch (e: any) {
      setStatus("错误：" + e.message);
    }
  };

  return (
    <div className="export-panel">
      {status && <span className="export-result">{status}</span>}
      <input
        type="text"
        placeholder="导出到文件夹..."
        value={targetFolder}
        onChange={(e) => setTargetFolder(e.target.value)}
      />
      <button className="export-browse-btn" onClick={handleBrowse} title="浏览">
        ...
      </button>
      <select value={format} onChange={(e) => setFormat(e.target.value)}>
        <option value="json">JSON 报告</option>
        <option value="csv">CSV 报告</option>
      </select>
      <button onClick={handleExport} disabled={!targetFolder.trim() || photoIds.length === 0}>
        导出 ({photoIds.length})
      </button>
    </div>
  );
}
