import type { PlayerSummary, SkillKey, SkillScores } from "./types";
import { isNum } from "./format";

export const SKILLS: SkillKey[] = [
  "shooting_form",
  "consistency",
  "ball_handling",
  "weak_hand",
  "court_vision",
  "athleticism",
];

export const SKILL_LABELS: Record<SkillKey, string> = {
  shooting_form: "Shooting form",
  consistency: "Consistency",
  ball_handling: "Ball handling",
  weak_hand: "Weak hand",
  court_vision: "Court vision",
  athleticism: "Athleticism",
};

export const SKILL_SORT_LABELS: Record<SkillKey, string> = {
  shooting_form: "Best shooters",
  consistency: "Most consistent",
  ball_handling: "Best ball handlers",
  weak_hand: "Best weak hand",
  court_vision: "Best court vision",
  athleticism: "Most athletic",
};

export type Weights = Record<SkillKey, number>;

export const DEFAULT_WEIGHTS: Weights = {
  shooting_form: 1,
  consistency: 1.5,
  ball_handling: 1,
  weak_hand: 1,
  court_vision: 1,
  athleticism: 1,
};

/** Σ(w_k × s_k) / Σ w_k over skills that have a value. */
export function weightedAverage(scores: SkillScores, weights: Weights): number | null {
  let num = 0;
  let den = 0;
  for (const k of SKILLS) {
    const v = scores[k];
    const w = weights[k] ?? 0;
    if (isNum(v) && w > 0) {
      num += w * v;
      den += w;
    }
  }
  return den > 0 ? num / den : null;
}

export function fairScoreFor(p: PlayerSummary, weights: Weights): number {
  const avg = weightedAverage(p.fair_scores, weights);
  if (avg === null) return p.fair_score;
  return Math.round((avg + (p.experience_bonus ?? 0)) * 10) / 10;
}

export const GEM_MIN_RANK_GAIN = 5;
export const GEM_TOP_SHARE = 0.25;

/** Recompute fair score, ranks and hidden gems within each rank group. */
export function rankPlayers(players: PlayerSummary[], weights: Weights): PlayerSummary[] {
  const out = players.map((p) => ({ ...p }));
  const groups = new Map<string, PlayerSummary[]>();
  for (const p of out) {
    if (p.status === "ranked") p.fair_score = fairScoreFor(p, weights);
    const list = groups.get(p.rank_group) ?? [];
    list.push(p);
    groups.set(p.rank_group, list);
  }
  for (const list of groups.values()) {
    const ranked = list.filter((p) => p.status === "ranked");
    [...ranked].sort((a, b) => b.raw_score - a.raw_score).forEach((p, i) => (p.raw_rank = i + 1));
    [...ranked].sort((a, b) => b.fair_score - a.fair_score).forEach((p, i) => (p.fair_rank = i + 1));
    const topCut = Math.ceil(ranked.length * GEM_TOP_SHARE);
    for (const p of ranked) {
      p.rank_change = (p.raw_rank as number) - (p.fair_rank as number);
      p.hidden_gem = p.rank_change >= GEM_MIN_RANK_GAIN && (p.fair_rank as number) <= topCut;
    }
    for (const p of list.filter((x) => x.status !== "ranked")) {
      p.raw_rank = null;
      p.fair_rank = null;
      p.rank_change = null;
      p.hidden_gem = false;
    }
  }
  return out;
}

export function topSkills(scores: SkillScores, n = 3): { key: SkillKey; value: number }[] {
  return SKILLS.filter((k) => isNum(scores[k]))
    .map((k) => ({ key: k, value: scores[k] as number }))
    .sort((a, b) => b.value - a.value)
    .slice(0, n);
}
