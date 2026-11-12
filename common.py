"""
common.py - shared helpers for the HoopScout test scripts.

Uses the CURRENT MediaPipe "Tasks" API (PoseLandmarker). The old
`mp.solutions.pose` API was removed in new MediaPipe versions.
The pose model file (~9 MB) downloads automatically on first run.
"""
import os
import sys
import urllib.request
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)  # NaN math on frames without a person

import cv2
import numpy as np

# ---------------------------------------------------------------- landmarks
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
L_FOOT, R_FOOT = 31, 32

SKELETON = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 31), (24, 26), (26, 28), (28, 32),
]

KEY_JOINTS = {
    "nose": NOSE, "L shoulder": L_SHOULDER, "R shoulder": R_SHOULDER,
    "L elbow": L_ELBOW, "R elbow": R_ELBOW, "L wrist": L_WRIST, "R wrist": R_WRIST,
    "L hip": L_HIP, "R hip": R_HIP, "L knee": L_KNEE, "R knee": R_KNEE,
    "L ankle": L_ANKLE, "R ankle": R_ANKLE,
}


def side_joints(hand):
    """Joint indices for the shooting side. MediaPipe LEFT/RIGHT = the person's own side."""
    if hand == "left":
        return dict(shoulder=L_SHOULDER, elbow=L_ELBOW, wrist=L_WRIST,
                    hip=L_HIP, knee=L_KNEE, ankle=L_ANKLE, foot=L_FOOT)
    return dict(shoulder=R_SHOULDER, elbow=R_ELBOW, wrist=R_WRIST,
                hip=R_HIP, knee=R_KNEE, ankle=R_ANKLE, foot=R_FOOT)


# ---------------------------------------------------------------- video I/O
def video_info(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"ERROR: cannot open {path}. Did you run step1_convert.py first?")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return fps, w, h, n


def iter_frames(path):
    """Yield (index, BGR frame) for every frame of the video."""
    cap = cv2.VideoCapture(path)
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        yield i, frame
        i += 1
    cap.release()


class H264Writer:
    """Writes an .mp4 that plays in browsers and Streamlit (H.264 / yuv420p)."""

    def __init__(self, path, w, h, fps):
        import imageio_ffmpeg
        self.w, self.h = w - (w % 2), h - (h % 2)   # H.264 needs even sizes
        self.gen = imageio_ffmpeg.write_frames(
            path, (self.w, self.h), fps=fps, codec="libx264",
            pix_fmt_out="yuv420p", macro_block_size=1, quality=7)
        self.gen.send(None)

    def write(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr[: self.h, : self.w], cv2.COLOR_BGR2RGB)
        self.gen.send(np.ascontiguousarray(rgb))

    def close(self):
        self.gen.close()


def out_name(path, suffix):
    base = os.path.splitext(os.path.basename(path))[0]
    os.makedirs("test_output", exist_ok=True)
    return os.path.join("test_output", f"{base}_{suffix}")


# ---------------------------------------------------------------- pose
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_full/float16/latest/pose_landmarker_full.task")
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "models", "pose_landmarker_full.task")


def get_pose_model():
    if not os.path.exists(MODEL_PATH):
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        print("Downloading MediaPipe pose model (one time, ~9 MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def extract_pose(path, on_frame=None):
    """
    Run MediaPipe on every frame.
    Returns dict:
      xy   (N,33,2) pixel coordinates (NaN where no person was found)
      vis  (N,33)   visibility 0..1
      detected (N,) bool
      fps, w, h
    on_frame(i, n): optional progress callback (used by the backend)
    """
    import mediapipe as mp
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision

    fps, w, h, n = video_info(path)
    options = vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=get_pose_model()),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    xy_list, vis_list, det_list = [], [], []
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        for i, frame in iter_frames(path):
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect_for_video(image, int(i * 1000 / fps))
            if res.pose_landmarks:
                lm = res.pose_landmarks[0]
                xy_list.append([[p.x * w, p.y * h] for p in lm])
                vis_list.append([p.visibility if p.visibility is not None else 1.0 for p in lm])
                det_list.append(True)
            else:
                xy_list.append(np.full((33, 2), np.nan))
                vis_list.append(np.zeros(33))
                det_list.append(False)
            if i % 30 == 0:
                if on_frame:
                    on_frame(i, n)
                else:
                    print(f"  pose: frame {i}/{n}", end="\r")
    print(" " * 40, end="\r")
    return dict(xy=np.array(xy_list, dtype=float), vis=np.array(vis_list, dtype=float),
                detected=np.array(det_list, dtype=bool), fps=fps, w=w, h=h)


def clean_pose(pose, max_gap_s=0.3, smooth=5):
    """Fill short gaps (linear interpolation) and smooth with a moving average."""
    xy = pose["xy"].copy()
    n = xy.shape[0]
    max_gap = int(max_gap_s * pose["fps"])
    t = np.arange(n)
    for j in range(33):
        for k in range(2):
            col = xy[:, j, k]
            good = ~np.isnan(col)
            if good.sum() < 2:
                continue
            filled = np.interp(t, t[good], col[good])
            # only fill gaps shorter than max_gap
            gap_mask = ~good
            run_start = None
            for i in range(n + 1):
                if i < n and gap_mask[i]:
                    if run_start is None:
                        run_start = i
                elif run_start is not None:
                    inside = run_start > 0 and i < n
                    if inside and (i - run_start) <= max_gap:
                        col[run_start:i] = filled[run_start:i]
                    run_start = None
            if smooth > 1:
                kernel = np.ones(smooth) / smooth
                valid = ~np.isnan(col)
                tmp = np.where(valid, col, 0.0)
                num = np.convolve(tmp, kernel, mode="same")
                den = np.convolve(valid.astype(float), kernel, mode="same")
                with np.errstate(invalid="ignore", divide="ignore"):
                    sm = num / den
                col = np.where(valid, sm, np.nan)
            xy[:, j, k] = col
    out = dict(pose)
    out["xy"] = xy
    return out


def joint_angle(xy, a, b, c):
    """Angle at joint b (degrees) for every frame. xy shape (N,33,2)."""
    ba = xy[:, a] - xy[:, b]
    bc = xy[:, c] - xy[:, b]
    dot = np.sum(ba * bc, axis=1)
    norm = np.linalg.norm(ba, axis=1) * np.linalg.norm(bc, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos = np.clip(dot / norm, -1.0, 1.0)
    return np.degrees(np.arccos(cos))


def body_height_px(xy):
    """Typical nose-to-ankle distance in pixels (median over the clip)."""
    ankle_y = np.nanmean(xy[:, [L_ANKLE, R_ANKLE], 1], axis=1)
    d = ankle_y - xy[:, NOSE, 1]
    d = d[~np.isnan(d)]
    return float(np.median(d)) if len(d) else float("nan")


def draw_skeleton(frame, pts, color=(255, 200, 0)):
    """pts: (33,2) pixel coordinates (may contain NaN)."""
    for a, b in SKELETON:
        pa, pb = pts[a], pts[b]
        if not (np.isnan(pa).any() or np.isnan(pb).any()):
            cv2.line(frame, tuple(int(v) for v in pa), tuple(int(v) for v in pb), color, 3)
    for j in set(i for pair in SKELETON for i in pair) | {NOSE}:
        p = pts[j]
        if not np.isnan(p).any():
            cv2.circle(frame, (int(p[0]), int(p[1])), 5, (255, 255, 255), -1)


def put_text(frame, text, y, color=(255, 255, 255), scale=0.8):
    cv2.putText(frame, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 5)
    cv2.putText(frame, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2)
