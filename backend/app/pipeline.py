"""
Video pipeline: runs the TESTED step scripts on one upload and returns the contract's
ShootingAnalysis / DribblingAnalysis / JumpAnalysis dict.

    step1 convert -> step2 pose + quality -> step3 / step4 / step5 -> annotated video

The step scripts stay the single source of truth: a fix in step4_shooting_test.py
(e.g. set-point detection) is used by the app automatically.
"""
import sys
import time
from typing import Callable, Optional

import numpy as np

from . import config
from .errors import PipelineError  # noqa: F401  (re-exported)
from .scoring import target_check

if str(config.ROOT) not in sys.path:          # the step scripts live in the repo root
    sys.path.insert(0, str(config.ROOT))

import common                                   # noqa: E402
import step1_convert                            # noqa: E402
import step2_pose_test                          # noqa: E402
import step3_dribble_ball_test as step3         # noqa: E402
import step4_shooting_test as step4             # noqa: E402
import step5_jump_test as step5                 # noqa: E402

Progress = Callable[[int, str], None]


def _r(v, nd=1):
    if v is None:
        return None
    v = float(v)
    return None if (np.isnan(v) or np.isinf(v)) else round(v, nd)


def _mean(vals, nd=1):
    vals = [v for v in vals if v is not None]
    return _r(np.mean(vals), nd) if vals else None


def _std(vals, nd=1):
    vals = [v for v in vals if v is not None]
    return _r(np.std(vals), nd) if len(vals) >= 2 else None


def _quality(tracking, reps, kind):
    min_reps = config.MIN_REPS[kind]
    ok = (tracking is not None and tracking >= config.MIN_TRACKING_PCT
          and reps is not None and reps >= min_reps)
    return {"tracking_pct": _r(tracking, 0), "reps": _r(reps, 1), "min_reps": min_reps, "ok": bool(ok)}


def _video_flags(check):
    """step2's camera problems ("Player too small -> move camera closer") as flags."""
    return [{"metric": "video", "value": _r(check["size_pct"], 0) or 0.0, "message": p}
            for p in check["problems"]]


def _sane(metric, value):
    lo, hi = config.SANITY[metric]
    return value is None or lo <= value <= hi


def _media_url(name):
    return f"{config.PUBLIC_BASE_URL}/media/{name}?v={int(time.time())}"   # ?v= busts the browser cache


# ------------------------------------------------------------------ the three kinds
def _shooting(pose, check, video, out, hand, progress):
    shots, summary, elbow, knee = step4.analyze_shooting(pose, hand, config.SHOT_MAX_KNEE)
    flags = _video_flags(check)
    rows = []
    for s in shots:
        e, k = s["elbow_set"], s["knee_min"]
        if not _sane("elbow_set_deg", e):
            flags.append({"metric": "elbow_set_deg", "value": e,
                          "message": f"Shot {s['shot']}: elbow {e:.0f}° is not realistic - tracking error?"})
            e = None
        if not _sane("knee_min_deg", k):
            flags.append({"metric": "knee_min_deg", "value": k,
                          "message": f"Shot {s['shot']}: knee {k:.0f}° is not realistic - tracking error?"})
            k = None
        rows.append({"index": s["shot"], "time_s": s["time_s"], "elbow_set_deg": _r(e),
                     "knee_min_deg": _r(k), "release_height_ratio": _r(s["release_height"], 3),
                     "leg_arm_timing_ms": _r(s["sync_ms"], 0), "follow_through_s": _r(s["follow_through_s"], 2)})
    col = lambda key: [r[key] for r in rows]                         # noqa: E731
    a = {
        "shots": rows,
        "skipped": [{"time_s": float(t), "reason": why} for t, why in summary["skipped"]],
        "avg_elbow_set_deg": _mean(col("elbow_set_deg")),
        "avg_knee_min_deg": _mean(col("knee_min_deg")),
        "avg_release_height_ratio": _mean(col("release_height_ratio"), 3),
        "avg_leg_arm_timing_ms": _mean(col("leg_arm_timing_ms"), 0),
        "avg_follow_through_s": _mean(col("follow_through_s"), 2),
        "spread_elbow_deg": _std(col("elbow_set_deg")),
        "spread_knee_deg": _std(col("knee_min_deg")),
        "spread_release": _std(col("release_height_ratio"), 3),
        "quality": _quality(check["det_rate"], len(rows), "shooting"),
        "flags": flags,
    }
    a["targets"] = [t for t in (target_check(m, a[m]) for m in
                    ("avg_elbow_set_deg", "avg_knee_min_deg", "avg_leg_arm_timing_ms",
                     "avg_follow_through_s")) if t]
    if shots:
        progress(80, "Drawing video")
        step4.save_annotated(video, pose, shots, elbow, knee, str(out))
    return a, bool(shots)


def _dribbling(pose, check, video, out, hand, progress):
    fps = pose["fps"]
    n_frames = len(pose["xy"])

    def on_ball(i):
        progress(35 + int(45 * i / max(n_frames, 1)), "Tracking ball")

    raw_xy, radii, _ = step3.detect_ball(video, config.YOLO_MODEL, config.BALL_CONF,
                                         pose_xy=pose["xy"], max_dist=config.BALL_MAX_DIST,
                                         on_frame=on_ball)
    progress(82, "Counting dribbles")
    ball_xy, interp = step3.fill_gaps(raw_xy, max_gap=int(0.3 * fps))
    ball_pct = 100 * float(np.mean(~np.isnan(ball_xy[:, 0]))) if len(ball_xy) else 0.0
    res = step3.analyze_dribble(pose, ball_xy, fps)
    duration = n_frames / fps
    flags = _video_flags(check)
    ball_ok = ball_pct >= 40

    if ball_ok:
        dribbles, dps = res["dribbles_ball"], res["dribbles_per_sec"]
        b = res["bounces"]
        span = (b[-1] - b[0]) / fps if len(b) >= 2 else 0.0
    else:   # fallback: wrist count, ball-based numbers are not trustworthy
        dribbles = res["dribbles_wrist"]
        dps = dribbles / duration if duration else None
        span = duration if dribbles else 0.0
        flags.append({"metric": "ball_tracking", "value": round(ball_pct, 0),
                      "message": f"Ball found in only {ball_pct:.0f}% of frames - dribbles counted from the wrists."})
    if dps is not None and not _sane("dribbles_per_sec", dps):
        flags.append({"metric": "dribbles_per_sec", "value": round(dps, 2),
                      "message": f"{dps:.1f} dribbles/sec is not realistic - tracking error?"})
        dps = None

    left, right = (res["left_hand_pct"], res["right_hand_pct"]) if ball_ok else (None, None)
    weak = left if hand == "right" else right
    a = {
        "duration_s": _r(duration),
        "dribbles": int(dribbles),
        "dribbles_per_sec": _r(dps, 2),
        "rhythm_score": None if not ball_ok or _r(res["rhythm_score"]) is None else int(round(res["rhythm_score"])),
        "ball_below_hip_pct": _r(res["pct_top_below_hip"], 0) if ball_ok else None,
        "ball_below_knee_pct": _r(res["pct_top_below_knee"], 0) if ball_ok else None,
        "left_hand_pct": _r(left, 0),
        "right_hand_pct": _r(right, 0),
        "weak_hand_pct": _r(weak, 0),
        "head_up_pct": _r(res["eyes_up_pct"], 0),
        "quality": _quality(min(check["det_rate"], ball_pct), span, "dribbling"),
        "flags": flags,
    }
    a["targets"] = [t for t in (target_check(m, a[m]) for m in
                    ("head_up_pct", "ball_below_hip_pct", "weak_hand_pct")) if t]
    progress(88, "Drawing video")
    step3.save_annotated(video, pose, ball_xy, radii, interp, res, str(out))
    return a, True


def _jump(pose, check, video, out, height_cm, progress):
    jumps, _ = step5.analyze_jump(pose, height_cm)
    flags = _video_flags(check)
    rows, valid = [], []
    for j in jumps:
        h = (j["h_flight_cm"] + j["h_hip_cm"]) / 2
        rows.append({"index": j["jump"], "air_time_s": _r(j["flight_s"], 2), "height_cm": _r(h)})
        if not _sane("jump_cm", h) or h <= 0:
            flags.append({"metric": "jump_cm", "value": _r(h),
                          "message": f"Jump {j['jump']}: {h:.0f} cm is not realistic - tracking error?"})
            continue
        if not j["agree"]:
            flags.append({"metric": "jump_methods", "value": _r(h),
                          "message": f"Jump {j['jump']}: air time ({j['h_flight_cm']:.0f} cm) and hip rise "
                                     f"({j['h_hip_cm']:.0f} cm) disagree - check the video."})
        valid.append(h)
    a = {
        "jumps": rows,
        "best_jump_cm": _r(max(valid)) if valid else None,
        "avg_jump_cm": _mean(valid),
        "targets": [],
        "quality": _quality(check["det_rate"], len(valid), "jump"),
        "flags": flags,
    }
    if jumps:
        progress(85, "Drawing video")
        step5.save_annotated(video, pose, jumps, str(out))
    return a, bool(jumps)


# ------------------------------------------------------------------ entry point
def run_analysis(player_input: dict, kind: str, upload_path: str, stem: str,
                 progress: Optional[Progress] = None) -> dict:
    """Full pipeline for one upload. stem = "p_001_shooting". Raises PipelineError."""
    progress = progress or (lambda pct, step: None)
    work = config.WORK_DIR / f"{stem}.mp4"
    out = config.MEDIA_DIR / f"{stem}.mp4"

    progress(2, "Converting video")
    try:
        step1_convert.convert(upload_path, work)
    except Exception as e:
        raise PipelineError(f"Could not read this video file ({e.__class__.__name__}). "
                            "Try exporting it again as .mp4 or .mov.")

    pose_end = 35 if kind == "dribbling" else 70
    n_total = max(common.video_info(str(work))[3], 1)

    def on_pose(i, n):
        progress(10 + int((pose_end - 10) * i / max(n or n_total, 1)), "Detecting pose")

    progress(10, "Detecting pose")
    raw = common.extract_pose(str(work), on_frame=on_pose)
    check = step2_pose_test.check_pose(raw)
    if check["det_rate"] < 30:
        raise PipelineError("The player was found in only "
                            f"{check['det_rate']:.0f}% of the video. " + " ".join(check["problems"]))
    pose = common.clean_pose(raw)

    hand = player_input["dominant_hand"]
    if kind == "shooting":
        progress(72, "Finding shots")
        a, has_video = _shooting(pose, check, str(work), out, hand, progress)
    elif kind == "dribbling":
        a, has_video = _dribbling(pose, check, str(work), out, hand, progress)
    elif kind == "jump":
        progress(72, "Finding jumps")
        a, has_video = _jump(pose, check, str(work), out, float(player_input["height_cm"]), progress)
    else:
        raise PipelineError(f"Unknown video kind {kind}")
    a["annotated_video_url"] = _media_url(out.name) if has_video and out.exists() else None
    progress(99, "Saving results")
    return a
