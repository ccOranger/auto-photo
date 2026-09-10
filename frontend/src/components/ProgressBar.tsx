interface Props {
  phase: string;
  total: number;
  processed: number;
  message: string;
}

const PHASE_LABELS: Record<string, string> = {
  scanning: "扫描文件夹",
  analyzing: "技术质量分析",
  features: "特征提取",
  clustering: "相似照片聚类",
  scoring: "美学评分",
};

export default function ProgressBar({ phase, total, processed, message }: Props) {
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <div className="progress-overlay">
      <div className="progress-phase">
        {PHASE_LABELS[phase] || message}
      </div>
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div style={{ fontSize: 12, color: "#666" }}>
        {processed} / {total}
      </div>
    </div>
  );
}
