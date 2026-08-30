"""Single percentile-rank implementation, used everywhere a player is
compared against the rest of a population (own role, own value-for-money
distribution, ...) instead of the three near-identical copies that used to
live in ranking/scorer.py, ranking/tiers.py and ranking/role_comparison.py
(P1-014/TASK-012)."""

import bisect


def percentile_rank(value, sorted_values: list) -> float:
    """0-100, mid-rank: the single best value in the population always
    scores exactly 100 and the single worst always scores exactly 0; tied
    values share the averaged rank of their tied block rather than an
    arbitrary ordering.

    The old bisect_left-only convention ("share of values strictly below
    this one") never let the best player reach 100 — with N players the
    best only got (N-1)/N*100 — which is what this replaces.

    `sorted_values` must already be ascending and include `value` itself
    (every call site builds it that way: it's "this player plus everyone
    else in the same population")."""
    n = len(sorted_values)
    if n == 0:
        return 50.0
    if n == 1:
        return 100.0
    lo = bisect.bisect_left(sorted_values, value)
    hi = bisect.bisect_right(sorted_values, value)
    mid_rank = (lo + hi - 1) / 2
    return round(mid_rank / (n - 1) * 100, 1)
