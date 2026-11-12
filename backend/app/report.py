"""
Strengths, weaknesses and the coach report (contract: Insight, Drill, CoachReport).

- insights(): rule-based, always present. Uses the measured numbers when there are
  analyses ("Release height varies only 1.8%"), otherwise the skill scores.
- coach_report(): AI (Groq) when GROQ_API_KEY is set and the API answers in time,
  otherwise the rule-based report ("source": "rules").

Privacy: the AI gets ONLY measured numbers + age group / position / hand.
Never the name, club, town, birth date, weight or any video.
"""
import json
from datetime import datetime, timezone

import httpx

from . import config

SKILL_NAMES = {"shooting_form": "shooting form", "consistency": "shot consistency",
               "ball_handling": "ball handling", "weak_hand": "weak hand",
               "court_vision": "court vision", "athleticism": "athleticism"}

DRILLS = {
    "shooting_form": ("Form shooting close to the rim", "One hand, 1 m from the rim, hold the follow-through until the ball lands.", "3 x 25 shots, 4 days this week"),
    # court_vision: the coach-finger drill needs a second person, this one works alone
    "court_vision": ("Eyes-up wall dribble", "Dribble while reading numbers taped on a wall in front of you, never looking at the ball.", "3 x 60 s, 4 days this week"),
    "consistency": ("Same-spot repeats", "10 shots from the same spot with exactly the same routine every time.", "5 x 10 shots, 4 days this week"),
    "ball_handling": ("Pound dribbles", "Hard, low dribbles as fast as possible while staying in control.", "4 x 30 s each hand, 4 days this week"),
    "weak_hand": ("Weak-hand only", "Dribble and finish lay-ups using only the weak hand.", "3 x 2 min, 5 days this week"),
    "athleticism": ("Box jumps", "Jump onto a low box, land softly on both feet, step down.", "3 x 8 jumps, 3 days this week"),
}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ------------------------------------------------------------------ insights (rules, always present)
def _metric_insights(analyses):
    """(score_for_sorting, Insight) pairs from measured numbers. High = strength, low = weakness."""
    good, bad = [], []
    s, d, j = analyses.get("shooting"), analyses.get("dribbling"), analyses.get("jump")
    if s and s.get("spread_release") is not None and s.get("avg_release_height_ratio"):
        pct = 100 * s["spread_release"] / s["avg_release_height_ratio"]
        item = {"metric": "spread_release",
                "detail": f"Release height varies only {pct:.1f}% between shots."}
        if pct <= 2.5:
            good.append((90, {**item, "title": "Very consistent release"}))
        elif pct >= 5:
            bad.append((30, {**item, "title": "Release point moves around",
                             "detail": f"Release height varies {pct:.1f}% between shots."}))
    if s and s.get("spread_elbow_deg") is not None:
        if s["spread_elbow_deg"] <= 3:
            good.append((85, {"title": "Same arm angle every shot", "metric": "spread_elbow_deg",
                              "detail": f"Elbow angle changes only {s['spread_elbow_deg']:.1f}° from shot to shot."}))
        elif s["spread_elbow_deg"] >= 8:
            bad.append((35, {"title": "Arm angle changes between shots", "metric": "spread_elbow_deg",
                             "detail": f"Elbow angle changes {s['spread_elbow_deg']:.1f}° from shot to shot."}))
    for a in (s, d, j):
        for t in (a or {}).get("targets", []):
            if t["status"] == "off" and t["value"] is not None:
                bad.append((t["score"] or 0, {
                    "title": t["label"], "metric": t["metric"],
                    "detail": f"{t['value']:.0f}{t['unit']} - the target is {t['ideal_min']:.0f}-{t['ideal_max']:.0f}{t['unit']}. {t['tip']}"}))
            elif t["status"] == "ideal" and t["value"] is not None:
                good.append((80, {"title": t["label"], "metric": t["metric"],
                                  "detail": f"{t['value']:.0f}{t['unit']}, inside the ideal range "
                                            f"({t['ideal_min']:.0f}-{t['ideal_max']:.0f}{t['unit']})."}))
    if d and d.get("weak_hand_pct") is not None and d["weak_hand_pct"] >= 40:
        good.append((88, {"title": "Uses both hands", "metric": "weak_hand_pct",
                          "detail": f"{d['weak_hand_pct']:.0f}% of dribbles with the weak hand."}))
    if d and d.get("head_up_pct") is not None and d["head_up_pct"] < 60:
        bad.append((d["head_up_pct"], {"title": "Eyes on the ball", "metric": "head_up_pct",
                                       "detail": f"Head is up only {d['head_up_pct']:.0f}% of the time while dribbling."}))
    if d and d.get("rhythm_score") is not None and d["rhythm_score"] < 50:
        bad.append((d["rhythm_score"], {"title": "Uneven dribble rhythm", "metric": "rhythm_score",
                                        "detail": f"Rhythm score {d['rhythm_score']}/100: the time between bounces changes a lot."}))
    return good, bad


def insights(scores, analyses):
    good, bad = _metric_insights(analyses or {})
    measured = [(v, k) for k, v in scores.items() if v is not None]
    for v, k in measured:   # score-based ones fill up when there are few measured insights
        name = SKILL_NAMES[k].capitalize()
        if v >= 70:
            good.append((v - 10, {"title": f"Strong {SKILL_NAMES[k]}", "metric": k, "detail": f"{name} score {v}/100."}))
        elif v < 50:
            bad.append((v + 10, {"title": f"{name} to improve", "metric": k, "detail": f"{name} score {v}/100."}))

    def pick(items, reverse):
        out, seen = [], set()
        for _, ins in sorted(items, key=lambda x: x[0], reverse=reverse):
            if ins["title"] not in seen:
                out.append(ins)
                seen.add(ins["title"])
        return out[:3]

    return pick(good, True), pick(bad, False)


# ------------------------------------------------------------------ coach report
def rules_report(scores, strengths, weaknesses):
    measured = sorted((v, k) for k, v in scores.items() if v is not None)
    if not measured:
        return {"source": "rules", "model": None, "generated_at": _now(),
                "summary": "No videos have been analyzed yet, so there is nothing to report.",
                "drills": [dict(zip(("name", "description", "dose"), DRILLS[k]))
                           for k in ("consistency", "ball_handling", "court_vision")]}
    best, worst = measured[-1][1], measured[0][1]
    parts = [f"The strongest area is {SKILL_NAMES[best]} ({scores[best]}/100)."]
    if strengths:
        parts.append(strengths[0]["detail"])
    parts.append(f"The biggest chance to improve is {SKILL_NAMES[worst]} ({scores[worst]}/100).")
    if weaknesses:
        parts.append(weaknesses[0]["detail"])
    parts.append("The three drills below target the lowest scores this week.")
    weakest = [k for _, k in measured[:3]]
    weakest += [k for k in ("consistency", "ball_handling", "court_vision") if k not in weakest]
    return {"source": "rules", "model": None, "generated_at": _now(), "summary": " ".join(parts),
            "drills": [dict(zip(("name", "description", "dose"), DRILLS[k])) for k in weakest[:3]]}


def _ai_payload(summary, scores, analyses):
    """Numbers only - nothing that identifies the kid."""
    def pick(a, keys):
        return {k: a.get(k) for k in keys} if a else None
    s, d, j = analyses.get("shooting"), analyses.get("dribbling"), analyses.get("jump")
    return {
        "age_group": summary["age_group"], "gender": summary["gender"],
        "position": summary["position"], "dominant_hand": summary["dominant_hand"],
        "years_playing": summary["years_playing"],
        "skill_scores_0_100": scores,
        # Only numbers the AI can judge: shot-to-shot spread (consistency) and targets that have
        # a checked ideal range. Raw angles/timings without a range are NOT sent - the AI would
        # guess what "good" is. Unvalidated targets (config.NOT_VALIDATED) are never sent.
        "shooting_consistency": pick(s, ["spread_elbow_deg", "spread_knee_deg", "spread_release"]),
        "shooting_targets": [{k: t[k] for k in ("label", "value", "unit", "ideal_min", "ideal_max", "status")}
                             for t in (s or {}).get("targets", [])
                             if t["metric"] not in config.NOT_VALIDATED and t["status"] != "unknown"],
        "dribbling": pick(d, ["dribbles_per_sec", "rhythm_score", "ball_below_hip_pct",
                              "weak_hand_pct", "head_up_pct"]),
        "jump": pick(j, ["best_jump_cm", "avg_jump_cm"]),
    }


SYSTEM_PROMPT = """You are a youth basketball coach writing a short weekly report for a coach and a young player.
You get ONLY measured numbers from video analysis. Rules:
- Explain only the numbers you are given. Never invent numbers, injuries, games or made/missed shots.
- Plain, encouraging language a 12-year-old understands. No medical advice.
- summary: 3-5 sentences. Name one clear strength and the 1-2 most important things to improve.
- Give technique advice ONLY for items in shooting_targets (they have an ideal range). Don't give advice
  about elbow angle, knee bend, timing or follow-through unless they are listed there.
- A skill score of null means not measured yet: don't mention it.
- shooting_consistency are spreads between shots (lower = more repeatable).
- drills: EXACTLY 3 drills for this week that target the weakest areas.
  Every drill must be doable by ONE player alone, with only a ball, a hoop and/or a wall.
  No teammates, partners, games, coaches or special equipment.
  Each: name (short), description (1 sentence), dose (e.g. "3 x 50 reps, 4 days this week").
Answer with JSON only: {"summary": "...", "drills": [{"name": "...", "description": "...", "dose": "..."}]}"""


_PLAIN = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": " - ",
                        "‘": "'", "’": "'", "“": '"', "”": '"', " ": " ",
                        " ": " ", " ": " "})


def _plain(text):
    """AI text sometimes has special dashes / spaces - keep it simple for every font and terminal."""
    return " ".join(text.translate(_PLAIN).split())


def _valid(out):
    if not isinstance(out, dict) or not isinstance(out.get("summary"), str) or len(out["summary"]) < 20:
        return False
    drills = out.get("drills")
    return (isinstance(drills, list) and len(drills) == 3
            and all(isinstance(x, dict) and all(isinstance(x.get(k), str) and x[k].strip()
                                                for k in ("name", "description", "dose")) for x in drills))


def ai_report(summary, scores, analyses):
    """Returns a CoachReport dict, or None if the AI is not configured / fails."""
    if not config.GROQ_API_KEY or all(v is None for v in scores.values()):
        return None
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            json={"model": config.GROQ_MODEL, "temperature": 0.4,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": json.dumps(_ai_payload(summary, scores, analyses))}]},
            timeout=config.AI_TIMEOUT_S)
        r.raise_for_status()
        out = json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception as e:                       # offline, timeout, bad key, bad JSON...
        print(f"AI coach report failed, using rules: {e.__class__.__name__}: {e}")
        return None
    if not _valid(out):
        print("AI coach report had the wrong shape, using rules")
        return None
    return {"source": "ai", "model": f"{config.GROQ_MODEL.split('/')[-1]} (Groq)", "generated_at": _now(),
            "summary": _plain(out["summary"]),
            "drills": [{k: _plain(x[k]) for k in ("name", "description", "dose")} for x in out["drills"]]}


def coach_report(summary, scores, analyses):
    strengths, weaknesses = insights(scores, analyses)
    return ai_report(summary, scores, analyses) or rules_report(scores, strengths, weaknesses)
