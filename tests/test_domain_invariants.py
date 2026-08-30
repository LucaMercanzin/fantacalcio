"""Domain tests (TASK-022): verify the RESULT the app produces against the
real database, not code paths against synthetic 3-5-player fixtures. Those
give a false sense of safety — the price-scale-mixing (P0-001), score-
inconsistency (P1-003) and team-universe (P0-006) bugs the audit found could
not have manifested against a hand-built fixture where everything is
consistent by construction. Skipped automatically when data/fantacalcio.db
doesn't exist (e.g. a fresh checkout with no scrape yet) via the `realdb`
marker registered in pytest.ini.

test_compute_decision_score_is_never_improved_by_lower_confidence needs no
DB at all — it's a pure-function property — so it isn't marked realdb; it's
kept here because the audit's "Testing Gaps" list groups it with the rest.
"""

import os

import pytest

from db.connection import get_connection
from dashboard.data_access import get_optimal_squad_lp, get_player_detail, get_ranked_role
from matching.player_matcher import normalize_team
from ranking.scorer import compute_decision_score
from config import CURRENT_SEASON, ROLE_SLOTS, TOTAL_CREDITS

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fantacalcio.db")

pytestmark = pytest.mark.realdb


@pytest.fixture
def conn():
    if not os.path.exists(DB_PATH):
        pytest.skip("data/fantacalcio.db not present — no real scrape to test against")
    connection = get_connection(DB_PATH)
    yield connection
    connection.close()


def test_price_current_never_exceeds_the_auction_budget(conn):
    """P0-001: a single player can never actually cost more than the whole
    500-credit budget. compute_source_scale_factors calibrates each source
    to its own 99th percentile, not its max, so without an explicit clamp
    (added while writing this test) the very top scorers could land above
    the canonical ceiling once rescaled — 3 real players did, up to 696."""
    for role in ROLE_SLOTS:
        for row in get_ranked_role(conn, role):
            price = row.get("price_current")
            if price is not None:
                assert 0 <= price <= TOTAL_CREDITS, (row["canonical_name"], price)


def test_score_is_consistent_between_player_detail_and_role_ranking(conn):
    """P1-003: get_player_detail(pid)["score"] must equal the same player's
    score in get_ranked_role(role) — both go through _build_player_rows, so
    a divergence here means that shared path broke. A sample (not every
    player) keeps this fast: get_player_detail re-runs a full role ranking
    internally, so checking all ~800 players would be much slower for no
    extra safety once the sample spans every role."""
    for role in ROLE_SLOTS:
        rows = get_ranked_role(conn, role)
        sample = rows[:3] + rows[len(rows) // 2 : len(rows) // 2 + 2] + rows[-2:]
        for row in sample:
            detail = get_player_detail(conn, row["player_id"])
            assert detail is not None
            assert detail["score"] == row["score"], row["canonical_name"]


def test_fantamedia_stays_within_the_serie_a_domain(conn):
    """P0-003/P0-004: fantamedia is a Fantacalcio match rating average —
    genuinely out-of-range values (0.0 placeholders, implausible 15+ marks)
    signal a scraper/parsing bug, not a real player's form."""
    rows = conn.execute(
        "SELECT fantamedia FROM quotations WHERE fantamedia IS NOT NULL"
    ).fetchall()
    assert rows, "no fantamedia data to check — did the scrape actually run?"
    for row in rows:
        assert 2.0 <= row["fantamedia"] <= 9.5, row["fantamedia"]


def test_team_universe_matches_the_configured_season(conn):
    """P0-006: every non-foreign, non-lower-league player's team, once
    normalized, must be exactly one of the current season's 20 Serie A
    clubs in the `teams` table — no promoted/relegated club silently
    missing or lingering. Checked straight against the DB table, not
    against dashboard/data_access.py's hardcoded TEAM_ABBREV_TO_FULL (that
    dict is a separate, currently-unverified copy of the same list — see
    TASK-021)."""
    excluded_teams = {"Estero", "Serie Minori"}
    player_rows = conn.execute("SELECT DISTINCT team FROM players").fetchall()
    player_codes = {
        normalize_team(row["team"])
        for row in player_rows
        if row["team"] not in excluded_teams
    }

    db_team_rows = conn.execute(
        "SELECT code FROM teams WHERE season = ?", (CURRENT_SEASON,)
    ).fetchall()
    db_codes = {row["code"] for row in db_team_rows}

    assert db_codes, f"no teams row for season {CURRENT_SEASON!r} — is config.CURRENT_SEASON stale?"
    assert player_codes == db_codes


def test_optimal_squad_from_scratch_is_feasible_and_within_budget(conn):
    """Domain-level regression guard for the LP: a from-scratch 25-player
    squad must be buildable at all (status "optimal", not "infeasible")
    and never spend past the budget. This is exactly the shape of bug that
    slipped through function-level tests earlier in the audit's fixes: the
    LP went infeasible on the real DB after the price-scale rescale
    (TASK-001) landed, because a naive fixed listino->auction conversion
    factor made even the cheapest possible squad unaffordable — pure
    synthetic fixtures with 3-5 players never hit that."""
    result = get_optimal_squad_lp(conn, mode="from_scratch")

    assert result["status"] == "optimal", result.get("reason")
    assert result["total_cost"] <= TOTAL_CREDITS
    for role, slots in ROLE_SLOTS.items():
        assert len(result["squad"].get(role, [])) == slots


def test_compute_decision_score_is_never_improved_by_lower_confidence():
    """P1-001: monotonicity over the full confidence range, not just a
    couple of sample points — lower data_confidence must never raise
    decision_score, all else equal (uncertainty should only ever increase
    effective risk)."""
    scores = [
        compute_decision_score(70.0, 50.0, 60.0, confidence)
        for confidence in range(0, 101, 5)
    ]
    # scores[i] corresponds to confidence = i*5, ascending confidence —
    # so the score sequence must be non-decreasing.
    assert scores == sorted(scores)
