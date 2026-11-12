import { describe, expect, it } from "vitest";
import { buildMockPlayers } from "@/mocks/players";
import { DEFAULT_WEIGHTS, fairScoreFor, rankPlayers, weightedAverage } from "@/lib/scoring";
import type { SkillScores } from "@/lib/types";

describe("scoring rules", () => {
  it("consistency weight defaults to 1.5, others 1", () => {
    expect(DEFAULT_WEIGHTS.consistency).toBe(1.5);
    expect(DEFAULT_WEIGHTS.shooting_form).toBe(1);
  });
  it("weighted average uses Σ(w×s)/Σw", () => {
    const s = { shooting_form: 80, consistency: 60, ball_handling: null, weak_hand: null, court_vision: null, athleticism: null };
    const w = { ...DEFAULT_WEIGHTS, shooting_form: 1, consistency: 3 };
    expect(weightedAverage(s, w)).toBe(65);
  });
  it("mock data has 24 players, 4 filmed, 3 gems, 2 provisional", () => {
    const p = buildMockPlayers();
    expect(p).toHaveLength(24);
    expect(p.filter((x) => x.is_real)).toHaveLength(4);
    expect(p.filter((x) => x.hidden_gem)).toHaveLength(3);
    expect(p.filter((x) => x.status === "provisional")).toHaveLength(2);
  });
  it("default weights keep the API's ranks and gems untouched", () => {
    const api = buildMockPlayers();
    const out = rankPlayers(api, DEFAULT_WEIGHTS);
    expect(out.map((p) => [p.fair_score, p.raw_rank, p.fair_rank, p.rank_change, p.hidden_gem])).toEqual(
      api.map((p) => [p.fair_score, p.raw_rank, p.fair_rank, p.rank_change, p.hidden_gem]),
    );
  });
  it("matches backend formula: nulls skipped, Math.round, tie → lower id first, raw_rank kept", () => {
    const empty: SkillScores = { shooting_form: null, consistency: null, ball_handling: null, weak_hand: null, court_vision: null, athleticism: null };
    const base = buildMockPlayers()[0]!;
    const mk = (id: string, s: Partial<SkillScores>, raw_rank: number) => ({
      ...base, id, rank_group: "T", status: "ranked" as const, experience_bonus: 0, raw_rank,
      fair_scores: { ...empty, ...s },
    });
    const w = { ...DEFAULT_WEIGHTS, shooting_form: 2 };
    // 70.5 → 71 (Python's round would give 70)
    expect(fairScoreFor(mk("x", { ball_handling: 70, weak_hand: 71 }, 1), DEFAULT_WEIGHTS)).toBe(71);
    const out = rankPlayers([mk("p_045", { ball_handling: 80 }, 1), mk("p_012", { ball_handling: 80 }, 2)], w);
    expect(out.find((p) => p.id === "p_012")!.fair_rank).toBe(1);
    expect(out.find((p) => p.id === "p_045")!.fair_rank).toBe(2);
    expect(out.find((p) => p.id === "p_045")!.raw_rank).toBe(1); // raw_rank comes from the API, never recomputed
  });
  it("gem needs ≥5 places gain and top 25% of group", () => {
    const p = rankPlayers(buildMockPlayers(), DEFAULT_WEIGHTS);
    for (const x of p.filter((y) => y.hidden_gem)) {
      const n = p.filter((y) => y.rank_group === x.rank_group && y.status === "ranked").length;
      expect(x.rank_change!).toBeGreaterThanOrEqual(5);
      expect(x.fair_rank!).toBeLessThanOrEqual(Math.ceil(n * 0.25));
    }
  });
});
