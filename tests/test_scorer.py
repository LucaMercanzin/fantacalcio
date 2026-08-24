from ranking.scorer import (
    compute_score, rank_players, compute_player_quality, compute_risk,
    compute_value_for_money, compute_decision_score, enrich_scores,
)


def test_compute_score_uses_fantamedia_when_present():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "ok"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 0


def test_compute_score_falls_back_to_avg_rating():
    row = {"fantamedia": None, "avg_rating": 6.0, "appearances": None, "status": "ok"}
    score = compute_score(row)
    assert score == 6.0 * 10 + 0.5 * 5 - 0


def test_compute_score_penalizes_injured_status():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "infortunato"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 15


def test_rank_players_orders_best_to_worst():
    rows = [
        {"canonical_name": "Low", "fantamedia": 5.0, "avg_rating": None, "appearances": 38, "status": "ok"},
        {"canonical_name": "High", "fantamedia": 8.0, "avg_rating": None, "appearances": 38, "status": "ok"},
    ]

    ranked = rank_players(rows)

    assert [r["canonical_name"] for r in ranked] == ["High", "Low"]
    assert ranked[0]["score"] > ranked[1]["score"]


def test_compute_player_quality_independent_of_price():
    strong_defender = {"avg_rating": 6.5, "fantamedia": 5.5}
    assert compute_player_quality(strong_defender) == 50.0


def test_compute_risk_high_when_injured_and_unreliable():
    row = {"appearances": 5, "status": "infortunato"}
    risk = compute_risk(row)
    assert risk > compute_risk({"appearances": 38, "status": "ok"})


def test_compute_value_for_money_none_without_price():
    assert compute_value_for_money(50.0, None) is None
    assert compute_value_for_money(50.0, 0) is None


def test_compute_value_for_money_higher_for_cheaper_player():
    cheap = compute_value_for_money(50.0, 10)
    expensive = compute_value_for_money(50.0, 40)
    assert cheap > expensive


def test_compute_decision_score_penalizes_risk():
    safe = compute_decision_score(70.0, 20.0, risk=10, confidence=90)
    risky = compute_decision_score(70.0, 20.0, risk=80, confidence=90)
    assert safe > risky


def test_enrich_scores_a_good_but_unaffordable_player_can_score_low_on_value():
    row = {
        "fantamedia": 8.0, "avg_rating": 7.5, "appearances": 38, "status": "ok",
        "price_current": 60, "confidence": 90,
    }
    enriched = enrich_scores(row)

    assert enriched["player_quality"] > 80
    # strong player, but expensive: value-for-money shouldn't also be top-tier
    assert enriched["value_for_money"] < enriched["player_quality"]
