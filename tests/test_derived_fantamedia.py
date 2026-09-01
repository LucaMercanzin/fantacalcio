from ranking.fantamedia import MIN_APPEARANCES, derive_fantamedia
from ranking.scorer import enrich_scores


def _season(**overrides):
    base = {
        "season": "2025/26", "appearances": 30, "avg_rating": 6.0,
        "goals_scored": 0, "assists": 0, "goals_conceded": None,
        "yellow_cards": 0, "red_cards": 0,
    }
    base.update(overrides)
    return base


def test_plain_season_with_no_bonuses_is_just_the_average_rating():
    assert derive_fantamedia(_season()) == 6.0


def test_goals_and_assists_raise_it_by_the_league_bonus_per_match():
    # 30 presenze, 10 gol (+30) e 6 assist (+6) => +36/30 = +1,2
    assert derive_fantamedia(_season(goals_scored=10, assists=6)) == 7.2


def test_cards_lower_it():
    # 8 gialli (-4) e 1 rosso (-1) su 30 presenze => -5/30 = -0,17
    assert derive_fantamedia(_season(yellow_cards=8, red_cards=1)) == 5.83


def test_a_goalkeeper_pays_for_the_goals_he_concedes():
    keeper = _season(goals_scored=None, goals_conceded=36, avg_rating=6.2)
    assert derive_fantamedia(keeper) == 6.2 - 36 / 30


def test_it_separates_two_players_the_price_estimate_would_merge():
    """È il motivo per cui questa funzione esiste: la stima da prezzo dà lo
    stesso numero a due difensori quotati uguale, uno che segna e uno no."""
    scorer = derive_fantamedia(_season(goals_scored=5))
    non_scorer = derive_fantamedia(_season(goals_scored=0))
    assert scorer > non_scorer


def test_too_few_matches_is_not_derivable():
    """Un gol in 2 partite vale +1,5 di fantamedia e descrive l'episodio."""
    assert derive_fantamedia(_season(appearances=MIN_APPEARANCES - 1, goals_scored=1)) is None


def test_without_an_average_rating_there_is_no_base_to_build_on():
    assert derive_fantamedia(_season(avg_rating=None)) is None


def test_missing_row_is_not_derivable():
    assert derive_fantamedia(None) is None


def test_an_implausible_result_is_discarded_not_clamped():
    """20 gol in 6 partite porterebbe a 16: non è una fantamedia, è un dato
    sbagliato. Troncarlo a 12 fabbricherebbe un numero credibile da uno che
    credibile non è."""
    assert derive_fantamedia(_season(appearances=6, goals_scored=20)) is None


def test_enrich_row_prefers_a_real_fantamedia_over_the_derived_one():
    row = {"role_classic": "C", "fantamedia": 7.0, "derived_fantamedia": 5.0,
           "price_current": 20, "appearances": 30}
    assert enrich_scores(row)["fantamedia_basis"] == "real"


def test_enrich_row_prefers_the_derived_one_over_the_price_estimate():
    row = {"role_classic": "C", "fantamedia": None, "derived_fantamedia": 6.8,
           "price_current": 20, "appearances": 30}
    curves = {"C": [(10, 5.5), (20, 6.0), (30, 6.5)]}

    enriched = enrich_scores(row, price_fantamedia_curves=curves)

    assert enriched["fantamedia_basis"] == "derived"
    # estimated resta False: la derivata non viene dal prezzo, quindi
    # value_for_money (che divide per il prezzo) non è circolare e va calcolato.
    assert enriched["estimated"] is False
    assert enriched["value_for_money"] is not None


def test_enrich_row_still_falls_back_to_the_price_estimate():
    row = {"role_classic": "C", "fantamedia": None, "derived_fantamedia": None,
           "price_current": 20, "appearances": 30}
    curves = {"C": [(10, 5.5), (20, 6.0), (30, 6.5)]}

    enriched = enrich_scores(row, price_fantamedia_curves=curves)

    assert enriched["fantamedia_basis"] == "estimated"
    assert enriched["estimated"] is True
