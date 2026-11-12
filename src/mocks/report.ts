import type { BiasData, CoachReport, DribblingAnalysis, Insight, JumpAnalysis, PlayerReport, PlayerSummary, ShootingAnalysis, SkillScores } from "@/lib/types";
import { SKILLS, SKILL_LABELS } from "@/lib/scoring";

export const FULL_REPORT_ID = "p01";

export function sampleShooting(): ShootingAnalysis {
  const shots = [
    [3.2, 88, 112, 1.24, 40, 0.42],
    [7.9, 91, 108, 1.27, 30, 0.5],
    [12.4, 79, 118, 1.2, 70, 0.31],
    [17.1, 86, 110, 1.25, 50, 0.45],
    [21.8, 93, 104, 1.29, 20, 0.55],
    [32.6, 84, 115, 1.22, 60, 0.38],
    [37.3, 89, 109, 1.26, 40, 0.48],
  ].map((r, i) => ({
    index: i + 1, time_s: r[0] ?? 0, elbow_set_deg: r[1] ?? null, knee_min_deg: r[2] ?? null,
    release_height_ratio: r[3] ?? null, leg_arm_timing_ms: r[4] ?? null, follow_through_s: r[5] ?? null,
  }));
  return {
    shots,
    skipped: [
      { time_s: 27.9, reason: "catch/pass, not counted" },
      { time_s: 41.0, reason: "ball left frame" },
    ],
    avg_elbow_set_deg: 87.1, avg_knee_min_deg: 110.9, avg_release_height_ratio: 1.25,
    avg_leg_arm_timing_ms: 44, avg_follow_through_s: 0.44,
    spread_elbow_deg: 4.6, spread_knee_deg: 4.5, spread_release: 0.03,
    targets: [
      { metric: "avg_elbow_set_deg", label: "Elbow angle at set point", value: 87.1, unit: "°", ideal_min: 80, ideal_max: 100, scale_min: 50, scale_max: 130, score: 92, status: "ideal", tip: "Great L-shape. Keep the elbow under the ball." },
      { metric: "avg_knee_min_deg", label: "Knee bend (lowest)", value: 110.9, unit: "°", ideal_min: 90, ideal_max: 105, scale_min: 70, scale_max: 150, score: 68, status: "close", tip: "Sit a little deeper to get more power from the legs." },
      { metric: "avg_leg_arm_timing_ms", label: "Legs → arm timing", value: 44, unit: " ms", ideal_min: 0, ideal_max: 60, scale_min: -100, scale_max: 250, score: 88, status: "ideal", tip: "Smooth one-motion shot. Keep it." },
      { metric: "avg_follow_through_s", label: "Follow-through hold", value: 0.44, unit: " s", ideal_min: 0.6, ideal_max: 1.2, scale_min: 0, scale_max: 1.5, score: 45, status: "off", tip: "Hold the 'hand in the cookie jar' until the ball lands." },
    ],
    quality: { tracking_pct: 98, reps: 7, min_reps: 6, ok: true },
    flags: [],
    annotated_video_url: null,
  };
}

export function sampleDribbling(): DribblingAnalysis {
  return {
    duration_s: 30, dribbles: 66, dribbles_per_sec: 2.2, rhythm_score: 81,
    ball_below_hip_pct: 92, ball_below_knee_pct: 41, left_hand_pct: 58, right_hand_pct: 42,
    weak_hand_pct: 42, head_up_pct: 63,
    targets: [
      { metric: "dribbles_per_sec", label: "Dribble speed", value: 2.2, unit: "/s", ideal_min: 2.0, ideal_max: 3.0, scale_min: 0.5, scale_max: 4, score: 84, status: "ideal", tip: "Good pace. Add speed changes next." },
      { metric: "weak_hand_pct", label: "Weak-hand share", value: 42, unit: "%", ideal_min: 45, ideal_max: 55, scale_min: 0, scale_max: 100, score: 72, status: "close", tip: "Almost balanced — a few more right-hand reps." },
      { metric: "head_up_pct", label: "Head up", value: 63, unit: "%", ideal_min: 80, ideal_max: 100, scale_min: 0, scale_max: 100, score: 52, status: "off", tip: "Eyes on the rim, not the ball. Try calling out fingers." },
    ],
    quality: { tracking_pct: 96, reps: 66, min_reps: 30, ok: true },
    flags: [{ metric: "left_hand_pct", value: 58, message: "Left-handed player: weak hand is the right hand." }],
    annotated_video_url: null,
  };
}

export function sampleJump(): JumpAnalysis {
  return {
    jumps: [
      { index: 1, air_time_s: 0.47, height_cm: 27.1 },
      { index: 2, air_time_s: 0.5, height_cm: 30.6 },
      { index: 3, air_time_s: 0.48, height_cm: 28.2 },
    ],
    best_jump_cm: 30.6, avg_jump_cm: 28.6,
    targets: [
      { metric: "best_jump_cm", label: "Best vertical jump", value: 30.6, unit: " cm", ideal_min: 35, ideal_max: 50, scale_min: 10, scale_max: 60, score: 62, status: "close", tip: "Explosive arm swing adds 3–5 cm." },
    ],
    quality: { tracking_pct: 99, reps: 3, min_reps: 3, ok: true },
    flags: [{ metric: "air_time_s", value: 0.5, message: "Landing slightly out of frame on jump 2 — height may be ±2 cm." }],
    annotated_video_url: null,
  };
}

export function groupAverage(players: PlayerSummary[], group: string): SkillScores {
  const inGroup = players.filter((p) => p.rank_group === group && p.status === "ranked");
  const avg = {} as SkillScores;
  for (const k of SKILLS) {
    const vals = inGroup.map((p) => p.fair_scores[k]).filter((v): v is number => typeof v === "number");
    avg[k] = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
  }
  return avg;
}

function insights(p: PlayerSummary): { strengths: Insight[]; weaknesses: Insight[] } {
  const list = SKILLS.filter((k) => typeof p.fair_scores[k] === "number").sort(
    (a, b) => (p.fair_scores[b] as number) - (p.fair_scores[a] as number),
  );
  return {
    strengths: list.slice(0, 2).map((k) => ({ title: SKILL_LABELS[k], detail: `${SKILL_LABELS[k]} is ${p.fair_scores[k]} after fair adjustment — above most kids this age.`, metric: k })),
    weaknesses: list.slice(-2).reverse().map((k) => ({ title: SKILL_LABELS[k], detail: `${SKILL_LABELS[k]} at ${p.fair_scores[k]} — the quickest win for this player.`, metric: k })),
  };
}

export function coachReportFor(p: PlayerSummary, source: "ai" | "rules", now: string): CoachReport {
  const first = p.name.split(" ")[0];
  return {
    source,
    model: source === "ai" ? "gemini-2.5-flash" : null,
    summary: `${first} reads the game well and has a smooth, repeatable shot for a ${Math.floor(p.age_months / 12)}-year-old. Being small for the age group hides how skilled ${first} already is. This week: hold the follow-through and keep the eyes up while dribbling.`,
    drills: [
      { name: "Freeze follow-through", description: "Form shots 1 m from the rim. Hold the wrist flick until the ball hits the floor.", dose: "3 × 15 shots, daily" },
      { name: "Finger-call dribble", description: "Partner holds up fingers; call the number while dribbling with the weak hand.", dose: "4 × 30 s, 4 days" },
      { name: "Arm-swing jumps", description: "Big arm swing into a two-foot jump, land soft and stick it.", dose: "3 × 8 jumps, 3 days" },
    ],
    generated_at: now,
  };
}

export function fullReport(p: PlayerSummary, players: PlayerSummary[]): PlayerReport {
  const sh = sampleShooting();
  const dr = sampleDribbling();
  const ju = sampleJump();
  const ins = insights(p);
  return {
    player: p,
    group_average: groupAverage(players, p.rank_group),
    shooting: sh,
    dribbling: dr,
    jump: ju,
    strengths: ins.strengths,
    weaknesses: ins.weaknesses,
    coach_report: coachReportFor(p, "ai", "2026-11-10T16:20:00Z"),
    sessions: [
      { session_id: "s1", date: "2026-09-14", fair_score: p.fair_score - 4, target_values: { avg_elbow_set_deg: 79, avg_knee_min_deg: 121, avg_leg_arm_timing_ms: 85, avg_follow_through_s: 0.3, dribbles_per_sec: 1.8, weak_hand_pct: 31, head_up_pct: 48, best_jump_cm: 27.5 } },
      { session_id: "s2", date: "2026-10-12", fair_score: p.fair_score - 2, target_values: { avg_elbow_set_deg: 84, avg_knee_min_deg: 116, avg_leg_arm_timing_ms: 60, avg_follow_through_s: 0.36, dribbles_per_sec: 2.0, weak_hand_pct: 37, head_up_pct: 55, best_jump_cm: 29.0 } },
      { session_id: "s3", date: "2026-11-09", fair_score: p.fair_score, target_values: { avg_elbow_set_deg: 87.1, avg_knee_min_deg: 110.9, avg_leg_arm_timing_ms: 44, avg_follow_through_s: 0.44, dribbles_per_sec: 2.2, weak_hand_pct: 42, head_up_pct: 63, best_jump_cm: 30.6 } },
    ],
  };
}

export function lightReport(p: PlayerSummary, players: PlayerSummary[]): PlayerReport {
  // Filmed ("real-looking") players get the complete report.
  if (p.is_real) return fullReport(p, players);
  const ins = insights(p);
  const real = p.is_real;
  return {
    player: p,
    group_average: groupAverage(players, p.rank_group),
    shooting: real ? sampleShooting() : null,
    dribbling: real ? sampleDribbling() : null,
    jump: real ? sampleJump() : null,
    strengths: ins.strengths,
    weaknesses: ins.weaknesses,
    coach_report: coachReportFor(p, "rules", "2026-11-08T10:00:00Z"),
    sessions: [],
  };
}

export function biasFrom(players: PlayerSummary[]): BiasData {
  const ranked = players.filter((p) => p.status === "ranked");
  const byRaw = [...ranked].sort((a, b) => b.raw_score - a.raw_score);
  const byFair = [...ranked].sort((a, b) => b.fair_score - a.fair_score);
  const q = (list: PlayerSummary[]) => {
    const c: [number, number, number, number] = [0, 0, 0, 0];
    list.forEach((p) => (c[p.birth_quarter - 1] = (c[p.birth_quarter - 1] ?? 0) + 1));
    return c;
  };
  const avgH = (list: PlayerSummary[]) => Math.round((list.reduce((a, p) => a + p.height_diff_cm, 0) / list.length) * 10) / 10;
  const rawRank = new Map(byRaw.map((p, i) => [p.id, i + 1]));
  const fairRank = new Map(byFair.map((p, i) => [p.id, i + 1]));
  return {
    birth_quarter: { all_players: q(ranked), raw_top10: q(byRaw.slice(0, 10)), fair_top10: q(byFair.slice(0, 10)) },
    height: {
      raw_top10_avg_diff_cm: avgH(byRaw.slice(0, 10)),
      fair_top10_avg_diff_cm: avgH(byFair.slice(0, 10)),
      points: ranked.map((p) => ({ id: p.id, name: p.name, height_diff_cm: p.height_diff_cm, raw_rank: rawRank.get(p.id)!, fair_rank: fairRank.get(p.id)! })),
    },
    explanation:
      "In the raw ranking the top 10 is dominated by kids born in January–June and kids who are taller than average for their age. After HoopScout adjusts for age, birth month, size and experience, late-born and smaller players with strong skills move up, and the top 10 spreads more evenly across the year.",
  };
}
