"""Every endpoint in the contract, with a FAKE pipeline (fast). Run from the repo root:
    python -m pytest backend/tests -q
"""
import copy
import io
import json

from fastapi.testclient import TestClient

from backend.app import jobs
from backend.app.main import app
from backend.app.synthetic import example_analyses


def fake_runner(job, progress):
    progress(50, "Detecting pose")
    if open(job["upload_path"], "rb").read() == b"FAIL":
        from backend.app.errors import PipelineError
        raise PipelineError("Player too small in the frame - move the camera closer.")
    return copy.deepcopy(example_analyses()[job["kind"]])


def test_all_endpoints():
    with TestClient(app) as c:
        jobs.RUNNER = fake_runner
        assert c.get("/api/health").json() == {"ok": True, "demo_mode": False}

        players = c.get("/api/players").json()
        assert len(players) > 400
        private = {"weight_kg", "sitting_height_cm", "birth_date", "email", "phone", "address"}
        assert not private & set(players[0])
        assert any(p["hidden_gem"] for p in players)
        for p in players:   # breakdown always sums to fair_score
            if p["breakdown"]:
                assert sum(s["value"] for s in p["breakdown"]) == p["fair_score"], p["id"]

        rep = c.get("/api/players/p_001").json()
        assert rep["player"]["rank_group"] == "Boys U14"   # born 2012 -> turns 14 in 2026
        assert rep["player"]["scores"]["consistency"] == 84          # step4 formula on the example
        assert rep["shooting"]["targets"][0]["metric"] == "avg_elbow_set_deg"
        assert c.get("/api/players/nope").json() == {"error": "Player nope not found"}

        bad = c.post("/api/players", json={"name": "x"})
        assert bad.status_code == 422 and "error" in bad.json()

        new = c.post("/api/players", json={
            "name": "Test Kid", "gender": "girl", "birth_date": "2014-11-02", "height_cm": 150,
            "weight_kg": 40, "sitting_height_cm": 78, "dominant_hand": "left", "position": "guard",
            "years_playing": 1, "club": "KK Test", "town": "Mostar"}).json()
        assert new["status"] == "provisional" and "weight_kg" not in new
        assert new["maturity_offset_years"] is not None
        pid = new["id"]

        assert c.post(f"/api/players/{pid}/videos", data={"kind": "jump"},
                      files={"file": ("x.txt", io.BytesIO(b"x"))}).status_code == 400
        assert c.post("/api/players/p_100/videos", data={"kind": "jump"},
                      files={"file": ("a.mp4", io.BytesIO(b"x"))}).status_code == 400   # simulated

        js = [c.post(f"/api/players/{pid}/videos", data={"kind": k},
                     files={"file": (f"{k}.mp4", io.BytesIO(b"fake"))}).json()
              for k in ("shooting", "dribbling", "jump")]
        jobs.wait_idle()
        assert all(c.get(f"/api/jobs/{j['job_id']}").json()["status"] == "done" for j in js)

        failed = c.post(f"/api/players/{pid}/videos", data={"kind": "jump"},
                        files={"file": ("bad.mp4", io.BytesIO(b"FAIL"))}).json()
        jobs.wait_idle()
        f = c.get(f"/api/jobs/{failed['job_id']}").json()
        assert f["status"] == "failed" and "camera" in f["error"]

        # auto-analyze: ranked right after the last video, without calling /analyze
        auto = c.get(f"/api/players/{pid}").json()
        assert auto["player"]["status"] == "ranked" and auto["coach_report"] is not None
        pj = c.get(f"/api/players/{pid}/jobs").json()
        assert [j["kind"] for j in pj] == ["shooting", "dribbling", "jump"]
        assert pj[2]["status"] == "failed"          # the newest jump upload is the failed one

        rep = c.post(f"/api/players/{pid}/analyze").json()
        assert rep["player"]["status"] == "ranked" and rep["player"]["fair_rank"]
        assert rep["player"]["rank_group"].startswith("Girls")
        assert len(rep["coach_report"]["drills"]) == 3
        assert rep["sessions"][0]["target_values"]["avg_elbow_set_deg"] == 56
        assert c.post(f"/api/players/{pid}/coach-report").json()["source"] == "rules"

        bias = c.get("/api/bias").json()
        json.dumps(bias, allow_nan=False)
        one = c.get("/api/bias", params={"rank_group": "Boys U14"}).json()
        assert sum(one["birth_quarter"]["raw_top10"]) == 10

    # restart: the real player is still there (SQLite)
    with TestClient(app) as c:
        again = c.get(f"/api/players/{pid}").json()
        assert again["player"]["status"] == "ranked" and again["shooting"] is not None


def test_demo_mode_replays_saved_results():
    from backend.app import config, store
    with TestClient(app) as c:
        config.DEMO_JOB_SECONDS = 0.2
        jobs.RUNNER = store._demo_runner
        pid = c.post("/api/players", json={
            "name": "Demo Kid", "gender": "boy", "birth_date": "2012-03-02", "height_cm": 160,
            "dominant_hand": "right", "position": "forward", "years_playing": 3,
            "club": "KK Test", "town": "Tuzla"}).json()["id"]
        js = [c.post(f"/api/players/{pid}/videos", data={"kind": k},
                     files={"file": (f"{k}.mp4", io.BytesIO(b"x"))}).json()
              for k in ("shooting", "dribbling", "jump")]
        jobs.wait_idle()
        assert all(c.get(f"/api/jobs/{j['job_id']}").json()["status"] == "done" for j in js)
        rep = c.post(f"/api/players/{pid}/analyze").json()
        assert rep["player"]["status"] == "ranked"
        assert rep["jump"]["best_jump_cm"] == c.get("/api/players/p_001").json()["jump"]["best_jump_cm"]


def test_video_urls_follow_the_address_the_browser_used():
    from backend.app.store import _with_current_media_urls
    saved = {"jump": {"annotated_video_url": "http://10.0.87.8:8000/media/p_001_jump.mp4?v=1"}, "dribbling": None}
    local = _with_current_media_urls(saved, "http://localhost:8000/")
    assert local["jump"]["annotated_video_url"] == "http://localhost:8000/media/p_001_jump.mp4?v=1"
    lan = _with_current_media_urls(saved, "http://10.0.87.8:8000/")
    assert lan["jump"]["annotated_video_url"] == "http://10.0.87.8:8000/media/p_001_jump.mp4?v=1"
    assert saved["jump"]["annotated_video_url"].startswith("http://10.0.87.8")   # stored value untouched


def test_unfinished_jobs_are_requeued_after_restart(monkeypatch):
    """Restarting the server must not lose queued uploads (same job_id keeps working)."""
    from backend.app import store
    monkeypatch.setattr(store, "_pipeline_runner", fake_runner)   # also used right at startup
    with TestClient(app) as c:
        jobs.RUNNER = fake_runner
        pid = c.post("/api/players", json={
            "name": "Restart Kid", "gender": "girl", "birth_date": "2013-02-02", "height_cm": 150,
            "dominant_hand": "right", "position": "guard", "years_playing": 1,
            "club": "KK Test", "town": "Zenica"}).json()["id"]
        jobs.wait_idle()
        # simulate "server stopped while this job was still waiting"
        import pathlib
        from backend.app import config, db
        up = config.UPLOAD_DIR / f"{pid}_jump_test.mp4"
        up.write_bytes(b"x")
        db.save_job({"job_id": "j_restart1", "player_id": pid, "kind": "jump", "status": "queued",
                     "progress": 0, "step": "Waiting in queue", "error": None, "upload_path": str(up)})
    with TestClient(app) as c:
        jobs.RUNNER = fake_runner
        jobs.wait_idle()
        j = c.get("/api/jobs/j_restart1").json()
        assert j["status"] == "done", j
        assert pathlib.Path(up).exists()
