"""
Scoring helpers shared by the mock and (later) the real pipeline.

- target_check():  kid's value vs the textbook ideal (TargetCheck)
- fair_from():     fair_k, fair_score and the "why this rank" breakdown
- rank_players():  ranks within rank_group, rank_change, hidden gems

Phase 3 replaces the fixed age/size coefficients with a regression fitted on the dataset.
"""
import math
from typing import Dict, List, Optional

from .config import IDEAL, NOT_VALIDATED, WEIGHTS, experience_bonus


def clean(v):
    """NaN/inf -> None (contract: unknown values are null, never NaN)."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def round_half_up(x) -> int:
    """Same as JavaScript Math.round (70.5 -> 71). Python's round() gives 70 (half to even),
    which would make the frontend's re-ranked board disagree with the API."""
    return int(math.floor(x + 0.5))


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


# ------------------------------------------------------------------ targets
def target_check(metric: str, value: Optional[float]) -> Optional[dict]:
    """TargetCheck for one metric. Returns None if the metric has no IDEAL entry at all."""
    if metric not in IDEAL:
        return None
    cfg = IDEAL[metric]
    if cfg is None:          # range not sourced yet
        return None
    lo, hi, smin, smax, unit, label, tip = cfg
    value = clean(value)
    out = dict(metric=metric, label=label, value=value, unit=unit,
               ideal_min=lo, ideal_max=hi, scale_min=smin, scale_max=smax, tip=tip)
    if value is None:
        return {**out, "score": None, "status": "unknown"}
    if metric in NOT_VALIDATED:     # measured, but not trusted yet -> shown, never scored
        return {**out, "score": None, "status": "unknown",
                "tip": "Not checked yet: we are still validating this measurement, so it is not scored."}
    if lo <= value <= hi:
        return {**out, "score": 100, "status": "ideal"}
    # linear drop from 100 at the ideal edge to 0 at the end of the scale
    if value < lo:
        dist, room, edge = lo - value, max(lo - smin, 1e-6), lo
    else:
        dist, room, edge = value - hi, max(smax - hi, 1e-6), hi
    score = int(round(clamp(100 * (1 - dist / room))))
    # "close" = within 15% of the nearest ideal edge (interpretation, confirm in contract)
    status = "close" if dist <= 0.15 * abs(edge) else "off"
    return {**out, "score": score, "status": status}


# ------------------------------------------------------------------ fair score
def weighted_mean(values: Dict[str, Optional[float]], weights=WEIGHTS) -> Optional[float]:
    num = den = 0.0
    for k, w in weights.items():
        v = values.get(k)
        if v is not None:
            num += w * v
            den += w
    return num / den if den else None


def fair_from(scores: Dict[str, Optional[int]], age_adj: Dict[str, float],
              size_adj: Dict[str, float], years_playing: int,
              age_label: str, size_label: str) -> dict:
    """
    fair_k     = clamp(skill_k + age_adj_k + size_adj_k, 0, 100)
    fair_score = sum(w_k * fair_k) / sum(w_k) + experience_bonus
    The breakdown always sums exactly to fair_score (rounding goes into the size step).
    """
    fair = {k: (None if v is None else round_half_up(clamp(v + age_adj.get(k, 0) + size_adj.get(k, 0))))
            for k, v in scores.items()}
    bonus = experience_bonus(years_playing)
    base = weighted_mean(scores)
    fair_mean = weighted_mean(fair)
    if base is None or fair_mean is None:
        return dict(fair_scores=fair, experience_bonus=bonus, fair_score=0, breakdown=[])
    fair_score = round_half_up(fair_mean + bonus)
    measured = {k: v for k, v in scores.items() if v is not None}
    age_step = round_half_up(weighted_mean({k: age_adj.get(k, 0) for k in measured}) or 0)
    base_step = round_half_up(base)
    size_step = fair_score - base_step - age_step - bonus
    yrs = f"{years_playing} year{'s' if years_playing != 1 else ''} of experience"
    breakdown = [
        {"label": "Skill score", "value": base_step},
        {"label": age_label, "value": age_step},
        {"label": size_label, "value": size_step},
        {"label": yrs, "value": bonus},
    ]
    return dict(fair_scores=fair, experience_bonus=bonus, fair_score=fair_score, breakdown=breakdown)


# ------------------------------------------------------------------ ranking
def rank_players(players: List[dict]) -> None:
    """
    In place. Ranks within rank_group (1 = best), provisional players get null ranks.
    Hidden gem: fair_rank >= 5 places better than raw_rank AND fair_score in the top 25% of its group.
    """
    groups: Dict[str, List[dict]] = {}
    for p in players:
        p["raw_rank"] = p["fair_rank"] = p["rank_change"] = None
        p["hidden_gem"] = False
        if p["status"] == "ranked":
            groups.setdefault(p["rank_group"], []).append(p)
    for members in groups.values():
        for key, rank_key in (("raw_score", "raw_rank"), ("fair_score", "fair_rank")):
            for i, p in enumerate(sorted(members, key=lambda q: (-q[key], q["id"])), start=1):
                p[rank_key] = i
        n = len(members)
        top_quarter = max(1, math.ceil(n * 0.25))
        for p in members:
            p["rank_change"] = p["raw_rank"] - p["fair_rank"]
            p["hidden_gem"] = p["rank_change"] >= 5 and p["fair_rank"] <= top_quarter
