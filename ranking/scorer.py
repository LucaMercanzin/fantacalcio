PENALIZED_STATUSES = {"infortunato", "squalificato"}


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


def compute_risk(row: dict) -> float:
    """0-100, higher = riskier: driven by how unreliable the appearance
    record is and whether the player is currently unavailable."""
    appearances = row.get("appearances")
    reliability = (min(appearances, 38) / 38) if appearances is not None else 0.5
    unreliability = 1 - reliability
    status_penalty = 40 if row.get("status") in PENALIZED_STATUSES else 0
    return round(min(100.0, unreliability * 60 + status_penalty), 1)


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


def compute_decision_score(fantasy_value: float, value_for_money, risk: float,
                            confidence) -> float:
    """Combines fantasy value, price efficiency and risk into one number for
    ranking auction targets — deliberately not the same thing as "how good is
    this player" (that's compute_player_quality)."""
    vfm = value_for_money if value_for_money is not None else 0.0
    conf_factor = (confidence if confidence is not None else 50.0) / 100
    return round(fantasy_value * 0.5 + vfm * 0.3 - risk * 0.2 * conf_factor, 1)


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
    enriched["decision_score"] = compute_decision_score(
        fantasy_value, enriched["value_for_money"], enriched["risk"], row.get("confidence"),
    )
    return enriched


def rank_players(rows: list) -> list:
    scored = [enrich_scores(row) for row in rows]
    return sorted(scored, key=lambda r: r["score"], reverse=True)
