"""
Run the video pipeline in a SEPARATE PROCESS with lower CPU priority.

Why: pose + YOLO keep the CPU and Python busy for 10+ minutes. In the API process that would
make /api/players and /api/jobs slow, and the frontend treats a slow answer as "backend down".
In its own low-priority process the API stays fast while a video is analyzed.

Progress messages come back through a queue; PipelineError keeps its coach-friendly text.
"""
import multiprocessing as mp
import os
import queue
import sys

from .errors import PipelineError


def _lower_priority():
    try:
        if sys.platform == "win32":
            import ctypes
            BELOW_NORMAL = 0x00004000
            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), BELOW_NORMAL)
        else:
            os.nice(10)
    except Exception:
        pass                                 # priority is nice-to-have, never fatal


def _child(args, q):
    _lower_priority()
    try:
        from .pipeline import run_analysis
        result = run_analysis(*args, progress=lambda pct, step: q.put(("progress", pct, step)))
        q.put(("done", result))
    except PipelineError as e:
        q.put(("pipeline_error", str(e)))
    except BaseException as e:               # SystemExit from the scripts too
        q.put(("error", f"{e.__class__.__name__}: {e}"))


def run_in_process(player_input, kind, upload_path, stem, progress):
    """Same arguments/result as pipeline.run_analysis, but in a child process."""
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_child, args=((player_input, kind, upload_path, stem), q),
                    daemon=True, name=f"hoopscout-{stem}")
    p.start()
    try:
        while True:
            try:
                msg = q.get(timeout=2)
            except queue.Empty:
                if not p.is_alive():
                    raise RuntimeError(f"analysis process stopped unexpectedly (exit code {p.exitcode})")
                continue
            if msg[0] == "progress":
                progress(msg[1], msg[2])
            elif msg[0] == "done":
                return msg[1]
            elif msg[0] == "pipeline_error":
                raise PipelineError(msg[1])
            else:
                raise RuntimeError(msg[1])
    finally:
        p.join(timeout=10)
        if p.is_alive():
            p.terminate()
