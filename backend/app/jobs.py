"""
Background worker: ONE thread analyzes ONE video at a time (pose + YOLO would fight
for the CPU otherwise). Jobs are kept in memory for fast polling and saved to SQLite.
"""
import queue
import threading
import time
import traceback
import uuid

from . import db
from .errors import PipelineError

JOBS: dict = {}                 # job_id -> Job dict (contract fields + upload_path)
_queue: "queue.Queue[str]" = queue.Queue()
_LOCK = threading.Lock()
_worker = None

# Replaceable for tests: runner(job) -> analysis dict. Set by store.start().
RUNNER = None
ON_DONE = None                  # callback(job, analysis)
AFTER_DONE = None               # callback(job) after the job is marked done (auto-analyze)


def _update(job_id, **fields):
    with _LOCK:
        JOBS[job_id].update(fields)
        db.save_job(JOBS[job_id])


def submit(player_id, kind, upload_path) -> dict:
    job_id = f"j_{uuid.uuid4().hex[:8]}"
    job = {"job_id": job_id, "player_id": player_id, "kind": kind, "status": "queued",
           "progress": 0, "step": "Waiting in queue", "error": None, "upload_path": str(upload_path),
           "created_at": time.time()}
    with _LOCK:
        JOBS[job_id] = job
        db.save_job(job)
    _queue.put(job_id)
    return view(job_id)


def view(job_id) -> dict:
    j = JOBS[job_id]
    return {k: j[k] for k in ("job_id", "player_id", "kind", "status", "progress", "step", "error")}


def player_jobs(player_id):
    return [j for j in JOBS.values() if j["player_id"] == player_id]


def latest_jobs(player_id):
    """The newest job per video kind for one player (what the profile shows)."""
    newest = {}
    for j in player_jobs(player_id):
        k = j["kind"]
        if k not in newest or j.get("created_at", 0) >= newest[k].get("created_at", 0):
            newest[k] = j
    order = {"shooting": 0, "dribbling": 1, "jump": 2}
    return [view(j["job_id"]) for j in sorted(newest.values(), key=lambda j: order[j["kind"]])]


def has_pending(player_id):
    return any(j["status"] in ("queued", "running") for j in player_jobs(player_id))


def _run_one(job_id):
    job = JOBS[job_id]
    _update(job_id, status="running", progress=1, step="Starting")

    def progress(pct, step):
        _update(job_id, progress=int(max(1, min(99, pct))), step=step)

    try:
        analysis = RUNNER(job, progress)
        ON_DONE(job, analysis)
        _update(job_id, status="done", progress=100, step="Done")
        if AFTER_DONE:
            try:
                AFTER_DONE(job)
            except Exception:                # never let auto-analyze break the worker
                traceback.print_exc()
    except BaseException as e:          # SystemExit from the scripts too
        if isinstance(e, PipelineError):
            msg = str(e)
        else:
            traceback.print_exc()
            msg = f"Analysis failed: {e}" if str(e) else f"Analysis failed ({e.__class__.__name__})"
        _update(job_id, status="failed", error=msg)


def _loop():
    while True:
        job_id = _queue.get()
        try:
            _run_one(job_id)
        finally:
            _queue.task_done()


def start(known_players=None):
    """Load old jobs. Jobs that were queued or running when the server stopped are QUEUED AGAIN
    (same job_id, so an open upload page keeps polling), as long as the uploaded video and the
    player still exist. Otherwise they are marked failed with a message for the coach."""
    global _worker
    old = sorted(db.load_jobs(), key=lambda j: j["job_id"])
    requeue = []
    for j in old:
        if j["status"] in ("queued", "running"):
            from pathlib import Path
            player_ok = known_players is None or j["player_id"] in known_players
            if player_ok and Path(j.get("upload_path", "")).exists():
                j.update(status="queued", progress=0, step="Waiting in queue", error=None)
                requeue.append(j["job_id"])
            else:
                j.update(status="failed", error="Server restarted during analysis - upload again.")
            db.save_job(j)
        JOBS[j["job_id"]] = j
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_loop, daemon=True, name="hoopscout-worker")
        _worker.start()
    for job_id in requeue:
        _queue.put(job_id)
    if requeue:
        print(f"Re-queued {len(requeue)} unfinished job(s) after restart")


def wait_idle():
    """For tests and scripts: block until the queue is empty."""
    _queue.join()
