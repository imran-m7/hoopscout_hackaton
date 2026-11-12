# HoopScout backend (FastAPI)

Builds against `api_contract.md` (v2). **Phase 1 = mock data**: every endpoint works and
returns contract-shaped JSON, so the frontend can build all screens now.

## Run

From the repo root, with the venv active:

```
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

- API docs (try every endpoint): http://localhost:8000/docs
- Frontend: set `VITE_API_URL=http://localhost:8000`
- Test: `python -m pytest backend/tests -q`

## What the mock does

| Endpoint | Mock behaviour |
|---|---|
| `GET /api/players` | 400 simulated players (`is_real: false`) + `p_001` (real test numbers) |
| `POST /api/players` | Creates a real player, `status: "provisional"` until analyzed |
| `POST /api/players/{id}/videos` | Saves the file to `data/uploads/`, returns a job |
| `GET /api/jobs/{id}` | Progress advances over ~12 s. A filename containing `fail` makes the job fail (to test the error UI) |
| `POST /api/players/{id}/analyze` | Attaches p_001's numbers (with jitter) for each finished upload, re-ranks everyone |
| `POST /api/players/{id}/coach-report` | Rule-based report (`source: "rules"`) |
| `GET /api/bias` | Computed from the current players |

Data lives in memory and resets when the server restarts.
Annotated video URLs are `null` unless a file exists in `data/media/` (e.g. `p_001_shooting.mp4`).

## Layout

```
backend/app/
  main.py        routes, CORS, /media, {"error": ...} handler, NaN -> null
  schemas.py     Pydantic copy of the contract types
  config.py      IDEAL ranges, weights, sanity limits, min reps (TODOs = need a coach source)
  derive.py      age, age group (by birth year), birth quarter, height diff, Mirwald
  scoring.py     target_check, fair score + breakdown, ranking + hidden gems
  mock_store.py  Phase 1 in-memory data (replaced in phases 2-3)
```
