from ranking.scorer import compute_score, rank_players


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
