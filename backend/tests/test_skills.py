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


def test_targets_depend_on_age_group():
    from backend.app.scoring import target_check
    # head up 55%: fine for a U10 kid (50-100), too low from U14 up (70-100)
    assert target_check("head_up_pct", 55, "U10")["status"] == "ideal"
    assert target_check("head_up_pct", 55, "U14")["status"] in ("close", "off")
    assert target_check("head_up_pct", 55, "U14")["ideal_min"] == 70
    # weak hand 32%: ideal for U10 (30-60), not for U16 (40-60)
    assert target_check("weak_hand_pct", 32, "U10")["score"] == 100
    assert target_check("weak_hand_pct", 32, "U16")["score"] < 100
    # no age group -> textbook range
    assert target_check("head_up_pct", 55)["ideal_min"] == 70


def test_jump_and_speed_are_percentiles_within_age_and_gender():
    a = example_analyses()
    a["jump"]["best_jump_cm"] = 31
    u10_girl = skills.athleticism(a["jump"], "girl", "U10")
    u14_boy = skills.athleticism(a["jump"], "boy", "U14")
    u18_boy = skills.athleticism(a["jump"], "boy", "U18")
    assert u10_girl > 90                    # 31 cm is excellent for a U10 girl
    assert 45 <= u14_boy <= 55              # about average for a U14 boy
    assert u18_boy < 10                     # well below average for a U18 boy
    # dribble speed: 1.5/s is typical at U10, slow at U18
    d = dict(a["dribbling"], dribbles_per_sec=1.5)
    assert skills.ball_handling(d, "boy", "U10") > skills.ball_handling(d, "boy", "U18")


def test_skill_scores_use_age_group_when_given():
    a = example_analyses()
    young = skills.skill_scores(a, "boy", "U12")
    old = skills.skill_scores(a, "boy", "U18")
    assert young["athleticism"] > old["athleticism"]      # same 33.1 cm jump
    assert young["consistency"] == old["consistency"]     # consistency doesn't depend on age
