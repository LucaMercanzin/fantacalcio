import bisect

PENALIZED_STATUSES = {"infortunato", "squalificato"}

# A fantamedia backed by only a handful of appearances is statistically
# unproven — some sources (e.g. Fantacalciopedia) even show a flat "6.0"
# placeholder for players who've barely played, which would otherwise let an
# unproven bench player outrank a real starter with a genuinely-earned lower
# average. Below this many appearances, dock a penalty that fades to 0 by
# the threshold, on top of the existing reliability bonus.
UNPROVEN_APPEARANCES_THRESHOLD = 5
UNPROVEN_PENALTY = 8


def compute_score(row: dict) -> float:
    """Fantasy Value: how useful this player is for the fantasy game — bonus
    production plus reliability, penalized when currently unavailable.
    Kept as the single ranking key everywhere it already drives sort order;
    see compute_player_quality/compute_risk/compute_value_for_money for the
    other scores the spec asks to keep separate (section "Separazione dei
    principali Score")."""
    base = row.get("fantamedia")
    if base is None:
        base = row.get("avg_rating")
    if base is None:
        base = 0.0

    appearances = row.get("appearances")
    reliability = (min(appearances, 38) / 38) if appearances is not None else 0.5

    penalty = 15 if row.get("status") in PENALIZED_STATUSES else 0
    if appearances is not None and appearances < UNPROVEN_APPEARANCES_THRESHOLD:
        penalty += UNPROVEN_PENALTY * (1 - appearances / UNPROVEN_APPEARANCES_THRESHOLD)

    return base * 10 + reliability * 5 - penalty


def compute_player_quality(row: dict) -> float:
    """0-100: raw footballing quality (avg_rating-driven), independent of
    fantasy scoring rules or price — a strong player stays high here even if
    he's a poor fantasy pick (e.g. a defender who never scores bonuses)."""
    rating = row.get("avg_rating")
    if rating is None:
        rating = row.get("fantamedia")
    if rating is None:
        return 0.0
    # Serie A ratings cluster roughly 5.0-8.5; stretch that band to 0-100.
    return round(max(0.0, min(100.0, (rating - 5.0) / 3.0 * 100)), 1)


# Weight applied to the Fantacalciopedia investment-stability/injury-resistance
# signal within compute_risk. Small on purpose: it's a secondary, third-party
# signal on top of our own appearance-based reliability, not a replacement
# for it. Missing entirely (player not yet detail-scraped) => 0, no regression.
FCP_RISK_WEIGHT = 0.2


def compute_risk(row: dict) -> float:
    """0-100, higher = riskier: driven by how unreliable the appearance
    record is, whether the player is currently unavailable, and — when
    available — Fantacalciopedia's own investment-stability/injury-resistance
    percentages (see docs/superpowers/specs/2026-08-25-fcp-metrics-design.md)."""
    appearances = row.get("appearances")
    reliability = (min(appearances, 38) / 38) if appearances is not None else 0.5
    unreliability = 1 - reliability
    status_penalty = 40 if row.get("status") in PENALIZED_STATUSES else 0

    fcp_signals = [
        row[key] for key in ("investment_stability_pct", "injury_resistance_pct")
        if row.get(key) is not None
    ]
    fcp_penalty = (100 - sum(fcp_signals) / len(fcp_signals)) * FCP_RISK_WEIGHT if fcp_signals else 0

    return round(min(100.0, unreliability * 60 + status_penalty + fcp_penalty), 1)


# Below this many credits, price stops being informative: nearly every
# third-choice bench player sits at the 1-credit auction floor regardless of
# how (mildly) useful he is, so dividing by the raw price there produces
# absurd ratios (e.g. a fringe keeper with a middling fantamedia looking like
# the best "value" player in the game). Floor the denominator instead.
MIN_PRICE_FOR_VALUE = 5


def compute_value_for_money(fantasy_value: float, price_current) -> float:
    """Fantasy value earned per credit spent. None when there's no price to
    divide by (e.g. before quotations are merged in)."""
    if not price_current:
        return None
    effective_price = max(price_current, MIN_PRICE_FOR_VALUE)
    return round(fantasy_value / effective_price * 10, 1)


# How many decision_score points a full swing in value-for-money percentile
# (worst in the role, 0, to best, 100) is worth — see compute_decision_score.
# 0.15 means the single best-value player in the role gets at most +7.5
# relative to a neutral (50th-percentile) player of identical fantasy_value:
# enough to break a near-tie between similar players, not enough to make a
# cheap mediocre player outrank a genuinely much stronger, pricier one.
VALUE_ADJUSTMENT_WEIGHT = 0.15


def compute_decision_score(fantasy_value: float, value_for_money_percentile, risk: float,
                            confidence) -> float:
    """Combines fantasy value, price efficiency and risk into one number for
    ranking auction targets — deliberately not the same thing as "how good is
    this player" (that's compute_player_quality).

    value_for_money_percentile: this player's value_for_money ranked against
    the rest of the population, 0-100 (see rank_players) — NOT the raw
    value_for_money ratio. That ratio is unbounded and grows sharply as price
    approaches compute_value_for_money's floor, so a cheap bench player could
    post a higher raw ratio than a genuinely stronger, pricier player and
    outrank him here purely on that scale mismatch. None (no population to
    rank against — e.g. a lone enrich_scores() call outside of rank_players)
    falls back to 50, the neutral midpoint.

    fantasy_value anchors the score; value-for-money only nudges it. A
    percentile always spans the full 0-100 range in any population by
    construction (someone is always "best" and someone "worst"), so weighting
    it as a coequal term with fantasy_value (as an earlier version of this
    function did, ~0.3 vs ~0.5) let being the single best-value player in the
    role outweigh a large, genuine quality gap — the fix isn't just bounding
    the scale, it's keeping the *adjustment* small relative to fantasy_value's
    own spread. +/-50 percentile points from the neutral midpoint moves the
    score by at most +/-VALUE_ADJUSTMENT_WEIGHT*50: a meaningful tie-breaker
    between similar players, not enough to flip a clearly-better, pricier
    player below a mediocre bargain.
    """
    vfm_pct = value_for_money_percentile if value_for_money_percentile is not None else 50.0
    conf_factor = (confidence if confidence is not None else 50.0) / 100
    value_adjustment = (vfm_pct - 50.0) * VALUE_ADJUSTMENT_WEIGHT
    return round(fantasy_value + value_adjustment - risk * 0.2 * conf_factor, 1)


def enrich_scores(row: dict) -> dict:
    """Attach the full separated-score set (player_quality, risk,
    value_for_money, decision_score) to a merged player row, on top of the
    existing `score` (Fantasy Value) that ranking/sorting already relies on."""
    enriched = dict(row)
    fantasy_value = compute_score(row)
    enriched["score"] = fantasy_value
    enriched["player_quality"] = compute_player_quality(row)
    enriched["risk"] = compute_risk(row)
    enriched["value_for_money"] = compute_value_for_money(fantasy_value, row.get("price_current"))
    # No population to compute a real percentile against here (see
    # rank_players, which recomputes this once the full role is known) —
    # neutral fallback so a lone enrich_scores() call still returns a usable
    # decision_score instead of one silently skewed by an unbounded ratio.
    enriched["value_for_money_percentile"] = None
    enriched["decision_score"] = compute_decision_score(
        fantasy_value, None, enriched["risk"], row.get("confidence"),
    )
    # Informational only — Fantacalciopedia's own algorithm score, kept
    # separate from our score/player_quality rather than blended in.
    enriched["alg_fcp"] = row.get("alg_fcp")
    return enriched


def _percentile_rank(value: float, sorted_values: list) -> float:
    """0-100: share of sorted_values this value is greater than or equal to.
    Population-relative, so it's comparable across players regardless of a
    metric's raw scale (value_for_money varies inversely with price, and
    unboundedly so near its floor)."""
    if not sorted_values:
        return 50.0
    idx = bisect.bisect_left(sorted_values, value)
    return round(idx / len(sorted_values) * 100, 1)


def rank_players(rows: list) -> list:
    scored = [enrich_scores(row) for row in rows]

    vfm_values = sorted(
        r["value_for_money"] for r in scored if r.get("value_for_money") is not None
    )
    for row in scored:
        vfm = row.get("value_for_money")
        vfm_percentile = _percentile_rank(vfm, vfm_values) if vfm is not None else None
        row["value_for_money_percentile"] = vfm_percentile
        row["decision_score"] = compute_decision_score(
            row["score"], vfm_percentile, row["risk"], row.get("confidence"),
        )

    return sorted(scored, key=lambda r: r["score"], reverse=True)
