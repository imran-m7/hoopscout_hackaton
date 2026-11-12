"""
HoopScout API (contract v2) - Phase 2: real video pipeline, SQLite, background worker.

Run from the repo root:
    uvicorn backend.app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import math
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from . import jobs, store
from .schemas import (BiasData, CoachReport, Gender, Health, Job, PlayerInput, PlayerReport,
                      PlayerSummary, VideoKind)


# ------------------------------------------------------------------ JSON: NaN -> null
def _no_nan(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return {k: _no_nan(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_no_nan(x) for x in v]
    return v


class SafeJSONResponse(JSONResponse):
    """Contract: unknown values are null, never NaN (NaN is invalid JSON)."""
    def render(self, content) -> bytes:
        return super().render(_no_nan(content))


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.start()
    yield


app = FastAPI(title="HoopScout API", version="2", default_response_class=SafeJSONResponse,
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory=config.MEDIA_DIR), name="media")


# ------------------------------------------------------------------ errors: { "error": "..." }
@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return SafeJSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    parts = []
    for e in exc.errors():
        field = ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path"))
        parts.append(f"{field}: {e['msg']}" if field else e["msg"])
    return SafeJSONResponse({"error": "; ".join(parts) or "Invalid request"}, status_code=422)


@app.exception_handler(Exception)
async def server_error(_: Request, exc: Exception):
    return SafeJSONResponse({"error": f"Server error: {exc}"}, status_code=500)


def _player_or_404(pid: str):
    pid = pid.strip()                      # "p_001 " typed by hand -> "p_001"
    if pid not in store.PLAYERS:
        raise HTTPException(404, f"Player {pid} not found")
    return store.PLAYERS[pid]


# ------------------------------------------------------------------ endpoints
@app.get("/api/health", response_model=Health)
def health():
    return {"ok": True, "demo_mode": config.DEMO_MODE}


@app.get("/api/players", response_model=List[PlayerSummary])
def list_players():
    return [r["summary"] for r in store.PLAYERS.values()]


@app.get("/api/players/{pid}", response_model=PlayerReport)
def get_player(pid: str):
    pid = pid.strip()
    _player_or_404(pid)
    return store.report(pid)


@app.post("/api/players", response_model=PlayerSummary, status_code=201)
def create_player(body: PlayerInput):
    inp = body.model_dump()
    inp["birth_date"] = body.birth_date.isoformat()
    return store.create_player(inp)


@app.post("/api/players/{pid}/videos", response_model=Job, status_code=202)
def upload_video(pid: str, kind: VideoKind = Form(...), file: UploadFile = File(...)):
    pid = pid.strip()
    rec = _player_or_404(pid)
    if not rec["is_real"]:
        raise HTTPException(400, "Simulated players can't get videos")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.VIDEO_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext or '?'}'. Use .mov, .mp4, .m4v or .avi")
    dest = config.UPLOAD_DIR / f"{pid}_{kind}_{uuid.uuid4().hex[:6]}{ext}"
    with dest.open("wb") as out:                       # streamed in chunks: no size limit
        shutil.copyfileobj(file.file, out, length=1024 * 1024)
    if dest.stat().st_size == 0:
        dest.unlink()
        raise HTTPException(400, "The uploaded file is empty")
    return jobs.submit(pid, kind, dest)


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job_id = job_id.strip()
    if job_id not in jobs.JOBS:
        raise HTTPException(404, f"Job {job_id} not found")
    return jobs.view(job_id)


@app.post("/api/players/{pid}/analyze", response_model=PlayerReport)
def analyze(pid: str):
    pid = pid.strip()
    rec = _player_or_404(pid)
    if not rec["is_real"]:
        raise HTTPException(400, "Simulated players can't be analyzed")
    try:
        return store.analyze(pid)
    except store.Busy as e:
        raise HTTPException(409, str(e))


@app.post("/api/players/{pid}/coach-report", response_model=CoachReport)
def coach_report(pid: str):
    pid = pid.strip()
    _player_or_404(pid)
    return store.regenerate_coach_report(pid)


@app.get("/api/bias", response_model=BiasData)
def get_bias(gender: Optional[Gender] = None, rank_group: Optional[str] = None):
    """Optional filters: ?gender=girl or ?rank_group=Boys U14. Groups are never mixed."""
    return store.bias(gender, rank_group)
