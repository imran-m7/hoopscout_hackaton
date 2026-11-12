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
        assert rep["player"]["rank_group"] == "Boys U16"
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
