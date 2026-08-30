"""TASK-013: consensus/engine.py is the actual home of the multi-source
consensus logic now (moved from dashboard/data_access.py, not rewritten —
dashboard.data_access re-imports the same names for its own callers and for
backward compatibility with the existing test suite, which still exercises
this logic in depth via tests/test_data_access.py). This just locks in that
the module works standalone, independent of the dashboard layer."""

from consensus.engine import (
    DEFAULT_LISTINO_TO_AUCTION_FACTOR,
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
