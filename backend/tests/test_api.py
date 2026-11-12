"""Smoke test for every endpoint in the contract. Run from the repo root:
    python -m pytest backend/tests -q        (or)   python backend/tests/test_api.py
"""
import io
import json
import time

from fastapi.testclient import TestClient

from backend.app import mock_store
from backend.app.main import app


def test_all_endpoints():
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"ok": True, "demo_mode": False}

        players = c.get("/api/players").json()
        assert len(players) > 100
        private = {"weight_kg", "sitting_height_cm", "birth_date", "email", "phone", "address"}
        assert not private & set(players[0])
        gems = [p for p in players if p["hidden_gem"]]
        assert gems, "mock data should contain hidden gems"
        for p in players:   # breakdown always sums to fair_score
            if p["breakdown"]:
                assert sum(s["value"] for s in p["breakdown"]) == p["fair_score"], p["id"]

        rep = c.get("/api/players/p_001").json()
        assert rep["player"]["rank_group"] == "Boys U16"
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

        bad_file = c.post(f"/api/players/{pid}/videos", data={"kind": "jump"},
                          files={"file": ("x.txt", io.BytesIO(b"x"))})
        assert bad_file.status_code == 400

        mock_store.JOB_SECONDS = 0.5        # speed up the fake analysis
        jobs = [c.post(f"/api/players/{pid}/videos", data={"kind": k},
                       files={"file": (f"{k}.mp4", io.BytesIO(b"fake"))}).json()
                for k in ("shooting", "dribbling", "jump")]
        time.sleep(1.2)
        assert all(c.get(f"/api/jobs/{j['job_id']}").json()["status"] == "done" for j in jobs)

        rep = c.post(f"/api/players/{pid}/analyze").json()
        assert rep["player"]["status"] == "ranked" and rep["player"]["fair_rank"]
        assert len(rep["coach_report"]["drills"]) == 3
        assert c.post(f"/api/players/{pid}/coach-report").json()["source"] == "rules"

        bias = c.get("/api/bias").json()
        assert sum(bias["birth_quarter"]["raw_top10"]) <= 10 * 10        # top 10 of each of 10 groups
        one = c.get("/api/bias", params={"rank_group": "Boys U14"}).json()
        assert sum(one["birth_quarter"]["raw_top10"]) == 10
        json.dumps(bias, allow_nan=False)
        print(f"OK - {len(players)} players, {len(gems)} hidden gems, "
              f"raw top10 quarters {bias['birth_quarter']['raw_top10']}, "
              f"fair top10 {bias['birth_quarter']['fair_top10']}, "
              f"height raw {bias['height']['raw_top10_avg_diff_cm']} vs fair {bias['height']['fair_top10_avg_diff_cm']}")


if __name__ == "__main__":
    test_all_endpoints()
