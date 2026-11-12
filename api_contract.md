# HoopScout API contract (v3)

The frontend (Lovable, React + TypeScript) and the backend (Python, FastAPI) both build against this file. Change it only when both people agree, then bump the version above.

A coach enters a kid's bio and uploads 3 videos. The app measures their skills, writes an AI report with strengths, weaknesses and drills, and places the kid on a fair Talent Board where scouts can filter, find hidden gems, and view each kid's profile, videos and AI summary.

## What changed since v2

Agreed by Faris (backend) and Imran (frontend).

1. **Age group by birth year**, not exact age: `U14` = turns 12 or 13 this calendar year. A Q4 birthday is the youngest in its group.
2. **Fair adjustment is measured against the kid's own rank group** (same gender + age group), not against all kids of that gender. The regression is still fitted per gender on all age groups together. Height uses `height_diff_cm`.
3. **Bias Check "top 10" = the top 10 of EACH rank group**, never across genders or age groups. New optional filters `?gender=` and `?rank_group=`.
4. **AI model** is `"gpt-oss-120b (Groq)"` (Groq removed Llama 3.3).
5. **`status: "close"`** = within 15% of the nearest edge of the ideal range.
6. **`raw_score`** = skill average plus the advantage of being older/taller (the fair adjustment with the opposite sign).
7. **Rounding** is half-up (JavaScript `Math.round`) everywhere; **ties** in ranks go to the lower `id`.
8. **Unvalidated measurements**: a target can be shown with `status: "unknown"` and `score: null` ("Not checked yet"). Right now the elbow at set point is unvalidated, so `scores.shooting_form` is `null` for real kids.
9. **💎 and rank change with sliders**: the API values are for the default weights; the frontend recomputes them only after a scout moves a slider (see 3.).
10. **Analyze returns 409** while a video is still being analyzed. **Demo mode** is defined (see Demo mode).

## Conventions

- Base URL: `http://localhost:8000` (frontend reads it from `VITE_API_URL`)
- JSON only, with snake_case field names
- An unknown or unmeasured value is `null`, never `NaN`. Show it as "not measured yet", never as 0.
- Dates use `YYYY-MM-DD`. Angles are in degrees, heights in cm, times in seconds unless a name says `_ms`.
- Scores are integers 0–100. Rounding is half-up (`Math.round`).
- Video files are served as static files under `/media/...`, and their URLs are absolute (they may end with `?v=...` to bust the browser cache). They are H.264 MP4 and play in a plain `<video>` tag.
- CORS allows `http://localhost:5173` and `http://localhost:8080`.
- Errors: `{ "error": "human readable message" }` with HTTP status 4xx or 5xx. Show the text.

| Status | Meaning |
|---|---|
| 400 | Wrong file type, empty file, or a simulated player (they can't get videos) |
| 404 | Unknown player or job |
| 409 | Analyze called while a video is still being analyzed |
| 422 | Invalid input; the message names the field |
| 500 | Server error |

## Privacy rules (both sides)

- **Never returned by the API:** home address, phone, email, weight, sitting height, birth date. Weight and sitting height are accepted on input and used only inside the calculations.
- **Location:** only town and club are shown.
- **Contact:** scouts contact a kid through the club or parents. The UI has a "Contact via club" button and never shows a direct contact.
- **Storage:** videos and data stay local, in the `data/` folder plus SQLite. Nothing is posted online, and `data/` is git-ignored.
- **The AI never sees video, only measured numbers.** It never gets the name, club, town, birth date or weight either.
- **Synthetic players** are always `is_real: false` and labelled "Simulated" in the UI.
- **The player card shows the age group**, not the birth date.

## How scoring works (backend logic, documented so judges and frontend agree)

### 1. Metrics → skill scores (0–100, direction-aware)

| Skill | Built from | Direction |
|---|---|---|
| shooting_form | elbow at set, knee bend, leg–arm timing, follow-through | distance from the textbook ideal range |
| consistency | shot-to-shot spread of elbow, knee, release height | lower spread is better: `100 - (2·sd_elbow + sd_knee + 300·sd_release)` |
| ball_handling | dribbles/sec (0.5–3.0 → 0–100), ball below hip %, rhythm | higher is better (average of the three) |
| weak_hand | weak hand % of dribbles | higher is better, capped at 50% (50% = 100 points) |
| court_vision | head up % while dribbling | higher is better |
| athleticism | best jump (10–50 cm → 0–100) | higher is better |

These are draft formulas (`backend/app/skills.py`), calibrated so far on one real kid.

There are no made/missed shots. The shooting score is form plus consistency only: "skill, not luck on the day".

**How `shooting_form` is scored:** against the textbook ideal (development goal). Ideal ranges live in one config file (`backend/app/config.py`, `IDEAL`). Each analysis returns them as `targets` (`TargetCheck[]`): value, ideal range, score, status and a short tip. The profile draws one bar per target, and `sessions[].target_values` keeps the history.

- Score = 100 inside the ideal range, then a linear drop to 0 at the end of the scale.
- `status`: `ideal` inside the range; `close` within 15% of the nearest edge; `off` further away; `unknown` when there is no value **or the measurement is not validated yet**.
- Ranges still missing (knee bend, leg–arm timing, follow-through) must come from a coach or a coaching source, so they are not returned yet. The dribbling ranges (head up 70–100%, ball below hip 80–100%, weak hand 40–60%) are placeholders until a coach confirms them.
- **Unvalidated measurements** (`config.NOT_VALIDATED`, now: elbow at set): shown with `status: "unknown"`, `score: null` and the tip "Not checked yet…". Never scored, never sent to the AI. **Why:** a kid with good, consistent form measured ~56° against the textbook 80–100°. Test: film one adult who shoots well and run step 4. About 85–95° means the measurement is right (remove it from `NOT_VALIDATED`); about 60° means fix the set-point detection first.

Fairness is kept by the fair score, not the form score: kids see the honest gap to the ideal, but aren't ranked down for being young.

Sanity limits (elbow 30–170°, knee 60–175°): values outside them are flagged as tracking errors and not scored.

**Shooting weight:** consistency counts more than form. Default weights: consistency 1.5, all others 1.

### 2. Fair score = skill compared with what's expected for that kid

For each skill k and each gender, a linear regression learns how many points a kid usually gains per month older (`b_k`) and per cm taller than the age average (`c_k`) **than the others in their own rank group**. It is fitted on all kids of that gender (all age groups together, so ~200 kids gives a stable fit). Slopes are clamped to ≥ 0: we only remove an advantage, we never penalise being young or small. With fewer than 20 kids, fallback slopes are used (0.30 per month, 0.40 per cm).

```
fair_k     = clamp(skill_k + age_adj_k + size_adj_k, 0, 100)
age_adj_k  = b_k * (group_avg_age_months   - age_months)       # younger than the group → +
size_adj_k = c_k * (group_avg_height_diff  - height_diff_cm)   # smaller for their age → +

fair_score = round( Σ w_k · fair_k / Σ w_k  +  experience_bonus )   # skip null skills in BOTH sums
experience_bonus = +4 for ≤1 year playing, +2 for 2–3 years, 0 for 4+

raw_score  = round( Σ w_k · skill_k / Σ w_k  -  Σ w_k · (age_adj_k + size_adj_k) / Σ w_k )
```

`height_diff_cm` = height minus the average height for that gender and exact age in months (approximate 50th-percentile table in `config.HEIGHT_REF`; replace with an official WHO/CDC table). The Mirwald `maturity_offset_years` is computed when sitting height and weight are given, but not used in the regression yet (the dataset has no sitting heights).

`raw_score` mimics a traditional scout: skill plus a bonus for being older and taller. The frontend never recomputes it.

`breakdown` ("why this rank") always sums exactly to `fair_score`: Skill score + age step + size step + experience.

The Bias Check `explanation` quotes the learned numbers, e.g. "For boys, being a year older than the group average adds about 6 points…".

### 3. Ranks, confidence, hidden gems

- **Ranks** are computed within the same `rank_group` (e.g. "Boys U14"), only for `status: "ranked"`. Sort high → low; **ties go to the lower `id`**.
- **Provisional** (`status: "provisional"`, ranks `null`) when a video is missing, or there are fewer than 6 shots, 20 s of dribbling or 3 jumps, or tracking quality is below 70%. `provisional_reason` says why, e.g. "No jump video yet", "Only 4 shots (need 6)".
- **Uncertainty:** `score_margin` starts at 3 and grows by 1 for each video with few reps (< 1.5 × minimum) or tracking < 90%; provisional = 10. Shown as `76 ± 5`.
- **💎 Hidden gem:** `fair_rank` at least 5 places better than `raw_rank` (`rank_change = raw_rank - fair_rank ≥ 5`) **and** `fair_rank ≤ ceil(0.25 × ranked players in the group)`.
- **Sanity flags:** impossible values (jump > 70 cm, more than 5 dribbles/sec, elbow < 30° or > 170°) are flagged and excluded from scoring.

**Frontend re-ranking (weight sliders).** With the default weights the frontend uses the API values unchanged; a backend test checks that the frontend formula gives exactly the API's `fair_score` and `fair_rank`. After a scout moves a slider, the frontend recomputes, per rank group:

```ts
function fairScore(p: PlayerSummary, w: Record<SkillKey, number>): number {
  let num = 0, den = 0;
  for (const k of Object.keys(w) as SkillKey[]) {
    const v = p.fair_scores[k];
    if (v === null) continue;            // skip null skills in BOTH sums
    num += w[k] * v; den += w[k];
  }
  return den ? Math.round(num / den + p.experience_bonus) : 0;
}
```

then `fair_rank` (rule above), `rank_change = raw_rank - fair_rank` (using the API's `raw_rank`), and 💎 with the same rule. `raw_score`, `raw_rank` and `score_margin` always come from the API.

## Video pipeline (backend): works for any kid's video

Each upload goes through the tested scripts, in a separate low-priority process (the API stays fast meanwhile, ~60 ms for `/api/players`). One video is analyzed at a time; the others wait in the queue.

| Upload | Scripts | Inputs taken from the profile |
|---|---|---|
| any | step1_convert first: any .mov/.mp4/.m4v/.avi, fixes rotation, max 1280 px, max 60 fps | — |
| shooting | step2 (pose check) + step4 | `--hand` = dominant_hand |
| dribbling | step2 + step3 | dominant_hand decides which hand is the weak hand |
| jump | step2 + step5 | `--height` = height_cm |

- **No upload size limit.** Phone videos are often 100–300 MB.
- **Processing time** on a normal laptop: shooting ~10 min, dribbling ~7 min, jump ~1–2 min.
- **Every kid is checked automatically.** step2's visibility and body-size check feeds `quality`, and its camera hints ("Player too small → move camera closer") come back as `flags`. If the kid is too small, joints are hidden or the ball is lost, the kid is provisional instead of getting wrong scores. If the player is found in under 30% of the video, the job fails with a message for the coach.
- **Ball tracking fallback:** if the ball is found in < 40% of frames, dribbles are counted from the wrists, the ball-based numbers are `null`, and a flag says so.
- **Built-in filters tested on real videos:** background objects mistaken for the ball (`--max-dist 0.5`), pass catches counted as shots (`--max-knee 150`, with skipped moments listed), standing read as jumping (local floor level). Keep these defaults and only tune them with evidence from several kids.
- **Filming side:** a left-handed shooter must be filmed from their left. The coach upload screen reminds them of this based on `dominant_hand`.

## Demo mode

Safety net for the stage. Started with `DEMO_MODE=true`:

- `GET /api/health` returns `"demo_mode": true`, and the UI shows the "Demo mode" badge.
- Uploads skip the analysis: the job walks through the real step names in ~10 s and then uses the saved real analysis of `p_001` (real numbers and real annotated videos).
- Everything else (players, ranks, AI report, bias) works normally.

Frontend rule: once the real backend has answered once, never switch to frontend mocks; treat a slow answer as "try again", not "backend down".

## Endpoints

| Method | Path | Purpose | Used by |
|---|---|---|---|
| GET | `/api/health` | `{ "ok": true, "demo_mode": false }` | all screens (shows the "Demo mode" badge) |
| GET | `/api/players` | All players → `PlayerSummary[]` | Talent Board, Compare, Bias |
| GET | `/api/players/{id}` | Full profile → `PlayerReport` | Player Profile |
| POST | `/api/players` | Create a kid, body `PlayerInput` → `PlayerSummary` (201) | Coach upload |
| POST | `/api/players/{id}/videos` | multipart: `kind` (shooting \| dribbling \| jump) + `file` → `Job` (202) | Coach upload |
| GET | `/api/jobs/{job_id}` | Poll analysis progress every 2 s → `Job` | Coach upload |
| POST | `/api/players/{id}/analyze` | After the jobs finish: compute scores, re-rank everyone, write the coach report → `PlayerReport` (409 if a job is still running; ~8 s because of the AI) | Coach upload ("Analyze and create report") |
| POST | `/api/players/{id}/coach-report` | Regenerate only the AI coach report → `CoachReport` (~8 s) | Player Profile |
| GET | `/api/bias` | Bias Check data → `BiasData`. Optional `?gender=boy\|girl` or `?rank_group=Boys U14` | Bias Check |

Job `step` values: "Waiting in queue", "Converting video", "Detecting pose", "Tracking ball", "Counting dribbles", "Finding shots", "Finding jumps", "Drawing video", "Saving results", "Done".

**Frontend-only (no API):** the role picker (Coach or Scout); the shortlist ⭐ and private scout notes (localStorage, per device); filters, sorting, weight sliders and Compare.

**Age group preview on the coach form:** `years = currentYear - birthYear`; `< 10` → U10, `< 12` → U12, `< 14` → U14, `< 16` → U16, else U18 (same as the backend).

## Types

```ts
type Gender = "boy" | "girl";
type AgeGroup = "U10" | "U12" | "U14" | "U16" | "U18";
type Hand = "right" | "left";
type Position = "guard" | "forward" | "center";
type SkillKey = "shooting_form" | "consistency" | "ball_handling" | "weak_hand" | "court_vision" | "athleticism";

interface PlayerInput {
  name: string;
  gender: Gender;
  birth_date: string;                // "2013-09-14", never returned (only age / age group)
  height_cm: number;                 // 80-230
  weight_kg?: number | null;         // private: calculations only, never returned
  sitting_height_cm?: number | null; // private: optional, for Mirwald maturity
  dominant_hand: Hand;
  position: Position;
  years_playing: number;             // 0-20
  club: string;
  town: string;
}

type SkillScores = Record<SkillKey, number | null>;   // 0-100, null = not measured yet

interface BreakdownStep {
  label: string;     // "Skill score", "Born late in the year (Q4)", "6 cm below age average", "2 years of experience"
  value: number;     // first step = base score, the rest are + / - adjustments; sums to fair_score
}

interface PlayerSummary {
  id: string;                      // "p_001"
  is_real: boolean;                // true = filmed, false = simulated
  name: string;
  gender: Gender;
  age_months: number;
  age_group: AgeGroup;             // by birth year
  rank_group: string;              // "Boys U14": ranks only compare within this group
  birth_quarter: 1 | 2 | 3 | 4;
  height_cm: number;
  height_diff_cm: number;          // vs average for exact age (months) + gender (+ = taller)
  maturity_offset_years: number | null;  // Mirwald, null if not measured
  dominant_hand: Hand;
  position: Position;
  years_playing: number;
  club: string;
  town: string;

  status: "ranked" | "provisional";
  provisional_reason: string | null;     // "Only 4 shots (need 6)"
  scores: SkillScores;             // measured skill
  fair_scores: SkillScores;        // adjusted for age + size (see scoring)
  experience_bonus: number;
  raw_score: number;               // traditional scout view (API only)
  fair_score: number;              // default weights
  score_margin: number;            // ± for fair_score
  raw_rank: number | null;         // within rank_group, 1 = best, null if provisional
  fair_rank: number | null;
  rank_change: number | null;      // raw_rank - fair_rank (+ = moved up)
  hidden_gem: boolean;             // for the default weights
  breakdown: BreakdownStep[];      // "why this rank": sums to fair_score
  photo_url: string | null;
}

interface QualityInfo {
  tracking_pct: number | null;     // % of frames where body (and ball) was detected
  reps: number | null;             // shots / jumps counted, or seconds of dribbling
  min_reps: number;                // 6 shots / 20 s / 3 jumps
  ok: boolean;
}

interface SanityFlag { metric: string; value: number; message: string; }
// "Jump 2: air time (30 cm) and hip rise (42 cm) disagree - check the video."
// metric "video" = camera hint from step 2, e.g. "Player too small -> move camera closer"

interface TargetCheck {            // development: kid's value vs the textbook ideal
  metric: string;                  // "avg_elbow_set_deg"
  label: string;                   // "Elbow angle at set point"
  value: number | null;            // 55.7
  unit: string;                    // "°", "cm", "ms", "%", "s"
  ideal_min: number;               // 80   (from the backend IDEAL config)
  ideal_max: number;               // 100
  scale_min: number;               // 30   (ends of the bar drawn in the UI)
  scale_max: number;               // 140
  score: number | null;            // 0-100, 100 = inside the ideal range; null = unknown
  status: "ideal" | "close" | "off" | "unknown";   // close = within 15% of the nearest edge
  tip: string;                     // for unknown: "Not checked yet: ..."
}

interface Shot {
  index: number;                   // 1-based
  time_s: number;                  // release moment in the video
  elbow_set_deg: number | null;
  knee_min_deg: number | null;
  release_height_ratio: number | null;   // release height / body height
  leg_arm_timing_ms: number | null;      // + = arm releases after legs extend
  follow_through_s: number | null;
}

interface ShootingAnalysis {
  shots: Shot[];
  skipped: { time_s: number; reason: string }[];  // e.g. catching a pass
  avg_elbow_set_deg: number | null;
  avg_knee_min_deg: number | null;
  avg_release_height_ratio: number | null;
  avg_leg_arm_timing_ms: number | null;
  avg_follow_through_s: number | null;
  spread_elbow_deg: number | null;
  spread_knee_deg: number | null;
  spread_release: number | null;
  targets: TargetCheck[];          // elbow (unknown for now); knee, timing, follow-through once sourced
  quality: QualityInfo;
  flags: SanityFlag[];
  annotated_video_url: string | null;
}

interface DribblingAnalysis {
  duration_s: number | null;
  dribbles: number | null;
  dribbles_per_sec: number | null;
  rhythm_score: number | null;     // 0-100
  ball_below_hip_pct: number | null;
  ball_below_knee_pct: number | null;
  left_hand_pct: number | null;
  right_hand_pct: number | null;
  weak_hand_pct: number | null;    // non-dominant hand
  head_up_pct: number | null;
  targets: TargetCheck[];          // head up %, ball below hip %, weak hand %
  quality: QualityInfo;
  flags: SanityFlag[];
  annotated_video_url: string | null;
}

interface JumpAnalysis {
  jumps: { index: number; air_time_s: number; height_cm: number }[];
  best_jump_cm: number | null;
  avg_jump_cm: number | null;
  targets: TargetCheck[];          // empty: jump has no textbook ideal, only a score
  quality: QualityInfo;
  flags: SanityFlag[];
  annotated_video_url: string | null;
}

interface Insight { title: string; detail: string; metric: string | null; }
// max 3 strengths + 3 weaknesses, one per skill, with real numbers when measured

interface Drill { name: string; description: string; dose: string; }
// dose: "3 x 50 reps, 4 days this week". Every drill can be done alone (ball, hoop, wall).

interface CoachReport {
  source: "ai" | "rules";          // "rules" when there is no key, no Wi-Fi, or a bad AI answer
  model: string | null;            // "gpt-oss-120b (Groq)"
  summary: string;                 // 3-5 sentences, plain language, only explains measured numbers
  drills: Drill[];                 // exactly 3, for this week
  generated_at: string;            // ISO datetime
}

interface SessionSummary {
  session_id: string;
  date: string;
  fair_score: number | null;
  target_values: Record<string, number | null>;   // metric -> value in that session
}

interface PlayerReport {
  player: PlayerSummary;
  group_average: SkillScores;      // same rank_group (ranked players), for the radar comparison
  shooting: ShootingAnalysis | null;   // null = video not uploaded yet
  dribbling: DribblingAnalysis | null;
  jump: JumpAnalysis | null;
  strengths: Insight[];            // rule-based, always present
  weaknesses: Insight[];           // "things to improve"
  coach_report: CoachReport | null;
  sessions: SessionSummary[];      // v1 has one; designed for progress over time later
}

interface Job {
  job_id: string;
  player_id: string;
  kind: "shooting" | "dribbling" | "jump";
  status: "queued" | "running" | "done" | "failed";
  progress: number;                // 0-100
  step: string;                    // see the step list above
  error: string | null;            // for failed: what the coach should change
}

interface BiasData {
  birth_quarter: {
    all_players: [number, number, number, number];   // Q1..Q4 counts
    raw_top10: [number, number, number, number];     // top 10 of EACH rank group, summed
    fair_top10: [number, number, number, number];
  };
  height: {
    raw_top10_avg_diff_cm: number;
    fair_top10_avg_diff_cm: number;
    points: { id: string; name: string; height_diff_cm: number;
              raw_rank: number; fair_rank: number }[];   // ranked players; ranks are within their group
  };
  explanation: string;             // includes the learned "a year older adds ~X points"
}
```

## Example: `GET /api/players/p_001` (shortened; real test numbers under a placeholder name)

```json
{
  "player": {
    "id": "p_001", "is_real": true, "name": "Player One", "gender": "boy",
    "age_months": 169, "age_group": "U16", "rank_group": "Boys U16", "birth_quarter": 4,
    "height_cm": 165, "height_diff_cm": 1.5, "maturity_offset_years": null,
    "dominant_hand": "right", "position": "guard", "years_playing": 2,
    "club": "KK Example", "town": "Sarajevo",
    "status": "ranked", "provisional_reason": null,
    "scores":      { "shooting_form": null, "consistency": 84, "ball_handling": 61,
                     "weak_hand": 100, "court_vision": 38, "athleticism": 60 },
    "fair_scores": { "shooting_form": null, "consistency": 88, "ball_handling": 67,
                     "weak_hand": 100, "court_vision": 43, "athleticism": 65 },
    "experience_bonus": 2,
    "raw_score": 65, "fair_score": 76, "score_margin": 5,
    "raw_rank": 12, "fair_rank": 2, "rank_change": 10, "hidden_gem": true,
    "breakdown": [
      { "label": "Skill score", "value": 70 },
      { "label": "Born late in the year (Q4)", "value": 5 },
      { "label": "Height close to age average", "value": -1 },
      { "label": "2 years of experience", "value": 2 }
    ],
    "photo_url": null
  },
  "group_average": { "shooting_form": 58, "consistency": 61, "ball_handling": 60,
                     "weak_hand": 58, "court_vision": 58, "athleticism": 56 },
  "shooting": {
    "shots": [ { "index": 1, "time_s": 2.3, "elbow_set_deg": 59.2, "knee_min_deg": 120.8,
                 "release_height_ratio": 1.166, "leg_arm_timing_ms": 167, "follow_through_s": 0.53 } ],
    "skipped": [ { "time_s": 27.89, "reason": "no knee bend (167 deg) - catch/pass/rebound?" } ],
    "avg_elbow_set_deg": 55.7, "avg_knee_min_deg": 107.2, "avg_release_height_ratio": 1.204,
    "avg_leg_arm_timing_ms": 114, "avg_follow_through_s": 0.58,
    "spread_elbow_deg": 2.4, "spread_knee_deg": 5.4, "spread_release": 0.018,
    "targets": [
      { "metric": "avg_elbow_set_deg", "label": "Elbow angle at set point",
        "value": 55.7, "unit": "°", "ideal_min": 80, "ideal_max": 100,
        "scale_min": 30, "scale_max": 140, "score": null, "status": "unknown",
        "tip": "Not checked yet: we are still validating this measurement, so it is not scored." }
    ],
    "quality": { "tracking_pct": 100, "reps": 10, "min_reps": 6, "ok": true },
    "flags": [],
    "annotated_video_url": "http://localhost:8000/media/p_001_shooting.mp4?v=1794478493"
  },
  "dribbling": {
    "duration_s": 29.9, "dribbles": 59, "dribbles_per_sec": 1.97, "rhythm_score": 36,
    "ball_below_hip_pct": 88, "ball_below_knee_pct": 2,
    "left_hand_pct": 50, "right_hand_pct": 50, "weak_hand_pct": 50, "head_up_pct": 38,
    "targets": [
      { "metric": "head_up_pct", "label": "Head up while dribbling", "value": 38, "unit": "%",
        "ideal_min": 70, "ideal_max": 100, "scale_min": 0, "scale_max": 100,
        "score": 54, "status": "off", "tip": "Look at the rim or the coach, not the ball." }
    ],
    "quality": { "tracking_pct": 98, "reps": 29.4, "min_reps": 20, "ok": true },
    "flags": [],
    "annotated_video_url": "http://localhost:8000/media/p_001_dribbling.mp4?v=1794478923"
  },
  "jump": {
    "jumps": [ { "index": 1, "air_time_s": 0.5, "height_cm": 31.7 } ],
    "best_jump_cm": 34.1, "avg_jump_cm": 31.3, "targets": [],
    "quality": { "tracking_pct": 100, "reps": 4, "min_reps": 3, "ok": true },
    "flags": [],
    "annotated_video_url": "http://localhost:8000/media/p_001_jump.mp4?v=1794479030"
  },
  "strengths": [ { "title": "Very consistent release",
                   "detail": "Release height varies only 1.5% between shots.",
                   "metric": "spread_release" } ],
  "weaknesses": [ { "title": "Eyes on the ball",
                    "detail": "Head is up only 38% of the time while dribbling.",
                    "metric": "head_up_pct" } ],
  "coach_report": {
    "source": "ai", "model": "gpt-oss-120b (Groq)",
    "summary": "Great job! Your weak-hand dribbling is top-notch, and your shooting consistency is solid...",
    "drills": [ { "name": "Head-Up Walking Dribble",
                  "description": "Walk the length of the court while dribbling, keeping your eyes up and not looking at the ball.",
                  "dose": "2 laps x 5 reps, 3 days" } ],
    "generated_at": "2026-11-12T10:25:53Z"
  },
  "sessions": [ { "session_id": "s_001", "date": "2026-11-12", "fair_score": 76,
                  "target_values": { "avg_elbow_set_deg": 55.7, "head_up_pct": 38,
                                     "ball_below_hip_pct": 88, "weak_hand_pct": 50 } } ]
}
```

The skill formulas are drafts calibrated on one real kid; field names are stable, values may still change.
