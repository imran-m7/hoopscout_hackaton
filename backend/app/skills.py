"""
Measured metrics -> skill scores 0-100 (contract section 1, direction-aware).

DRAFT formulas: they give sensible numbers for the tested videos, but must be
calibrated in Phase 3 with more kids. Every constant is here so it's easy to tune.
"""
import math
from typing import Optional

from . import config
from .scoring import clamp

# ball_handling: dribbles/sec mapped linearly between these (per second)
DPS_LOW, DPS_HIGH = 0.5, 3.0
# athleticism: best jump mapped linearly between these (cm)  TODO: age/gender norms
JUMP_LOW, JUMP_HIGH = 10.0, 50.0


def _lin(v, lo, hi):
    return None if v is None else clamp(100 * (v - lo) / (hi - lo))


def percentile(value, gender, age_group, norms):
    """Score 0-100 = percentile among kids of the same gender + age group (normal curve).
    50 = typical for the group. None if there is no norm for that group."""
    table = norms.get(gender, norms) if gender in norms else norms
    if value is None or age_group not in table:
        return None
    median, sd = table[age_group]
    z = (value - median) / sd
    return clamp(100 * 0.5 * (1 + math.erf(z / math.sqrt(2))))


def _avg(values):
    vals = [v for v in values if v is not None]
    return int(round(sum(vals) / len(vals))) if vals else None


def shooting_form(shooting: Optional[dict]):
    """Mean score of the form targets (distance from the textbook ideal range)."""
    if not shooting:
        return None
    return _avg(t["score"] for t in shooting["targets"])


def consistency(shooting: Optional[dict]):
    """Lower shot-to-shot spread is better (step4's draft formula)."""
    if not shooting or shooting["spread_elbow_deg"] is None:
        return None
    penalty = (shooting["spread_elbow_deg"] * 2 + shooting["spread_knee_deg"] * 1
               + shooting["spread_release"] * 300)
    return int(round(clamp(100 - penalty)))


def ball_handling(dribbling: Optional[dict], gender=None, age_group=None):
    """Speed, ball kept low, and an even rhythm. Speed is the percentile among kids of the
    same age group (a 10-year-old dribbles slower than a 17-year-old); without an age group
    it falls back to the fixed 0.5-3.0 /s scale."""
    if not dribbling:
        return None
    speed = percentile(dribbling["dribbles_per_sec"], gender, age_group, config.DPS_NORMS)
    if speed is None:
        speed = _lin(dribbling["dribbles_per_sec"], DPS_LOW, DPS_HIGH)
    return _avg([speed, dribbling["ball_below_hip_pct"], dribbling["rhythm_score"]])


def weak_hand(dribbling: Optional[dict]):
    """Weak-hand share, capped at 50% (50% = 100 points)."""
    if not dribbling or dribbling["weak_hand_pct"] is None:
        return None
    return int(round(min(dribbling["weak_hand_pct"], 50) * 2))


def court_vision(dribbling: Optional[dict]):
    if not dribbling or dribbling["head_up_pct"] is None:
        return None
    return int(round(clamp(dribbling["head_up_pct"])))


def athleticism(jump: Optional[dict], gender=None, age_group=None):
    """Best jump as a percentile among kids of the same gender + age group
    (31 cm is average for a U14 boy but excellent for a U10 girl). Without gender/age group
    it falls back to the fixed 10-50 cm scale."""
    if not jump or jump["best_jump_cm"] is None:
        return None
    p = percentile(jump["best_jump_cm"], gender, age_group, config.JUMP_NORMS_CM)
    if p is None:
        p = _lin(jump["best_jump_cm"], JUMP_LOW, JUMP_HIGH)
    return int(round(p))


def skill_scores(analyses: dict, gender=None, age_group=None) -> dict:
    s, d, j = analyses.get("shooting"), analyses.get("dribbling"), analyses.get("jump")
    return {"shooting_form": shooting_form(s), "consistency": consistency(s),
            "ball_handling": ball_handling(d, gender, age_group), "weak_hand": weak_hand(d),
            "court_vision": court_vision(d), "athleticism": athleticism(j, gender, age_group)}


def status_for(analyses: dict):
    """(status, provisional_reason, score_margin). Contract section 3."""
    for kind in ("shooting", "dribbling", "jump"):
        a = analyses.get(kind)
        if a is None:
            return "provisional", f"No {kind} video yet", 10
    for kind, unit in (("shooting", "shots"), ("dribbling", "s of dribbling"), ("jump", "jumps")):
        q = analyses[kind]["quality"]
        if q["reps"] is None or q["reps"] < q["min_reps"]:
            got = 0 if q["reps"] is None else int(q["reps"])
            return "provisional", f"Only {got} {unit} (need {q['min_reps']})", 10
        if q["tracking_pct"] is None or q["tracking_pct"] < 70:
            return "provisional", f"{kind.capitalize()} tracking quality {q['tracking_pct'] or 0:.0f}% (need 70%)", 10
    # margin: bigger with few reps / weaker tracking (draft)
    margin = 3
    for kind in ("shooting", "dribbling", "jump"):
        q = analyses[kind]["quality"]
        if q["reps"] < 1.5 * q["min_reps"]:
            margin += 1
        if q["tracking_pct"] < 90:
            margin += 1
    return "ranked", None, margin
