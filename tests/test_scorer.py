from ranking.scorer import (
    compute_decision_score,
    compute_player_quality,
    compute_risk,
    compute_score,
    compute_value_for_money,
    enrich_scores,
    rank_players,
)


def test_compute_score_uses_fantamedia_when_present():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "ok"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 0


def test_compute_score_returns_none_without_fantamedia():
    # P0-002: fantamedia and avg_rating are not the same scale (for
    # portieri fantamedia < avg_rating, since goals conceded are a malus
    # there but not in avg_rating) — falling back to avg_rating used to
    # silently invert rankings, so a missing fantamedia must not produce a
    # score at all.
    row = {"fantamedia": None, "avg_rating": 6.0, "appearances": None, "status": "ok"}
    assert compute_score(row) is None


def test_compute_score_penalizes_injured_status():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "infortunato"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 15


def test_compute_score_penalizes_unproven_low_appearances():
    # A source-default "neutral" fantamedia (6.0) backed by a single
    # appearance shouldn't outrank a real starter with a genuinely lower
    # but proven average (regression: was ranking above real starters).
    unproven = {"fantamedia": 6.0, "avg_rating": None, "appearances": 1, "status": "ok"}
    proven_starter = {"fantamedia": 5.7, "avg_rating": None, "appearances": 30, "status": "ok"}
    assert compute_score(unproven) < compute_score(proven_starter)


def test_compute_score_unproven_penalty_fades_out_by_threshold():
    at_threshold = {"fantamedia": 6.0, "avg_rating": None, "appearances": 5, "status": "ok"}
    full_season = {"fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok"}
    # no unproven penalty left at the threshold — only the reliability bonus differs
    assert compute_score(at_threshold) == 60.0 + (5 / 38) * 5
    assert compute_score(full_season) == 60.0 + 5.0


def test_rank_players_orders_best_to_worst():
    rows = [
        {"canonical_name": "Low", "fantamedia": 5.0, "avg_rating": None, "appearances": 38, "status": "ok"},
        {"canonical_name": "High", "fantamedia": 8.0, "avg_rating": None, "appearances": 38, "status": "ok"},
    ]

    ranked, insufficient_data = rank_players(rows)

    assert [r["canonical_name"] for r in ranked] == ["High", "Low"]
    assert ranked[0]["score"] > ranked[1]["score"]
    assert insufficient_data == []


def test_rank_players_excludes_missing_fantamedia_from_ranking():
    # P0-002 acceptance criterion: a player with no fantamedia must not be
    # ranked (let alone rank #1) — he's split into insufficient_data instead.
    rows = [
        {"canonical_name": "Real Starter", "fantamedia": 6.36, "avg_rating": 6.36,
         "appearances": 37, "status": "ok"},
        {"canonical_name": "No Fantamedia Reserve", "fantamedia": None, "avg_rating": 6.20,
         "appearances": 5, "status": "ok"},
    ]

    ranked, insufficient_data = rank_players(rows)

    assert [r["canonical_name"] for r in ranked] == ["Real Starter"]
    assert [r["canonical_name"] for r in insufficient_data] == ["No Fantamedia Reserve"]
    assert insufficient_data[0]["score"] is None
    assert insufficient_data[0]["decision_score"] is None


def test_compute_player_quality_independent_of_price():
    strong_defender = {"avg_rating": 6.5, "fantamedia": 5.5}
    assert compute_player_quality(strong_defender) == 50.0


def test_compute_risk_high_when_injured_and_unreliable():
    row = {"appearances": 5, "status": "infortunato"}
    risk = compute_risk(row)
    assert risk > compute_risk({"appearances": 38, "status": "ok"})


def test_compute_risk_unchanged_when_fcp_signals_missing():
    row = {"appearances": 38, "status": "ok"}
    assert compute_risk(row) == compute_risk({"appearances": 38, "status": "ok"})


def test_compute_risk_higher_with_low_fcp_stability():
    base = {"appearances": 38, "status": "ok"}
    low_stability = {
        **base, "investment_stability_pct": 20, "injury_resistance_pct": 20,
    }
    high_stability = {
        **base, "investment_stability_pct": 90, "injury_resistance_pct": 90,
    }
    assert compute_risk(low_stability) > compute_risk(high_stability)
    assert compute_risk(low_stability) > compute_risk(base)


def test_enrich_scores_exposes_alg_fcp_without_affecting_score():
    row = {
        "fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "alg_fcp": 90,
    }
    enriched = enrich_scores(row)
    assert enriched["alg_fcp"] == 90
    assert enriched["score"] == compute_score(row)


def test_compute_value_for_money_none_without_price():
    assert compute_value_for_money(50.0, None) is None
    assert compute_value_for_money(50.0, 0) is None


def test_compute_value_for_money_floors_price_for_minimum_credit_players():
    # A 1-credit bench player and a 5-credit player should score identically
    # on value-for-money — dividing by the raw 1-credit price would make the
    # bench player look like an incredible bargain, which it isn't.
    at_floor = compute_value_for_money(50.0, 1)
    at_min_price = compute_value_for_money(50.0, 5)
    assert at_floor == at_min_price


def test_compute_value_for_money_higher_for_cheaper_player():
    cheap = compute_value_for_money(50.0, 10)
    expensive = compute_value_for_money(50.0, 40)
    assert cheap > expensive


def test_compute_decision_score_penalizes_risk():
    safe = compute_decision_score(70.0, 20.0, risk=10, confidence=90)
    risky = compute_decision_score(70.0, 20.0, risk=80, confidence=90)
    assert safe > risky


def test_rank_players_decision_score_does_not_favor_cheap_fringe_player_over_star():
    # Regression: value_for_money is fantasy_value/price, unbounded and
    # floored at a 5-credit minimum price — a bench player at that floor can
    # score a much higher raw ratio than a genuinely strong, pricier player.
    # Mixed directly into decision_score at a coequal weight, that let the
    # bench player outrank the star — both because the raw ratio is
    # unbounded, and because a percentile (even once bounded to 0-100) always
    # spans the *full* range in any population, so it must be weighted as a
    # smaller adjustment to fantasy_value rather than a coequal term, or the
    # single best-value player in a role would still out-rank a much
    # stronger, pricier one on value alone. Uses a realistic-sized role (not
    # just 2 players) since percentile rank is degenerate at n=2.
    rows = [
        {
            "canonical_name": "Star Player", "fantamedia": 8.5,
            "avg_rating": None, "appearances": 38, "status": "ok",
            "price_current": 55, "confidence": 90,
        },
        {
            "canonical_name": "Cheap Fringe Player", "fantamedia": 5.6,
            "avg_rating": None, "appearances": 38, "status": "ok",
            "price_current": 5, "confidence": 90,
        },
    ]
    filler_fantamedia_price = [
        (6.0, 8), (6.2, 12), (6.4, 15), (6.5, 18), (6.6, 20), (6.8, 22),
        (7.0, 25), (7.0, 28), (7.2, 30), (7.3, 32), (7.4, 35), (6.1, 10),
    ]
    for i, (fantamedia, price) in enumerate(filler_fantamedia_price):
        rows.append({
            "canonical_name": f"Filler{i}", "fantamedia": fantamedia,
            "avg_rating": None, "appearances": 38, "status": "ok",
            "price_current": price, "confidence": 90,
        })

    ranked, _insufficient_data = rank_players(rows)
    by_name = {r["canonical_name"]: r for r in ranked}

    assert by_name["Star Player"]["decision_score"] > by_name["Cheap Fringe Player"]["decision_score"]


def test_enrich_scores_a_good_but_unaffordable_player_can_score_low_on_value():
    row = {
        "fantamedia": 8.0, "avg_rating": 7.5, "appearances": 38, "status": "ok",
        "price_current": 60, "confidence": 90,
    }
    enriched = enrich_scores(row)

    assert enriched["player_quality"] > 80
    # strong player, but expensive: value-for-money shouldn't also be top-tier
    assert enriched["value_for_money"] < enriched["player_quality"]


def test_compute_score_rewards_offensive_tactical_profile_for_defenders():
    base = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "D", "role_mantra": "DC",
    }
    quinto_offensivo = {
        **base, "role_mantra": "E", "season_goals_scored": 4, "season_assists": 5,
    }
    assert compute_score(quinto_offensivo) > compute_score(base)


def test_compute_score_does_not_use_tactical_profile_for_attaccanti():
    base = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "A", "role_mantra": "PC",
    }
    same_but_winger_mantra = {**base, "role_mantra": "W"}
    # role_mantra differs but role_classic "A" isn't nudged by tactical
    # profile in compute_score — attaccanti are scored on fantamedia alone.
    assert compute_score(base) == compute_score(same_but_winger_mantra)


def test_enrich_scores_exposes_tactical_profile_score():
    row = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "C", "role_mantra": "T",
    }
    enriched = enrich_scores(row)
    assert enriched["tactical_profile_score"] is not None
    assert 0 <= enriched["tactical_profile_score"] <= 100


def test_enrich_scores_tactical_profile_score_none_for_portieri():
    row = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "P", "role_mantra": "POR",
    }
    assert enrich_scores(row)["tactical_profile_score"] is None
