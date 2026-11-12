# HoopScout backend (FastAPI)

Builds against `api_contract.md` (v2).

**Done:** Phase 2 (real video pipeline, SQLite, background worker) and Phase 4 (AI coach report).
Skill scores use draft formulas ([skills.py](app/skills.py)); the fair-score coefficients are
still fixed numbers (Phase 3 = regression).

## AI coach report

Put a Groq key in `.env` (copy `.env.example`; `.env` is git-ignored):

```
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b      # Llama 3.3 from the contract is no longer on Groq
```

- The AI gets only numbers: skill scores, shot-to-shot spreads, targets with a checked ideal
  range, dribbling and jump metrics, plus age group / gender / position / hand / years playing.
  Never the name, club, town, birth date, weight or video.
- Drills must work for one player alone (ball, hoop, wall).
- No key, no Wi-Fi, timeout (15 s) or a wrong answer shape -> rule-based report (`"source": "rules"`).
- `config.NOT_VALIDATED` (now: elbow at set) = shown in the profile, never scored, never sent to the AI.

## Run

From the repo root, with the venv active:

```
pip install -r requirements.txt
uvicorn backend.app.main:app --port 8000
```

- API docs (try every endpoint): http://localhost:8000/docs
- Frontend: set `VITE_API_URL=http://localhost:8000`
- Tests (fake pipeline, fast): `python -m pytest backend/tests -q`

Don't use `--reload` while a video is being analyzed: saving a file restarts the server
and the running job is marked failed.

## How an upload flows

```
POST /api/players/{id}/videos   file saved to data/uploads/  -> Job (queued)
   worker thread (one video at a time):
     step1 convert      -> data/work/{id}_{kind}.mp4
     step2 pose + check -> quality, camera problems as flags
     step3 / 4 / 5      -> metrics, sanity flags
     annotated video    -> data/media/{id}_{kind}.mp4  (served at /media)
GET  /api/jobs/{job_id}         poll every 2 s: progress + step
POST /api/players/{id}/analyze  metrics -> skill scores -> fair score -> re-rank everyone
```

The pipeline calls the tested step scripts in the repo root directly, so a fix in
e.g. `step4_shooting_test.py` is used by the app automatically.

Inputs from the profile: shooting `--hand` = `dominant_hand`, the weak hand = the other
hand, jump `--height` = `height_cm`.

## Data

- `data/hoopscout.db`: real players (incl. private input fields, never returned) and jobs
- `data/uploads`, `data/work`, `data/media`: videos. All local, all git-ignored
- 400 simulated players (`is_real: false`) are regenerated from a fixed seed at startup
- First start: `p_001` is created with the contract example numbers

Delete `data/hoopscout.db` to start over.

## Layout

```
backend/app/
  main.py        routes, CORS, /media, {"error": ...} handler, NaN -> null
  schemas.py     Pydantic copy of the contract types
  config.py      IDEAL ranges, weights, sanity limits, min reps, pipeline defaults
  pipeline.py    runs step1-5 on one upload -> contract analysis dict
  jobs.py        background worker (one job at a time), progress
  skills.py      metrics -> skill scores 0-100, ranked / provisional (DRAFT formulas)
  store.py       players, fair score, ranks, reports, bias
  synthetic.py   simulated players + the contract example
  derive.py      age, age group (by birth year), birth quarter, height diff, Mirwald
  scoring.py     target_check, fair score + breakdown, ranking + hidden gems
  db.py          SQLite
```
