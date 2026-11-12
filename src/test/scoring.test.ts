import { describe, expect, it } from "vitest";
import { buildMockPlayers } from "@/mocks/players";
import { DEFAULT_WEIGHTS, rankPlayers, weightedAverage } from "@/lib/scoring";

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
  it("gem needs ≥5 places gain and top 25% of group", () => {
    const p = rankPlayers(buildMockPlayers(), DEFAULT_WEIGHTS);
    for (const x of p.filter((y) => y.hidden_gem)) {
      const n = p.filter((y) => y.rank_group === x.rank_group && y.status === "ranked").length;
      expect(x.rank_change!).toBeGreaterThanOrEqual(5);
      expect(x.fair_rank!).toBeLessThanOrEqual(Math.ceil(n * 0.25));
    }
  });
});
