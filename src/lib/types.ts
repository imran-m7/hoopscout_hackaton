export type Gender = "boy" | "girl";
export type AgeGroup = "U10" | "U12" | "U14" | "U16" | "U18";
export type Hand = "right" | "left";
export type Position = "guard" | "forward" | "center";
export type SkillKey = "shooting_form" | "consistency" | "ball_handling" | "weak_hand" | "court_vision" | "athleticism";
export type SkillScores = Record<SkillKey, number | null>;

export interface PlayerInput {
  name: string; gender: Gender; birth_date: string; height_cm: number;
  weight_kg?: number | null; sitting_height_cm?: number | null;
  dominant_hand: Hand; position: Position; years_playing: number; club: string; town: string;
}
export interface BreakdownStep { label: string; value: number; }
export interface PlayerSummary {
  id: string; is_real: boolean; name: string; gender: Gender;
  age_months: number; age_group: AgeGroup; rank_group: string; birth_quarter: 1 | 2 | 3 | 4;
  height_cm: number; height_diff_cm: number; maturity_offset_years: number | null;
  dominant_hand: Hand; position: Position; years_playing: number; club: string; town: string;
  status: "ranked" | "provisional"; provisional_reason: string | null;
  scores: SkillScores; fair_scores: SkillScores; experience_bonus: number;
  raw_score: number; fair_score: number; score_margin: number;
  raw_rank: number | null; fair_rank: number | null; rank_change: number | null;
  hidden_gem: boolean; breakdown: BreakdownStep[]; photo_url: string | null;
}
export interface QualityInfo { tracking_pct: number | null; reps: number | null; min_reps: number; ok: boolean; }
export interface SanityFlag { metric: string; value: number; message: string; }
export interface TargetCheck {
  metric: string; label: string; value: number | null; unit: string;
  ideal_min: number; ideal_max: number; scale_min: number; scale_max: number;
  score: number | null; status: "ideal" | "close" | "off" | "unknown"; tip: string;
}
export interface Shot {
  index: number; time_s: number; elbow_set_deg: number | null; knee_min_deg: number | null;
  release_height_ratio: number | null; leg_arm_timing_ms: number | null; follow_through_s: number | null;
}
export interface ShootingAnalysis {
  shots: Shot[]; skipped: { time_s: number; reason: string }[];
  avg_elbow_set_deg: number | null; avg_knee_min_deg: number | null;
  avg_release_height_ratio: number | null; avg_leg_arm_timing_ms: number | null;
  avg_follow_through_s: number | null;
  spread_elbow_deg: number | null; spread_knee_deg: number | null; spread_release: number | null;
  targets: TargetCheck[]; quality: QualityInfo; flags: SanityFlag[]; annotated_video_url: string | null;
}
export interface DribblingAnalysis {
  duration_s: number | null; dribbles: number | null; dribbles_per_sec: number | null;
  rhythm_score: number | null; ball_below_hip_pct: number | null; ball_below_knee_pct: number | null;
  left_hand_pct: number | null; right_hand_pct: number | null; weak_hand_pct: number | null;
  head_up_pct: number | null; targets: TargetCheck[]; quality: QualityInfo; flags: SanityFlag[]; annotated_video_url: string | null;
}
export interface JumpAnalysis {
  jumps: { index: number; air_time_s: number; height_cm: number }[];
  best_jump_cm: number | null; avg_jump_cm: number | null;
  targets: TargetCheck[]; quality: QualityInfo; flags: SanityFlag[]; annotated_video_url: string | null;
}
export interface Insight { title: string; detail: string; metric: string | null; }
export interface Drill { name: string; description: string; dose: string; }
export interface CoachReport {
  source: "ai" | "rules"; model: string | null; summary: string; drills: Drill[]; generated_at: string;
}
export interface SessionSummary {
  session_id: string; date: string; fair_score: number | null;
  target_values: Record<string, number | null>;
}
export interface PlayerReport {
  player: PlayerSummary; group_average: SkillScores;
  shooting: ShootingAnalysis | null; dribbling: DribblingAnalysis | null; jump: JumpAnalysis | null;
  strengths: Insight[]; weaknesses: Insight[]; coach_report: CoachReport | null; sessions: SessionSummary[];
}
export interface Job {
  job_id: string; player_id: string; kind: "shooting" | "dribbling" | "jump";
  status: "queued" | "running" | "done" | "failed"; progress: number; step: string; error: string | null;
}
export interface BiasData {
  birth_quarter: { all_players: [number, number, number, number];
                   raw_top10: [number, number, number, number];
                   fair_top10: [number, number, number, number]; };
  height: { raw_top10_avg_diff_cm: number; fair_top10_avg_diff_cm: number;
            points: { id: string; name: string; height_diff_cm: number; raw_rank: number; fair_rank: number }[]; };
  explanation: string;
}
