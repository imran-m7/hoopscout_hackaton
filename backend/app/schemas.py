"""
Pydantic copy of the types in api_contract.md (v2).

Keep this file in sync with the contract. If a field changes here, it must
change in the contract (and the frontend types) too.
"""
from datetime import date
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

Gender = Literal["boy", "girl"]
AgeGroup = Literal["U10", "U12", "U14", "U16", "U18"]
Hand = Literal["right", "left"]
Position = Literal["guard", "forward", "center"]
VideoKind = Literal["shooting", "dribbling", "jump"]

SKILL_KEYS = ("shooting_form", "consistency", "ball_handling",
              "weak_hand", "court_vision", "athleticism")


class SkillScores(BaseModel):
    shooting_form: Optional[int] = None
    consistency: Optional[int] = None
    ball_handling: Optional[int] = None
    weak_hand: Optional[int] = None
    court_vision: Optional[int] = None
    athleticism: Optional[int] = None


# ------------------------------------------------------------------ input
class PlayerInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    gender: Gender
    birth_date: date
    height_cm: float = Field(gt=80, lt=230)
    weight_kg: Optional[float] = Field(default=None, gt=15, lt=200)          # private
    sitting_height_cm: Optional[float] = Field(default=None, gt=40, lt=130)  # private
    dominant_hand: Hand
    position: Position
    years_playing: int = Field(ge=0, le=20)
    club: str = Field(min_length=1, max_length=80)
    town: str = Field(min_length=1, max_length=80)


# ------------------------------------------------------------------ summary
class BreakdownStep(BaseModel):
    label: str
    value: int


class PlayerSummary(BaseModel):
    id: str
    is_real: bool
    name: str
    gender: Gender
    age_months: int
    age_group: AgeGroup
    rank_group: str
    birth_quarter: Literal[1, 2, 3, 4]
    height_cm: float
    height_diff_cm: float
    maturity_offset_years: Optional[float] = None
    dominant_hand: Hand
    position: Position
    years_playing: int
    club: str
    town: str

    status: Literal["ranked", "provisional"]
    provisional_reason: Optional[str] = None
    scores: SkillScores
    fair_scores: SkillScores
    experience_bonus: int
    raw_score: int
    fair_score: int
    score_margin: int
    raw_rank: Optional[int] = None
    fair_rank: Optional[int] = None
    rank_change: Optional[int] = None
    hidden_gem: bool
    breakdown: List[BreakdownStep]
    photo_url: Optional[str] = None


# ------------------------------------------------------------------ analyses
class QualityInfo(BaseModel):
    tracking_pct: Optional[float] = None
    reps: Optional[float] = None
    min_reps: int
    ok: bool


class SanityFlag(BaseModel):
    metric: str
    value: float
    message: str


class TargetCheck(BaseModel):
    metric: str
    label: str
    value: Optional[float] = None
    unit: str
    ideal_min: float
    ideal_max: float
    scale_min: float
    scale_max: float
    score: Optional[int] = None
    status: Literal["ideal", "close", "off", "unknown"]
    tip: str


class Shot(BaseModel):
    index: int
    time_s: float
    elbow_set_deg: Optional[float] = None
    knee_min_deg: Optional[float] = None
    release_height_ratio: Optional[float] = None
    leg_arm_timing_ms: Optional[float] = None
    follow_through_s: Optional[float] = None


class SkippedMoment(BaseModel):
    time_s: float
    reason: str


class ShootingAnalysis(BaseModel):
    shots: List[Shot]
    skipped: List[SkippedMoment]
    avg_elbow_set_deg: Optional[float] = None
    avg_knee_min_deg: Optional[float] = None
    avg_release_height_ratio: Optional[float] = None
    avg_leg_arm_timing_ms: Optional[float] = None
    avg_follow_through_s: Optional[float] = None
    spread_elbow_deg: Optional[float] = None
    spread_knee_deg: Optional[float] = None
    spread_release: Optional[float] = None
    targets: List[TargetCheck]
    quality: QualityInfo
    flags: List[SanityFlag]
    annotated_video_url: Optional[str] = None


class DribblingAnalysis(BaseModel):
    duration_s: Optional[float] = None
    dribbles: Optional[int] = None
    dribbles_per_sec: Optional[float] = None
    rhythm_score: Optional[int] = None
    ball_below_hip_pct: Optional[float] = None
    ball_below_knee_pct: Optional[float] = None
    left_hand_pct: Optional[float] = None
    right_hand_pct: Optional[float] = None
    weak_hand_pct: Optional[float] = None
    head_up_pct: Optional[float] = None
    targets: List[TargetCheck]
    quality: QualityInfo
    flags: List[SanityFlag]
    annotated_video_url: Optional[str] = None


class Jump(BaseModel):
    index: int
    air_time_s: float
    height_cm: float


class JumpAnalysis(BaseModel):
    jumps: List[Jump]
    best_jump_cm: Optional[float] = None
    avg_jump_cm: Optional[float] = None
    targets: List[TargetCheck]
    quality: QualityInfo
    flags: List[SanityFlag]
    annotated_video_url: Optional[str] = None


# ------------------------------------------------------------------ report
class Insight(BaseModel):
    title: str
    detail: str
    metric: Optional[str] = None


class Drill(BaseModel):
    name: str
    description: str
    dose: str


class CoachReport(BaseModel):
    source: Literal["ai", "rules"]
    model: Optional[str] = None
    summary: str
    drills: List[Drill]
    generated_at: str


class SessionSummary(BaseModel):
    session_id: str
    date: str
    fair_score: Optional[int] = None
    target_values: Dict[str, Optional[float]]


class PlayerReport(BaseModel):
    player: PlayerSummary
    group_average: SkillScores
    shooting: Optional[ShootingAnalysis] = None
    dribbling: Optional[DribblingAnalysis] = None
    jump: Optional[JumpAnalysis] = None
    strengths: List[Insight]
    weaknesses: List[Insight]
    coach_report: Optional[CoachReport] = None
    sessions: List[SessionSummary]


# ------------------------------------------------------------------ jobs, bias, health
class Job(BaseModel):
    job_id: str
    player_id: str
    kind: VideoKind
    status: Literal["queued", "running", "done", "failed"]
    progress: int
    step: str
    error: Optional[str] = None


class BirthQuarterBias(BaseModel):
    all_players: Tuple[int, int, int, int]
    raw_top10: Tuple[int, int, int, int]
    fair_top10: Tuple[int, int, int, int]


class HeightPoint(BaseModel):
    id: str
    name: str
    height_diff_cm: float
    raw_rank: int
    fair_rank: int


class HeightBias(BaseModel):
    raw_top10_avg_diff_cm: float
    fair_top10_avg_diff_cm: float
    points: List[HeightPoint]


class BiasData(BaseModel):
    birth_quarter: BirthQuarterBias
    height: HeightBias
    explanation: str


class Health(BaseModel):
    ok: bool
    demo_mode: bool
