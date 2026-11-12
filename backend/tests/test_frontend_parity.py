"""The frontend re-ranks the board with the scout's weight sliders. With the DEFAULT weights,
its result must equal the API exactly. This test does what the frontend does (JS rules)."""
import math

from backend.app import store
from backend.app.config import WEIGHTS
from backend.app.scoring import fair_from, round_half_up
from backend.app.synthetic import simulated_players


def js_round(x):                      # JavaScript Math.round
    return math.floor(x + 0.5)


def frontend_fair_score(p, weights):
    num = den = 0.0
    for k, w in weights.items():
        v = p["fair_scores"][k]
        if v is not None:              # skip skills with no score (null)
            num += w * v
            den += w
    return js_round(num / den + p["experience_bonus"]) if den else 0


def frontend_ranks(players, key):
    ranks = {}
    groups = {}
    for p in players:
        if p["status"] == "ranked":    # provisional players are not ranked
            groups.setdefault(p["rank_group"], []).append(p)
    for members in groups.values():
        members.sort(key=lambda p: (-key(p), p["id"]))   # ties: lower id first
        for i, p in enumerate(members, start=1):
            ranks[p["id"]] = i
    return ranks


def test_half_rounds_up_like_js():
    assert round_half_up(70.5) == 71 and round_half_up(71.5) == 72 and round(70.5) == 70


def test_board_matches_api_with_default_weights():
    store.PLAYERS.clear()
    for rec in simulated_players():
        store.PLAYERS[rec["id"]] = rec
    store.PLAYERS["p_100"]["scores"]["shooting_form"] = None    # a kid with a missing skill
    store.recompute_all()
    players = [r["summary"] for r in store.PLAYERS.values()]
    for p in players:
        assert frontend_fair_score(p, WEIGHTS) == p["fair_score"], p["id"]
    ranks = frontend_ranks(players, lambda p: frontend_fair_score(p, WEIGHTS))
    for p in players:
        assert ranks.get(p["id"]) == p["fair_rank"], p["id"]


def test_exact_half_case():
    """Consistency missing + 2 skills left: (70 + 71) / 2 = 70.5 -> must be 71 on both sides."""
    scores = {"shooting_form": None, "consistency": None, "ball_handling": 70,
              "weak_hand": 71, "court_vision": None, "athleticism": None}
    f = fair_from(scores, {}, {}, 10, "age", "size")     # 10 years playing -> bonus 0
    assert f["fair_score"] == 71 == js_round(70.5)
    assert sum(step["value"] for step in f["breakdown"]) == 71
