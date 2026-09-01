from ranking.percentile import percentile_rank
from ranking.tactical_profile import compute_tactical_profile_score

PENALIZED_STATUSES = {"infortunato", "squalificato"}

# TASK-011b/movimento.md §21-22: titolarità now scales the *entire* base
# score multiplicatively (score = base*10*multiplier) instead of the old
# additive "+reliability*5 -unproven_penalty" (5 points out of ~70 — too
# small to matter, and the flat unproven penalty double-penalized on top of
# the small bonus). MIN_STARTER_FLOOR is the multiplier at
# starter_probability=0: a player with *zero* signal (no appearances, no
# predicted_appearances) still keeps half his base score rather than being
# additively docked for it — movimento.md §22 explicitly forbids penalizing
# a player with no Serie A history.
MIN_STARTER_FLOOR = 0.5

# Used only when a player has neither real appearances nor a
# predicted_appearances estimate to fall back on (e.g. a brand-new arrival
# before Fantacalciopedia has published a prediction) — genuinely unknown,
# not "proven unreliable", so this is the same neutral midpoint
# MIN_STARTER_FLOOR itself represents, not a penalty.
STARTER_PROBABILITY_NEUTRAL_FALLBACK = 0.5


def _appearances_estimate_from_range(text) -> float:
    """Fantacalciopedia's predicted_appearances bucket format ("0/10",
    "11/20", "21/30", "30+") -> a single numeric estimate: the bucket
    midpoint, or (for the open-ended "30+") the midpoint between its lower
    bound and the 38-match season ceiling. None/unparseable -> None."""
    if not text:
        return None
    text = str(text).strip()
    if text.endswith("+"):
        try:
            low = float(text[:-1].strip())
        except ValueError:
            return None
        return (low + 38) / 2
    parts = text.replace(",", ".").split("/")
    try:
        values = [float(p.strip()) for p in parts if p.strip()]
    except ValueError:
        return None
    return sum(values) / len(values) if values else None


def _starter_probability(row: dict) -> float:
    """0-1: how much of a nailed-on starter this player is, driving both
    compute_score's multiplier and compute_risk's reliability term (TASK-
    011b point 2). Real `appearances` first; predicted_appearances (Fanta-
    calciopedia, already scraped into fcp_metrics but unused before this)
    as a fallback for players without Serie A history yet — a new arrival
    isn't just assumed unreliable for lack of a stat that was never going
    to exist. STARTER_PROBABILITY_NEUTRAL_FALLBACK only when *neither*
    signal is available."""
    appearances = row.get("appearances")
    if appearances is not None:
        return min(appearances, 38) / 38
    estimate = _appearances_estimate_from_range(row.get("predicted_appearances"))
    if estimate is not None:
        return min(estimate, 38) / 38
    return STARTER_PROBABILITY_NEUTRAL_FALLBACK


# compute_score nudges Fantasy Value by tactical_profile_score for
# difensori/centrocampisti only (giocatori/movimento.md, giocatori/
# rosa-ideale.md both single out these two reparti — attaccanti's threat
# is already captured by fantamedia/gol). Centered on a neutral baseline
# rather than added raw, so an average-profile player isn't inflated
# relative to portieri/attaccanti scores compute_score also produces
# (ideal_squad/lp_optimizer sum "score" across roles): only a clearly
# above/below-average tactical profile moves the score, and only by a
# bounded +/-7 at the extremes — small next to fantamedia's *10 term, same
# "adjustment, not a coequal term" philosophy as VALUE_ADJUSTMENT_WEIGHT
# below.
TACTICAL_PROFILE_WEIGHT = 0.10
# Fallback baseline for callers with no population to compute a real median
# against (e.g. dashboard/data_access.py's single-row enrich_scores() call
# for a player-detail view) — rank_players computes the real per-role
# median (TASK-011b point 4, compute_neutral_tactical_profiles) and passes
# it through instead of relying on this constant.
NEUTRAL_TACTICAL_PROFILE_DEFAULT = 30.0
TACTICAL_PROFILE_ROLES = {"D", "C"}


def compute_score(row: dict, neutral_tactical_profiles: dict | None = None):
    """Fantasy Value: how useful this player is for the fantasy game —
    production scaled by how much of a starter he actually is, penalized
    when currently unavailable. Kept as the single ranking key everywhere
    it already drives sort order; see compute_player_quality/compute_risk/
    compute_value_for_money for the other scores the spec asks to keep
    separate (section "Separazione dei principali Score").

    Returns None when fantamedia is missing — fantamedia and avg_rating are
    not the same scale (for portieri fantamedia < avg_rating, since goals
    conceded are a malus there but not in avg_rating), so estimating a
    fantamedia from avg_rating used to silently invert rankings, e.g. a
    reserve keeper with no fantamedia outranking real starters (P0-002).
    A None score marks this player insufficient_data instead (see
    enrich_scores/rank_players) rather than ranking him on a fabricated
    baseline.

    Portieri (role_classic == "P") delegate entirely to
    ranking.goalkeeper_score.compute_goalkeeper_score: fantamedia alone is a
    thin signal for a keeper (P2-020/TASK-025b) — the goalkeeper-specific
    formula blends it with goals-conceded rate and team defensive strength
    instead, on the same numeric scale so portieri stay comparable to
    outfield players wherever Fantasy Value is summed across roles.

    neutral_tactical_profiles: optional {role_classic: median
    tactical_profile_score} from compute_neutral_tactical_profiles(rows) —
    see NEUTRAL_TACTICAL_PROFILE_DEFAULT above for the fallback."""
    if row.get("role_classic") == "P":
        from ranking.goalkeeper_score import compute_goalkeeper_score
        return compute_goalkeeper_score(row)

    base = row.get("fantamedia")
    if base is None:
        return None

    multiplier = MIN_STARTER_FLOOR + (1 - MIN_STARTER_FLOOR) * _starter_probability(row)
    penalty = 15 if row.get("status") in PENALIZED_STATUSES else 0

    score = base * 10 * multiplier - penalty

    role_classic = row.get("role_classic")
    if role_classic in TACTICAL_PROFILE_ROLES:
        tactical = compute_tactical_profile_score(row)
        if tactical is not None:
            neutral = (neutral_tactical_profiles or {}).get(role_classic, NEUTRAL_TACTICAL_PROFILE_DEFAULT)
            score += (tactical - neutral) * TACTICAL_PROFILE_WEIGHT

    return score


def _median(values: list):
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def compute_neutral_tactical_profiles(rows: list) -> dict:
    """{role_classic: median tactical_profile_score} across `rows`, for the
    two reparti compute_score nudges by tactical profile (TASK-011b point
    4) — replaces the flat NEUTRAL_TACTICAL_PROFILE_DEFAULT=30 constant
    with what difensori/centrocampisti actually score this season, so the
    nudge is centered on the real observed population, not an assumption
    calibrated once and never revisited."""
    by_role: dict = {}
    for row in rows:
        role = row.get("role_classic")
        if role not in TACTICAL_PROFILE_ROLES:
            continue
        tactical = compute_tactical_profile_score(row)
        if tactical is not None:
            by_role.setdefault(role, []).append(tactical)
    return {role: _median(scores) for role, scores in by_role.items()}


def compute_price_fantamedia_curves(rows: list) -> dict:
    """{role_classic: [(price, fantamedia), ...] sorted by price} across
    `rows` with BOTH a real fantamedia and a real consensus price —
    TASK-011b point 3's last-resort fallback for a new arrival with *no*
    fantamedia from any source at all (a brand-new signing has quotations/
    prices from day one, but fantamedia only after he's actually played).
    movimento.md §22 point 5 explicitly sanctions "costo/valutazione se
    disponibile" as a fallback signal. Previous-season/foreign-league stats
    (§22 points 2-4) aren't used: no scraper in this codebase collects them,
    so estimating from them would be fabricating data, not falling back to
    it.

    A rank-based mapping (see estimate_fantamedia), not a fantamedia/price
    RATIO: price is floored near the 1-credit auction minimum for most
    squad-filler players while fantamedia never compresses anywhere near
    that hard (real range ~5.0-9.5), so a plain ratio is dominated by cheap
    players and wildly overstates a genuine new arrival's likely fantamedia
    once applied to his own (much higher, star-caliber) consensus price —
    found while checking this against the real DB (Kolo Muani/Gonçalo Ramos
    came out estimated at fantamedia ~360-400, an impossible value on the
    real ~2-9.5 scale)."""
    by_role: dict = {}
    for row in rows:
        role = row.get("role_classic")
        fantamedia = row.get("fantamedia")
        price = row.get("price_current")
        if role is None or fantamedia is None or not price:
            continue
        by_role.setdefault(role, []).append((price, fantamedia))
    for pairs in by_role.values():
        pairs.sort(key=lambda pair: pair[0])
    return by_role


def estimate_fantamedia(row: dict, price_fantamedia_curves: dict):
    """This role's real players, ranked by consensus price
    (compute_price_fantamedia_curves), mapped by percentile: finds where
    `row`'s own price ranks among priced peers, then returns the fantamedia
    a real player at that same percentile actually has. None when there's
    no price either (nothing left to estimate from — stays insufficient_
    data) or no reference curve for this role (population too small to
    trust one, e.g. a lone-row test)."""
    price = row.get("price_current")
    pairs = price_fantamedia_curves.get(row.get("role_classic"))
    if not price or not pairs:
        return None
    prices = [p for p, _ in pairs]
    pct = percentile_rank(price, prices)
    index = min(int(pct / 100 * (len(pairs) - 1)), len(pairs) - 1)
    return pairs[index][1]


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
    # Same signal compute_score's multiplier uses (TASK-011b): a new
    # arrival with no Serie A appearances yet but a predicted_appearances
    # estimate isn't marked maximally risky purely for lacking a stat he
    # never had the chance to accumulate.
    unreliability = 1 - _starter_probability(row)
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


def enrich_scores(row: dict, neutral_tactical_profiles: dict | None = None,
                   price_fantamedia_curves: dict | None = None) -> dict:
    """Attach the full separated-score set (player_quality, risk,
    value_for_money, decision_score) to a merged player row, on top of the
    existing `score` (Fantasy Value) that ranking/sorting already relies on.

    insufficient_data=True (score is None — see compute_score/P0-002) means
    value_for_money/decision_score are also None: both are built on top of
    fantasy_value, so there's nothing honest to compute from a missing
    baseline. player_quality/risk stay independent (avg_rating/appearances
    driven) and are still computed.

    neutral_tactical_profiles: see compute_score — a lone call outside
    rank_players (e.g. dashboard/data_access.py's player-detail view) has no
    population to compute a real median against, so it falls back to
    NEUTRAL_TACTICAL_PROFILE_DEFAULT same as compute_score does on its own.

    price_fantamedia_curves (TASK-011b point 3): when `row` has no
    fantamedia from any source, estimate_fantamedia() gives it one derived
    from this role's price/fantamedia relationship instead of leaving him
    insufficient_data (movimento.md §22: "non assegnare automaticamente un
    punteggio basso solamente perché non esiste uno storico Serie A").
    enriched["estimated"]=True marks the row and value_for_money (fantasy_
    value/price) stays None for it — dividing a price-*derived* score by
    that same price would be circular. decision_score still gets computed:
    it doesn't divide by price directly (only through value_for_money_
    percentile, which is None here and so contributes nothing — see
    compute_decision_score), so "fantasy_value minus a risk penalty" stays
    a meaningful, non-circular number for these rows too."""
    enriched = dict(row)
    estimated = False
    row_for_score = row
    if row.get("fantamedia") is None:
        # BACKLOG-2026-08-31 §3: la fantamedia ricavata dalle componenti
        # della stagione (ranking/fantamedia.py) si inserisce qui, *prima*
        # della stima da prezzo e *dopo* qualsiasi fantamedia vera. Il
        # motivo dell'ordine: la derivata distingue due giocatori che
        # rendono in modo diverso allo stesso prezzo, cosa che la stima da
        # prezzo non può fare per costruzione. Non viene marcata
        # estimated=True — non è derivata dal prezzo, quindi dividerla per
        # il prezzo in value_for_money non è circolare e quel numero resta
        # calcolabile, a differenza delle righe stimate.
        derived = row.get("derived_fantamedia")
        if derived is not None:
            row_for_score = {**row, "fantamedia": derived}
        estimated_fantamedia = (
            None if derived is not None
            else estimate_fantamedia(row, price_fantamedia_curves or {})
        )
        if estimated_fantamedia is not None:
            # Only fed into compute_score below — compute_player_quality's
            # own avg_rating->fantamedia fallback must stay price-*inde*
            # pendent (its whole point per its docstring), so it keeps
            # reading the original, unestimated `row`.
            row_for_score = {**row, "fantamedia": estimated_fantamedia}
            estimated = True
    fantasy_value = compute_score(row_for_score, neutral_tactical_profiles)
    enriched["score"] = fantasy_value
    enriched["estimated"] = estimated
    # Da dove viene la fantamedia su cui è costruito questo punteggio. Tre
    # valori con tre gradi di affidabilità molto diversi, e finora
    # distinguibili solo dal flag booleano `estimated`, che non bastava più
    # da quando i ripieghi sono due (BACKLOG-2026-08-31 §3).
    enriched["fantamedia_basis"] = (
        "real" if row.get("fantamedia") is not None
        else "derived" if row.get("derived_fantamedia") is not None
        else "estimated" if estimated
        else None
    )
    enriched["insufficient_data"] = fantasy_value is None
    enriched["player_quality"] = compute_player_quality(row)
    enriched["risk"] = compute_risk(row)
    enriched["tactical_profile_score"] = compute_tactical_profile_score(row)
    if fantasy_value is None:
        enriched["value_for_money"] = None
        enriched["value_for_money_percentile"] = None
        enriched["decision_score"] = None
    else:
        enriched["value_for_money"] = (
            None if estimated else compute_value_for_money(fantasy_value, row.get("price_current"))
        )
        # No population to compute a real percentile against here (see
        # rank_players, which recomputes this once the full role is known) —
        # neutral fallback so a lone enrich_scores() call still returns a
        # usable decision_score instead of one silently skewed by an
        # unbounded ratio.
        enriched["value_for_money_percentile"] = None
        enriched["decision_score"] = compute_decision_score(
            fantasy_value, None, enriched["risk"], row.get("data_confidence"),
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
    # TASK-011b points 3-4: computed once against the *whole* population
    # passed in (not just `ranked`, which doesn't exist yet) before any
    # per-row score, so compute_score's tactical nudge is centered on what
    # D/C players actually score this run rather than a flat constant, and
    # a fantamedia-less new arrival is estimated from the same population's
    # real price/fantamedia relationship rather than a fabricated constant.
    neutral_tactical_profiles = compute_neutral_tactical_profiles(rows)
    price_fantamedia_curves = compute_price_fantamedia_curves(rows)
    scored = [
        enrich_scores(row, neutral_tactical_profiles, price_fantamedia_curves) for row in rows
    ]
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
            row["score"], vfm_percentile, row["risk"], row.get("data_confidence"),
        )

    return sorted(ranked, key=lambda r: r["score"], reverse=True), insufficient_data
