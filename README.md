# 🏀 HoopScout

**Skill, not size.** HoopScout turns three phone videos of a young basketball player into
measured skills, an AI coach report with drills, and a **fair** ranking that finds the
talented kids traditional scouting overlooks.

## The problem

In youth sport, kids born early in the year and early growers are bigger, stronger and faster
than their teammates, and get picked. Late-born and late-developing kids with real skill are
overlooked before anyone sees what they can do. This is the *relative age effect*, and it shows
up in almost every youth team.

## What HoopScout does

1. **A coach adds a kid** (bio + 3 short phone videos: shooting, dribbling, jump).
2. **Computer vision measures the skills** on the laptop: pose tracking (MediaPipe) and ball
   tracking (YOLO) produce elbow and knee angles, release height, shot-to-shot consistency,
   dribbles per second, weak-hand use, head-up time and jump height. Every video comes back
   annotated (skeleton, ball circle, shot phases, jump labels).
3. **An AI coach report** explains the numbers in plain language and gives 3 drills a kid can
   do alone this week. The AI only sees numbers, never the video or the kid's name.
4. **A fair Talent Board** ranks every kid within their gender and age group twice:
   - **Scout view (raw):** how a traditional scout sees it, where older and taller kids look better.
   - **Fair view:** skill compared with what's expected for the kid's age and size.

   Kids who rank much higher in Fair view than in Scout view, and are in the top 25% of their
   group, are marked as **💎 hidden gems**. Each kid has a "why this rank" breakdown.
5. **Scouts** filter the board, change the skill weights with sliders, compare kids side by
   side, keep a shortlist, and see the **Bias Check**: how the fair ranking reduces the
   advantage of being born early or being tall.

## How the fair score works

- **Skill scores (0–100)** come from the video metrics. Shot-to-shot **consistency** counts 1.5×,
  because repeating the same motion is the most reliable sign of skill at any age. There are no
  made/missed shots: it measures skill, not luck on the day.
- **Age-appropriate scoring:** technique targets are wider for U10/U12 (less strength, lower hoop,
  smaller ball), and jump height and dribble speed are scored as a percentile among kids of the
  same gender and age group.
- **Fair adjustment:** a linear regression per skill and gender learns how many points a kid
  usually gains per month older and per cm taller than the others in their group. Younger and
  smaller kids get those points back; older and taller kids lose them. Ranks are only ever
  compared within the same gender and age group (Bosnian categories: U16 = turns 15 or 16 this year).
- **Honest uncertainty:** every score has a ± margin. Kids with too few reps or poor tracking are
  shown as *provisional* (not ranked) instead of getting wrong scores, and implausible values
  are flagged as tracking errors.

The full rules are in the [API contract](api_contract.md).

## Privacy by design

- Videos, the database and API keys stay on the laptop (`data/`, `.env` are git-ignored).
  Nothing is uploaded online.
- The AI coach gets only measured numbers, never video, name, club, town or birth date.
- The app never shows a birth date, weight, address or direct contact. Scouts contact a kid
  through the club ("Contact via club"). Cards show the age group.
- Coaches only see the kids of their own club.
- Simulated players are always labelled "Simulated".

## Tech stack

| Part | Technology |
|---|---|
| Frontend | React + TypeScript, TanStack Start/Router/Query, Tailwind CSS (built with Lovable) |
| Backend | Python, FastAPI, SQLite |
| Video analysis | MediaPipe Pose, Ultralytics YOLOv8 (ball), OpenCV, ffmpeg |
| Scoring | NumPy regression per skill + gender |
| AI coach report | Groq (`gpt-oss-120b`), with a rule-based fallback when offline |

Videos are analyzed in a background worker, one at a time, in a separate low-priority process,
so the app stays fast. The kid is ranked automatically after the last video.

## Run it locally

You need **Python 3.11–3.13** and **Node.js 20+**.

**1. Backend** (terminal 1, from the repo root):

```
python -m venv venv
venv\Scripts\activate                 # Windows
source venv/bin/activate              # Mac/Linux
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

The first video analysis downloads the pose model (~9 MB) and the ball model (~6 MB).
API docs: http://localhost:8000/docs

**2. Frontend** (terminal 2, from the repo root):

```
npm install
npm run dev
```

Open **http://localhost:5173**, pick **Coach** to add a kid, or **Scout** to explore the board.
The frontend reads the API from `VITE_API_URL` (default `http://localhost:8000`).

**3. AI coach report (optional):** copy `.env.example` to `.env` and add a Groq API key
(`GROQ_API_KEY=...`). Without a key, the rule-based report is used.

**Demo mode** (uploads finish in ~10 s by replaying saved results, useful on stage):

```
$env:DEMO_MODE="true"; python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

**Tests:**

```
python -m pytest backend/tests -q      # backend
npm test                               # frontend
```

## Filming tips (for good measurements)

- Phone steady (tripod), filmed from the side, **only the kid** in the frame.
- Whole body visible, head to feet, filling about a third to three quarters of the frame height.
- **Shooting:** at least 6 shots, filmed from the shooting-hand side (a left-hander from the left).
- **Dribbling:** at least 20–30 seconds, ball clearly visible against the floor.
- **Jump:** at least 3 jumps, 60 fps if possible. Good light, no window behind the kid.

## Repository layout

```
backend/             FastAPI app, scoring, AI report, tests  (see backend/README.md)
src/                 React frontend (routes, components, API client, tests)
public/              static files (icons)
step1_convert.py …   tested video analysis scripts, used by the backend
step5_jump_test.py   (testing them on new videos: backend/VIDEO_TESTING.md)
api_contract.md      the API contract frontend and backend build against
```

## Status and next steps

HoopScout is a hackathon prototype. Today it has **one real filmed player**, compared with a
**simulated dataset** of 400 kids that has a realistic relative-age and height bias.

Next steps:
- Validate the elbow measurement with an adult shooter, then switch on the shooting-form score.
- Replace the placeholder age-group targets and jump/dribble norms with numbers from coaches
  and official youth norm tables.
- Film more kids to calibrate the skill formulas.
- Progress over time: the data model already stores sessions per kid.

## Team

- **Faris** – backend, video analysis, scoring, AI coach report
- **Imran** – frontend (Talent Board, profiles, coach upload, Bias Check)
