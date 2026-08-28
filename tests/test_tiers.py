from ranking.tiers import (
    BASSO_PREZZO,
    DA_EVITARE,
    SCOMMESSA,
    SEMI_TOP,
    TITOLARE_FISSO,
    TOP,
    classify_role,
)


def _player(name, score, risk=20.0, appearances=30, price=20, decision_score=60.0,
            vfm_pct=50.0, status="ok", is_in_roster=False, taken_by=None):
    return {
        "player_id": name, "canonical_name": name, "score": score, "risk": risk,
        "appearances": appearances, "price_current": price, "decision_score": decision_score,
        "value_for_money_percentile": vfm_pct, "status": status,
        "is_in_roster": is_in_roster, "taken_by": taken_by,
    }


def _filler_pool(n, score_start=40, score_step=1, **kwargs):
    # decision_score must vary across fillers (roughly tracking score, like
    # real data would) — a uniform default would make any single test
    # player with a lower-than-default decision_score trivially "worst in
    # the population" and always DA_EVITARE, regardless of what the test is
    # actually trying to isolate.
    players = []
    for i in range(n):
        score = score_start + i * score_step
        row_kwargs = {"decision_score": score + 10, **kwargs}
        players.append(_player(f"Filler{i}", score, **row_kwargs))
    return players


def test_top_requires_high_score_low_risk_and_proven_appearances():
    star = _player("Star", score=95, risk=20, appearances=35, decision_score=70)
    pool = _filler_pool(15, score_start=40, score_step=2) + [star]

    tiers = classify_role(pool)

    assert star in tiers[TOP]


def test_unproven_star_is_a_scommessa_not_top():
    # Same excellent score as a proven star, but almost no appearances —
    # too little signal to trust as Top, but not bad either.
    newcomer = _player("Newcomer", score=95, risk=20, appearances=3, decision_score=70)
    pool = _filler_pool(15, score_start=40, score_step=2) + [newcomer]

    tiers = classify_role(pool)

    assert newcomer not in tiers.get(TOP, [])
    assert newcomer in tiers[SCOMMESSA]


def test_nailed_on_low_scorer_is_titolare_fisso():
    # score sits at this pool's 50th percentile (comfortably above the
    # tier's 40th-percentile quality floor, below Semi-top's 75th) and
    # decision_score is mid-pack too (fillers run 40-68), not the worst —
    # isolates the appearances/risk rule from both DA_EVITARE and SEMI_TOP.
    reliable = _player("Reliable", score=45, risk=15, appearances=37, decision_score=65)
    pool = _filler_pool(15, score_start=30, score_step=2) + [reliable]

    tiers = classify_role(pool)

    assert reliable in tiers[TITOLARE_FISSO]
    assert reliable not in tiers.get(TOP, []) and reliable not in tiers.get(SEMI_TOP, [])


def test_cheap_high_value_player_is_basso_prezzo():
    # decision_score mid-pack (fillers run 60-74), not the population's worst.
    bargain = _player(
        "Bargain", score=55, risk=25, appearances=25, price=6,
        vfm_pct=95, decision_score=65,
    )
    pool = _filler_pool(15, score_start=50, score_step=1, price=30) + [bargain]

    tiers = classify_role(pool)

    assert bargain in tiers[BASSO_PREZZO]


def test_injured_player_is_always_da_evitare_regardless_of_score():
    star_but_injured = _player(
        "Injured Star", score=95, risk=20, appearances=35,
        decision_score=70, status="infortunato",
    )
    pool = _filler_pool(15, score_start=40, score_step=2) + [star_but_injured]

    tiers = classify_role(pool)

    assert star_but_injured in tiers[DA_EVITARE]
    assert star_but_injured not in tiers.get(TOP, [])


def test_worst_decision_score_is_da_evitare():
    pool = [_player(f"P{i}", score=50 + i, decision_score=50 + i * 3) for i in range(20)]

    tiers = classify_role(pool)

    worst = min(pool, key=lambda r: r["decision_score"])
    assert worst in tiers[DA_EVITARE]


def test_owned_and_taken_players_are_excluded_entirely():
    mine = _player("Mine", score=95, is_in_roster=True)
    opponents = _player("Taken", score=95, taken_by="Avversario1")
    pool = _filler_pool(15, score_start=40, score_step=2) + [mine, opponents]

    tiers = classify_role(pool)

    all_classified = {p["player_id"] for players in tiers.values() for p in players}
    assert "Mine" not in all_classified
    assert "Taken" not in all_classified


def test_tiers_sorted_best_first_by_score():
    pool = _filler_pool(20, score_start=40, score_step=3)

    tiers = classify_role(pool)

    for players in tiers.values():
        scores = [p["score"] for p in players]
        assert scores == sorted(scores, reverse=True)
