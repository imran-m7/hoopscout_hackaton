"""Metrics -> skill scores and the ranked / provisional rules (contract sections 1 + 3)."""
import copy

from backend.app import skills
from backend.app.synthetic import example_analyses


def test_example_scores():
    s = skills.skill_scores(example_analyses())
    assert s["consistency"] == 84            # 100 - (2.7*2 + 4.9 + 0.018*300)
    assert s["weak_hand"] == 100             # 50% weak hand = 100 points (capped)
    assert s["court_vision"] == 37           # head up 37%
    assert s["shooting_form"] is None        # elbow is NOT_VALIDATED yet -> no form score
    assert s["athleticism"] == 58            # 33.1 cm between 10 and 50 cm


def test_weak_hand_cap():
    a = example_analyses()
    a["dribbling"]["weak_hand_pct"] = 70
    assert skills.weak_hand(a["dribbling"]) == 100


def test_provisional_rules():
    a = example_analyses()
    assert skills.status_for(a)[0] == "ranked"
    b = copy.deepcopy(a); b["jump"] = None
    assert skills.status_for(b)[:2] == ("provisional", "No jump video yet")
    b = copy.deepcopy(a); b["shooting"]["quality"]["reps"] = 4
    assert skills.status_for(b)[:2] == ("provisional", "Only 4 shots (need 6)")
    b = copy.deepcopy(a); b["dribbling"]["quality"]["tracking_pct"] = 62
    assert skills.status_for(b)[1] == "Dribbling tracking quality 62% (need 70%)"


def test_unvalidated_elbow_is_shown_not_scored():
    t = example_analyses()["shooting"]["targets"][0]
    assert t["metric"] == "avg_elbow_set_deg" and t["value"] == 56
    assert t["score"] is None and t["status"] == "unknown" and "Not checked yet" in t["tip"]


def test_ai_gets_no_unvalidated_or_unranged_numbers():
    from backend.app import report
    a = example_analyses()
    summary = dict(age_group="U16", gender="boy", position="guard", dominant_hand="right", years_playing=2)
    payload = str(report._ai_payload(summary, skills.skill_scores(a), a))
    for banned in ("avg_elbow_set_deg", "avg_knee_min_deg", "avg_follow_through_s", "Elbow angle",
                   "Player One", "KK Example", "Sarajevo"):
        assert banned not in payload, banned


def test_insights_one_per_skill():
    from backend.app import report
    a = example_analyses()
    st, wk = report.insights(skills.skill_scores(a), a)
    for items in (st, wk):
        fam = [report.SKILL_OF[i["metric"]] for i in items]
        assert len(fam) == len(set(fam)), fam
    assert "Court vision score" not in str(wk)          # measured "Head is up only 37%" wins
