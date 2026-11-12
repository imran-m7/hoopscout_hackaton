"""
STEP 4 - First shooting numbers (side-view shooting videos)

Finds each shot automatically and measures:
  elbow angle at set point, deepest knee bend, release height,
  leg-arm timing, follow-through, and form consistency across shots.

Usage:
    python step4_shooting_test.py videos/amar_shooting.mp4 --hand right
"""
import argparse
import csv

import numpy as np

from common import (NOSE, H264Writer, body_height_px, clean_pose, draw_skeleton, extract_pose,
                    iter_frames, joint_angle, out_name, put_text, side_joints)


def find_shot_segments(wrist_y, nose_y, fps, min_len_s=0.12, merge_gap_s=0.35):
    """A shot = the shooting wrist goes ABOVE the nose (smaller y in image)."""
    above = (wrist_y < nose_y) & ~np.isnan(wrist_y) & ~np.isnan(nose_y)
    segs, start = [], None
    for i, a in enumerate(np.append(above, False)):
        if a and start is None:
            start = i
        elif not a and start is not None:
            segs.append([start, i - 1])
            start = None
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] <= merge_gap_s * fps:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return [s for s in merged if (s[1] - s[0] + 1) >= min_len_s * fps]


def analyze_shooting(pose, hand="right", max_knee=150.0):
    """max_knee: a real shot needs the knee to bend below this angle (deg) before release
    and then straighten again (leg drive). Catching a pass / rebounding / waving
    raises the arm above the head too, but without that load-and-push."""
    xy, fps = pose["xy"], pose["fps"]
    J = side_joints(hand)
    elbow = joint_angle(xy, J["shoulder"], J["elbow"], J["wrist"])
    knee = joint_angle(xy, J["hip"], J["knee"], J["ankle"])
    wrist_y = xy[:, J["wrist"], 1]
    shoulder_y = xy[:, J["shoulder"], 1]
    ankle_y = xy[:, J["ankle"], 1]
    nose_y = xy[:, NOSE, 1]
    body = body_height_px(xy)
    n = len(xy)

    shots, skipped = [], []
    prev_end = 0
    for s, e in find_shot_segments(wrist_y, nose_y, fps):
        # look for the dip only after the previous arm-raise ended
        pre = max(prev_end, s - int(1.2 * fps))
        prev_end = e + 1
        # release = highest wrist point during the shot
        rel = s + int(np.nanargmin(wrist_y[s:e + 1]))
        # dip = deepest knee bend before the arm goes up
        kseg = knee[pre:s + 1]
        if np.isnan(kseg).all():
            skipped.append((round(rel / fps, 2), "knee not visible"))
            continue
        dip = pre + int(np.nanargmin(kseg))
        if knee[dip] > max_knee:
            skipped.append((round(rel / fps, 2),
                            f"no knee bend ({knee[dip]:.0f} deg) - catch/pass/rebound?"))
            continue
        # set point = smallest elbow angle while wrist is above the shoulder, before release
        cand = [f for f in range(dip, rel + 1)
                if not np.isnan(wrist_y[f]) and wrist_y[f] < shoulder_y[f] and not np.isnan(elbow[f])]
        set_f = min(cand, key=lambda f: elbow[f]) if cand else s
        # legs extended = first frame after dip with knee > 160 deg
        ext = next((f for f in range(dip, min(n, rel + int(0.5 * fps)))
                    if not np.isnan(knee[f]) and knee[f] >= 160), None)
        if ext is None:
            skipped.append((round(rel / fps, 2), "legs never straightened (no leg drive)"))
            continue
        sync_ms = (rel - ext) / fps * 1000 if ext is not None else float("nan")
        # follow-through = how long the wrist stays above the shoulder after release
        f = rel
        while f < n and not np.isnan(wrist_y[f]) and wrist_y[f] < shoulder_y[f]:
            f += 1
        follow_s = (f - rel) / fps
        release_ratio = (ankle_y[rel] - wrist_y[rel]) / body
        shots.append(dict(
            shot=len(shots) + 1, dip=dip, set=set_f, release=rel,
            time_s=round(rel / fps, 2),
            elbow_set=round(float(elbow[set_f]), 1),
            elbow_release=round(float(elbow[rel]), 1),
            knee_min=round(float(knee[dip]), 1),
            release_height=round(float(release_ratio), 3),
            sync_ms=round(float(sync_ms), 0),
            follow_through_s=round(float(follow_s), 2),
        ))

    summary = {"shots": len(shots), "skipped": skipped}
    if len(shots) >= 2:
        def sd(k):
            v = np.array([s[k] for s in shots], float)
            return float(np.nanstd(v))
        summary.update(
            elbow_set_avg=float(np.mean([s["elbow_set"] for s in shots])),
            knee_min_avg=float(np.mean([s["knee_min"] for s in shots])),
            release_height_avg=float(np.mean([s["release_height"] for s in shots])),
            sync_ms_avg=float(np.nanmean([s["sync_ms"] for s in shots])),
            follow_avg=float(np.mean([s["follow_through_s"] for s in shots])),
            sd_elbow=sd("elbow_set"), sd_knee=sd("knee_min"), sd_release=sd("release_height"),
        )
        # DRAFT consistency formula - tune these weights with a coach later
        penalty = summary["sd_elbow"] * 2 + summary["sd_knee"] * 1 + summary["sd_release"] * 300
        summary["consistency"] = float(np.clip(100 - penalty, 0, 100))
    return shots, summary, elbow, knee


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--hand", choices=["right", "left"], default="right",
                    help="shooting hand of the player")
    ap.add_argument("--max-knee", type=float, default=150.0,
                    help="knee must bend below this angle (deg) to count as a shot; "
                         "raise it (e.g. 160) if real shots are being skipped")
    args = ap.parse_args()

    print(f"Analyzing {args.video} ({args.hand}-handed) ...")
    pose = clean_pose(extract_pose(args.video))
    shots, summary, elbow, knee = analyze_shooting(pose, args.hand, args.max_knee)

    print(f"\nShots found: {summary['shots']}   <- COMPARE with the real number of shots in the video!")
    for t, why in summary["skipped"]:
        print(f"  skipped arm-raise at {t:>6} s: {why}")
    if not shots:
        print("No shots found. Check: correct --hand? whole body visible? (run step2 first)")
        return
    print(f"\n{'#':>2} {'time':>6} {'elbow@set':>10} {'knee min':>9} {'release h':>10} {'leg-arm ms':>11} {'follow s':>9}")
    for s in shots:
        print(f"{s['shot']:>2} {s['time_s']:>6} {s['elbow_set']:>10} {s['knee_min']:>9} "
              f"{s['release_height']:>10} {s['sync_ms']:>11} {s['follow_through_s']:>9}")

    if summary["shots"] >= 2:
        print("\nAverages:")
        print(f"  Elbow angle at set point:  {summary['elbow_set_avg']:.0f} deg  (spread {summary['sd_elbow']:.1f})")
        print(f"  Deepest knee bend:         {summary['knee_min_avg']:.0f} deg  (spread {summary['sd_knee']:.1f})")
        print(f"  Release height:            {summary['release_height_avg']:.2f} x body (spread {summary['sd_release']:.3f})")
        print(f"  Leg-arm timing:            {summary['sync_ms_avg']:.0f} ms  (+ = arm releases after legs extend)")
        print(f"  Follow-through:            {summary['follow_avg']:.2f} s")
        print(f"  CONSISTENCY SCORE (draft): {summary['consistency']:.0f} / 100")
        print("\nSanity check: elbow at set usually 60-110 deg, knee bend 100-150 deg.")
        print(f"Timing precision: 1 frame = {1000 / pose['fps']:.0f} ms at this fps.")

    csv_path = out_name(args.video, "shots.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(shots[0].keys()))
        w.writeheader()
        w.writerows(shots)
    print(f"\nPer-shot numbers saved: {csv_path}")

    # annotated video: skeleton + live angles + shot markers
    out = out_name(args.video, "shooting.mp4")
    writer = H264Writer(out, pose["w"], pose["h"], pose["fps"])
    marks = {}
    for s in shots:
        for key in ("dip", "set", "release"):
            for k in range(int(pose["fps"] * 0.25)):   # show label for 0.25 s
                marks[s[key] + k] = f"Shot {s['shot']}: {key.upper()}"
    for i, frame in iter_frames(args.video):
        if i >= len(pose["xy"]):
            break
        if not np.isnan(pose["xy"][i]).all():
            draw_skeleton(frame, pose["xy"][i])
        if not np.isnan(elbow[i]):
            put_text(frame, f"Elbow {elbow[i]:.0f} deg   Knee {knee[i]:.0f} deg", 40)
        if i in marks:
            put_text(frame, marks[i], 80, (0, 200, 255), 1.0)
        writer.write(frame)
    writer.close()
    print(f"Shooting video saved: {out}  -> check DIP / SET / RELEASE labels appear at the right moments")


if __name__ == "__main__":
    main()
