const API_BASE = "/api";

export interface PhotoInfo {
  id: string;
  path: string;
  filename: string;
  status: string;
  is_sharp: boolean | null;
  sharpness_score: number | null;
  is_exposed: boolean | null;
  has_closed_eyes: boolean | null;
  face_count: number | null;
  technical_issues: string[];
  eyes_closed_is_emotional: boolean | null;
  cluster_id: number | null;
  cluster_rank: number | null;
  cluster_size: number | null;
  score_composition: number | null;
  score_color: number | null;
  score_lighting: number | null;
  score_overall: number | null;
  user_decision: string | null;
}

export interface ScanProgress {
  phase: string;
  total: number;
  processed: number;
  message: string;
  error: string | null;
}

export interface ClusterGroup {
  cluster_id: number;
  photos: PhotoInfo[];
  best_index: number;
}

export async function startScan(folderPath: string): Promise<{ session_id: string }> {
  const res = await fetch(`${API_BASE}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_path: folderPath }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getProgress(sessionId: string): Promise<ScanProgress> {
  const res = await fetch(`${API_BASE}/progress/${sessionId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getPhotos(sessionId: string, params?: Record<string, string>): Promise<PhotoInfo[]> {
  const url = new URL(`${API_BASE}/photos/${sessionId}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getClusters(sessionId: string): Promise<ClusterGroup[]> {
  const res = await fetch(`${API_BASE}/clusters/${sessionId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function setDecision(sessionId: string, photoId: string, decision: "keep" | "discard" | "clear"): Promise<void> {
  const res = await fetch(`${API_BASE}/photos/${sessionId}/${photoId}/decision?decision=${decision}`, {
    method: "PUT",
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function exportResults(
  sessionId: string,
  photoIds: string[],
  targetFolder: string,
  format: string = "json"
): Promise<{ copied_count: number; report_path: string; errors: string[] }> {
  const res = await fetch(`${API_BASE}/export/${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds, target_folder: targetFolder, format }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function imageUrl(sessionId: string, photoId: string): string {
  return `${API_BASE}/photos/${sessionId}/${photoId}/image`;
}

export function thumbUrl(sessionId: string, photoId: string): string {
  return `${API_BASE}/thumbs/${sessionId}/${photoId}`;
}

export function mediumUrl(sessionId: string, photoId: string): string {
  return `${API_BASE}/thumbs/${sessionId}/${photoId}?size=1200`;
}

// ── Saved Sessions ──────────────────────────────────────────────────────────

export interface SavedSession {
  session_id: string;
  folder_path: string;
  phase: string;
  total: number;
  keepers: number;
  created_at: string;
}

export async function listSessions(): Promise<SavedSession[]> {
  const res = await fetch(`${API_BASE}/sessions`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function restoreSession(sessionId: string): Promise<{ session_id: string; message: string }> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/restore`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}

// ── Auto Decide ──────────────────────────────────────────────────────────────

export async function autoDecide(sessionId: string): Promise<{ decided: number; skipped: number }> {
  const res = await fetch(`${API_BASE}/auto-decide/${sessionId}`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Batch Decide ────────────────────────────────────────────────────────────

export type BatchAction = "keep-best" | "discard-issues" | "clear";

export async function batchDecide(sessionId: string, action: BatchAction): Promise<{ affected: number; action: string }> {
  const res = await fetch(`${API_BASE}/batch-decide/${sessionId}/${action}`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
