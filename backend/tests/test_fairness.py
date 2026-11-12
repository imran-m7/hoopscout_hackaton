"""
Fairness rules that must keep holding in every phase:
  1. Age counts in MONTHS: a kid born in January and one born in December of the
     same year are not treated the same.
  2. Boys and girls are never mixed (ranks, group averages, bias data).
Run from the repo root:  python -m pytest backend/tests -q
"""
from datetime import date

from backend.app import store as s
from backend.app.synthetic import new_record, simulated_players
from backend.app.derive import age_months, avg_height_cm

BASE = dict(height_cm=165, weight_kg=None, sitting_height_cm=None, dominant_hand="right",
            position="guard", years_playing=2, club="X", town="Y")
TWINS = {  # identical skills and height, only birth month and gender differ
    "t_jan_boy": ("boy", "2012-01-15"), "t_dec_boy": ("boy", "2012-12-15"),
    "t_jan_girl": ("girl", "2012-01-15"), "t_dec_girl": ("girl", "2012-12-15"),
}


def _seed_with_twins(average_height=True):
    """average_height: each twin is exactly average height for their age, so only age differs."""
    s.PLAYERS.clear()
    for rec in simulated_players():
        s.PLAYERS[rec["id"]] = rec
    for pid, (gender, birth) in TWINS.items():
        inp = dict(BASE, name=pid, gender=gender, birth_date=birth)
        if average_height:
            months = age_months(date.fromisoformat(birth))
            inp["height_cm"] = round(avg_height_cm(gender, months), 1)
        r = new_record(pid, inp, True)
        r["scores"] = {"shooting_form": 74, "consistency": 84, "ball_handling": 66, "weak_hand": 100, "court_vision": 37, "athleticism": 58}
        r["status"], r["provisional_reason"] = "ranked", None
        s.PLAYERS[pid] = r
    s.recompute_all()
    return {pid: s.PLAYERS[pid]["summary"] for pid in TWINS}


def test_birth_month_matters():
    t = _seed_with_twins()
    for g in ("boy", "girl"):
        jan, dec = t[f"t_jan_{g}"], t[f"t_dec_{g}"]
        assert jan["rank_group"] == dec["rank_group"]              # same birth year -> same group
        assert jan["age_months"] - dec["age_months"] == 11         # ...but 11 months apart
        assert (jan["birth_quarter"], dec["birth_quarter"]) == (1, 4)
        assert dec["fair_score"] > jan["fair_score"]               # younger -> fair score corrects up
        assert dec["fair_rank"] < jan["fair_rank"]
        assert dec["breakdown"][1]["value"] > jan["breakdown"][1]["value"]   # age step


def test_same_height_judged_by_age_in_months():
    t = _seed_with_twins(average_height=False)       # all four are 165 cm
    assert t["t_dec_boy"]["height_diff_cm"] > t["t_jan_boy"]["height_diff_cm"]   # taller for a younger kid


def test_boys_and_girls_never_mixed():
    t = _seed_with_twins(average_height=False)
    players = [r["summary"] for r in s.PLAYERS.values()]
    groups = {}
    for p in players:
        groups.setdefault(p["rank_group"], set()).add(p["gender"])
    assert all(len(g) == 1 for g in groups.values())
    assert t["t_jan_boy"]["rank_group"] == "Boys U16" and t["t_jan_girl"]["rank_group"] == "Girls U16"
    # same height is judged against the gender's own average
    assert t["t_jan_boy"]["height_diff_cm"] != t["t_jan_girl"]["height_diff_cm"]
    # ranks 1..n inside every group, no gaps or duplicates
    for g in groups:
        ranks = sorted(p["fair_rank"] for p in players if p["rank_group"] == g and p["fair_rank"])
        assert ranks == list(range(1, len(ranks) + 1))
    # bias data: top 10 is taken inside each group, never across genders
    girls = s.bias(gender="girl")
    assert all(p["id"] in {q["id"] for q in players if q["gender"] == "girl"}
               for p in girls["height"]["points"])
    one = s.bias(rank_grp="Girls U16")
    assert sum(one["birth_quarter"]["raw_top10"]) == 10


def test_regression_learns_the_bias_per_gender():
    """The simulated kids have +0.30 points/month and +0.40 points/cm built in.
    The regression must find a clearly positive effect, separately for boys and girls."""
    from backend.app import fairness
    _seed_with_twins()
    for gender in ("boy", "girl"):
        c = s.COEFS[gender]
        assert all(v["n"] >= 190 and not v["fallback"] for v in c.values())
        avg_age = sum(v["age"] for v in c.values()) / len(c)
        avg_size = sum(v["size"] for v in c.values()) / len(c)
        assert 0.15 < avg_age < 0.7, avg_age
        assert 0.15 < avg_size < 0.7, avg_size
    assert "For boys" in fairness.describe(s.COEFS) and "For girls" in fairness.describe(s.COEFS)


def test_fallback_when_too_few_kids():
    from backend.app import fairness
    rows = [dict(rank_group="Boys U14", gender="boy", months=150 + i, diff=0.0,
                 scores={"consistency": 50 + i}) for i in range(5)]
    c = fairness.fit(rows)["boy"]["consistency"]
    assert c["fallback"] and c["age"] == fairness.FALLBACK["age"]
