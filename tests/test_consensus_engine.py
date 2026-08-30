"""TASK-013: consensus/engine.py is the actual home of the multi-source
consensus logic now (moved from dashboard/data_access.py, not rewritten —
dashboard.data_access re-imports the same names for its own callers and for
backward compatibility with the existing test suite, which still exercises
this logic in depth via tests/test_data_access.py). This just locks in that
the module works standalone, independent of the dashboard layer."""

import pytest

from consensus.engine import (
    AUCTION_CANONICAL_CEILING,
    DEFAULT_LISTINO_TO_AUCTION_FACTOR,
    LISTINO_CANONICAL_CEILING,
    REAL_PRICE_SOURCES,
    _merge_player_rows,
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
