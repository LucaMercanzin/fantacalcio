"""Multi-source consensus engine (TASK-013/A2/DB1): turns each player's raw
per-source quotation rows into one merged row — weighted price/fantamedia/
avg_rating/appearances averages, outlier detection, price-scale rescaling
(P0-001/TASK-001), price_agreement and data_confidence.

Moved here from dashboard/data_access.py (moved, not rewritten — same
functions, same behavior) so the consensus logic has one home independent
of the dashboard layer: pipeline/run_scraping.py now calls it directly to
materialize a player_consensus snapshot at the end of every run, instead of
this only ever running inline inside a Streamlit page request."""

import math
import statistics
from datetime import date

from config import LEAGUE_TEAMS, ROLE_SLOTS, TOTAL_CREDITS

# Fallback used when no per-league weight configuration is available (e.g. in
# tests that call _merge_player_rows directly). Real weights live in the
# `sources` table and are configurable without touching this code (see
# repository.get_source_weights / set_source_weight).
DEFAULT_SOURCE_WEIGHTS = {
    "fantacalcio_it": 3, "fantacalciopedia": 2, "fantapazz": 1.5,
    "pianetafanta": 1.5,
}
DEFAULT_SOURCE_WEIGHT = 1  # weight for a source with no explicit configuration

# fantacalcio_it/fantacalciopedia/fantapazz/pianetafanta all publish a
# "listino" — an editorial estimate of what a player *should* cost, not what
# anyone actually paid. fantacalcio_online and fantanalisi instead aggregate
# real credits spent in real auctions by real leagues. For the price_current
# field specifically, the estimated sources are excluded outright rather than
# just down-weighted — they don't get a vote on what something actually
# costs. They still contribute to fantamedia/avg_rating/appearances/status,
# which they do measure directly. Falls back to every source when a player
# has no real-auction data yet, so newly-listed players don't just go blank.
REAL_PRICE_SOURCES = {"fantacalcio_online", "fantanalisi"}

# The two canonical ceilings every source's raw price_current gets rescaled
# to before it is ever averaged or compared (P0-001/TASK-001): 40 is the
# classic fantacalcio "listino" scale ceiling, not a fitted parameter.
# AUCTION_CANONICAL_CEILING is config.TOTAL_CREDITS itself (TASK-019/A4) —
# the auction-credit scale's ceiling and the league's total budget are the
# same fact about the game by definition, not two numbers that happen to
# coincide.
LISTINO_CANONICAL_CEILING = 40
AUCTION_CANONICAL_CEILING = TOTAL_CREDITS

# Fallback for compute_listino_to_auction_factor when too few players have
# both scales to trust an empirical sample (tests; a near-empty DB). NOT
# used on real data once >=MIN_FACTOR_SAMPLES players qualify — see there
# for why the naive AUCTION_CANONICAL_CEILING/LISTINO_CANONICAL_CEILING=12.5
# is wrong in practice.
DEFAULT_LISTINO_TO_AUCTION_FACTOR = AUCTION_CANONICAL_CEILING / LISTINO_CANONICAL_CEILING
MIN_FACTOR_SAMPLES = 20


def compute_listino_to_auction_factor(rows: list, scale_factors: dict) -> float:
    """Converts an already-canonicalized price_listino (0-40 scale) into
    auction-credit terms (0-500) when no real-auction price is available —
    the fallback path in _compute_price below.

    Median, across players with both a real-auction and a listino price (on
    the same per-source-rescaled canonical values compute_source_scale_
    factors produces), of their auction average / listino average. NOT the
    naive AUCTION_CANONICAL_CEILING/LISTINO_CANONICAL_CEILING=12.5: that
    assumes the two 0-40/0-500 scales are linear rescalings of each other,
    which the real distributions aren't (auction credits are far more
    top-heavy — a handful of stars absorb most of the 500-credit pool, while
    filler players cluster near the floor on both scales, just not
    proportionally). 12.5 overvalued cheap listino-only players so badly
    that, discovered while investigating TASK-016's LP infeasibility, the
    25 *cheapest possible* players across all 4 roles already cost more than
    the entire 500-credit budget combined — a full squad was mathematically
    unaffordable regardless of which players the optimizer picked. The
    empirical median (measured ~2.5 on the real DB, not ~12.5) reflects how
    real auction spend actually compresses at the low end.

    rows: repository.get_all_latest_quotations(conn) — every player's latest
    per-source quotations, not filtered to one role, so the sample draws
    from the whole player pool."""
    by_player: dict = {}
    for row in rows:
        price = row.get("price_current")
        if price is None:
            continue
        scaled = price * scale_factors.get(row["source"], 1.0)
        by_player.setdefault(row["player_id"], {})[row["source"]] = scaled

    ratios = []
    for prices in by_player.values():
        auction_vals = [v for s, v in prices.items() if s in REAL_PRICE_SOURCES]
        listino_vals = [v for s, v in prices.items() if s not in REAL_PRICE_SOURCES]
        if auction_vals and listino_vals:
            ratios.append((sum(auction_vals) / len(auction_vals)) / (sum(listino_vals) / len(listino_vals)))

    if len(ratios) < MIN_FACTOR_SAMPLES:
        return DEFAULT_LISTINO_TO_AUCTION_FACTOR
    ratios.sort()
    mid = len(ratios) // 2
    return ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2


# The lowest bid the auction actually accepts: no player is ever bought for
# less than 1 credit, so the normalization below must respect that floor
# rather than scaling the cheap tail down to fractions of a credit.
MIN_AUCTION_BID = 1.0

# Enough of the bought pool must have a price for the budget identity to mean
# anything. Below this the sample is too thin to calibrate on and
# compute_league_price_scale returns 1.0 (no normalization) rather than
# inventing a factor from a handful of players.
MIN_LEAGUE_SCALE_COVERAGE = 0.5


def _solve_price_scale(prices: list, target: float, min_bid: float = MIN_AUCTION_BID) -> float:
    """Smallest k such that sum(max(min_bid, k * p)) == target.

    Monotonic non-decreasing in k, so plain bisection converges. Returns the
    bracket end when the target is unreachable: at k->0 every price is
    floored to min_bid (total = n * min_bid), so a target below that floor
    can't be met by scaling at all."""
    if not prices or target <= 0:
        return 1.0

    def total(k: float) -> float:
        return sum(max(min_bid, k * p) for p in prices)

    lo, hi = 1e-9, 1.0
    if total(lo) >= target:
        return lo
    while total(hi) < target and hi < 1e9:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if total(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def compute_league_price_scale(rows: list, weights: dict, reference_date: date,
                                scale_factors: dict, listino_to_auction_factor: float,
                                league_teams: int = LEAGUE_TEAMS,
                                role_slots: dict | None = None,
                                total_credits: int = TOTAL_CREDITS) -> float:
    """Final normalization factor that puts every consensus price into *this
    league's* credits, anchored on the one identity an auction cannot break:

        sum(winning bids) == league_teams * total_credits

    Every credit in the league gets spent (leftover credits are worthless),
    and exactly league_teams * sum(role_slots) players get bought, so the
    prices of the players who will actually be bought must sum to the money
    that will actually be spent. This is the *only* thing that fixes the
    absolute scale; everything upstream (compute_source_scale_factors,
    compute_listino_to_auction_factor) only makes sources commensurable with
    each other, which leaves the whole vector free to sit at any multiple.

    Why this is needed at all (found 2026-08-31, a day before a real
    auction): AUCTION_CANONICAL_CEILING was TOTAL_CREDITS, on the reasoning
    that "the auction-credit scale's ceiling and the league's total budget
    are the same fact by definition". They are not. TOTAL_CREDITS is what
    one manager spends on *25 players*; the ceiling anchored each source's
    single most expensive player to that whole-squad budget. On the real DB
    that put the top player at 500 credits — one player costing an entire
    roster — and made the 200 players who get bought sum to 13.767 credits
    against the 4.000 that exist, a 3,44x inflation applied to every price
    the auction pages show. Auction Intelligence takes those as fair_price,
    so its "maximum bid" inherited the same inflation and would have advised
    spending most of a budget on the first player called.

    The bought pool is taken per role (league_teams * slots per role), not
    as a flat top-200: a league buys 24 goalkeepers and 64 midfielders
    whatever their relative prices, so scoring the pool by global price rank
    would silently under-count the cheap roles.

    Returns 1.0 (explicit no-op) when too few of the pool are priced to
    calibrate on — see MIN_LEAGUE_SCALE_COVERAGE."""
    role_slots = role_slots if role_slots is not None else ROLE_SLOTS

    by_player: dict = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row)

    priced_by_role: dict = {role: [] for role in role_slots}
    for player_rows in by_player.values():
        role = player_rows[0].get("role_classic")
        if role not in priced_by_role:
            continue
        price = _compute_price(
            player_rows, weights, reference_date, scale_factors, listino_to_auction_factor,
        )["price_current"]
        if price:
            priced_by_role[role].append(price)

    pool = []
    slots_wanted = 0
    for role, slots in role_slots.items():
        need = slots * league_teams
        slots_wanted += need
        pool += sorted(priced_by_role[role], reverse=True)[:need]

    if not slots_wanted or len(pool) < slots_wanted * MIN_LEAGUE_SCALE_COVERAGE:
        return 1.0
    return _solve_price_scale(pool, league_teams * total_credits)


def compute_source_scale_factors(source_price_ceiling: dict) -> dict:
    """Per-source multiplier that rescales that source's raw price_current
    onto its family's canonical ceiling, derived every run from the highest
    price that source publishes (repository.get_source_price_ceiling) — the
    two ceilings above are fixed, but which multiplier gets each source
    there is computed from real data, not hardcoded per source. Confirmed on
    the real DB: even the two "real auction" sources publish on visibly
    different raw scales (fantacalcio_online tops out ~142, fantanalisi
    ~382) despite both claiming 500-credit budgets — without this, they'd
    still be blended together unscaled.

    Anchoring on the source's maximum (rather than its 99th percentile, as
    until 2026-08-31) is what makes the canonical ceiling an actual ceiling:
    every rescaled reading is <= ceiling by construction, so a weighted
    average of them is too, and _compute_price's clamp no longer has to
    flatten the most expensive players onto the same value. See
    repository.get_source_price_ceiling for the measurements behind the
    switch and for the robustness trade-off it accepts."""
    factors = {}
    for source, source_ceiling in source_price_ceiling.items():
        if not source_ceiling:
            continue
        ceiling = (
            AUCTION_CANONICAL_CEILING if source in REAL_PRICE_SOURCES
            else LISTINO_CANONICAL_CEILING
        )
        factors[source] = ceiling / source_ceiling
    return factors


# A source whose price deviates from the consensus median by more than this
# fraction has its weight cut, so one broken/stale scrape can't swing the
# consensus price on its own — but its data point is kept, not discarded.
OUTLIER_DEVIATION_THRESHOLD = 0.4
OUTLIER_WEIGHT_PENALTY = 0.3

# peso_recenza = e^(-giorni/30) (spec sezione 8): a quotation this old has
# already lost half its influence, so a fresh scrape reliably wins over a
# stale one without needing to zero the stale one out. Only applied to
# price_current (in _weighted_price_average below) — the field an auction
# decision actually depends on.
PRICE_RECENCY_HALF_LIFE_DAYS = 30

# price_current is handled separately by _compute_price (see below): it is
# the one field that can't be averaged the same way as the others, because
# its sources live on incompatible scales (P0-001/TASK-001).
#
# fantamedia/avg_rating are split out from price_initial (TASK-008/P0-004):
# they're *statistical* fields — a season/competition question, not a price
# one — so they're averaged over STATS_ELIGIBLE_ROWS (see
# _stats_eligible_rows below), not every row a player has. price_initial
# stays on the full row set; a listino starting price isn't season-scoped
# the way a performance stat is.
PRICE_AVERAGED_FIELDS = ("price_initial",)
STATS_AVERAGED_FIELDS = ("fantamedia", "avg_rating")
# appearances is NOT in here: it gets its own weighted average with
# disagreement detection below (P1-006/TASK-011), not "whichever source
# happened to answer the query first" like the remaining FILLED_FIELDS.
FILLED_FIELDS = ("status",)


def _stats_eligible_rows(player_rows: list) -> list:
    """TASK-008/P0-004 point 3: rows whose stats_competition is either
    unknown (NULL — every row from a source/scraper version that doesn't
    declare it, or hasn't been re-scraped since this column was added) or
    explicitly 'serie_a'. Only a row *positively* labeled as a foreign
    competition is excluded — see repository.get_all_latest_player_season_
    stats for why this is a NULL-passes, not NULL-excludes, filter: no
    current scraper ever contaminates fantamedia/avg_rating/appearances
    with a foreign reading in a way this row set doesn't already guard
    against a bit more directly (fantacalcio_online and fantacalciopedia
    are both verified Serie-A-scoped sources — see their own comments),
    but this stands ready for the day a source does.

    Rows reading a season that has barely started are excluded too, on the
    same principle one level up: a fantamedia over 1 played match is not a
    worse estimate of the player, it is an estimate of a different thing.
    Found 2026-08-31, the day before a real auction — fantacalciopedia
    rolled its list page over to the new season between the 26th and the
    31st, and the 31st's scrape (the "latest", so the one that wins) carries
    avg_app 0,77 against the 26th's 22,04. Ranking on it put Douvikas top of
    the attackers on a 9,5 fantamedia from his single played match, while
    Lautaro sat on 5,0 from his, and his real 8,25 went unused: the four
    priciest strikers in the league all fell out of the top 12 the user
    would have opened during the auction."""
    eligible = [r for r in player_rows if r.get("stats_competition") in (None, "serie_a")]
    appearances = [r["appearances"] for r in eligible if r.get("appearances") is not None]
    if not appearances or max(appearances) < COMPLETED_SEASON_APPEARANCES_MIN:
        return eligible
    completed = [
        r for r in eligible
        if r.get("appearances") is None
        or r["appearances"] > FRESH_SEASON_APPEARANCES_MAX
    ]
    return completed if completed else eligible

# Sources differing by more than this many matches on the same player is
# flagged as a disagreement worth surfacing in Monitoraggio (TASK-011 point
# 3) rather than silently averaged away.
APPEARANCES_DISAGREEMENT_THRESHOLD = 3

# The season-mismatch guard in _weighted_appearances below. A source
# reporting <= FRESH_SEASON_APPEARANCES_MAX matches while another reports at
# least COMPLETED_SEASON_APPEARANCES_MIN is not disagreeing about one
# season, it is reading a different one: no player has 28 matches and 1
# match in the same season. 2 and 10 leave a wide dead zone between them on
# purpose — anything landing in it is treated as a genuine disagreement and
# averaged as before, so the guard only fires where the two readings cannot
# both describe the same season.
FRESH_SEASON_APPEARANCES_MAX = 2
COMPLETED_SEASON_APPEARANCES_MIN = 10


def _recency_weight(scrape_date: str, reference_date: date) -> float:
    try:
        scraped = date.fromisoformat(scrape_date)
    except (TypeError, ValueError):
        return 1.0
    age_days = max((reference_date - scraped).days, 0)
    return math.exp(-age_days / PRICE_RECENCY_HALF_LIFE_DAYS)


def _detect_outliers(values_by_source: dict) -> set:
    """Sources whose value deviates too far from the group median.

    Needs at least 3 values: with only 1-2 sources there's no way to tell
    which one (if any) is the odd one out.
    """
    if len(values_by_source) < 3:
        return set()
    sorted_values = sorted(values_by_source.values())
    mid = len(sorted_values) // 2
    median = (
        sorted_values[mid] if len(sorted_values) % 2
        else (sorted_values[mid - 1] + sorted_values[mid]) / 2
    )
    if median == 0:
        return set()
    return {
        source for source, value in values_by_source.items()
        if abs(value - median) / median > OUTLIER_DEVIATION_THRESHOLD
    }


MIN_REAL_PRICE_SOURCES = 2


def _weighted_average(player_rows: list, field: str, stats_weights: dict):
    """Weighted average for the non-price fields (price_initial, fantamedia,
    avg_rating) — none of these mix incompatible scales the way
    price_current does, so a plain weighted mean (no recency, no
    rescaling) is enough. See _compute_price for price_current."""
    values_by_source = {
        row["source"]: row[field] for row in player_rows if row.get(field) is not None
    }
    if not values_by_source:
        return None, set()

    outliers = _detect_outliers(values_by_source)
    weighted_sum = 0.0
    weight_total = 0.0
    for row in player_rows:
        value = row.get(field)
        if value is None:
            continue
        source = row["source"]
        weight = stats_weights.get(source, DEFAULT_SOURCE_WEIGHT)
        if source in outliers:
            weight *= OUTLIER_WEIGHT_PENALTY
        weighted_sum += value * weight
        weight_total += weight

    avg = round(weighted_sum / weight_total, 2) if weight_total else None
    return avg, outliers


def _weighted_appearances(player_rows: list, stats_weights: dict) -> tuple:
    """Weighted average of appearances across sources, rounded to the
    nearest whole match (P1-006/TASK-011) — not "whichever source happened
    to answer the query first" like the plain FILLED_FIELDS.

    Returns (appearances, disagreement): disagreement is True when sources
    span more than APPEARANCES_DISAGREEMENT_THRESHOLD matches, so the
    caller can surface it instead of hiding it behind a silent average.

    Callers pass rows that _stats_eligible_rows has already vetted, so the
    season-mismatch case (one source still reading a barely-started season
    against another reading a completed one) has been removed upstream and
    never reaches the average here — see _stats_eligible_rows for why that
    matters and what it cost. What remains is genuine disagreement between
    sources about the same season, which is exactly what this average and
    its flag were built for."""
    avg, _outliers = _weighted_average(player_rows, "appearances", stats_weights)
    if avg is None:
        return None, False
    values = [r["appearances"] for r in player_rows if r.get("appearances") is not None]
    disagreement = (max(values) - min(values)) > APPEARANCES_DISAGREEMENT_THRESHOLD if len(values) > 1 else False
    return round(avg), disagreement


def _weighted_price_average(rows: list, weights: dict, reference_date: date,
                             scale_factors: dict) -> tuple:
    """Weighted average of price_current across `rows`, each value first
    rescaled by scale_factors (compute_source_scale_factors) so sources on
    different raw scales are commensurable before they're ever combined or
    compared for outliers (P0-001/TASK-001)."""
    values_by_source = {}
    for row in rows:
        value = row.get("price_current")
        if value is None:
            continue
        values_by_source[row["source"]] = value * scale_factors.get(row["source"], 1.0)
    if not values_by_source:
        return None, set(), {}

    outliers = _detect_outliers(values_by_source)
    weighted_sum = 0.0
    weight_total = 0.0
    for row in rows:
        if row.get("price_current") is None:
            continue
        source = row["source"]
        value = values_by_source[source]
        weight = weights.get(source, DEFAULT_SOURCE_WEIGHT)
        if source in outliers:
            weight *= OUTLIER_WEIGHT_PENALTY
        weight *= _recency_weight(row.get("scrape_date"), reference_date)
        weighted_sum += value * weight
        weight_total += weight

    avg = round(weighted_sum / weight_total, 2) if weight_total else None
    return avg, outliers, values_by_source


def _compute_price(player_rows: list, weights: dict, reference_date: date,
                    scale_factors: dict, listino_to_auction_factor: float) -> dict:
    """Produces price_listino and price_auction — each the weighted average
    of only its own family, on its own canonical scale, never blended with
    the other — plus the consumer-facing price_current/price_basis.

    price_current is price_auction when at least MIN_REAL_PRICE_SOURCES
    real-auction sources have a value for this player (a single real-auction
    reading can be a fluke — e.g. one source reporting 92 credits for a
    goalkeeper off a thin early-season sample); otherwise it's price_listino
    converted via listino_to_auction_factor (compute_listino_to_auction_
    factor), and price_basis says so.

    If neither is available (no listino source either, and fewer than
    MIN_REAL_PRICE_SOURCES real sources — ~1.7% of priced players on the
    real DB), price_current is None rather than built from a single
    unverified reading (P0-001/TASK-001)."""
    auction_rows = [r for r in player_rows if r["source"] in REAL_PRICE_SOURCES]
    listino_rows = [r for r in player_rows if r["source"] not in REAL_PRICE_SOURCES]

    auction_source_count = sum(1 for r in auction_rows if r.get("price_current") is not None)
    if auction_source_count >= MIN_REAL_PRICE_SOURCES:
        price_auction, auction_outliers, auction_values = _weighted_price_average(
            auction_rows, weights, reference_date, scale_factors,
        )
        if price_auction is not None:
            # A single player can never actually cost more than the entire
            # auction budget (found while writing TASK-022's domain tests:
            # 3 of the real DB's top scorers priced at 502-696 credits
            # against a 500 ceiling).
            #
            # Now a defensive guard rather than a load-bearing correction:
            # since compute_source_scale_factors anchors each source on its
            # own maximum, every rescaled reading is already <= the ceiling
            # and so is any weighted average of them. It still fires for a
            # caller that passes hand-built scale factors (tests) or none
            # at all, where a raw price above the ceiling reaches here
            # unscaled. When it does fire it destroys ordering — two
            # different players come out at the same 500.00 — which is
            # exactly the failure the max anchor removes on real data.
            price_auction = min(price_auction, AUCTION_CANONICAL_CEILING)
    else:
        price_auction, auction_outliers, auction_values = None, set(), {}

    price_listino, listino_outliers, listino_values = _weighted_price_average(
        listino_rows, weights, reference_date, scale_factors,
    )

    if price_auction is not None:
        return {
            "price_current": price_auction,
            "price_listino": price_listino,
            "price_auction": price_auction,
            "price_basis": "auction",
            "price_outlier_sources": auction_outliers,
            "price_values_by_source": auction_values,
        }
    if price_listino is not None:
        return {
            "price_current": round(price_listino * listino_to_auction_factor, 2),
            "price_listino": price_listino,
            "price_auction": price_auction,
            "price_basis": "listino_converted",
            "price_outlier_sources": listino_outliers,
            "price_values_by_source": listino_values,
        }
    return {
        "price_current": None,
        "price_listino": None,
        "price_auction": None,
        "price_basis": None,
        "price_outlier_sources": set(),
        "price_values_by_source": {},
    }


def _scaled_price(price, league_price_scale: float):
    """Applies the league normalization to one credit-denominated price,
    respecting the 1-credit auction floor. None stays None: "no price" is
    not the same fact as "costs the minimum", and every consumer already
    distinguishes them."""
    if price is None:
        return None
    if league_price_scale == 1.0:
        return price
    return round(max(MIN_AUCTION_BID, price * league_price_scale), 1)


def _price_agreement(values_by_source: dict) -> float:
    """0-100: how tightly the sources' price readings cluster around the
    median, via IQR/median (P1-001/TASK-010) rather than the old (max-min)/
    mean range — a single wild outlier no longer swings the whole score the
    way a raw range does, since the IQR ignores the tails.

    A single source has nothing to agree with, so it's capped at 40
    (unverified by anyone else) — same convention as before the rename
    (was _consensus_confidence)."""
    values = list(values_by_source.values())
    if not values:
        return 0.0
    if len(values) == 1:
        return 40.0
    median = statistics.median(values)
    if median == 0:
        return 40.0
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    spread = (q3 - q1) / median
    agreement = max(0.0, 1 - min(1.0, spread))
    return round(100 * agreement, 1)


# Weights for _data_confidence below: how much do we trust this player's
# data overall, not just the price. price_agreement/match_confidence carry
# the most weight (both are direct signals of "did the sources actually
# agree, on the right player"); coverage and a real fantamedia are smaller,
# corroborating signals.
DATA_CONFIDENCE_WEIGHTS = {
    "price_agreement": 0.35,
    "match_confidence": 0.35,
    "coverage": 0.20,
    "fantamedia": 0.10,
}
# A player with no player_source_matches row at all (shouldn't normally
# happen — every scraped record gets one, see pipeline/run_scraping.py) has
# no evidence of a matching problem either, so it's treated as neutral
# rather than penalized for missing data it was never given a chance to have.
DEFAULT_MATCH_CONFIDENCE = 70.0


def _data_confidence(source_count: int, price_agreement: float, has_real_fantamedia: bool,
                      match_confidence: float | None) -> float:
    """0-100 composite: how much to trust this player's merged data overall
    (P1-002/TASK-010) — broader than price_agreement alone, which only
    measures whether the price readings cluster. Folds in how many sources
    contributed, whether the identity match across sources was solid, and
    whether fantamedia is a real reading rather than absent."""
    coverage = min(source_count / 4, 1.0) * 100
    fantamedia_signal = 100.0 if has_real_fantamedia else 0.0
    match_signal = match_confidence if match_confidence is not None else DEFAULT_MATCH_CONFIDENCE
    return round(
        price_agreement * DATA_CONFIDENCE_WEIGHTS["price_agreement"]
        + match_signal * DATA_CONFIDENCE_WEIGHTS["match_confidence"]
        + coverage * DATA_CONFIDENCE_WEIGHTS["coverage"]
        + fantamedia_signal * DATA_CONFIDENCE_WEIGHTS["fantamedia"],
        1,
    )


def _merge_player_rows(rows: list, weights: dict | None = None, reference_date: date | None = None,
                        stats_weights: dict | None = None, source_scale_factors: dict | None = None,
                        listino_to_auction_factor: float | None = None,
                        match_confidences: dict | None = None,
                        league_price_scale: float | None = None,
                        stats_rows_by_player: dict | None = None) -> list:
    weights = weights if weights is not None else DEFAULT_SOURCE_WEIGHTS
    # Falls back to the price weights when no stats weights are given (tests,
    # or any caller that doesn't care about the distinction) so a single
    # weights dict still behaves exactly as before.
    stats_weights = stats_weights if stats_weights is not None else weights
    reference_date = reference_date if reference_date is not None else date.today()
    # No-op (multiply by 1.0) when not given: every production call site
    # passes the real per-source factors (repository.get_source_price_ceiling +
    # compute_source_scale_factors); tests that call this directly with
    # synthetic source names get the pre-TASK-001 behaviour unchanged.
    source_scale_factors = source_scale_factors if source_scale_factors is not None else {}
    listino_to_auction_factor = (
        listino_to_auction_factor if listino_to_auction_factor is not None
        else DEFAULT_LISTINO_TO_AUCTION_FACTOR
    )
    # No-op (neutral fallback for every player) when not given: only the
    # call sites that actually expose data_confidence to a reader
    # (get_ranked_role/get_player_detail, get_monitoring_data) pass the real
    # per-player match confidences — see repository.get_all_match_confidences.
    match_confidences = match_confidences if match_confidences is not None else {}
    # 1.0 = no-op. Only the production call sites that can see the whole
    # player population (and so can measure the budget identity) pass a real
    # factor — see compute_league_price_scale. A per-role caller must never
    # compute one from its own slice: 64 defenders can't tell you what a
    # league's 4.000 credits buy.
    league_price_scale = league_price_scale if league_price_scale is not None else 1.0
    # {player_id: rows to read the season-scoped stats from} when the caller
    # can supply them (repository.get_latest_stats_quotations). Falls back to
    # the player's own rows, which is what every test and any caller without
    # a DB gets.
    stats_rows_by_player = stats_rows_by_player if stats_rows_by_player is not None else {}
    by_player = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row)

    merged = []
    for player_rows in by_player.values():
        result = dict(player_rows[0])
        for field in PRICE_AVERAGED_FIELDS:
            avg, _outliers = _weighted_average(player_rows, field, stats_weights)
            result[field] = avg
        stats_rows = _stats_eligible_rows(
            stats_rows_by_player.get(result["player_id"]) or player_rows
        )
        for field in STATS_AVERAGED_FIELDS:
            avg, _outliers = _weighted_average(stats_rows, field, stats_weights)
            result[field] = avg
        result["appearances"], result["appearances_disagreement"] = _weighted_appearances(
            stats_rows, stats_weights,
        )
        price = _compute_price(
            player_rows, weights, reference_date, source_scale_factors, listino_to_auction_factor,
        )
        # price_current/price_auction are denominated in auction credits, so
        # both carry the league normalization; price_listino deliberately
        # does not — it stays on the published 0-40 editorial listino scale
        # the sources actually print, which is what the UI labels it as.
        result["price_current"] = _scaled_price(price["price_current"], league_price_scale)
        result["price_listino"] = price["price_listino"]
        result["price_auction"] = _scaled_price(price["price_auction"], league_price_scale)
        result["price_basis"] = price["price_basis"]
        for field in FILLED_FIELDS:
            result[field] = next(
                (r[field] for r in player_rows if r.get(field) is not None), None
            )
        result["source"] = "+".join(r["source"] for r in player_rows)
        result["source_count"] = len(player_rows)
        price_agreement = _price_agreement(price["price_values_by_source"])
        result["price_agreement"] = price_agreement
        result["data_confidence"] = _data_confidence(
            result["source_count"], price_agreement, result.get("fantamedia") is not None,
            match_confidences.get(result["player_id"]),
        )
        result["price_outlier_sources"] = sorted(price["price_outlier_sources"])
        merged.append(result)

    return merged
