from ranking.verdict import compute_verdict
from ranking.tiers import TOP, SCOMMESSA


def test_top_tier_gets_five_stars_and_matching_strengths():
    row = {
        "tier": TOP, "appearances": 35, "risk": 20.0,
        "value_for_money_percentile": 70.0, "tactical_profile_score": 50.0,
        "status": "ok",
    }

    verdict = compute_verdict(row, set_pieces=[])

    assert verdict["stars"] == 5
    assert "Titolare quasi certo" in verdict["strengths"]
    assert "Buon rapporto qualità/prezzo" in verdict["strengths"]


def test_injured_player_gets_a_risk_flag():
    row = {
        "tier": SCOMMESSA, "appearances": 5, "risk": 70.0,
        "value_for_money_percentile": None, "tactical_profile_score": None,
        "status": "infortunato",
    }

    verdict = compute_verdict(row, set_pieces=[])

    assert any("infortunato" in r for r in verdict["risks"])
    assert verdict["stars"] == 2


def test_penalty_taker_is_a_strength():
    row = {
        "tier": None, "appearances": 20, "risk": 40.0,
        "value_for_money_percentile": 50.0, "tactical_profile_score": None,
        "status": "ok",
    }
    set_pieces = [{"category": "Rigori", "rank": 1, "label": "Principale", "updated_at": "2026-08-01"}]

    verdict = compute_verdict(row, set_pieces=set_pieces)

    assert any("Rigorista" in s for s in verdict["strengths"])


def test_unclassified_tier_gets_no_stars_not_a_default_three():
    """P2-003: a player classify_role left unclassified must not be
    presented as an average 'Titolare affidabile' — that's a specific claim
    about a player the system has no verdict on."""
    row = {
        "tier": None, "appearances": None, "risk": None,
        "value_for_money_percentile": None, "tactical_profile_score": None,
        "status": "ok",
    }

    verdict = compute_verdict(row, set_pieces=[])

    assert verdict["stars"] is None
    assert verdict["headline"] == "Non classificabile: dati insufficienti per questo ruolo/tier"


def test_unknown_status_is_flagged_not_silently_treated_as_no_risk():
    """P0-008: status is never populated by any scraper today. Silence here
    would read as 'no risk found' when it actually means 'never checked'."""
    row = {
        "tier": TOP, "appearances": 35, "risk": 20.0,
        "value_for_money_percentile": 70.0, "tactical_profile_score": 50.0,
        "status": None,
    }

    verdict = compute_verdict(row, set_pieces=[])

    assert any("non verificata" in r for r in verdict["risks"])
