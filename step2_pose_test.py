"""
STEP 2 - Can MediaPipe see the player? (run on EVERY video)

Checks: % of frames with a person, visibility of each joint,
player size in frame, frame rate. Saves a video with the skeleton drawn.

Usage:
    python step2_pose_test.py videos/amar_shooting.mp4
"""
import sys

import numpy as np

from common import (KEY_JOINTS, L_ANKLE, R_ANKLE, NOSE, body_height_px, draw_skeleton,
                    extract_pose, iter_frames, out_name, put_text, H264Writer)


def check_pose(pose):
    """The step-2 checks as numbers (used by the backend for QualityInfo)."""
    xy, vis, det = pose["xy"], pose["vis"], pose["detected"]
    fps, h = pose["fps"], pose["h"]
    n = len(det)
    problems = []

    det_rate = det.mean() * 100 if n else 0
    if det_rate < 90:
        problems.append("Person missing in many frames -> better light, camera closer, nobody else in shot")

    joints = {name: (vis[det, j].mean() * 100 if det.any() else 0) for name, j in KEY_JOINTS.items()}

    ank = vis[det][:, [L_ANKLE, R_ANKLE]].mean() * 100 if det.any() else 0
    if ank < 60:
        problems.append("Feet often not visible -> whole body must be in frame")

    size = body_height_px(xy) / h * 100
    if np.isnan(size) or size < 30:
        problems.append("Player too small -> move camera closer")
    elif size > 80:
        problems.append("Player too big -> move camera back (jumps get cut off)")

    # is the head ever cut off at the top?
    nose_y = xy[det, NOSE, 1]
    if len(nose_y) and np.nanmin(nose_y) < 0.03 * h:
        problems.append("Head reaches the top edge -> leave more space above the player")

    if fps < 29:
        problems.append("Low fps -> film at 30 or 60 fps")
    return dict(frames=n, fps=fps, det_rate=float(det_rate), joints=joints, ankle_vis=float(ank),
                size_pct=float(size), problems=problems, good=not problems)


def report(pose):
    c = check_pose(pose)
    n, fps, problems = c["frames"], c["fps"], c["problems"]
    print(f"\nFrames: {n}  ({n / fps:.1f} s at {fps:.0f} fps)")
    print(f"Person detected in: {c['det_rate']:.0f}% of frames")
    print("\nJoint visibility (average when person is detected):")
    for name, v in c["joints"].items():
        print(f"  {name:<11} {v:5.0f}%  {'OK' if v >= 60 else 'LOW'}")
    print(f"\nPlayer (nose to ankle) fills ~{c['size_pct']:.0f}% of frame height (target 30-80%)")

    print("\nVERDICT:", "GOOD - ready for analysis" if not problems else "NEEDS FIXING")
    for p in problems:
        print("  -", p)
    return not problems


def save_annotated(path, pose):
    out = out_name(path, "pose.mp4")
    writer = H264Writer(out, pose["w"], pose["h"], pose["fps"])
    for i, frame in iter_frames(path):
        if i >= len(pose["detected"]):
            break
        if pose["detected"][i]:
            draw_skeleton(frame, pose["xy"][i])
        else:
            put_text(frame, "NO PERSON DETECTED", 50, (0, 0, 255), 1.0)
        writer.write(frame)
    writer.close()
    print(f"\nSkeleton video saved: {out}  -> open it and check the skeleton follows the body")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python step2_pose_test.py <video.mp4>")
    path = sys.argv[1]
    print(f"Analyzing {path} ...")
    pose = extract_pose(path)
    report(pose)
    save_annotated(path, pose)
