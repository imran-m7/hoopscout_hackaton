"""
STEP 3 - Can YOLO track the ball? + first dribbling numbers (dribbling videos)

This is the RISKIEST part of the app, so test it early.
It reports how often the ball is found, counts dribbles two ways
(ball tracking and wrist movement as a fallback) and saves a video
with the ball and skeleton drawn on top.

Usage:
    python step3_dribble_ball_test.py videos/amar_dribbling.mp4
    python step3_dribble_ball_test.py videos/amar_dribbling.mp4 --model yolov8s.pt   (more accurate, slower)
"""
import argparse

import cv2
import numpy as np
from scipy.signal import find_peaks

from common import (L_HIP, R_HIP, L_KNEE, R_KNEE, L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST,
                    NOSE, H264Writer, body_height_px, clean_pose, draw_skeleton, extract_pose,
                    iter_frames, out_name, put_text)

SPORTS_BALL = 32  # COCO class id


# ------------------------------------------------------------------ detection
def plausible_ball(mids, boxes, joints, body, prev, frames_since_prev, max_dist):
    """Mask of detections that can really be the dribbled ball.
    Rejects things far from the player (e.g. white paint on the wall),
    boxes far too big/small for a basketball, and sudden jumps."""
    keep = np.ones(len(mids), bool)
    if np.isnan(body):
        return keep
    size = np.maximum(boxes[:, 2] - boxes[:, 0], boxes[:, 3] - boxes[:, 1])
    keep &= (size > 0.04 * body) & (size < 0.6 * body)
    pts = joints[~np.isnan(joints).any(axis=1)]
    if len(pts):
        d = np.linalg.norm(mids[:, None, :] - pts[None, :, :], axis=2).min(axis=1)
        keep &= d < max_dist * body
    if prev is not None and frames_since_prev <= 3:
        keep &= np.linalg.norm(mids - prev, axis=1) < 0.45 * body * frames_since_prev
    return keep


def detect_ball(path, model_name="yolov8n.pt", conf=0.15, pose_xy=None, max_dist=0.5):
    from ultralytics import YOLO
    model = YOLO(model_name)  # downloads automatically the first time
    body = body_height_px(pose_xy) if pose_xy is not None else float("nan")
    centers, radii, confs = [], [], []
    prev, last_seen = None, -999
    rejected = 0
    for i, frame in iter_frames(path):
        r = model.predict(frame, classes=[SPORTS_BALL], conf=conf, imgsz=640, verbose=False)[0]
        if len(r.boxes) and pose_xy is not None and i < len(pose_xy):
            boxes = r.boxes.xyxy.cpu().numpy()
            mids = np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2]
            ok = plausible_ball(mids, boxes, pose_xy[i], body, prev, i - last_seen, max_dist)
            rejected += int((~ok).sum())
            r = r[ok] if ok.any() else r[:0]
        if len(r.boxes):
            boxes = r.boxes.xyxy.cpu().numpy()
            cs = r.boxes.conf.cpu().numpy()
            mids = np.c_[(boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2]
            if prev is not None and len(mids) > 1:
                # prefer the box closest to the last ball position
                k = int(np.argmin(np.linalg.norm(mids - prev, axis=1) - cs * 50))
            else:
                k = int(np.argmax(cs))
            b = boxes[k]
            centers.append(mids[k])
            radii.append(max(b[2] - b[0], b[3] - b[1]) / 2)
            confs.append(float(cs[k]))
            prev, last_seen = mids[k], i
        else:
            centers.append([np.nan, np.nan])
            radii.append(np.nan)
            confs.append(0.0)
        if i % 30 == 0:
            print(f"  ball: frame {i}", end="\r")
    print(" " * 40, end="\r")
    if rejected:
        print(f"Ignored {rejected} false ball detections (too far from player / wrong size / jumped)")
    return np.array(centers, float), np.array(radii, float), np.array(confs, float)


def fill_gaps(arr, max_gap):
    """Linear interpolation of NaN gaps no longer than max_gap frames. Returns (filled, was_filled_mask)."""
    arr = arr.copy()
    filled_mask = np.zeros(len(arr), bool)
    good = ~np.isnan(arr[:, 0])
    idx = np.where(good)[0]
    for a, b in zip(idx[:-1], idx[1:]):
        gap = b - a - 1
        if 0 < gap <= max_gap:
            for k in range(1, gap + 1):
                t = k / (gap + 1)
                arr[a + k] = arr[a] * (1 - t) + arr[b] * t
                filled_mask[a + k] = True
    return arr, filled_mask


def peaks_in_valid_segments(y, **kw):
    """find_peaks on each continuous non-NaN stretch."""
    peaks = []
    valid = ~np.isnan(y)
    i, n = 0, len(y)
    while i < n:
        if valid[i]:
            j = i
            while j < n and valid[j]:
                j += 1
            if j - i > 3:
                p, _ = find_peaks(y[i:j], **kw)
                peaks.extend((p + i).tolist())
            i = j
        else:
            i += 1
    return np.array(sorted(peaks), int)


# ------------------------------------------------------------------ analysis
def analyze_dribble(pose, ball_xy, fps):
    """pose: cleaned pose dict. ball_xy: (N,2) gap-filled ball centers."""
    xy = pose["xy"]
    n = min(len(xy), len(ball_xy))
    xy, ball_xy = xy[:n], ball_xy[:n]
    body = body_height_px(xy)
    res = {"body_px": body}

    # --- dribbles from the ball: a bounce = ball at its LOWEST point (max y in image)
    ball_y = ball_xy[:, 1]
    bounces = peaks_in_valid_segments(ball_y, distance=max(1, int(0.15 * fps)),
                                      prominence=0.08 * body)
    res["bounces"] = bounces
    res["dribbles_ball"] = len(bounces)

    if len(bounces) >= 2:
        span = (bounces[-1] - bounces[0]) / fps
        res["dribbles_per_sec"] = (len(bounces) - 1) / span if span > 0 else float("nan")
        intervals = np.diff(bounces) / fps
        cv = intervals.std() / intervals.mean()
        res["rhythm_score"] = float(np.clip(100 - cv * 200, 0, 100))
    else:
        res["dribbles_per_sec"] = float("nan")
        res["rhythm_score"] = float("nan")

    # --- ball top between bounces: height vs hip/knee + which hand
    below_hip, below_knee, hands = 0, 0, []
    tops = []
    for a, b in zip(bounces[:-1], bounces[1:]):
        seg = ball_y[a:b + 1]
        if np.isnan(seg).all():
            continue
        t = a + int(np.nanargmin(seg))
        tops.append(t)
        hip_y = np.nanmean(xy[t, [L_HIP, R_HIP], 1])
        knee_y = np.nanmean(xy[t, [L_KNEE, R_KNEE], 1])
        if ball_y[t] > hip_y:
            below_hip += 1
        if ball_y[t] > knee_y:
            below_knee += 1
        dl = np.linalg.norm(ball_xy[t] - xy[t, L_WRIST])
        dr = np.linalg.norm(ball_xy[t] - xy[t, R_WRIST])
        if not (np.isnan(dl) or np.isnan(dr)):
            hands.append("L" if dl < dr else "R")
    res["tops"] = tops
    res["pct_top_below_hip"] = 100 * below_hip / len(tops) if tops else float("nan")
    res["pct_top_below_knee"] = 100 * below_knee / len(tops) if tops else float("nan")
    res["left_hand_pct"] = 100 * hands.count("L") / len(hands) if hands else float("nan")
    res["right_hand_pct"] = 100 * hands.count("R") / len(hands) if hands else float("nan")

    # --- eyes up: vertical gap nose -> shoulder line, compared with the most upright moments
    sh_y = np.nanmean(xy[:, [L_SHOULDER, R_SHOULDER], 1], axis=1)
    gap = (sh_y - xy[:, NOSE, 1]) / body
    ok = ~np.isnan(gap)
    if ok.sum() > 10:
        upright = np.percentile(gap[ok], 90)
        res["eyes_up_pct"] = float(100 * np.mean(gap[ok] >= 0.75 * upright))
    else:
        res["eyes_up_pct"] = float("nan")

    # --- FALLBACK: dribbles from wrist movement (no ball needed)
    count = 0
    for w in (L_WRIST, R_WRIST):
        wy = xy[:, w, 1]
        p = peaks_in_valid_segments(wy, distance=max(1, int(0.15 * fps)), prominence=0.04 * body)
        # only count pushes made below the shoulders (real dribbles, not waving)
        p = [k for k in p if not np.isnan(sh_y[k]) and wy[k] > sh_y[k] + 0.1 * body]
        count += len(p)
    res["dribbles_wrist"] = count
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--max-dist", type=float, default=0.5,
                    help="max distance of ball from nearest body joint, in body heights "
                         "(lower = stricter against background false detections)")
    args = ap.parse_args()

    print(f"Analyzing {args.video} ...")
    pose = clean_pose(extract_pose(args.video))
    fps = pose["fps"]
    raw_xy, radii, confs = detect_ball(args.video, args.model, args.conf,
                                       pose_xy=pose["xy"], max_dist=args.max_dist)
    n = len(raw_xy)
    raw_rate = 100 * np.mean(~np.isnan(raw_xy[:, 0])) if n else 0
    ball_xy, interp = fill_gaps(raw_xy, max_gap=int(0.3 * fps))
    filled_rate = 100 * np.mean(~np.isnan(ball_xy[:, 0])) if n else 0

    res = analyze_dribble(pose, ball_xy, fps)

    print("\n================ BALL TRACKING ================")
    print(f"Ball found by YOLO:          {raw_rate:5.0f}% of frames")
    print(f"After filling short gaps:    {filled_rate:5.0f}% of frames")
    print(f"Average detection confidence:{np.mean(confs[confs > 0]) if (confs > 0).any() else 0:6.2f}")

    print("\n================ DRIBBLING (first test) ================")
    print(f"Dribbles counted (ball):     {res['dribbles_ball']}")
    print(f"Dribbles counted (wrists):   {res['dribbles_wrist']}   <- fallback method")
    print(f"Dribbles per second:         {res['dribbles_per_sec']:.2f}")
    print(f"Rhythm score (0-100):        {res['rhythm_score']:.0f}")
    print(f"Ball top below hip:          {res['pct_top_below_hip']:.0f}% of dribbles")
    print(f"Ball top below knee:         {res['pct_top_below_knee']:.0f}% of dribbles")
    print(f"Hand use:                    L {res['left_hand_pct']:.0f}%  /  R {res['right_hand_pct']:.0f}%")
    print(f"Eyes up (approx.):           {res['eyes_up_pct']:.0f}% of the time")

    print("\nVERDICT:")
    if filled_rate >= 70:
        print("  GOOD - ball tracking works for this video.")
    elif filled_rate >= 40:
        print("  OK - usable, but try --model yolov8s.pt or better light/contrast.")
    else:
        print("  WEAK - use the wrist-based dribble count as fallback, or re-film (brighter, ball contrasting with floor).")
    db, dw = res["dribbles_ball"], res["dribbles_wrist"]
    if db and dw and abs(db - dw) / max(db, dw) <= 0.25:
        print("  Ball and wrist counts agree (within 25%) -> numbers are trustworthy.")
    else:
        print("  Ball and wrist counts differ a lot -> COUNT THE DRIBBLES YOURSELF in the video and see which is right.")

    # ---------- annotated video
    out = out_name(args.video, "ball.mp4")
    writer = H264Writer(out, pose["w"], pose["h"], fps)
    bounce_set = set(res["bounces"].tolist())
    seen = 0
    trail = []
    for i, frame in iter_frames(args.video):
        if i >= n:
            break
        if not np.isnan(pose["xy"][i]).all():
            draw_skeleton(frame, pose["xy"][i])
        c = ball_xy[i]
        if not np.isnan(c).any():
            r = radii[i] if not np.isnan(radii[i]) else 15
            color = (0, 255, 255) if interp[i] else (0, 255, 0)  # yellow = interpolated
            cv2.circle(frame, (int(c[0]), int(c[1])), int(r), color, 3)
            trail.append((int(c[0]), int(c[1])))
        trail = trail[-15:]
        for a, b in zip(trail[:-1], trail[1:]):
            cv2.line(frame, a, b, (0, 165, 255), 2)
        if i in bounce_set:
            seen += 1
        put_text(frame, f"Dribbles: {seen}", 40)
        put_text(frame, "green = ball found, yellow = filled gap", 75, scale=0.6)
        writer.write(frame)
    writer.close()
    print(f"\nBall video saved: {out}  -> check the circle stays on the ball")


if __name__ == "__main__":
    main()
