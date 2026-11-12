"""
Player store: real players (SQLite) + simulated players (regenerated), fair scores,
ranks, reports and bias data.

Phase 3 replaces the fixed B_AGE / C_SIZE coefficients with a regression per skill + gender.
Phase 4 replaces the rule-based coach report with the AI one (rules stay as fallback).
"""
import threading
from datetime import date
from statistics import mean

from . import config, db, fairness, jobs, report as rep, skills
from .derive import (age_group, age_months, birth_quarter, height_diff_cm, mirwald_offset,
                     rank_group)
from .schemas import SKILL_KEYS
from .scoring import clamp, fair_from, rank_players, round_half_up, target_check, weighted_mean
from .synthetic import EXAMPLE_INPUT, example_analyses, new_record, simulated_players

LOCK = threading.RLock()
PLAYERS: dict = {}   # id -> record

COEFS: dict = {}     # fitted regression slopes {gender: {skill: {"age", "size", "n"}}}


class Busy(Exception):
    pass


# ------------------------------------------------------------------ startup
def start(runner=None):
    """Load real players from SQLite, add the simulated ones, start the job worker.
    runner(job, progress) -> analysis; default = the real video pipeline."""
    with LOCK:
        PLAYERS.clear()
        real = db.load_players()
        if not real:                    # first start: the contract example, so the UI has a real kid
            rec = new_record("p_001", dict(EXAMPLE_INPUT), is_real=True)
            rec["analyses"] = example_analyses()
            _score(rec)
            st, wk = rep.insights(rec["scores"], rec["analyses"])
            rec["coach_report"] = rep.rules_report(rec["scores"], st, wk)
            db.save_player(rec)
            real = [rec]
        for rec in real:
            PLAYERS[rec["id"]] = rec
        for rec in simulated_players():
            PLAYERS.setdefault(rec["id"], rec)
        recompute_all()
    jobs.RUNNER = runner or (_demo_runner if config.DEMO_MODE else _pipeline_runner)
    jobs.ON_DONE = _job_done
    jobs.start()


DEMO_SOURCE = "p_001"     # the kid whose saved results demo mode replays


def _demo_runner(job, progress):
    """DEMO MODE (safety net for the stage): no video processing. Walks through the real
    steps in ~config.DEMO_JOB_SECONDS and returns the saved analysis of DEMO_SOURCE
    (real numbers + real annotated video). /api/health shows demo_mode: true the whole time."""
    import copy
    import time
    from .pipeline_steps import STEPS
    steps = STEPS[job["kind"]]
    for i, step in enumerate(steps):
        progress(int(100 * i / len(steps)) + 1, step)
        time.sleep(config.DEMO_JOB_SECONDS / len(steps))
    src = PLAYERS.get(DEMO_SOURCE, {}).get("analyses", {}).get(job["kind"])
    return copy.deepcopy(src or example_analyses()[job["kind"]])


def _pipeline_runner(job, progress):
    """Real analysis in a separate low-priority process, so the API stays fast meanwhile."""
    from .proc import run_in_process
    rec = PLAYERS[job["player_id"]]
    return run_in_process(dict(rec["input"]), job["kind"], job["upload_path"],
                          f"{job['player_id']}_{job['kind']}", progress)


def _job_done(job, analysis):
    with LOCK:
        rec = PLAYERS[job["player_id"]]
        rec["analyses"][job["kind"]] = analysis
        db.save_player(rec)


def _next_real_id():
    n = 1
    while f"p_{n:03d}" in PLAYERS:
        n += 1
    return f"p_{n:03d}"


# ------------------------------------------------------------------ recompute (fair score + ranks)
def _labels(months, group_avg_months, diff):
    """Breakdown labels. The age step compares the kid with the AVERAGE AGE OF THEIR GROUP
    (a group has two birth years), so the label says months older/younger, not the quarter."""
    gap = round(group_avg_months - months)            # + = younger than the group
    if abs(gap) < 2:
        age_label = "Age close to group average"
    else:
        age_label = f"{abs(gap)} months {'younger' if gap > 0 else 'older'} than group average"
    if abs(diff) < 3:
        size_label = "Height close to age average"
    else:
        size_label = f"{abs(diff):.0f} cm {'above' if diff > 0 else 'below'} age average"
    return age_label, size_label


def recompute_all(today=None):
    """Rebuild every PlayerSummary and re-rank everyone (within gender + age group)."""
    today = today or date.today()
    derived = {}
    for pid, rec in PLAYERS.items():
        inp = rec["input"]
        birth = date.fromisoformat(inp["birth_date"])
        months = age_months(birth, today)
        grp = age_group(birth, today)
        derived[pid] = dict(months=months, group=grp, rank_group=rank_group(inp["gender"], grp),
                            quarter=birth_quarter(birth),
                            diff=height_diff_cm(inp["gender"], months, inp["height_cm"]))
    rows = [dict(rank_group=d["rank_group"], gender=PLAYERS[pid]["input"]["gender"],
                 months=d["months"], diff=d["diff"], scores=PLAYERS[pid]["scores"])
            for pid, d in derived.items()]
    means = fairness.group_means(rows)
    COEFS.clear()
    COEFS.update(fairness.fit(rows))          # regression per skill + gender (Phase 3)

    summaries = []
    for pid, rec in PLAYERS.items():
        inp, d = rec["input"], derived[pid]
        age_adj, size_adj = fairness.adjustments(COEFS, inp["gender"], d["months"], d["diff"],
                                                 means[d["rank_group"]])
        age_label, size_label = _labels(d["months"], means[d["rank_group"]]["months"], d["diff"])
        f = fair_from(rec["scores"], age_adj, size_adj, inp["years_playing"], age_label, size_label)
        base = weighted_mean(rec["scores"])
        # traditional scout: skill PLUS the advantage of being older and taller
        # (= the fair adjustment with the opposite sign, weighted over the measured skills)
        measured = [k for k, v in rec["scores"].items() if v is not None]
        adv = weighted_mean({k: age_adj[k] + size_adj[k] for k in measured}) or 0
        raw = 0 if base is None else round_half_up(clamp(base - adv))
        summaries.append(dict(
            id=pid, is_real=rec["is_real"], name=inp["name"], gender=inp["gender"],
            age_months=d["months"], age_group=d["group"], rank_group=d["rank_group"],
            birth_quarter=d["quarter"], height_cm=inp["height_cm"], height_diff_cm=d["diff"],
            maturity_offset_years=mirwald_offset(inp["gender"], d["months"], inp["height_cm"],
                                                 inp.get("sitting_height_cm"), inp.get("weight_kg")),
            dominant_hand=inp["dominant_hand"], position=inp["position"],
            years_playing=inp["years_playing"], club=inp["club"], town=inp["town"],
            status=rec["status"], provisional_reason=rec["provisional_reason"],
            scores=rec["scores"], fair_scores=f["fair_scores"], experience_bonus=f["experience_bonus"],
            raw_score=raw, fair_score=f["fair_score"], score_margin=rec["score_margin"],
            breakdown=f["breakdown"], photo_url=None))
    rank_players(summaries)
    for s in summaries:
        PLAYERS[s["id"]]["summary"] = s


# ------------------------------------------------------------------ report pieces
def group_average(rank_grp):
    members = [r["summary"] for r in PLAYERS.values()
               if r["summary"]["rank_group"] == rank_grp and r["summary"]["status"] == "ranked"]
    out = {}
    for k in SKILL_KEYS:
        vals = [m["scores"][k] for m in members if m["scores"][k] is not None]
        out[k] = int(round(mean(vals))) if vals else None
    return out


def _with_current_media_urls(analyses):
    """Saved video URLs contain the address the server had at analysis time
    (e.g. http://localhost:8000). Rewrite them to the CURRENT PUBLIC_BASE_URL, so they also
    work from another laptop (http://10.0.87.8:8000)."""
    out = {}
    for kind, a in analyses.items():
        if a and a.get("annotated_video_url") and "/media/" in a["annotated_video_url"]:
            a = dict(a)
            a["annotated_video_url"] = config.PUBLIC_BASE_URL + "/media/" + a["annotated_video_url"].split("/media/", 1)[1]
        out[kind] = a
    return out


def report(pid):
    rec = PLAYERS[pid]
    s = rec["summary"]
    strengths, weaknesses = rep.insights(rec["scores"], rec["analyses"])
    return {"player": s, "group_average": group_average(s["rank_group"]),
            **_with_current_media_urls(rec["analyses"]), "strengths": strengths, "weaknesses": weaknesses,
            "coach_report": rec["coach_report"], "sessions": rec["sessions"]}


# ------------------------------------------------------------------ actions used by the routes
def _refresh_targets(analyses):
    """Re-check every target against the CURRENT config (IDEAL, NOT_VALIDATED), so a config
    change applies at the next /analyze without re-processing the videos."""
    for a in analyses.values():
        if a:
            a["targets"] = [t for t in (target_check(t["metric"], t["value"]) for t in a["targets"]) if t]


def _score(rec):
    """Metrics -> skill scores, status, coach report, session (one session in v1)."""
    _refresh_targets(rec["analyses"])
    rec["scores"] = skills.skill_scores(rec["analyses"])
    rec["status"], rec["provisional_reason"], rec["score_margin"] = skills.status_for(rec["analyses"])


def create_player(inp: dict) -> dict:
    with LOCK:
        pid = _next_real_id()
        rec = new_record(pid, inp, is_real=True)
        PLAYERS[pid] = rec
        db.save_player(rec)
        recompute_all()
        return rec["summary"]


def analyze(pid) -> dict:
    busy = [j for j in jobs.player_jobs(pid) if j["status"] in ("queued", "running")]
    if busy:
        raise Busy(f"{busy[0]['kind'].capitalize()} video is still being analyzed - wait until it is done.")
    with LOCK:
        rec = PLAYERS[pid]
        _score(rec)
        recompute_all()
        targets = {t["metric"]: t["value"] for a in rec["analyses"].values() if a for t in a["targets"]}
        rec["sessions"] = [{"session_id": f"s_{pid[2:]}", "date": date.today().isoformat(),
                            "fair_score": rec["summary"]["fair_score"], "target_values": targets}]
        summary, scores, analyses = dict(rec["summary"]), dict(rec["scores"]), rec["analyses"]
    cr = rep.coach_report(summary, scores, analyses)      # AI (network) outside the lock
    with LOCK:
        rec["coach_report"] = cr
        db.save_player(rec)
        return report(pid)


def regenerate_coach_report(pid) -> dict:
    with LOCK:
        rec = PLAYERS[pid]
        summary, scores, analyses = dict(rec["summary"]), dict(rec["scores"]), rec["analyses"]
    cr = rep.coach_report(summary, scores, analyses)
    with LOCK:
        rec["coach_report"] = cr
        if rec["is_real"]:
            db.save_player(rec)
        return cr


def bias(gender=None, rank_grp=None):
    """
    Never mixes boys and girls or age groups: "top 10" = the top 10 of EACH rank_group,
    using the ranks computed inside that group (raw_rank <= 10 / fair_rank <= 10).
    Optional filters: gender ("boy"/"girl") or one rank_group ("Boys U14").
    """
    everyone = [r["summary"] for r in PLAYERS.values()
                if (gender is None or r["summary"]["gender"] == gender)
                and (rank_grp is None or r["summary"]["rank_group"] == rank_grp)]
    ranked = [p for p in everyone if p["status"] == "ranked"]

    def quarters(players):
        q = [0, 0, 0, 0]
        for p in players:
            q[p["birth_quarter"] - 1] += 1
        return q

    def avg_diff(players):
        return round(mean(p["height_diff_cm"] for p in players), 1) if players else 0.0

    raw10 = [p for p in ranked if p["raw_rank"] <= 10]
    fair10 = [p for p in ranked if p["fair_rank"] <= 10]
    return {
        "birth_quarter": {"all_players": quarters(everyone), "raw_top10": quarters(raw10),
                          "fair_top10": quarters(fair10)},
        "height": {
            "raw_top10_avg_diff_cm": avg_diff(raw10),
            "fair_top10_avg_diff_cm": avg_diff(fair10),
            "points": [{"id": p["id"], "name": p["name"], "height_diff_cm": p["height_diff_cm"],
                        "raw_rank": p["raw_rank"], "fair_rank": p["fair_rank"]} for p in ranked],
        },
        "explanation": (fairness.describe(COEFS) + " "
                        "Counts use the top 10 of each group (same gender and age group). "
                        "A traditional ranking favours kids born early in the year and kids who are "
                        "taller than average, because they are simply further in their growth. "
                        "The fair score compares each kid with what is expected for their age and "
                        "size, so late-born and smaller kids with real skill move up."),
    }
