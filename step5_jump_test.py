"""
STEP 5 - Vertical jump height (side-view standing jump videos)

Measures each jump two ways and compares them:
  A) flight time  : height = g * t^2 / 8
  B) hip rise     : how far the hips rise after take-off, converted to cm
                    using the player's real height
If both methods roughly agree, the measurement is trustworthy.

Usage:
    python step5_jump_test.py videos/amar_jump.mp4 --height 158
"""
import argparse

import numpy as np

from common import (L_FOOT, R_FOOT, L_HIP, R_HIP, H264Writer, body_height_px, clean_pose,
                    draw_skeleton, extract_pose, iter_frames, out_name, put_text)

NOSE_TO_ANKLE_RATIO = 0.88   # nose-to-ankle is roughly 88% of standing height (approximation)


def analyze_jump(pose, height_cm):
    xy, fps = pose["xy"], pose["fps"]
    body = body_height_px(xy)
    px_per_cm = body / (NOSE_TO_ANKLE_RATIO * height_cm)
    toe_y = np.nanmean(xy[:, [L_FOOT, R_FOOT], 1], axis=1)
    hip_y = np.nanmean(xy[:, [L_HIP, R_HIP], 1], axis=1)
    n = len(toe_y)

    # The toe point sits lower in the image during a squat than when standing
    # (foot rolls forward), so a single "floor level" for the whole clip makes
    # normal standing look like being in the air. Use a LOCAL floor level instead.
    w = int(1.0 * fps)
    base = np.array([np.nanpercentile(toe_y[max(0, i - w):i + w + 1], 90)
                     if not np.isnan(toe_y[max(0, i - w):i + w + 1]).all() else np.nan
                     for i in range(n)])

    # 1) find clear jumps: toes well above the local floor (10% of body height)
    clear = toe_y < base - 0.10 * body
    cores, start = [], None
    for i, a in enumerate(np.append(clear, False)):
        if a and start is None:
            start = i
        elif not a and start is not None:
            cores.append((start, i - 1))
            start = None

    # 2) take-off / landing = toes leave / return to the floor level measured
    #    just before / just after this jump (small threshold = precise timing)
    lift = 0.03 * body
    win = int(0.6 * fps)
    jumps, prev_e = [], -1
    for cs, ce in cores:
        pre = toe_y[max(prev_e + 1, cs - win):cs]
        post = toe_y[ce + 1:ce + 1 + win]
        if np.isnan(pre).all() or np.isnan(post).all():
            continue
        g_pre, g_post = np.nanpercentile(pre, 90), np.nanpercentile(post, 90)
        s, e = cs, ce
        while s - 1 > prev_e and toe_y[s - 1] < g_pre - lift:
            s -= 1
        while e + 1 < n and toe_y[e + 1] < g_post - lift:
            e += 1
        if s <= prev_e or (e - s + 1) < 0.1 * fps:   # overlap / too short to be a jump
            continue
        jumps.append((s, e))
        prev_e = e

    results = []
    for s, e in jumps:
        t = (e - s + 1) / fps
        h_flight = 9.81 * t ** 2 / 8 * 100
        takeoff = max(0, s - 1)
        peak = s + int(np.nanargmin(hip_y[s:e + 1]))
        h_hip = (hip_y[takeoff] - hip_y[peak]) / px_per_cm
        agree = abs(h_flight - h_hip) / max(h_flight, h_hip, 1e-6) <= 0.3
        results.append(dict(jump=len(results) + 1, start=s, end=e, peak=peak,
                            flight_s=round(t, 3), h_flight_cm=round(h_flight, 1),
                            h_hip_cm=round(float(h_hip), 1), agree=agree))
    return results, px_per_cm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--height", type=float, required=True, help="player height in cm")
    args = ap.parse_args()

    print(f"Analyzing {args.video} ...")
    pose = clean_pose(extract_pose(args.video))
    jumps, px_per_cm = analyze_jump(pose, args.height)
    fps = pose["fps"]

    print(f"\nScale: {px_per_cm:.2f} pixels per cm (from player height {args.height:.0f} cm)")
    print(f"Jumps found: {len(jumps)}   <- COMPARE with the real number of jumps!")
    if not jumps:
        print("No jumps found. Check that the feet are visible (run step2 first).")
        return
    print(f"\n{'#':>2} {'air time s':>10} {'flight cm':>10} {'hip-rise cm':>12}  methods agree?")
    for j in jumps:
        print(f"{j['jump']:>2} {j['flight_s']:>10} {j['h_flight_cm']:>10} {j['h_hip_cm']:>12}  "
              f"{'yes' if j['agree'] else 'NO'}")
    best = max(jumps, key=lambda j: (j["h_flight_cm"] + j["h_hip_cm"]) / 2)
    print(f"\nBest jump (average of both methods): {(best['h_flight_cm'] + best['h_hip_cm']) / 2:.1f} cm")
    print(f"Precision note: at {fps:.0f} fps one frame = {1000 / fps:.0f} ms of air time"
          f" -> about +/-{(9.81 * ((best['flight_s'] + 1 / fps) ** 2 - best['flight_s'] ** 2) / 8 * 100):.1f} cm on the flight method.")
    print("Typical standing jumps for 10-14 year olds are roughly 20-45 cm; far outside that = check the video.")

    out = out_name(args.video, "jump.mp4")
    writer = H264Writer(out, pose["w"], pose["h"], fps)
    label = {}
    for j in jumps:
        for f in range(j["start"], j["end"] + 1):
            label[f] = f"Jump {j['jump']}: IN THE AIR"
        for f in range(j["end"] + 1, min(len(pose["xy"]), j["end"] + 1 + int(fps))):
            label[f] = f"Jump {j['jump']}: {(j['h_flight_cm'] + j['h_hip_cm']) / 2:.0f} cm"
    for i, frame in iter_frames(args.video):
        if i >= len(pose["xy"]):
            break
        if not np.isnan(pose["xy"][i]).all():
            draw_skeleton(frame, pose["xy"][i])
        if i in label:
            put_text(frame, label[i], 50, (0, 200, 255), 1.0)
        writer.write(frame)
    writer.close()
    print(f"\nJump video saved: {out}")


if __name__ == "__main__":
    main()
