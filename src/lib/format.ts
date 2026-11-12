import type { AgeGroup, Gender } from "./types";

export const DASH = "—";
/** Shown for a skill score that is null (e.g. shooting_form before the elbow check exists). Never show 0. */
export const NOT_MEASURED = "not measured yet";

export function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

export function fmt(v: number | null | undefined, digits = 0, unit = ""): string {
  if (!isNum(v)) return DASH;
  return `${v.toFixed(digits)}${unit}`;
}

export function fmtSigned(v: number | null | undefined, digits = 0, unit = ""): string {
  if (!isNum(v)) return DASH;
  const s = v.toFixed(digits);
  return `${v > 0 ? "+" : ""}${s}${unit}`;
}

export function fmtText(v: string | null | undefined): string {
  return v && v.trim() ? v : DASH;
}

export function formatAge(months: number | null | undefined): string {
  if (!isNum(months)) return DASH;
  return `${Math.floor(months / 12)} y ${Math.round(months % 12)} m`;
}

export function scoreTone(v: number | null | undefined): "good" | "ok" | "weak" | "none" {
  if (!isNum(v)) return "none";
  if (v >= 70) return "good";
  if (v >= 50) return "ok";
  return "weak";
}

export const toneText = {
  good: "text-good",
  ok: "text-ok",
  weak: "text-weak",
  none: "text-neutral",
} as const;

export const toneBg = {
  good: "bg-good",
  ok: "bg-ok",
  weak: "bg-weak",
  none: "bg-neutral",
} as const;

export function ageMonthsFrom(birthDate: string, now = new Date()): number | null {
  const d = new Date(birthDate);
  if (Number.isNaN(d.getTime())) return null;
  let m = (now.getFullYear() - d.getFullYear()) * 12 + (now.getMonth() - d.getMonth());
  if (now.getDate() < d.getDate()) m -= 1;
  return m >= 0 ? m : null;
}

export function ageGroupFor(months: number | null): AgeGroup | null {
  if (!isNum(months)) return null;
  const y = months / 12;
  if (y < 10) return "U10";
  if (y < 12) return "U12";
  if (y < 14) return "U14";
  if (y < 16) return "U16";
  return "U18";
}

export function birthQuarterOf(birthDate: string): 1 | 2 | 3 | 4 | null {
  const d = new Date(birthDate);
  if (Number.isNaN(d.getTime())) return null;
  return (Math.floor(d.getMonth() / 3) + 1) as 1 | 2 | 3 | 4;
}

export function rankGroupLabel(gender: Gender, group: AgeGroup): string {
  return `${gender === "boy" ? "Boys" : "Girls"} ${group}`;
}

const AVG_HEIGHT: Record<Gender, number[]> = {
  boy: [139, 144, 150, 157, 164, 170, 174, 176, 177],
  girl: [138, 144, 151, 156, 160, 162, 163, 163, 164],
};

export function expectedHeight(gender: Gender, months: number): number {
  const idx = Math.min(8, Math.max(0, Math.floor(months / 12) - 10));
  return AVG_HEIGHT[gender][idx] ?? 160;
}

export function formatBytes(n: number): string {
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function cap(s: string | null | undefined): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : DASH;
}
