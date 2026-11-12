"""
PHASE 1 MOCK: in-memory data so the frontend can build every screen now.

- ~400 simulated players (40 per gender + age group) (is_real: false) with a built-in relative-age / height bias,
  so the Talent Board, hidden gems and Bias Check have something to show.
- p_001 = Hamza's real test numbers from the contract (placeholder name).
- Uploads are saved to data/uploads, but "analysis" is faked: jobs advance by time,
  and /analyze attaches p_001's numbers with a little jitter.

Everything here is replaced by SQLite + the real pipeline in phases 2-3.
Data is lost when the server restarts.
"""
import copy
import random
import threading
import time
import uuid
from datetime import date, datetime, timezone
from statistics import mean

from . import config
from .derive import (age_group, age_months, avg_height_cm, birth_quarter, height_diff_cm,
                     mirwald_offset, rank_group)
from .schemas import SKILL_KEYS
from .scoring import clamp, fair_from, rank_players, target_check, weighted_mean

LOCK = threading.Lock()
PLAYERS: dict = {}   # id -> record
JOBS: dict = {}      # job_id -> record

# Mock coefficients (Phase 3: fitted by regression per skill + gender).
B_AGE = 0.30         # points per month younger than the group average
C_SIZE = 0.40        # points per cm smaller than the group average

JOB_SECONDS = 12     # fake analysis duration


def _media_url(filename):
    return f"{config.PUBLIC_BASE_URL}/media/{filename}" if (config.MEDIA_DIR / filename).exists() else None


# ------------------------------------------------------------------ p_001 fixture (from the contract)
def _hamza_analyses(pid="p_001"):
    shooting = {
        "shots": [
            {"index": 1, "time_s": 2.3, "elbow_set_deg": 60.2, "knee_min_deg": 119.7,
             "release_height_ratio": 1.165, "leg_arm_timing_ms": 167, "follow_through_s": 0.53},
            {"index": 2, "time_s": 5.1, "elbow_set_deg": 55.4, "knee_min_deg": 104.2,
             "release_height_ratio": 1.21, "leg_arm_timing_ms": 133, "follow_through_s": 0.57},
            {"index": 3, "time_s": 8.0, "elbow_set_deg": 54.1, "knee_min_deg": 106.0,
             "release_height_ratio": 1.205, "leg_arm_timing_ms": 117, "follow_through_s": 0.55},
        ],
        "skipped": [{"time_s": 27.89, "reason": "no knee bend - catch/pass/rebound?"}],
        "avg_elbow_set_deg": 56, "avg_knee_min_deg": 107, "avg_release_height_ratio": 1.20,
        "avg_leg_arm_timing_ms": 137, "avg_follow_through_s": 0.56,
        "spread_elbow_deg": 2.7, "spread_knee_deg": 4.9, "spread_release": 0.018,
        "quality": {"tracking_pct": 100, "reps": 10, "min_reps": 6, "ok": True},
        "flags": [],
        "annotated_video_url": _media_url(f"{pid}_shooting.mp4"),
    }
    shooting["targets"] = [t for t in (target_check(m, shooting[m]) for m in
                           ("avg_elbow_set_deg", "avg_knee_min_deg",
                            "avg_leg_arm_timing_ms", "avg_follow_through_s")) if t]
    dribbling = {
        "duration_s": 29.9, "dribbles": 59, "dribbles_per_sec": 1.97, "rhythm_score": 32,
        "ball_below_hip_pct": 88, "ball_below_knee_pct": 2,
        "left_hand_pct": 50, "right_hand_pct": 50, "weak_hand_pct": 50, "head_up_pct": 37,
        "quality": {"tracking_pct": 98, "reps": 30, "min_reps": 20, "ok": True},
        "flags": [],
        "annotated_video_url": _media_url(f"{pid}_dribbling.mp4"),
    }
    dribbling["targets"] = [t for t in (target_check(m, dribbling[m]) for m in
                            ("head_up_pct", "ball_below_hip_pct", "weak_hand_pct")) if t]
    jump = {
        "jumps": [{"index": 1, "air_time_s": 0.50, "height_cm": 31.8},
                  {"index": 2, "air_time_s": 0.52, "height_cm": 33.1},
                  {"index": 3, "air_time_s": 0.49, "height_cm": 30.2},
                  {"index": 4, "air_time_s": 0.50, "height_cm": 31.7}],
        "best_jump_cm": 33.1, "avg_jump_cm": 31.7, "targets": [],
        "quality": {"tracking_pct": 100, "reps": 4, "min_reps": 3, "ok": True},
        "flags": [],
        "annotated_video_url": _media_url(f"{pid}_jump.mp4"),
    }
    return {"shooting": shooting, "dribbling": dribbling, "jump": jump}


HAMZA_SCORES = {"shooting_form": 74, "consistency": 84, "ball_handling": 66,
                "weak_hand": 100, "court_vision": 37, "athleticism": 58}


# ------------------------------------------------------------------ records
def _new_record(pid, inp, is_real):
    return {"id": pid, "is_real": is_real, "input": inp,
            "scores": {k: None for k in SKILL_KEYS}, "status": "provisional",
            "provisional_reason": "No videos analyzed yet", "score_margin": 10,
            "analyses": {"shooting": None, "dribbling": None, "jump": None},
            "coach_report": None, "sessions": [], "summary": None}


def _next_real_id():
    n = 1
    while f"p_{n:03d}" in PLAYERS:
        n += 1
    return f"p_{n:03d}"


FIRST = {"boy": ["Amar", "Emir", "Tarik", "Kenan", "Adnan", "Haris", "Dino", "Luka", "Ivan", "Marko",
                 "Faris", "Benjamin", "Daris", "Vedad", "Eldar", "Nikola", "Mirza", "Ajdin"],
         "girl": ["Amila", "Lejla", "Ema", "Sara", "Ajla", "Merima", "Lana", "Nina", "Hana", "Dalia",
                  "Ena", "Maja", "Iva", "Selma", "Amina", "Lea", "Tea", "Asja"]}
LAST = ["Hodžić", "Begić", "Kovač", "Delić", "Mehić", "Halilović", "Babić", "Jurić", "Petrović",
        "Šarić", "Mujić", "Alić", "Kurtović", "Husić", "Marić", "Omerović"]
TOWNS = ["Sarajevo", "Mostar", "Tuzla", "Zenica", "Banja Luka", "Bihać"]
CLUBS = ["KK Orlovi", "KK Vukovi", "KK Sokolovi", "KK Hrast", "KK Ris", "KK Plamen"]
GROUP_AGE = {"U10": (8, 9), "U12": (10, 11), "U14": (12, 13), "U16": (14, 15), "U18": (16, 17)}


def _seed_synthetic(rng, today, per_group=40):
    n = 100
    for gender in ("boy", "girl"):
        for group, ages in GROUP_AGE.items():
            for _ in range(per_group):
                years = rng.choice(ages)            # age reached this calendar year
                # relative age effect: selected kids are more often born early in the year
                q = rng.choices([1, 2, 3, 4], weights=[0.34, 0.28, 0.22, 0.16])[0]
                birth = date(today.year - years, rng.randint(3 * q - 2, 3 * q), rng.randint(1, 28))
                months = age_months(birth, today)
                height = round(avg_height_cm(gender, months) + rng.gauss(0, 7), 1)
                inp = dict(name=f"{rng.choice(FIRST[gender])} {rng.choice(LAST)}", gender=gender,
                           birth_date=birth.isoformat(), height_cm=height, weight_kg=None,
                           sitting_height_cm=None, dominant_hand=rng.choices(["right", "left"], [0.85, 0.15])[0],
                           position=rng.choice(["guard", "forward", "center"]),
                           years_playing=rng.randint(1, max(1, years - 6)),
                           club=rng.choice(CLUBS), town=rng.choice(TOWNS))
                pid = f"p_{n:03d}"
                n += 1
                rec = _new_record(pid, inp, is_real=False)
                talent = rng.gauss(55, 10)
                # measured skill = talent + bias from being older (in months) and taller
                rel_age = months - (ages[0] * 12 + 10)   # months older than the middle of the group
                bias = 0.30 * rel_age + 0.40 * (height - avg_height_cm(gender, months))
                rec["scores"] = {k: int(round(clamp(talent + bias + rng.gauss(0, 8)))) for k in SKILL_KEYS}
                if rng.random() < 0.08:
                    rec["provisional_reason"] = rng.choice(
                        ["Only 4 shots (need 6)", "Only 14 s of dribbling (need 20)",
                         "Tracking quality 62% (need 70%)"])
                    rec["score_margin"] = 10
                else:
                    rec["status"], rec["provisional_reason"] = "ranked", None
                    rec["score_margin"] = rng.randint(3, 7)
                PLAYERS[pid] = rec


def _seed_hamza(today):
    inp = dict(name="Player One", gender="boy", birth_date="2012-10-05", height_cm=165,
               weight_kg=None, sitting_height_cm=None, dominant_hand="right", position="guard",
               years_playing=2, club="KK Example", town="Sarajevo")
    rec = _new_record("p_001", inp, is_real=True)
    rec["scores"] = dict(HAMZA_SCORES)
    rec["status"], rec["provisional_reason"], rec["score_margin"] = "ranked", None, 4
    rec["analyses"] = _hamza_analyses()
    rec["coach_report"] = None
    PLAYERS["p_001"] = rec


# ------------------------------------------------------------------ recompute (fair score + ranks)
def _labels(quarter, diff):
    age_label = {1: "Born early in the year (Q1)", 2: "Born in Q2", 3: "Born in Q3",
                 4: "Born late in the year (Q4)"}[quarter]
    if abs(diff) < 3:
        size_label = "Height close to age average"
    else:
        size_label = f"{abs(diff):.0f} cm {'above' if diff > 0 else 'below'} age average"
    return age_label, size_label


def recompute_all(today=None):
    """Rebuild every PlayerSummary and re-rank everyone."""
    today = today or date.today()
    derived = {}
    for pid, rec in PLAYERS.items():
        inp = rec["input"]
        birth = date.fromisoformat(inp["birth_date"])
        months = age_months(birth, today)
        grp = age_group(birth, today)
        derived[pid] = dict(months=months, group=grp, rank_group=rank_group(inp["gender"], grp),
                            quarter=birth_quarter(birth),
                            diff=height_diff_cm(inp["gender"], months, inp["height_cm"]))
    # group means (mock uses rank_group; see the note in the contract questions)
    by_group = {}
    for pid, d in derived.items():
        by_group.setdefault(d["rank_group"], []).append(pid)
    means = {g: (mean(derived[p]["months"] for p in ids), mean(derived[p]["diff"] for p in ids))
             for g, ids in by_group.items()}

    summaries = []
    for pid, rec in PLAYERS.items():
        inp, d = rec["input"], derived[pid]
        m_age, m_diff = means[d["rank_group"]]
        age_adj = {k: B_AGE * (m_age - d["months"]) for k in SKILL_KEYS}
        size_adj = {k: C_SIZE * (m_diff - d["diff"]) for k in SKILL_KEYS}
        age_label, size_label = _labels(d["quarter"], d["diff"])
        f = fair_from(rec["scores"], age_adj, size_adj, inp["years_playing"], age_label, size_label)
        base = weighted_mean(rec["scores"])
        # traditional scout: skill plus a bonus for being older and taller
        raw = 0 if base is None else int(round(clamp(base - age_adj["consistency"] - size_adj["consistency"])))
        summaries.append(dict(
            id=pid, is_real=rec["is_real"], name=inp["name"], gender=inp["gender"],
            age_months=d["months"], age_group=d["group"], rank_group=d["rank_group"],
            birth_quarter=d["quarter"], height_cm=inp["height_cm"], height_diff_cm=d["diff"],
            maturity_offset_years=mirwald_offset(inp["gender"], d["months"], inp["height_cm"],
                                                 inp.get("sitting_height_cm"), inp.get("weight_kg")),
            dominant_hand=inp["dominant_hand"], position=inp["position"],
            years_playing=inp["years_playing"], club=inp["club"], town=inp["town"],
            status=rec["status"], provisional_reason=rec["provisional_reason"],
            scores=rec["scores"], fair_scores=f["fair_scores"], experience_bonus=f["experience_bonus"],
            raw_score=raw, fair_score=f["fair_score"], score_margin=rec["score_margin"],
            breakdown=f["breakdown"], photo_url=None))
    rank_players(summaries)
    for s in summaries:
        PLAYERS[s["id"]]["summary"] = s


# ------------------------------------------------------------------ report pieces
SKILL_TEXT = {
    "shooting_form": ("Clean shooting form", "Shooting form needs work"),
    "consistency": ("Very repeatable shot", "Shot changes from rep to rep"),
    "ball_handling": ("Quick, controlled dribble", "Dribble speed and rhythm"),
    "weak_hand": ("Uses both hands", "Weak hand rarely used"),
    "court_vision": ("Plays with the head up", "Eyes on the ball"),
    "athleticism": ("Explosive jump", "Jump power"),
}
DRILLS = {
    "shooting_form": ("Form shooting close to the rim", "One hand, 1 m from the rim, hold the follow-through.", "3 x 25 shots, 4 days this week"),
    "consistency": ("Same-spot repeats", "10 shots from the same spot with the same routine every time.", "5 x 10 shots, 4 days this week"),
    "ball_handling": ("Pound dribbles", "Hard, low dribbles as fast as possible while staying in control.", "4 x 30 s each hand, 4 days this week"),
    "weak_hand": ("Weak-hand only", "Dribble and lay up using only the weak hand.", "3 x 2 min, 5 days this week"),
    "court_vision": ("Eyes-up dribble", "Dribble while calling out the number of fingers the coach holds up.", "3 x 60 s, 4 days this week"),
    "athleticism": ("Box jumps", "Jump onto a low box, land softly on both feet.", "3 x 8 jumps, 3 days this week"),
}


def insights(scores):
    measured = sorted(((v, k) for k, v in scores.items() if v is not None), reverse=True)
    strengths = [{"title": SKILL_TEXT[k][0], "detail": f"{k.replace('_', ' ').capitalize()} score {v}/100.",
                  "metric": k} for v, k in measured[:2] if v >= 60]
    weaknesses = [{"title": SKILL_TEXT[k][1], "detail": f"{k.replace('_', ' ').capitalize()} score {v}/100.",
                   "metric": k} for v, k in measured[::-1][:2] if v < 60]
    return strengths, weaknesses


def rules_coach_report(rec):
    scores = rec["scores"]
    measured = sorted((v, k) for k, v in scores.items() if v is not None)
    if not measured:
        summary = "No videos have been analyzed yet, so there is nothing to report."
        weakest = ["consistency", "ball_handling", "court_vision"]
    else:
        best, worst = measured[-1][1], measured[0][1]
        summary = (f"Strongest area: {best.replace('_', ' ')} ({scores[best]}/100). "
                   f"Biggest chance to improve: {worst.replace('_', ' ')} ({scores[worst]}/100). "
                   "The drills below target the lowest scores this week.")
        weakest = [k for _, k in measured[:3]]
    drills = [dict(zip(("name", "description", "dose"), DRILLS[k])) for k in weakest]
    return {"source": "rules", "model": None, "summary": summary, "drills": drills,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}


def group_average(rank_grp):
    members = [r["summary"] for r in PLAYERS.values()
               if r["summary"]["rank_group"] == rank_grp and r["summary"]["status"] == "ranked"]
    out = {}
    for k in SKILL_KEYS:
        vals = [m["scores"][k] for m in members if m["scores"][k] is not None]
        out[k] = int(round(mean(vals))) if vals else None
    return out


def report(pid):
    rec = PLAYERS[pid]
    s = rec["summary"]
    strengths, weaknesses = insights(rec["scores"])
    return {"player": s, "group_average": group_average(s["rank_group"]),
            **rec["analyses"], "strengths": strengths, "weaknesses": weaknesses,
            "coach_report": rec["coach_report"], "sessions": rec["sessions"]}


# ------------------------------------------------------------------ actions used by the routes
def create_player(inp: dict) -> dict:
    with LOCK:
        pid = _next_real_id()
        PLAYERS[pid] = _new_record(pid, inp, is_real=True)
        recompute_all()
        return PLAYERS[pid]["summary"]


STEPS = {
    "shooting": ["Converting video", "Detecting pose", "Finding shots", "Measuring form", "Saving results"],
    "dribbling": ["Converting video", "Detecting pose", "Tracking ball", "Counting dribbles", "Saving results"],
    "jump": ["Converting video", "Detecting pose", "Finding jumps", "Measuring height", "Saving results"],
}


def create_job(pid, kind, filename) -> dict:
    job_id = f"j_{uuid.uuid4().hex[:8]}"
    with LOCK:
        JOBS[job_id] = {"job_id": job_id, "player_id": pid, "kind": kind, "started": time.time(),
                        "fail": "fail" in filename.lower()}   # name a file *fail* to test errors
    return job_view(job_id)


def job_view(job_id) -> dict:
    j = JOBS[job_id]
    elapsed = time.time() - j["started"]
    steps = STEPS[j["kind"]]
    base = {"job_id": job_id, "player_id": j["player_id"], "kind": j["kind"], "error": None}
    if elapsed < 1:
        return {**base, "status": "queued", "progress": 0, "step": "Waiting in queue"}
    if j["fail"] and elapsed > JOB_SECONDS / 2:
        return {**base, "status": "failed", "progress": 50, "step": steps[2],
                "error": "Player too small in the frame - move the camera closer and film again."}
    if elapsed >= JOB_SECONDS:
        return {**base, "status": "done", "progress": 100, "step": "Done"}
    progress = int(100 * elapsed / JOB_SECONDS)
    return {**base, "status": "running", "progress": progress,
            "step": steps[min(len(steps) - 1, progress * len(steps) // 100)]}


def analyze(pid) -> dict:
    """Mock: attach p_001's numbers (jittered) for every finished upload, then re-rank everyone."""
    done = {JOBS[j]["kind"] for j in JOBS
            if JOBS[j]["player_id"] == pid and job_view(j)["status"] == "done"}
    rng = random.Random(pid)
    with LOCK:
        rec = PLAYERS[pid]
        if pid != "p_001":
            fixture = _hamza_analyses(pid)
            rec["analyses"] = {k: (fixture[k] if k in done else None) for k in fixture}
            skill_kind = {"shooting_form": "shooting", "consistency": "shooting",
                          "ball_handling": "dribbling", "weak_hand": "dribbling",
                          "court_vision": "dribbling", "athleticism": "jump"}
            rec["scores"] = {k: (int(clamp(v + rng.randint(-12, 12))) if skill_kind[k] in done else None)
                             for k, v in HAMZA_SCORES.items()}
            missing = [k for k in ("shooting", "dribbling", "jump") if k not in done]
            if missing:
                rec["status"] = "provisional"
                rec["provisional_reason"] = f"No {missing[0]} video yet"
                rec["score_margin"] = 10
            else:
                rec["status"], rec["provisional_reason"], rec["score_margin"] = "ranked", None, 5
        recompute_all()
        rec["coach_report"] = rules_coach_report(rec)
        targets = {t["metric"]: t["value"] for a in rec["analyses"].values() if a for t in a["targets"]}
        rec["sessions"] = [{"session_id": f"s_{pid[2:]}", "date": date.today().isoformat(),
                            "fair_score": rec["summary"]["fair_score"], "target_values": targets}]
        return report(pid)


def regenerate_coach_report(pid) -> dict:
    with LOCK:
        rec = PLAYERS[pid]
        rec["coach_report"] = rules_coach_report(rec)
        return rec["coach_report"]


def bias(gender=None, rank_grp=None):
    """
    Never mixes boys and girls or age groups: "top 10" = the top 10 of EACH rank_group,
    using the ranks computed inside that group (raw_rank <= 10 / fair_rank <= 10).
    Optional filters: gender ("boy"/"girl") or one rank_group ("Boys U14").
    """
    everyone = [r["summary"] for r in PLAYERS.values()
                if (gender is None or r["summary"]["gender"] == gender)
                and (rank_grp is None or r["summary"]["rank_group"] == rank_grp)]
    ranked = [p for p in everyone if p["status"] == "ranked"]

    def quarters(players):
        q = [0, 0, 0, 0]
        for p in players:
            q[p["birth_quarter"] - 1] += 1
        return q

    def avg_diff(players):
        return round(mean(p["height_diff_cm"] for p in players), 1) if players else 0.0

    all_q = quarters(everyone)
    raw10 = [p for p in ranked if p["raw_rank"] <= 10]
    fair10 = [p for p in ranked if p["fair_rank"] <= 10]
    return {
        "birth_quarter": {"all_players": all_q, "raw_top10": quarters(raw10), "fair_top10": quarters(fair10)},
        "height": {
            "raw_top10_avg_diff_cm": avg_diff(raw10),
            "fair_top10_avg_diff_cm": avg_diff(fair10),
            "points": [{"id": p["id"], "name": p["name"], "height_diff_cm": p["height_diff_cm"],
                        "raw_rank": p["raw_rank"], "fair_rank": p["fair_rank"]} for p in ranked],
        },
        "explanation": ("Counts use the top 10 of each group (same gender and age group). "
                        "A traditional ranking favours kids born early in the year and kids who are "
                        "taller than average, because they are simply further in their growth. "
                        "The fair score compares each kid with what is expected for their age and "
                        "size, so late-born and smaller kids with real skill move up."),
    }


# ------------------------------------------------------------------ startup
def seed():
    PLAYERS.clear()
    JOBS.clear()
    today = date.today()
    _seed_hamza(today)
    _seed_synthetic(random.Random(42), today)
    recompute_all(today)
