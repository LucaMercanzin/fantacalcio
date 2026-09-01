"""TASK-013: consensus/engine.py is the actual home of the multi-source
consensus logic now (moved from dashboard/data_access.py, not rewritten —
dashboard.data_access re-imports the same names for its own callers and for
backward compatibility with the existing test suite, which still exercises
this logic in depth via tests/test_data_access.py). This just locks in that
the module works standalone, independent of the dashboard layer."""

from datetime import date

import pytest

from config import CURRENT_SEASON, LEAGUE_TEAMS, ROLE_SLOTS, TOTAL_CREDITS
from consensus.engine import (
    AUCTION_CANONICAL_CEILING,
    DEFAULT_LISTINO_TO_AUCTION_FACTOR,
    LISTINO_CANONICAL_CEILING,
    REAL_PRICE_SOURCES,
    _merge_player_rows,
    compute_league_price_scale,
    compute_listino_to_auction_factor,
    compute_source_scale_factors,
)


def test_merge_player_rows_importable_and_works_standalone():
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 30,
         "price_initial": 28, "fantamedia": 6.5, "avg_rating": 6.3,
         "status": "ok", "appearances": 30},
    ]

    merged = _merge_player_rows(rows)

    assert len(merged) == 1
    assert merged[0]["fantamedia"] == 6.5


def test_compute_source_scale_factors_importable_and_works_standalone():
    factors = compute_source_scale_factors({"fantacalcio_it": 40})
    assert factors["fantacalcio_it"] == 1.0


def test_compute_listino_to_auction_factor_falls_back_without_enough_samples():
    assert compute_listino_to_auction_factor([], {}) == DEFAULT_LISTINO_TO_AUCTION_FACTOR


def test_merge_player_rows_excludes_a_foreign_competition_stat_from_the_consensus():
    """TASK-008/P0-004 point 3: a row explicitly labeled as a foreign
    competition must not contribute to fantamedia/avg_rating/appearances —
    price_initial (not a season/competition-scoped field) is unaffected."""
    rows = [
        {"player_id": 1, "source": "fantacalciopedia", "price_current": None,
         "price_initial": 20, "fantamedia": 8.8, "avg_rating": None, "status": "ok",
         "appearances": 19, "stats_competition": "bundesliga_ger"},
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 30,
         "price_initial": 28, "fantamedia": None, "avg_rating": None,
         "status": "ok", "appearances": None},
    ]

    merged = _merge_player_rows(rows)

    assert merged[0]["fantamedia"] is None
    assert merged[0]["appearances"] is None
    # price_initial still averages across every row, foreign-stats-labeled
    # or not — it isn't a season/competition-scoped stat.
    assert merged[0]["price_initial"] is not None


def test_merge_player_rows_keeps_a_stat_with_no_competition_label():
    """NULL stats_competition (every row from before this column existed,
    or a scraper that doesn't declare it) must still count — only an
    explicit non-serie_a label excludes a row."""
    rows = [
        {"player_id": 1, "source": "fantacalciopedia", "price_current": None,
         "price_initial": 20, "fantamedia": 6.5, "avg_rating": None, "status": "ok",
         "appearances": 19},
    ]

    merged = _merge_player_rows(rows)

    assert merged[0]["fantamedia"] == 6.5
    assert merged[0]["appearances"] == 19


def test_dashboard_data_access_reexports_the_same_objects():
    """dashboard.data_access imports these from consensus.engine rather than
    redefining them — same function/constant objects, not copies."""
    from dashboard import data_access

    assert data_access._merge_player_rows is _merge_player_rows
    assert data_access.compute_source_scale_factors is compute_source_scale_factors
    assert data_access.compute_listino_to_auction_factor is compute_listino_to_auction_factor


def test_max_anchored_scale_factors_keep_the_two_priciest_players_distinct():
    """Regression for the clamp collapse (AUDIT_2026-08-30_CORREZIONI §5):
    with the scale factors anchored on each source's own maximum
    (repository.get_source_price_ceiling), the most expensive player lands
    exactly on the canonical ceiling and everyone else strictly below it —
    so _compute_price's clamp has nothing left to flatten.

    Under the previous p99 anchor both of these players came out at exactly
    500.00 (clamped) and were indistinguishable; the real DB had 4 attackers
    in that state."""
    source_max = {"fantacalcio_online": 141.74, "fantanalisi": 382.0}
    factors = compute_source_scale_factors(source_max)
    weights = {"fantacalcio_online": 45, "fantanalisi": 35}
    rows = [
        # the priciest player on both sources: their maxima, by definition
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 141.74,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantanalisi", "price_current": 382.0,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        # the runner-up, clearly cheaper on both sources
        {"player_id": 2, "source": "fantacalcio_online", "price_current": 139.5,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 2, "source": "fantanalisi", "price_current": 336.0,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]

    merged = {r["player_id"]: r for r in _merge_player_rows(
        rows, weights=weights, source_scale_factors=factors,
    )}

    assert merged[1]["price_current"] == AUCTION_CANONICAL_CEILING
    assert merged[2]["price_current"] < AUCTION_CANONICAL_CEILING
    assert merged[1]["price_current"] != merged[2]["price_current"]


def test_scale_factors_never_push_a_source_reading_above_the_ceiling():
    """The property the max anchor buys, stated directly: no rescaled
    reading can exceed its family's canonical ceiling, so no weighted
    average of them can either. This is what makes the clamp a defensive
    guard instead of a load-bearing correction that destroys ordering."""
    source_max = {"fantacalcio_online": 141.74, "fantanalisi": 382.0,
                  "fantacalcio_it": 36.0}
    factors = compute_source_scale_factors(source_max)

    for source, top_price in source_max.items():
        ceiling = (
            AUCTION_CANONICAL_CEILING if source in REAL_PRICE_SOURCES
            else LISTINO_CANONICAL_CEILING
        )
        assert top_price * factors[source] == pytest.approx(ceiling)


def test_appearances_ignores_a_source_still_reading_the_new_season():
    """A near-zero count against a completed-season count is a season
    mismatch, not a disagreement: no player has 28 matches and 0 matches in
    the same season. Averaging them invents a number describing neither
    (28 and 0 -> 14) and cost 136 real starters their place in the role
    rankings the day before an auction."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "appearances": 28,
         "price_current": None, "scrape_date": "2026-08-31"},
        {"player_id": 1, "source": "fantacalciopedia", "appearances": 0,
         "price_current": None, "scrape_date": "2026-08-31"},
    ]
    merged = _merge_player_rows(rows, weights={"fantacalcio_online": 1, "fantacalciopedia": 1})[0]

    assert merged["appearances"] == 28
    # Not flagged as a disagreement: the fresh-season row is dropped before
    # the average, so there is nothing left disagreeing. The flag means
    # "two sources read the same season differently, go look" — raising it
    # for the ~550 players in a normal August rollover would be noise.
    assert merged["appearances_disagreement"] is False


def test_appearances_still_averages_when_sources_agree():
    """The disagreement rule must not swallow the ordinary case: sources
    within the threshold are reading the same season, so they keep the
    weighted average they always had."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "appearances": 30,
         "price_current": None, "scrape_date": "2026-08-31"},
        {"player_id": 1, "source": "fantacalciopedia", "appearances": 28,
         "price_current": None, "scrape_date": "2026-08-31"},
    ]
    merged = _merge_player_rows(rows, weights={"fantacalcio_online": 1, "fantacalciopedia": 1})[0]

    assert merged["appearances"] == 29
    assert merged["appearances_disagreement"] is False


def test_league_price_scale_makes_the_bought_pool_sum_to_the_league_budget():
    """compute_league_price_scale solves for the factor that satisfies the
    budget identity. Built here on a synthetic population big enough to fill
    every role's slots so the solver has a real pool to work on."""
    rows = []
    player_id = 0
    for role, slots in ROLE_SLOTS.items():
        for i in range(slots * LEAGUE_TEAMS):
            player_id += 1
            # Deliberately on an absurd scale (thousands of "credits"): the
            # factor has to bring any input scale back onto the league's.
            rows.append({
                "player_id": player_id, "source": "fantanalisi", "role_classic": role,
                "price_current": 1000.0 + i, "scrape_date": "2026-08-31",
            })
            rows.append({
                "player_id": player_id, "source": "fantacalcio_online", "role_classic": role,
                "price_current": 1000.0 + i, "scrape_date": "2026-08-31",
            })

    weights = {"fantanalisi": 1, "fantacalcio_online": 1}
    scale = compute_league_price_scale(rows, weights, date(2026, 8, 31), {}, 1.0)
    merged = _merge_player_rows(rows, weights, league_price_scale=scale)

    by_role = {}
    for row in merged:
        by_role.setdefault(row["role_classic"], []).append(row["price_current"])
    bought = []
    for role, slots in ROLE_SLOTS.items():
        bought += sorted(by_role[role], reverse=True)[:slots * LEAGUE_TEAMS]

    assert sum(bought) == pytest.approx(LEAGUE_TEAMS * TOTAL_CREDITS, rel=0.02)


def test_league_price_scale_defaults_to_no_op():
    """An absent factor must leave prices exactly as they were — a per-role
    caller cannot measure the identity and must not silently rescale."""
    rows = [
        {"player_id": 1, "source": "fantanalisi", "price_current": 300.0,
         "scrape_date": "2026-08-31"},
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 300.0,
         "scrape_date": "2026-08-31"},
    ]
    weights = {"fantanalisi": 1, "fantacalcio_online": 1}

    assert (_merge_player_rows(rows, weights)[0]["price_current"]
            == _merge_player_rows(rows, weights, league_price_scale=1.0)[0]["price_current"])


def test_appearances_keeps_averaging_a_genuine_same_season_disagreement():
    """The season-mismatch guard must stay narrow: 10 vs 20 is two sources
    differing about the same season, and TASK-011's weighted average still
    owns that case."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "appearances": 10,
         "price_current": None, "scrape_date": "2026-08-31"},
        {"player_id": 1, "source": "fantacalciopedia", "appearances": 20,
         "price_current": None, "scrape_date": "2026-08-31"},
    ]
    merged = _merge_player_rows(
        rows, stats_weights={"fantacalcio_it": 3, "fantacalciopedia": 2},
    )[0]

    assert merged["appearances"] == 14
    assert merged["appearances_disagreement"] is True


def test_appearances_of_a_player_who_really_never_played_stays_zero():
    """Every source agreeing on ~0 is not a season mismatch — there is no
    completed-season reading to prefer, so the guard must not fire and
    invent appearances for a player who genuinely has none."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "appearances": 0,
         "price_current": None, "scrape_date": "2026-08-31"},
        {"player_id": 1, "source": "fantacalciopedia", "appearances": 0,
         "price_current": None, "scrape_date": "2026-08-31"},
    ]
    merged = _merge_player_rows(
        rows, stats_weights={"fantacalcio_online": 1, "fantacalciopedia": 1},
    )[0]

    assert merged["appearances"] == 0


def test_declared_season_beats_the_appearances_heuristic_in_october():
    """BACKLOG-2026-08-31 §6. La guardia sulle presenze regge solo finché la
    stagione in corso sta sotto le 10 giornate. A ottobre — 12 presenze nella
    2026/27 contro 28 nella 2025/26 — smette di distinguerle e le media
    (12 e 28 -> 20), che è un numero di nessuna delle due stagioni. Con la
    stagione dichiarata la scelta resta corretta."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "appearances": 28,
         "fantamedia": 7.2, "stats_season": "2025/26",
         "price_current": None, "scrape_date": "2026-10-20"},
        {"player_id": 1, "source": "fantacalciopedia", "appearances": 12,
         "fantamedia": 5.1, "stats_season": CURRENT_SEASON,
         "price_current": None, "scrape_date": "2026-10-20"},
    ]
    merged = _merge_player_rows(
        rows, weights={"fantacalcio_online": 1, "fantacalciopedia": 1},
    )[0]

    assert merged["appearances"] == 28
    assert merged["fantamedia"] == 7.2


def test_current_season_rows_survive_when_they_are_all_there_is():
    """A stagione inoltrata tutte le fonti parlano della stagione in corso:
    quella è l'unica lettura disponibile ed è anche quella giusta. La
    guardia non deve svuotare l'insieme."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "appearances": 25,
         "fantamedia": 6.8, "stats_season": CURRENT_SEASON,
         "price_current": None, "scrape_date": "2027-03-01"},
        {"player_id": 1, "source": "fantacalciopedia", "appearances": 25,
         "fantamedia": 6.8, "stats_season": CURRENT_SEASON,
         "price_current": None, "scrape_date": "2027-03-01"},
    ]
    merged = _merge_player_rows(
        rows, weights={"fantacalcio_online": 1, "fantacalciopedia": 1},
    )[0]

    assert merged["appearances"] == 25
    assert merged["fantamedia"] == 6.8


def test_the_only_stats_row_survives_even_if_it_is_the_new_season():
    """Quattro fonti su sei danno solo il listino. Se l'unica riga con una
    fantamedia è quella appena rotolata sulla stagione nuova, scartarla non
    lascia una lettura migliore: lascia il nulla. Sui dati del 31/08 questo
    caso vale 73 giocatori."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "appearances": None,
         "fantamedia": None, "price_current": 12, "scrape_date": "2026-08-31"},
        {"player_id": 1, "source": "fantapazz", "appearances": None,
         "fantamedia": None, "price_current": 11, "scrape_date": "2026-08-31"},
        {"player_id": 1, "source": "fantacalciopedia", "appearances": 1,
         "fantamedia": 6.5, "stats_season": CURRENT_SEASON,
         "price_current": None, "scrape_date": "2026-08-31"},
    ]
    merged = _merge_player_rows(rows, weights={
        "fantacalcio_it": 1, "fantapazz": 1, "fantacalciopedia": 1,
    })[0]

    assert merged["fantamedia"] == 6.5
