import type { BiasData, CoachReport, Job, PlayerInput, PlayerReport, PlayerSummary, SkillScores } from "@/lib/types";
import { ageGroupFor, ageMonthsFrom, birthQuarterOf, expectedHeight, rankGroupLabel } from "@/lib/format";
import { DEFAULT_WEIGHTS, SKILLS, rankPlayers, weightedAverage } from "@/lib/scoring";
import { buildMockPlayers, experienceBonus } from "./players";
import { FULL_REPORT_ID, biasFrom, coachReportFor, fullReport, lightReport } from "./report";

let store: PlayerSummary[] | null = null;
function players(): PlayerSummary[] {
  if (!store) store = buildMockPlayers();
  return store;
}
const jobs = new Map<string, { job: Job; start: number }>();
const coachOverrides = new Map<string, CoachReport>();
const analyzed = new Set<string>();

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
let counter = 0;

function hash(s: string): number {
  let h = 7;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 1000;
  return h;
}

function report(id: string): PlayerReport {
  const all = players();
  const p = all.find((x) => x.id === id);
  if (!p) throw new Error("Player not found");
  const r = id === FULL_REPORT_ID ? fullReport(p, all) : lightReport(p, all);
  if (analyzed.has(id)) {
    const f = fullReport(p, all);
    r.shooting = f.shooting;
    r.dribbling = f.dribbling;
    r.jump = f.jump;
    r.sessions = f.sessions.slice(-1);
  }
  const c = coachOverrides.get(id);
  if (c) r.coach_report = c;
  return clone(r);
}

const STEPS = ["Queued", "Detecting body pose", "Tracking the ball", "Measuring movements", "Drawing annotated video", "Done"];

export const mockApi = {
  async getHealth() {
    return { status: "ok", mock: true };
  },
  async getPlayers(): Promise<PlayerSummary[]> {
    await wait(250);
    return clone(players());
  },
  async getPlayer(id: string): Promise<PlayerReport> {
    await wait(250);
    return report(id);
  },
  async createPlayer(input: PlayerInput): Promise<PlayerSummary> {
    await wait(400);
    const months = ageMonthsFrom(input.birth_date) ?? 156;
    const group = ageGroupFor(months) ?? "U14";
    const empty = Object.fromEntries(SKILLS.map((k) => [k, null])) as SkillScores;
    const p: PlayerSummary = {
      id: `new-${Date.now()}-${++counter}`,
      is_real: true,
      name: input.name,
      gender: input.gender,
      age_months: months,
      age_group: group,
      rank_group: rankGroupLabel(input.gender, group),
      birth_quarter: birthQuarterOf(input.birth_date) ?? 1,
      height_cm: input.height_cm,
      height_diff_cm: Math.round(input.height_cm - expectedHeight(input.gender, months)),
      maturity_offset_years: input.sitting_height_cm ? -0.4 : null,
      dominant_hand: input.dominant_hand,
      position: input.position,
      years_playing: input.years_playing,
      club: input.club,
      town: input.town,
      status: "provisional",
      provisional_reason: "videos not analyzed yet",
      scores: empty,
      fair_scores: { ...empty },
      experience_bonus: experienceBonus(input.years_playing),
      raw_score: 0,
      fair_score: 0,
      score_margin: 5,
      raw_rank: null,
      fair_rank: null,
      rank_change: null,
      hidden_gem: false,
      breakdown: [],
      photo_url: null,
    };
    store = [...players(), p];
    return clone(p);
  },
  async uploadVideo(id: string, kind: Job["kind"], file: File, onProgress?: (pct: number) => void): Promise<Job> {
    const steps = 12;
    const delay = Math.min(180, 60 + file.size / 5_000_000);
    for (let i = 1; i <= steps; i++) {
      await wait(delay);
      onProgress?.(Math.round((i / steps) * 100));
    }
    const job: Job = { job_id: `job-${kind}-${Date.now()}`, player_id: id, kind, status: "queued", progress: 0, step: "Queued", error: null };
    jobs.set(job.job_id, { job, start: Date.now() });
    return clone(job);
  },
  async getJob(jobId: string): Promise<Job> {
    await wait(100);
    const entry = jobs.get(jobId);
    if (!entry) throw new Error("Job not found");
    const elapsed = (Date.now() - entry.start) / 1000;
    const total = entry.job.kind === "shooting" ? 9 : entry.job.kind === "dribbling" ? 7 : 5;
    const progress = Math.min(100, Math.round((elapsed / total) * 100));
    const step = STEPS[Math.min(STEPS.length - 1, Math.floor((progress / 100) * (STEPS.length - 1)))] ?? "Processing";
    return { ...entry.job, status: progress >= 100 ? "done" : progress > 0 ? "running" : "queued", progress, step };
  },
  async analyzePlayer(id: string): Promise<PlayerReport> {
    await wait(800);
    const all = players();
    const p = all.find((x) => x.id === id);
    if (!p) throw new Error("Player not found");
    const h = hash(p.name);
    const base = 58 + (h % 15);
    const adj = p.birth_quarter >= 3 ? 4 : 0 + (p.height_diff_cm < 0 ? 3 : -1);
    SKILLS.forEach((k, j) => {
      const v = base + ((h + j * 7) % 13) - 6;
      p.scores[k] = v;
      p.fair_scores[k] = v + adj;
    });
    const raw = weightedAverage(p.scores, DEFAULT_WEIGHTS) ?? 0;
    p.raw_score = Math.round(raw * 10) / 10;
    p.status = "ranked";
    p.provisional_reason = null;
    p.breakdown = [
      { label: "Skill score", value: p.raw_score },
      { label: p.birth_quarter >= 3 ? "Born late in the year" : "Born early in the year", value: p.birth_quarter >= 3 ? 4 : 0 },
      { label: "Height", value: p.height_diff_cm < 0 ? 3 : -1 },
      { label: "Experience", value: p.experience_bonus },
    ];
    store = rankPlayers(all, DEFAULT_WEIGHTS, { recomputeRaw: true });
    analyzed.add(id);
    return report(id);
  },
  async regenerateCoachReport(id: string): Promise<CoachReport> {
    await wait(1200);
    const p = players().find((x) => x.id === id);
    if (!p) throw new Error("Player not found");
    const c = coachReportFor(p, "ai", new Date().toISOString());
    coachOverrides.set(id, c);
    return clone(c);
  },
  async getBias(): Promise<BiasData> {
    await wait(250);
    return biasFrom(players());
  },
};
