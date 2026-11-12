"""
All tunable numbers in one place (paths, CORS, scoring config).

Values marked TODO must come from a coach or a coaching source - don't guess them.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # repo root
load_dotenv(ROOT / ".env")

# ------------------------------------------------------------------ server
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o.strip()]
# DEMO MODE = stage safety net: uploads skip the 10-20 min analysis and replay p_001's saved
# results in ~DEMO_JOB_SECONDS. /api/health returns demo_mode: true so the UI shows the badge.
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_JOB_SECONDS = float(os.getenv("DEMO_JOB_SECONDS", "10"))

# AI coach report (Groq). Empty key = rule-based report only.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")   # Llama 3.3 is no longer on Groq
AI_TIMEOUT_S = float(os.getenv("AI_TIMEOUT_S", "15"))

# ------------------------------------------------------------------ storage (local only, never online)
DATA_DIR = Path(os.getenv("HOOPSCOUT_DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"       # original files from the coach
WORK_DIR = DATA_DIR / "work"            # converted .mp4 (step 1)
MEDIA_DIR = DATA_DIR / "media"          # annotated videos, served at /media
DB_PATH = DATA_DIR / "hoopscout.db"
for _d in (UPLOAD_DIR, WORK_DIR, MEDIA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Models (absolute paths, so the server can start from any folder)
YOLO_MODEL = os.getenv("YOLO_MODEL", str(ROOT / "yolov8n.pt"))

# Pipeline defaults tested on real videos - only tune with evidence from several kids.
BALL_MAX_DIST = 0.5      # step3 --max-dist
BALL_CONF = 0.15         # step3 --conf
SHOT_MAX_KNEE = 150.0    # step4 --max-knee

VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi"}

# ------------------------------------------------------------------ scoring
# Weights w_k for fair_score (contract: consistency 1.5, others 1).
WEIGHTS = {
    "shooting_form": 1.0,
    "consistency": 1.5,
    "ball_handling": 1.0,
    "weak_hand": 1.0,
    "court_vision": 1.0,
    "athleticism": 1.0,
}


def experience_bonus(years_playing: int) -> int:
    """Contract: +4 for 1 year playing, +2 for 2-3 years, 0 for 4+."""
    if years_playing <= 1:
        return 4
    if years_playing <= 3:
        return 2
    return 0


# Minimum reps before a kid can be ranked (else status "provisional").
MIN_REPS = {"shooting": 6, "dribbling": 20, "jump": 3}   # shots / seconds / jumps
MIN_TRACKING_PCT = 70

# Values outside these are tracking errors: flagged and excluded from scoring.
SANITY = {
    "elbow_set_deg": (30, 170),
    "knee_min_deg": (60, 175),
    "jump_cm": (0, 70),
    "dribbles_per_sec": (0, 5),
}

# Textbook ideal ranges for the development targets.
# (ideal_min, ideal_max, scale_min, scale_max, unit, label, tip)
# None = not sourced yet -> the target is returned with status "unknown".
IDEAL = {
    "avg_elbow_set_deg": (80, 100, 30, 140, "°", "Elbow angle at set point",
                          "Hold the ball a bit higher and further from your head before the push."),
    "avg_knee_min_deg": None,        # TODO: from a coach / coaching source
    "avg_leg_arm_timing_ms": None,   # TODO: from a coach / coaching source
    "avg_follow_through_s": None,    # TODO: from a coach / coaching source
    # Dribbling targets - PLACEHOLDERS for the mock, confirm with a coach:
    "head_up_pct": (70, 100, 0, 100, "%", "Head up while dribbling",
                    "Look at the rim or the coach, not the ball."),
    "ball_below_hip_pct": (80, 100, 0, 100, "%", "Ball stays below the hip",
                           "Push the ball down hard so it comes back low."),
    "weak_hand_pct": (40, 60, 0, 100, "%", "Weak-hand dribbles",
                      "Do every drill with the weak hand first."),
}

# Age-appropriate ideal ranges. The IDEAL range above is the target from U14 up (textbook form).
# Younger kids get a wider / lower target: less strength, more leg drive, and in Bosnian
# minibasket (U10-U12) usually a lower hoop (2.60 m) and a smaller ball (size 5).
# PLACEHOLDERS - confirm every number with a coach. Missing group -> the IDEAL range.
IDEAL_BY_AGE = {
    "avg_elbow_set_deg":  {"U10": (60, 100), "U12": (70, 100)},
    "head_up_pct":        {"U10": (50, 100), "U12": (60, 100)},
    "ball_below_hip_pct": {"U10": (70, 100)},
    "weak_hand_pct":      {"U10": (30, 60), "U12": (35, 60)},
}

# Norms for skills where a raw number means different things at different ages:
# (median, standard deviation) per gender + age group. A kid's score = their percentile among
# kids of the same gender and age group (50 = typical for the group, 84 = one SD above).
# APPROXIMATE PLACEHOLDERS (rough youth countermovement-jump values) - replace with official
# norm tables, ideally from the federation / a sports-science source.
JUMP_NORMS_CM = {
    "boy":  {"U10": (24, 5), "U12": (27, 5), "U14": (31, 6), "U16": (37, 6), "U18": (41, 6)},
    "girl": {"U10": (23, 5), "U12": (25, 5), "U14": (27, 5), "U16": (28, 5), "U18": (29, 5)},
}
# Dribbles per second while dribbling in place - PLACEHOLDERS, same for boys and girls.
DPS_NORMS = {"U10": (1.5, 0.45), "U12": (1.7, 0.45), "U14": (1.9, 0.45), "U16": (2.1, 0.45), "U18": (2.2, 0.45)}

# Measurements we show but don't score or give advice on yet.
# Elbow at set: Hamza reads ~56° vs the textbook 80-100°. Film one adult who shoots well
# and run step 4: ~85-95° -> remove it from this set; ~60° -> fix set-point detection first.
NOT_VALIDATED = {"avg_elbow_set_deg"}

# Average height (cm) by age in years, 50th percentile. APPROXIMATE values for the
# mock - replace with an official WHO/CDC table before the real ranking.
HEIGHT_REF = {
    "boy":  {8: 128, 9: 133, 10: 138, 11: 143, 12: 149, 13: 156, 14: 163, 15: 169, 16: 173, 17: 175, 18: 176},
    "girl": {8: 127, 9: 133, 10: 138, 11: 144, 12: 151, 13: 156, 14: 159, 15: 161, 16: 162, 17: 163, 18: 163},
}
