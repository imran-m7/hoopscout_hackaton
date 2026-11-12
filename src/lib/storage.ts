import { useCallback, useEffect, useMemo, useState } from "react";

const EVT = "hoopscout-storage";
const ROLE_KEY = "hoopscout.role";
const SHORTLIST_KEY = "hoopscout.shortlist";
const NOTE_KEY = (id: string) => `hoopscout.note.${id}`;

function read(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage full / blocked */
  }
  try {
    window.dispatchEvent(new Event(EVT));
  } catch {
    /* ignore */
  }
}
function subscribe(cb: () => void) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(EVT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVT, cb);
    window.removeEventListener("storage", cb);
  };
}
function useStored(key: string): string | null {
  // First render (server + hydration) is always null; stored value is read after mount.
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    const sync = () => setValue(read(key));
    sync();
    return subscribe(sync);
  }, [key]);
  return value;
}

export type Role = "coach" | "scout";

export function useRole(): [Role | null, (r: Role | null) => void] {
  const raw = useStored(ROLE_KEY);
  const role = raw === "coach" || raw === "scout" ? raw : null;
  const set = useCallback((r: Role | null) => write(ROLE_KEY, r), []);
  return [role, set];
}

export function useShortlist() {
  const raw = useStored(SHORTLIST_KEY);
  const ids = useMemo<string[]>(() => {
    try {
      const v = JSON.parse(raw ?? "[]");
      return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
    } catch {
      return [];
    }
  }, [raw]);
  const toggle = useCallback(
    (id: string) => {
      const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
      write(SHORTLIST_KEY, JSON.stringify(next));
    },
    [ids],
  );
  const has = useCallback((id: string) => ids.includes(id), [ids]);
  return { ids, toggle, has };
}

export function useNote(id: string): [string, (v: string) => void] {
  const raw = useStored(NOTE_KEY(id));
  const set = useCallback((v: string) => write(NOTE_KEY(id), v || null), [id]);
  return [raw ?? "", set];
}

export function readNote(id: string): string {
  return read(NOTE_KEY(id)) ?? "";
}

const CLUB_KEY = "hoopscout.coachClub";
export function useCoachClub(): [string | null, (c: string | null) => void] {
  const raw = useStored(CLUB_KEY);
  const set = useCallback((c: string | null) => write(CLUB_KEY, c && c.trim() ? c.trim() : null), []);
  return [raw && raw.trim() ? raw : null, set];
}

/** False during server render and the first client render; true once saved settings are loaded. */
export function useStorageReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  return ready;
}
