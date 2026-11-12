"""
Simulated players (is_real: false) and the contract's p_001 example.

The simulated kids have a built-in relative-age and height bias (like real youth
selection), so the fair ranking, hidden gems and Bias Check have something to show.
Generated from a fixed seed: the same 400 kids every run, never stored in the DB.
"""
import random
from datetime import date

from .config import MIN_REPS
from .derive import age_months, avg_height_cm
from .schemas import SKILL_KEYS
from .scoring import clamp, target_check

FIRST = {"boy": ["Amar", "Emir", "Tarik", "Kenan", "Adnan", "Haris", "Dino", "Luka", "Ivan", "Marko",
                 "Faris", "Benjamin", "Daris", "Vedad", "Eldar", "Nikola", "Mirza", "Ajdin"],
         "girl": ["Amila", "Lejla", "Ema", "Sara", "Ajla", "Merima", "Lana", "Nina", "Hana", "Dalia",
                  "Ena", "Maja", "Iva", "Selma", "Amina", "Lea", "Tea", "Asja"]}
LAST = ["Hodžić", "Begić", "Kovač", "Delić", "Mehić", "Halilović", "Babić", "Jurić", "Petrović",
        "Šarić", "Mujić", "Alić", "Kurtović", "Husić", "Marić", "Omerović"]
TOWNS = ["Sarajevo", "Mostar", "Tuzla", "Zenica", "Banja Luka", "Bihać"]
CLUBS = ["KK Orlovi", "KK Vukovi", "KK Sokolovi", "KK Hrast", "KK Ris", "KK Plamen"]
GROUP_AGE = {"U10": (8, 9), "U12": (10, 11), "U14": (12, 13), "U16": (14, 15), "U18": (16, 17)}
PER_GROUP = 40


def new_record(pid, inp, is_real):
    return {"id": pid, "is_real": is_real, "input": inp,
            "scores": {k: None for k in SKILL_KEYS}, "status": "provisional",
            "provisional_reason": "No videos analyzed yet", "score_margin": 10,
            "analyses": {"shooting": None, "dribbling": None, "jump": None},
            "coach_report": None, "sessions": [], "summary": None}


def simulated_players(today=None, seed=42):
    today = today or date.today()
    rng = random.Random(seed)
    out, n = [], 100
    for gender in ("boy", "girl"):
        for ages in GROUP_AGE.values():
            for _ in range(PER_GROUP):
                years = rng.choice(ages)            # age reached this calendar year
                # relative age effect: selected kids are more often born early in the year
                q = rng.choices([1, 2, 3, 4], weights=[0.34, 0.28, 0.22, 0.16])[0]
                birth = date(today.year - years, rng.randint(3 * q - 2, 3 * q), rng.randint(1, 28))
                months = age_months(birth, today)
                height = round(avg_height_cm(gender, months) + rng.gauss(0, 7), 1)
                inp = dict(name=f"{rng.choice(FIRST[gender])} {rng.choice(LAST)}", gender=gender,
                           birth_date=birth.isoformat(), height_cm=height, weight_kg=None,
                           sitting_height_cm=None,
                           dominant_hand=rng.choices(["right", "left"], [0.85, 0.15])[0],
                           position=rng.choice(["guard", "forward", "center"]),
                           years_playing=rng.randint(1, max(1, years - 6)),
                           club=rng.choice(CLUBS), town=rng.choice(TOWNS))
                rec = new_record(f"p_{n:03d}", inp, is_real=False)
                n += 1
                talent = rng.gauss(55, 10)
                # measured skill = talent + bias from being older (in months) and taller
                rel_age = months - (ages[0] * 12 + 10)      # months older than the middle of the group
                bias = 0.30 * rel_age + 0.40 * (height - avg_height_cm(gender, months))
                rec["scores"] = {k: int(round(clamp(talent + bias + rng.gauss(0, 8)))) for k in SKILL_KEYS}
                if rng.random() < 0.08:
                    rec["provisional_reason"] = rng.choice(
                        ["Only 4 shots (need 6)", "Only 14 s of dribbling (need 20)",
                         "Tracking quality 62% (need 70%)"])
                else:
                    rec["status"], rec["provisional_reason"] = "ranked", None
                    rec["score_margin"] = rng.randint(3, 7)
                out.append(rec)
    return out


# ------------------------------------------------------------------ contract example (p_001)
EXAMPLE_INPUT = dict(name="Player One", gender="boy", birth_date="2012-10-05", height_cm=165,
                     weight_kg=None, sitting_height_cm=None, dominant_hand="right", position="guard",
                     years_playing=2, club="KK Example", town="Sarajevo")


def example_analyses():
    """Analyses from the contract example - used by tests (fake pipeline) and the first start."""
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
        "quality": {"tracking_pct": 100, "reps": 10, "min_reps": MIN_REPS["shooting"], "ok": True},
        "flags": [], "annotated_video_url": None,
    }
    shooting["targets"] = [t for t in (target_check(m, shooting[m]) for m in
                           ("avg_elbow_set_deg", "avg_knee_min_deg",
                            "avg_leg_arm_timing_ms", "avg_follow_through_s")) if t]
    dribbling = {
        "duration_s": 29.9, "dribbles": 59, "dribbles_per_sec": 1.97, "rhythm_score": 32,
        "ball_below_hip_pct": 88, "ball_below_knee_pct": 2,
        "left_hand_pct": 50, "right_hand_pct": 50, "weak_hand_pct": 50, "head_up_pct": 37,
        "quality": {"tracking_pct": 98, "reps": 30, "min_reps": MIN_REPS["dribbling"], "ok": True},
        "flags": [], "annotated_video_url": None,
    }
    dribbling["targets"] = [t for t in (target_check(m, dribbling[m]) for m in
                            ("head_up_pct", "ball_below_hip_pct", "weak_hand_pct")) if t]
    jump = {
        "jumps": [{"index": 1, "air_time_s": 0.50, "height_cm": 31.8},
                  {"index": 2, "air_time_s": 0.52, "height_cm": 33.1},
                  {"index": 3, "air_time_s": 0.49, "height_cm": 30.2},
                  {"index": 4, "air_time_s": 0.50, "height_cm": 31.7}],
        "best_jump_cm": 33.1, "avg_jump_cm": 31.7, "targets": [],
        "quality": {"tracking_pct": 100, "reps": 4, "min_reps": MIN_REPS["jump"], "ok": True},
        "flags": [], "annotated_video_url": None,
    }
    return {"shooting": shooting, "dribbling": dribbling, "jump": jump}
