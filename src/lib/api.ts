import type { BiasData, CoachReport, Job, PlayerInput, PlayerReport, PlayerSummary } from "./types";
import { mockApi } from "@/mocks";

const BASE_URL = ((import.meta.env["VITE_API_URL"] as string | undefined) || "http://localhost:8000").replace(/\/$/, "");
const FORCE_MOCK = import.meta.env["VITE_USE_MOCK"] === "true";

/** Backend returns media paths like "/media/p1_shooting.mp4"; make them absolute so they load from the API host, not the frontend dev server. */
export function mediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^(https?:|blob:|data:)/i.test(url)) return url;
  return `${BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

// ---- Demo mode (mock data) state ----
let demo = FORCE_MOCK;
const listeners = new Set<() => void>();
export const isDemoMode = () => demo;
export const demoServerSnapshot = () => FORCE_MOCK;
export function subscribeDemo(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}
function enterDemo() {
  if (!demo) {
    demo = true;
    listeners.forEach((l) => l());
  }
}

export class ApiError extends Error {}
class Unreachable extends Error {}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...init, signal: AbortSignal.timeout(timeoutMs) });
  } catch {
    throw new Unreachable("API unreachable");
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    if (res.status >= 502 && res.status <= 504) throw new Unreachable("API unreachable");
    const msg = (body as { error?: string } | null)?.error;
    throw new ApiError(msg || `Request failed (${res.status})`);
  }
  return body as T;
}

async function withFallback<T>(real: () => Promise<T>, mock: () => Promise<T>): Promise<T> {
  if (demo) return mock();
  try {
    return await real();
  } catch (e) {
    if (e instanceof Unreachable) {
      enterDemo();
      return mock();
    }
    throw e;
  }
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getHealth = () =>
  withFallback(() => request<{ status: string }>("/api/health", undefined, 3000), mockApi.getHealth);

export const getPlayers = () =>
  withFallback(() => request<PlayerSummary[]>("/api/players"), mockApi.getPlayers);

export const getPlayer = (id: string) =>
  withFallback(() => request<PlayerReport>(`/api/players/${encodeURIComponent(id)}`), () => mockApi.getPlayer(id));

export const createPlayer = (input: PlayerInput) =>
  withFallback(() => request<PlayerSummary>("/api/players", json(input)), () => mockApi.createPlayer(input));

export function uploadVideo(
  id: string,
  kind: Job["kind"],
  file: File,
  onProgress?: (pct: number) => void,
): Promise<Job> {
  const real = () =>
    new Promise<Job>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE_URL}/api/players/${encodeURIComponent(id)}/videos`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          /* ignore */
        }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as Job);
        else if (xhr.status >= 502 && xhr.status <= 504) reject(new Unreachable("API unreachable"));
        else reject(new ApiError((body as { error?: string } | null)?.error || `Upload failed (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Unreachable("API unreachable"));
      const fd = new FormData();
      fd.append("kind", kind);
      fd.append("file", file);
      xhr.send(fd);
    });
  return withFallback(real, () => mockApi.uploadVideo(id, kind, file, onProgress));
}

export const getJob = (jobId: string) =>
  withFallback(() => request<Job>(`/api/jobs/${encodeURIComponent(jobId)}`), () => mockApi.getJob(jobId));

export const analyzePlayer = (id: string) =>
  withFallback(
    () => request<PlayerReport>(`/api/players/${encodeURIComponent(id)}/analyze`, { method: "POST" }, 120000),
    () => mockApi.analyzePlayer(id),
  );

export const regenerateCoachReport = (id: string) =>
  withFallback(
    () => request<CoachReport>(`/api/players/${encodeURIComponent(id)}/coach-report`, { method: "POST" }, 60000),
    () => mockApi.regenerateCoachReport(id),
  );

export const getBias = () => withFallback(() => request<BiasData>("/api/bias"), mockApi.getBias);
