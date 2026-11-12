"""
Background worker: ONE thread analyzes ONE video at a time (pose + YOLO would fight
for the CPU otherwise). Jobs are kept in memory for fast polling and saved to SQLite.
"""
import queue
import threading
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


def _update(job_id, **fields):
    with _LOCK:
        JOBS[job_id].update(fields)
        db.save_job(JOBS[job_id])


def submit(player_id, kind, upload_path) -> dict:
    job_id = f"j_{uuid.uuid4().hex[:8]}"
    job = {"job_id": job_id, "player_id": player_id, "kind": kind, "status": "queued",
           "progress": 0, "step": "Waiting in queue", "error": None, "upload_path": str(upload_path)}
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


def _run_one(job_id):
    job = JOBS[job_id]
    _update(job_id, status="running", progress=1, step="Starting")

    def progress(pct, step):
        _update(job_id, progress=int(max(1, min(99, pct))), step=step)

    try:
        analysis = RUNNER(job, progress)
        ON_DONE(job, analysis)
        _update(job_id, status="done", progress=100, step="Done")
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


def start():
    """Load old jobs; jobs that were running when the server stopped are marked failed."""
    global _worker
    for j in db.load_jobs():
        if j["status"] in ("queued", "running"):
            j.update(status="failed", error="Server restarted during analysis - upload again.")
            db.save_job(j)
        JOBS[j["job_id"]] = j
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_loop, daemon=True, name="hoopscout-worker")
        _worker.start()


def wait_idle():
    """For tests and scripts: block until the queue is empty."""
    _queue.join()
