from ranking.percentile import percentile_rank
from ranking.tactical_profile import compute_tactical_profile_score

PENALIZED_STATUSES = {"infortunato", "squalificato"}

# A fantamedia backed by only a handful of appearances is statistically
# unproven — some sources (e.g. Fantacalciopedia) even show a flat "6.0"
# placeholder for players who've barely played, which would otherwise let an
# unproven bench player outrank a real starter with a genuinely-earned lower
# average. Below this many appearances, dock a penalty that fades to 0 by
# the threshold, on top of the existing reliability bonus.
UNPROVEN_APPEARANCES_THRESHOLD = 5
UNPROVEN_PENALTY = 8

# compute_score nudges Fantasy Value by tactical_profile_score for
# difensori/centrocampisti only (giocatori/movimento.md, giocatori/
# rosa-ideale.md both single out these two reparti — attaccanti's threat
# is already captured by fantamedia/gol). Centered on a fixed neutral
# baseline rather than added raw, so an average-profile player isn't
# inflated relative to portieri/attaccanti scores compute_score also
# produces (ideal_squad/lp_optimizer sum "score" across roles): only a
# clearly above/below-average tactical profile moves the score, and only by
# a bounded +/-7 at the extremes — small next to fantamedia's *10 term, same
# "adjustment, not a coequal term" philosophy as VALUE_ADJUSTMENT_WEIGHT
# below.
TACTICAL_PROFILE_WEIGHT = 0.10
NEUTRAL_TACTICAL_PROFILE = 30.0
TACTICAL_PROFILE_ROLES = {"D", "C"}


def compute_score(row: dict):
    """Fantasy Value: how useful this player is for the fantasy game — bonus
    production plus reliability, penalized when currently unavailable.
    Kept as the single ranking key everywhere it already drives sort order;
    see compute_player_quality/compute_risk/compute_value_for_money for the
    other scores the spec asks to keep separate (section "Separazione dei
    principali Score").

    Returns None when fantamedia is missing — fantamedia and avg_rating are
    not the same scale (for portieri fantamedia < avg_rating, since goals
    conceded are a malus there but not in avg_rating), so estimating a
    fantamedia from avg_rating used to silently invert rankings, e.g. a
    reserve keeper with no fantamedia outranking real starters (P0-002).
    A None score marks this player insufficient_data instead (see
    enrich_scores/rank_players) rather than ranking him on a fabricated
    baseline."""
    base = row.get("fantamedia")
    if base is None:
        return None

    appearances = row.get("appearances")
    reliability = (min(appearances, 38) / 38) if appearances is not None else 0.5

    penalty = 15 if row.get("status") in PENALIZED_STATUSES else 0
    if appearances is not None and appearances < UNPROVEN_APPEARANCES_THRESHOLD:
        penalty += UNPROVEN_PENALTY * (1 - appearances / UNPROVEN_APPEARANCES_THRESHOLD)

    score = base * 10 + reliability * 5 - penalty

    if row.get("role_classic") in TACTICAL_PROFILE_ROLES:
        tactical = compute_tactical_profile_score(row)
        if tactical is not None:
            score += (tactical - NEUTRAL_TACTICAL_PROFILE) * TACTICAL_PROFILE_WEIGHT

    return score


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
    # uncertainty_factor ranges 1 (full confidence, sources agree — no change
    # from the plain risk*0.2 penalty) to 2 (zero confidence — that penalty
    # doubles). Previously this multiplied risk by confidence/100 directly:
    # LOW confidence (sources disagree) shrank the risk penalty instead of
    # growing it, so a player with unreliable data scored *higher* than an
    # equally risky one with solid data (P1-001/TASK-010) — uncertainty must
    # increase effective risk, not discount it. Confidence can now only ever
    # match or reduce the decision_score relative to the full-confidence
    # baseline, never improve it.
    confidence = confidence if confidence is not None else 50.0
    uncertainty_factor = 2 - confidence / 100
    value_adjustment = (vfm_pct - 50.0) * VALUE_ADJUSTMENT_WEIGHT
    return round(fantasy_value + value_adjustment - risk * 0.2 * uncertainty_factor, 1)


def enrich_scores(row: dict) -> dict:
    """Attach the full separated-score set (player_quality, risk,
    value_for_money, decision_score) to a merged player row, on top of the
    existing `score` (Fantasy Value) that ranking/sorting already relies on.

    insufficient_data=True (score is None — see compute_score/P0-002) means
    value_for_money/decision_score are also None: both are built on top of
    fantasy_value, so there's nothing honest to compute from a missing
    baseline. player_quality/risk stay independent (avg_rating/appearances
    driven) and are still computed."""
    enriched = dict(row)
    fantasy_value = compute_score(row)
    enriched["score"] = fantasy_value
    enriched["insufficient_data"] = fantasy_value is None
    enriched["player_quality"] = compute_player_quality(row)
    enriched["risk"] = compute_risk(row)
    enriched["tactical_profile_score"] = compute_tactical_profile_score(row)
    if fantasy_value is None:
        enriched["value_for_money"] = None
        enriched["value_for_money_percentile"] = None
        enriched["decision_score"] = None
    else:
        enriched["value_for_money"] = compute_value_for_money(fantasy_value, row.get("price_current"))
        # No population to compute a real percentile against here (see
        # rank_players, which recomputes this once the full role is known) —
        # neutral fallback so a lone enrich_scores() call still returns a
        # usable decision_score instead of one silently skewed by an
        # unbounded ratio.
        enriched["value_for_money_percentile"] = None
        enriched["decision_score"] = compute_decision_score(
            fantasy_value, None, enriched["risk"], row.get("confidence"),
        )
    # Informational only — Fantacalciopedia's own algorithm score, kept
    # separate from our score/player_quality rather than blended in.
    enriched["alg_fcp"] = row.get("alg_fcp")
    return enriched


def rank_players(rows: list) -> tuple:
    """Splits into (ranked, insufficient_data): ranked is sorted best-to-
    worst by score among players with a real fantamedia; insufficient_data
    holds everyone else (score is None — see compute_score/P0-002),
    excluded from the ordering and from the value-for-money percentile/
    decision-score math below rather than computed against a missing
    baseline (that math would crash on a None score, not just be wrong)."""
    scored = [enrich_scores(row) for row in rows]
    ranked = [r for r in scored if not r["insufficient_data"]]
    insufficient_data = [r for r in scored if r["insufficient_data"]]

    vfm_values = sorted(
        r["value_for_money"] for r in ranked if r.get("value_for_money") is not None
    )
    for row in ranked:
        vfm = row.get("value_for_money")
        vfm_percentile = percentile_rank(vfm, vfm_values) if vfm is not None else None
        row["value_for_money_percentile"] = vfm_percentile
        row["decision_score"] = compute_decision_score(
            row["score"], vfm_percentile, row["risk"], row.get("confidence"),
        )

    return sorted(ranked, key=lambda r: r["score"], reverse=True), insufficient_data
