"""
Do what the coach upload screen does, from the terminal: upload videos for a player,
poll the jobs every 2 s, then analyze. The server must be running.

    python backend/scripts/upload_videos.py p_001 --shooting raw_videos/hamza_shooting.MOV \
        --dribbling raw_videos/hamza_dribbling.mp4 --jump raw_videos/hamza_jump.MOV
"""
import argparse
import sys
import time

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player_id")
    ap.add_argument("--shooting")
    ap.add_argument("--dribbling")
    ap.add_argument("--jump")
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()

    c = httpx.Client(base_url=args.api, timeout=600)
    start = time.time()
    jobs = {}
    for kind in ("shooting", "dribbling", "jump"):
        path = getattr(args, kind)
        if not path:
            continue
        with open(path, "rb") as f:
            r = c.post(f"/api/players/{args.player_id}/videos", data={"kind": kind},
                       files={"file": (path.replace("\\", "/").split("/")[-1], f)})
        if r.status_code >= 400:
            sys.exit(f"{kind}: {r.json()['error']}")
        jobs[kind] = r.json()["job_id"]
        print(f"uploaded {kind:<9} -> job {jobs[kind]}")

    last = {}
    while True:
        states = {k: c.get(f"/api/jobs/{j}").json() for k, j in jobs.items()}
        for k, s in states.items():
            line = f"{s['status']:<7} {s['progress']:3d}%  {s['step']}"
            if last.get(k) != line:
                print(f"[{time.time() - start:5.0f} s] {k:<9} {line}"
                      + (f"  ERROR: {s['error']}" if s["error"] else ""))
                last[k] = line
        if all(s["status"] in ("done", "failed") for s in states.values()):
            break
        time.sleep(2)

    r = c.post(f"/api/players/{args.player_id}/analyze")
    if r.status_code >= 400:
        sys.exit(f"analyze: {r.json()['error']}")
    p = r.json()["player"]
    print(f"\nTotal {time.time() - start:.0f} s")
    print(f"{p['name']} ({p['rank_group']}): status {p['status']}"
          + (f" - {p['provisional_reason']}" if p["provisional_reason"] else ""))
    print("scores     ", p["scores"])
    print("fair_scores", p["fair_scores"])
    print(f"raw {p['raw_score']} (rank {p['raw_rank']})  ->  fair {p['fair_score']} ± {p['score_margin']} "
          f"(rank {p['fair_rank']})  hidden gem: {p['hidden_gem']}")


if __name__ == "__main__":
    main()
