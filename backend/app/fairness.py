"""
Phase 3: the fair-score adjustment learned from the data (contract section 2).

For every skill k and gender, a linear regression answers: "how many points does a kid
usually gain per month older, and per cm taller, than the others in their group?"

    skill_k - group_avg  =  b_k * (age_months - group_avg_age)  +  c_k * (height_diff - group_avg_height_diff)

- Fitted on ALL kids of that gender (U10..U18 together, ~200 kids -> a stable fit), but every
  kid is measured against their OWN rank group (Boys U14...), so a U10 kid is never compared
  with a U18 kid.
- Height uses height_diff_cm (height vs the average for that exact age in months), so height
  and age don't count the same thing twice.
- Slopes are clamped to >= 0: we only remove an ADVANTAGE from being older/bigger, we never
  penalise being young or small.

Then, exactly as in the contract:
    age_adj_k  = b_k * (group_avg_age - age_months)        # younger than the group -> +
    size_adj_k = c_k * (group_avg_height_diff - height_diff)  # smaller than the group -> +
"""
from statistics import mean
from typing import Dict, List

import numpy as np

from .schemas import SKILL_KEYS

MIN_KIDS = 20                         # fewer -> use the fallback slopes below
FALLBACK = {"age": 0.30, "size": 0.40}  # points per month / per cm (only if too little data)
MAX_SLOPE = {"age": 1.5, "size": 2.0}   # safety cap against a crazy fit


def group_means(rows: List[dict]) -> Dict[str, dict]:
    """rows: dicts with rank_group, months, diff, scores. Returns per-group averages."""
    by = {}
    for r in rows:
        by.setdefault(r["rank_group"], []).append(r)
    out = {}
    for g, members in by.items():
        sk = {}
        for k in SKILL_KEYS:
            vals = [m["scores"][k] for m in members if m["scores"].get(k) is not None]
            sk[k] = mean(vals) if vals else None
        out[g] = {"months": mean(m["months"] for m in members),
                  "diff": mean(m["diff"] for m in members), "skills": sk}
    return out


def fit(rows: List[dict]) -> Dict[str, Dict[str, dict]]:
    """Returns {gender: {skill: {"age": b, "size": c, "n": kids, "fallback": bool}}}."""
    means = group_means(rows)
    out = {}
    for gender in ("boy", "girl"):
        out[gender] = {}
        for k in SKILL_KEYS:
            X, y = [], []
            for r in rows:
                v = r["scores"].get(k)
                gm = means[r["rank_group"]]
                if r["gender"] != gender or v is None or gm["skills"][k] is None:
                    continue
                X.append([r["months"] - gm["months"], r["diff"] - gm["diff"]])
                y.append(v - gm["skills"][k])
            if len(y) < MIN_KIDS:
                out[gender][k] = {**FALLBACK, "n": len(y), "fallback": True}
                continue
            (b, c), *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
            out[gender][k] = {"age": float(min(max(b, 0.0), MAX_SLOPE["age"])),
                              "size": float(min(max(c, 0.0), MAX_SLOPE["size"])),
                              "n": len(y), "fallback": False}
    return out


def adjustments(coefs, gender, months, diff, group_mean):
    """age_adj_k and size_adj_k for one kid (contract formulas)."""
    c = coefs[gender]
    age = {k: c[k]["age"] * (group_mean["months"] - months) for k in SKILL_KEYS}
    size = {k: c[k]["size"] * (group_mean["diff"] - diff) for k in SKILL_KEYS}
    return age, size


def describe(coefs) -> str:
    """One sentence per gender for the Bias Check explanation."""
    parts = []
    for gender, label in (("boy", "boys"), ("girl", "girls")):
        c = coefs.get(gender, {})
        if not c:
            continue
        a = mean(v["age"] for v in c.values()) * 12
        s = mean(v["size"] for v in c.values()) * 5
        parts.append(f"For {label}, being a year older than the group average adds about {a:.0f} "
                     f"points and being 5 cm taller adds about {s:.0f} points, on average over the skills.")
    return " ".join(parts)
