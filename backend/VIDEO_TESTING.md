# Video analysis: testing the scripts on new videos

Use this to check new videos **before** adding a kid in the app: is the person found, is the ball
tracked, are shots, dribbles and jumps counted correctly? The backend uses the same scripts,
so a fix here is used by the app automatically.

## Step 0 – Setup (once)

Install the backend as described in the main [README](../README.md#run-it-locally)
(Python 3.11–3.13, `pip install -r requirements.txt`). `ultralytics` installs PyTorch, which is a
big download, so do this on good Wi-Fi. The MediaPipe pose model and the YOLO ball model
download automatically the first time.

Open a terminal in the **repo root** (where `step1_convert.py` is) and activate the venv.
Put the raw phone videos in `raw_videos/`; the other folders are created automatically.
All of them are git-ignored, because they contain kids' videos.

```
<repo root>/
├── raw_videos/      <- your phone videos (.MOV / .mp4)
├── videos/          <- converted .mp4 files (step 1 creates this)
├── test_output/     <- annotated videos + CSV (created automatically)
└── step1_convert.py … step5_jump_test.py
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

## Results table

| Kid | Step 2 pose | Step 3 ball % | Dribbles (real / app) | Shots (real / app) | Jumps (real / app) | Jump cm |
|-----|-------------|---------------|-----------------------|--------------------|--------------------|---------|
|     |             |               |                       |                    |                    |         |

If all rows look good, the video analysis works for that kid's videos.

## Notes

- The scripts use the current MediaPipe "Tasks" API (the old `mp.solutions.pose` API was removed).
- Filter defaults (`--max-dist 0.5`, `--max-knee 150`) were tuned on real videos. Only change them with
  evidence from several kids; the backend reads the same defaults from `backend/app/config.py`.
