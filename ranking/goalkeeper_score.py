"""Goalkeeper-specific Fantasy Value (TASK-025b/P2-020, rosa-ideale.md §4's
four-factor model): fantamedia alone is a thin signal for portieri — few
sources report it reliably for backups, and it doesn't separate "plays for
a defensively strong team" from "plays for a leaky one". xg/xga/ppda
(team_strength) and goals_conceded (player_season_stats) are already
scraped and stored but never fed into any score (P2-020) — this is what
finally uses them.

The coefficients below are explicit, declared choices — not fitted on
data, the same "not a fit, a reasonable starting point" philosophy already
used in ranking/price_engine.py, because we don't have the multi-season
real-auction-result history a real fit would need.
"""

GOALS_CONCEDED_RATE_CEILING = 2.0  # goals conceded per appearance at/above
                                    # which the defensive factor bottoms out at 0
DEFAULT_GOALS_CONCEDED_GOODNESS = 0.5  # no season_stats row for this keeper yet
DEFAULT_CLEAN_SHEET_PROXY = 0.45  # no team_strength row for his club yet —
                                   # roughly the middle of the real observed
                                   # range (~0.38-0.52 across the 20 clubs)

# Sum to 1.0: how much each factor drives the "quality" half of the score.
# avg_rating carries the most weight (closest analogue to fantamedia's role
# for outfield players); the team's clean-sheet proxy is deliberately the
# smallest of the three since it describes the team, not the keeper
# himself — titolarita (appearances) is NOT a fourth term in this blend, it
# stays the same outer reliability*5 bonus compute_score already applies to
# every role, so it isn't counted twice.
WEIGHT_RATING = 0.45
WEIGHT_GOALS_CONCEDED = 0.35
WEIGHT_CLEAN_SHEET = 0.20


def _rating_quality(row: dict) -> float:
    """0-1, same 5.0-8.0 band ranking.scorer.compute_player_quality stretches
    to 0-100 — avg_rating when available, fantamedia otherwise (a fallback,
    not a scale substitution: this only kicks in when avg_rating is simply
    missing, same convention as compute_player_quality itself)."""
    rating = row.get("avg_rating")
    if rating is None:
        rating = row.get("fantamedia")
    if rating is None:
        return 0.5
    return max(0.0, min(1.0, (rating - 5.0) / 3.0))


def _goals_conceded_goodness(row: dict) -> float:
    """0-1: fewer goals conceded per appearance is better. Real DB range for
    keepers with 20+ appearances runs about 0.7 (best) to 1.9 (worst) per
    match; GOALS_CONCEDED_RATE_CEILING=2.0 is where the factor bottoms out,
    not a fitted cutoff."""
    goals_conceded = row.get("season_goals_conceded")
    appearances = row.get("appearances")
    if goals_conceded is None or not appearances:
        return DEFAULT_GOALS_CONCEDED_GOODNESS
    rate = goals_conceded / appearances
    return max(0.0, min(1.0, 1 - rate / GOALS_CONCEDED_RATE_CEILING))


def _clean_sheet_proxy(row: dict) -> float:
    """1/(1+team_xga): a team conceding fewer expected goals per match makes
    a clean sheet more likely for whoever's in goal, independent of his own
    individual performance that day."""
    team_xga = row.get("team_xga")
    if team_xga is None:
        return DEFAULT_CLEAN_SHEET_PROXY
    return 1 / (1 + team_xga)


def compute_goalkeeper_score(row: dict):
    """Same insufficient_data gate and overall numeric scale as
    ranking.scorer.compute_score (fantamedia presence required, same
    equivalent_fantamedia*10*starter_multiplier - penalty shape, TASK-011b)
    so portieri stay comparable to outfield players wherever Fantasy Value
    is summed across roles (Rosa Ideale, the LP optimizer) — only the
    *source* of the quality term changes, from a single fantamedia reading
    to the rating/goals-conceded/team-defense blend below.

    Returns None when fantamedia is missing (P0-002/TASK-002's existing
    insufficient_data rule, unchanged for portieri)."""
    if row.get("fantamedia") is None:
        return None

    from ranking.scorer import MIN_STARTER_FLOOR, PENALIZED_STATUSES, _starter_probability

    quality = (
        WEIGHT_RATING * _rating_quality(row)
        + WEIGHT_GOALS_CONCEDED * _goals_conceded_goodness(row)
        + WEIGHT_CLEAN_SHEET * _clean_sheet_proxy(row)
    )
    equivalent_fantamedia = 5.0 + quality * 3.0

    multiplier = MIN_STARTER_FLOOR + (1 - MIN_STARTER_FLOOR) * _starter_probability(row)
    penalty = 15 if row.get("status") in PENALIZED_STATUSES else 0

    return equivalent_fantamedia * 10 * multiplier - penalty
