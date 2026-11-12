# HoopScout

A coach enters a kid's bio and uploads 3 phone videos (shooting, dribbling, jump). The app
measures their skills, writes an AI coach report with drills, and places the kid on a fair
Talent Board where scouts can find hidden gems — kids who are overlooked because they were born
late in the year or are still small.

- **API contract** (frontend + backend build against it): [api_contract.md](api_contract.md)
- **Backend** (Python, FastAPI): [backend/README.md](backend/README.md)
- **Frontend** (React + TypeScript, TanStack Start, built with Lovable): `src/`

## Run everything locally

Backend (terminal 1, from this folder):

```
python -m venv venv
venv\Scripts\activate            (Windows)    source venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Frontend (terminal 2, from this folder):

```
npm i
npm run dev
```

Open http://localhost:5173. The frontend reads the API from `VITE_API_URL`
(default `http://localhost:8000`).

Demo mode (stage safety net, uploads finish in ~10 s with saved results):

```
$env:DEMO_MODE="true"; python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Privacy

Kids' videos, the database (`data/`) and `.env` (API keys) stay on the laptop and are
git-ignored. The AI only ever sees measured numbers.

## Video analysis test scripts

`step1_convert.py` … `step5_jump_test.py` are the tested video analysis scripts the backend
uses. See the section below for testing them on new videos.

---

## HoopScout – video testing, step by step

Goal: before the hackathon, prove that the video analysis works on YOUR videos.
Do the steps in order. Each step tells you GOOD / NEEDS FIXING.

## Step 0 – Setup (once, at home)

1. Install Python 3.11 or 3.12 (3.13 also works).
2. Open a terminal in this folder and run:

```
python -m venv venv
venv\Scripts\activate          (Windows)
source venv/bin/activate       (Mac/Linux)
pip install -r requirements.txt
```

`ultralytics` installs PyTorch, which is a big download, so do this on good Wi-Fi.
The MediaPipe pose model and the YOLO model download automatically the first time.

Folder layout:

```
hoopscout_test/
├── raw_videos/      <- put your .MOV files here
├── videos/          <- converted .mp4 files (step 1 creates this)
├── test_output/     <- annotated videos + CSV (created automatically)
└── *.py
```

Name the files like: `amar_shooting.MOV`, `amar_dribbling.MOV`, `amar_jump.MOV`.

## Step 1 – Convert the videos

```
python step1_convert.py raw_videos videos
```

✅ Every file says OK. Check the **out fps** column: 60 is best for the jump, 30 is fine.

## Step 2 – Can MediaPipe see the player? (run on EVERY video)

```
python step2_pose_test.py videos/amar_shooting.mp4
```

✅ VERDICT: GOOD, person detected ≥ 90%.
👀 Open `test_output/amar_shooting_pose.mp4`: the skeleton must follow the body.
❌ NEEDS FIXING → follow the hint (closer camera, whole body in frame, better light) and re-film.

## Step 3 – Ball tracking + dribbling (the riskiest part)

```
python step3_dribble_ball_test.py videos/amar_dribbling.mp4
```

✅ "After filling short gaps" ≥ 70% = ball tracking works.
👀 Open `test_output/amar_dribbling_ball.mp4`: the circle must stay on the ball.
✋ **Count the dribbles yourself** in the video and compare with the two counts.
If the ball is found < 70%, try the bigger model:

```
python step3_dribble_ball_test.py videos/amar_dribbling.mp4 --model yolov8s.pt
```

If it is still weak, the app will use the wrist-based count (fallback).

## Step 4 – Shooting numbers

```
python step4_shooting_test.py videos/amar_shooting.mp4 --hand right
```

✅ "Shots found" = the real number of shots in the video.
✅ Elbow at set point is usually 60–110°, knee bend 100–150°.
👀 Open `test_output/amar_shooting_shooting.mp4`: the DIP / SET / RELEASE labels should
appear at the right moments. Per-shot numbers are in `test_output/amar_shooting_shots.csv`.

## Step 5 – Vertical jump

```
python step5_jump_test.py videos/amar_jump.mp4 --height 158
```

(`--height` = the kid's real height in cm)

✅ "Jumps found" = the real number of jumps.
✅ Both methods agree ("yes") and the height is realistic (roughly 20–45 cm for 10–14 year olds).

## Results table – fill this in for all 4 kids

| Kid | Step 2 pose | Step 3 ball % | Dribbles (real / app) | Shots (real / app) | Jumps (real / app) | Jump cm |
|-----|-------------|---------------|-----------------------|--------------------|--------------------|---------|
|     |             |               |                       |                    |                    |         |

If all rows look good, the video part of the app is proven, and the hackathon is
"only" building the app around it.

## Notes

- `check_video.py` from earlier uses the OLD MediaPipe API that new versions removed.
  Use `step2_pose_test.py` instead.
- Thresholds such as the consistency formula are first drafts. Tune them after seeing real numbers.
