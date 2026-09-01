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

from config import CURRENT_SEASON, LEAGUE_TEAMS, ROLE_SLOTS, TOTAL_CREDITS
from dashboard.data_access import (
    get_insufficient_data_players,
    get_optimal_squad_lp,
    get_player_detail,
    get_ranked_role,
)
from db.connection import get_connection
from matching.player_matcher import normalize_team
from ranking.scorer import compute_decision_score

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


def test_the_priciest_players_are_not_flattened_onto_the_budget_ceiling(conn):
    """AUDIT_2026-08-30_CORREZIONI §5: the previous p99 scale anchor left the
    top ~1% of every source above the canonical ceiling, so the clamp in
    consensus.engine._compute_price collapsed them onto exactly TOTAL_CREDITS
    — 4 attackers (Hojlund, Malen, Lautaro, Ramos) all priced 500.00 and
    therefore indistinguishable exactly where the price gap matters most.

    Anchoring each source on its own maximum
    (repository.get_source_price_ceiling) makes the ceiling reachable by at
    most the single most expensive player in the game, never by two at once.
    """
    for role in ROLE_SLOTS:
        at_ceiling = [
            row["canonical_name"] for row in get_ranked_role(conn, role)
            if row.get("price_current") == TOTAL_CREDITS
        ]
        assert len(at_ceiling) <= 1, (role, at_ceiling)


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


def test_the_players_who_get_bought_cost_what_the_league_actually_has(conn):
    """The budget identity, and the single strongest check that prices are
    denominated in *this league's* credits at all: every credit in the
    league gets spent and exactly LEAGUE_TEAMS * 25 players get bought, so
    the prices of the players who will be bought must sum to the money that
    exists (LEAGUE_TEAMS * TOTAL_CREDITS).

    Found 2026-08-31, one day before a real auction, with the whole 459-test
    suite green: AUCTION_CANONICAL_CEILING was TOTAL_CREDITS, which anchored
    each source's most expensive single player to the budget for a whole
    25-man squad. The top player came out at 500 credits — an entire roster
    — and the 200 players who get bought summed to 13.767 against the 4.000
    that exist: every displayed price, and every Auction Intelligence
    maximum bid derived from it, inflated 3,44x. No function-level test
    could catch it because each function was individually correct; only the
    league-wide sum is wrong. See consensus.engine.compute_league_price_scale.
    """
    prices_by_role = {role: [] for role in ROLE_SLOTS}
    for role in ROLE_SLOTS:
        for row in get_ranked_role(conn, role):
            price = row.get("price_current")
            if price:
                prices_by_role[role].append(price)

    bought = []
    for role, slots in ROLE_SLOTS.items():
        bought += sorted(prices_by_role[role], reverse=True)[:slots * LEAGUE_TEAMS]

    budget = LEAGUE_TEAMS * TOTAL_CREDITS
    # 20% band: the normalization targets the identity exactly, but
    # get_ranked_role applies its own reliability filters on top, so the
    # pool priced here is a subset of the one calibrated on.
    assert 0.8 * budget <= sum(bought) <= 1.2 * budget, (
        f"the 200 bought players sum to {sum(bought):.0f} credits "
        f"against the {budget} the league actually has"
    )


def test_no_regular_starter_is_missing_from_his_role_ranking(conn):
    """A player who started ~30 matches last season must appear on the page
    the user actually opens during the auction.

    Found 2026-08-31: sources report appearances for *different seasons* at
    this point in the calendar — fantacalciopedia the season just underway
    (0-1 matches played), fantacalcio_online last season's completed total
    (~28). Averaging them landed 136 real starters on exactly (28+0)/2 = 14,
    one short of RELIABLE_APPEARANCES_MIN = 15, which silently removed them
    from their role ranking: Thuram, Leao, Bastoni and Koopmeiners were all
    invisible on auction day. See consensus.engine._weighted_appearances.

    "Visible" means anywhere on the role page, so the check covers
    get_insufficient_data_players too: render_tier_sections shows those rows
    in their own section (TASK-004, "no data" must not read as "no problem"),
    and a player whose price comes from a single source legitimately lands
    there — price_current is None by design in that case (P0-001, see
    consensus.engine._compute_price). The bug this test guards against put
    players in *neither* list, filtered out by RELIABLE_APPEARANCES_MIN
    before scoring ever ran, so widening the set here doesn't blunt it."""
    ranked_names = set()
    for role in ROLE_SLOTS:
        ranked_names |= {row["canonical_name"] for row in get_ranked_role(conn, role)}
        ranked_names |= {
            row["canonical_name"] for row in get_insufficient_data_players(conn, role)
        }

    starters = conn.execute(
        """
        SELECT p.canonical_name, q.appearances
        FROM quotations q JOIN players p ON p.id = q.player_id
        WHERE q.source = 'fantacalcio_online' AND q.appearances >= 25 AND p.active = 1
          AND q.id = (
            SELECT q2.id FROM quotations q2
            WHERE q2.player_id = q.player_id AND q2.source = q.source
            ORDER BY q2.scrape_date DESC, q2.id DESC LIMIT 1)
        """
    ).fetchall()
    if not starters:
        pytest.skip("no source reports a completed-season appearance count yet")

    missing = [row["canonical_name"] for row in starters
               if row["canonical_name"] not in ranked_names]
    assert not missing, (
        f"{len(missing)} players with >=25 appearances last season are absent "
        f"from their role page entirely, e.g. {missing[:5]}"
    )


def test_the_priciest_attackers_are_in_their_role_ranking_top_tier(conn):
    """The league's most expensive strikers must be near the top of the page
    the user opens to bid on strikers. Not a tautology — score and price are
    computed from different fields, so this only holds if both are reading
    sane data.

    Found 2026-08-31: fantacalciopedia rolled its list page to the new
    season between the 26th and the 31st, and the 31st scrape's single-match
    samples (avg 0,77 appearances) became "the latest" and therefore the
    stats the ranking used. Douvikas led the attackers on a 9,5 fantamedia
    from one match while Lautaro sat on 5,0 from one match and his real 8,25
    went unread: Lautaro, Malen, Thuram and Hojlund were all outside the top
    12 on auction eve. See repository.get_latest_stats_quotations."""
    ranked = sorted(
        (r for r in get_ranked_role(conn, "A") if r.get("score") is not None),
        key=lambda r: -r["score"],
    )
    if len(ranked) < 20:
        pytest.skip("attacker pool too small to talk about a top tier")

    by_price = sorted(
        (r for r in ranked if r.get("price_current")),
        key=lambda r: -r["price_current"],
    )
    top_tier = {r["canonical_name"] for r in ranked[:len(ranked) // 3]}
    priciest = by_price[:5]

    missing = [r["canonical_name"] for r in priciest if r["canonical_name"] not in top_tier]
    assert len(missing) <= 1, (
        f"{len(missing)} of the 5 priciest attackers are outside the top third "
        f"of their own ranking: {missing}"
    )
