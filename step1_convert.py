"""
STEP 1 - Convert iPhone .MOV videos to browser-friendly .mp4

- Fixes rotation (sideways videos)
- Converts HEVC/H.265 to H.264 (OpenCV and browsers can read it)
- Resizes so the longest side is max 1280 px (faster analysis)
- Slow-motion videos (>60 fps) are reduced to 60 fps
- Removes audio

Usage:
    python step1_convert.py raw_videos videos
    (raw_videos = folder with your .MOV files, videos = output folder)
"""
import pathlib
import subprocess
import sys

import cv2
import imageio_ffmpeg

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".avi"}


def source_fps(path):
    """Read fps using ffmpeg itself (works even for HEVC that OpenCV can't open)."""
    import warnings
    warnings.filterwarnings("ignore")
    try:
        reader = imageio_ffmpeg.read_frames(str(path))
        meta = next(reader)
        reader.close()
        return float(meta.get("fps") or 30.0)
    except Exception:
        return 30.0


def convert(src, dst):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    fps = source_fps(src)
    vf = ("scale=w=1280:h=1280:force_original_aspect_ratio=decrease,"
          "scale=trunc(iw/2)*2:trunc(ih/2)*2")
    if fps > 61:
        vf += ",fps=60"
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-an", str(dst)]
    subprocess.run(cmd, check=True)
    return fps


def main(src_dir, dst_dir):
    src_dir, dst_dir = pathlib.Path(src_dir), pathlib.Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src_dir.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not files:
        sys.exit(f"No videos found in {src_dir}")

    print(f"{'file':<40} {'src fps':>8} {'out size':>11} {'out fps':>8} {'seconds':>8}  status")
    for f in files:
        out = dst_dir / (f.stem + ".mp4")
        try:
            in_fps = convert(f, out)
            cap = cv2.VideoCapture(str(out))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            secs = n / fps if fps else 0
            note = "OK"
            if fps < 29:
                note = "OK (low fps: jump/timing less precise)"
            if h > w:
                note += " | portrait video"
            print(f"{f.name:<40} {in_fps:>8.0f} {f'{w}x{h}':>11} {fps:>8.0f} {secs:>8.1f}  {note}")
        except subprocess.CalledProcessError:
            print(f"{f.name:<40} {'':>8} {'':>11} {'':>8} {'':>8}  FAILED to convert")
    print(f"\nDone. Converted videos are in: {dst_dir}/")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python step1_convert.py <raw_videos_folder> <output_folder>")
    main(sys.argv[1], sys.argv[2])
