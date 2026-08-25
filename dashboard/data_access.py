import math
from datetime import date
from db import repository
from ranking.scorer import rank_players, enrich_scores

PROMOTED_TEAMS = {"VEN", "Venezia", "FRO", "Frosinone", "MON", "Monza"}

TEAM_ABBREV_TO_FULL = {
    "ATA": "Atalanta", "BOL": "Bologna", "CAG": "Cagliari", "COM": "Como",
    "FIO": "Fiorentina", "FRO": "Frosinone", "GEN": "Genoa", "INT": "Inter",
    "JUV": "Juventus", "LAZ": "Lazio", "LEC": "Lecce", "MIL": "Milan",
    "MON": "Monza", "NAP": "Napoli", "PAR": "Parma", "ROM": "Roma",
    "SAS": "Sassuolo", "TOR": "Torino", "UDI": "Udinese", "VEN": "Venezia",
}


def normalize_team_name(team: str) -> str:
    return TEAM_ABBREV_TO_FULL.get(team, team)


# Fallback used when no per-league weight configuration is available (e.g. in
# tests that call _merge_player_rows directly). Real weights live in the
# `sources` table and are configurable without touching this code (see
# repository.get_source_weights / set_source_weight).
DEFAULT_SOURCE_WEIGHTS = {
    "fantacalcio_it": 3, "fantacalciopedia": 2, "fantapazz": 1.5,
    "pianetafanta": 1.5,
}
DEFAULT_SOURCE_WEIGHT = 1  # weight for a source with no explicit configuration

# A source whose price deviates from the consensus median by more than this
# fraction has its weight cut, so one broken/stale scrape can't swing the
# consensus price on its own — but its data point is kept, not discarded.
OUTLIER_DEVIATION_THRESHOLD = 0.4
OUTLIER_WEIGHT_PENALTY = 0.3

# peso_recenza = e^(-giorni/30) (spec sezione 8): a quotation this old has
# already lost half its influence, so a fresh scrape reliably wins over a
# stale one without needing to zero the stale one out. Only applied to
# price_current — the field an auction decision actually depends on.
PRICE_RECENCY_HALF_LIFE_DAYS = 30
RECENCY_AWARE_FIELDS = ("price_current",)

AVERAGED_FIELDS = ("price_current", "price_initial", "fantamedia", "avg_rating")
FILLED_FIELDS = ("status", "appearances")


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


def _weighted_average(player_rows: list, field: str, weights: dict, reference_date: date):
    values_by_source = {
        row["source"]: row[field] for row in player_rows if row.get(field) is not None
    }
    if not values_by_source:
        return None, set()

    outliers = _detect_outliers(values_by_source)
    apply_recency = field in RECENCY_AWARE_FIELDS
    weighted_sum = 0.0
    weight_total = 0.0
    for row in player_rows:
        value = row.get(field)
        if value is None:
            continue
        source = row["source"]
        weight = weights.get(source, DEFAULT_SOURCE_WEIGHT)
        if source in outliers:
            weight *= OUTLIER_WEIGHT_PENALTY
        if apply_recency:
            weight *= _recency_weight(row.get("scrape_date"), reference_date)
        weighted_sum += value * weight
        weight_total += weight

    avg = round(weighted_sum / weight_total, 2) if weight_total else None
    return avg, outliers


def _consensus_confidence(values_by_source: dict) -> float:
    """0-100 score for how much the sources agree on the consensus price.

    A single source is capped at 40 (unverified by anyone else); more
    sources agreeing pushes it toward 100, while a wide spread pulls it down
    even with many sources.
    """
    values = list(values_by_source.values())
    if not values:
        return 0.0
    if len(values) == 1:
        return 40.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 40.0
    spread = (max(values) - min(values)) / mean
    agreement = max(0.0, 1 - spread)
    coverage = min(len(values) / 4, 1.0)
    return round(100 * agreement * (0.5 + 0.5 * coverage), 1)


def _merge_player_rows(rows: list, weights: dict = None, reference_date: date = None) -> list:
    weights = weights if weights is not None else DEFAULT_SOURCE_WEIGHTS
    reference_date = reference_date if reference_date is not None else date.today()
    by_player = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row)

    merged = []
    for player_rows in by_player.values():
        result = dict(player_rows[0])
        price_outliers = set()
        price_values_by_source = {}
        for field in AVERAGED_FIELDS:
            avg, outliers = _weighted_average(player_rows, field, weights, reference_date)
            result[field] = avg
            if field == "price_current":
                price_outliers = outliers
                price_values_by_source = {
                    row["source"]: row[field] for row in player_rows
                    if row.get(field) is not None
                }
        for field in FILLED_FIELDS:
            result[field] = next(
                (r[field] for r in player_rows if r.get(field) is not None), None
            )
        result["source"] = "+".join(r["source"] for r in player_rows)
        result["source_count"] = len(player_rows)
        result["confidence"] = _consensus_confidence(price_values_by_source)
        result["price_outlier_sources"] = sorted(price_outliers)
        merged.append(result)

    return merged


def get_ranked_role(conn, role_classic: str) -> list:
    weights = repository.get_source_weights(conn)
    rows = repository.get_latest_quotations(conn, role_classic)
    rows = _merge_player_rows(rows, weights)
    ranked = rank_players(rows)

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}
    taken_by = {p["player_id"]: p["opponent_name"] for p in repository.get_opponent_picks(conn)}

    for row in ranked:
        row["notes"] = repository.get_player_notes(conn, row["player_id"]) or ""
        row["is_in_roster"] = row["player_id"] in roster_player_ids
        row["is_promoted"] = row["team"] in PROMOTED_TEAMS
        row["taken_by"] = taken_by.get(row["player_id"])
        row["team"] = normalize_team_name(row["team"])

    return ranked


def search_and_sort(rows: list, query: str, sort_by: str) -> list:
    filtered = rows
    if query:
        query_lower = query.lower()
        filtered = [r for r in rows if query_lower in r["canonical_name"].lower()]

    if sort_by == "team":
        return sorted(filtered, key=lambda r: r["team"])
    if sort_by == "price":
        return sorted(filtered, key=lambda r: r["price_current"] or 0, reverse=True)

    non_promoted = [r for r in filtered if not r.get("is_promoted")]
    promoted = [r for r in filtered if r.get("is_promoted")]
    return non_promoted + promoted


def get_injury_summary(conn, player_id: int) -> dict:
    injuries = repository.get_player_injuries(conn, player_id)
    total_days = sum(i["days_out"] or 0 for i in injuries)
    total_matches_missed = sum(i["matches_missed"] or 0 for i in injuries)
    return {
        "injuries": injuries,
        "total_days_out": total_days,
        "total_matches_missed": total_matches_missed,
    }


def get_player_extra(conn, player_id: int) -> dict:
    return {
        "transfermarkt_id": repository.get_transfermarkt_id(conn, player_id),
    }


SET_PIECE_RANK_LABELS = {1: "Principale", 2: "Secondario"}
SET_PIECE_CATEGORY_LABELS = {"rigori": "Rigori", "punizioni": "Punizioni"}


def get_set_piece_summary(conn, player_id: int) -> list:
    """One entry per category (rigori/punizioni) this player has a role in,
    with a human label for the rank (spec sez. 22, 158-159)."""
    rows = repository.get_player_set_pieces(conn, player_id)
    summary = []
    for row in rows:
        label = SET_PIECE_RANK_LABELS.get(row["rank"], "Riserva")
        summary.append({
            "category": SET_PIECE_CATEGORY_LABELS.get(row["category"], row["category"]),
            "rank": row["rank"],
            "label": label,
            "updated_at": row["updated_at"],
        })
    return summary


def get_player_detail(conn, player_id: int):
    rows = repository.get_latest_quotations_for_player(conn, player_id)
    if not rows:
        return None

    weights = repository.get_source_weights(conn)
    merged = enrich_scores(_merge_player_rows(rows, weights)[0])

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}
    taken_by = {p["player_id"]: p["opponent_name"] for p in repository.get_opponent_picks(conn)}
    merged["notes"] = repository.get_player_notes(conn, player_id) or ""
    merged["is_in_roster"] = player_id in roster_player_ids
    merged["is_promoted"] = merged["team"] in PROMOTED_TEAMS
    merged["taken_by"] = taken_by.get(player_id)
    merged["team"] = normalize_team_name(merged["team"])

    role_rows = get_ranked_role(conn, merged["role_classic"])
    role_rows_sorted = sorted(role_rows, key=lambda r: r["score"], reverse=True)
    rank_position = next(
        (i + 1 for i, r in enumerate(role_rows_sorted) if r["player_id"] == player_id),
        None,
    )
    merged["rank_in_role"] = rank_position
    merged["role_total"] = len(role_rows_sorted)

    return merged


def get_monitoring_data(conn) -> dict:
    """Data-health snapshot for the admin monitoring page: per-source freshness/
    volume, consensus confidence distribution, and which players currently have
    a flagged outlier source (see sections 6/7/9/172 of imperfezioni.md)."""
    weights = repository.get_source_weights(conn)
    source_stats = repository.get_source_stats(conn)

    rows = repository.get_all_latest_quotations(conn)
    merged = _merge_player_rows(rows, weights)

    confidences = [m["confidence"] for m in merged if m.get("confidence") is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else None
    low_confidence_players = sorted(
        (m for m in merged if m.get("confidence") is not None and m["confidence"] < 50),
        key=lambda m: m["confidence"],
    )
    outlier_players = [m for m in merged if m.get("price_outlier_sources")]

    # Uncertain entity matches (spec section 5): a fuzzy match below 95%
    # similarity is queued for review instead of trusted silently forever.
    match_review_queue = repository.get_low_confidence_matches(conn, threshold=95.0)

    return {
        "weights": weights,
        "source_stats": source_stats,
        "total_players": len(merged),
        "avg_confidence": avg_confidence,
        "low_confidence_players": low_confidence_players,
        "outlier_players": outlier_players,
        "match_review_queue": match_review_queue,
    }


# A player with a known appearance count below this (out of 38) was a clear
# backup last season — not "cheap and undervalued", just someone who barely
# played. Without this floor, minimum-priced bench players dominate the
# suggestions on Value for Money alone (dividing a middling rating by a
# 1-credit price looks amazing on paper but nobody would actually start
# them). Unknown appearances (None — e.g. summer signings) are kept, since
# there's no evidence either way for them.
RELIABLE_APPEARANCES_MIN = 10


def get_squad_suggestions(conn, limit_per_role: int = 5) -> dict:
    """Rosa Ideale Realistica (spec sez. 26): per ogni ruolo con slot ancora
    liberi, i migliori candidati non già in rosa e acquistabili col budget
    residuo, ordinati per Decision Score. Aggiornata automaticamente ad ogni
    variazione della rosa (sez. 27), perché legge sempre lo stato attuale."""
    from ranking.budget import compute_budget_summary

    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)
    roster_ids = {r["player_id"] for r in roster}
    taken_ids = {p["player_id"] for p in repository.get_opponent_picks(conn)}
    unavailable_ids = roster_ids | taken_ids

    suggestions = {}
    for role, slot in summary["slots"].items():
        if slot["remaining"] <= 0:
            suggestions[role] = []
            continue
        ranked = get_ranked_role(conn, role)
        candidates = [
            r for r in ranked
            if r["player_id"] not in unavailable_ids
            and r.get("price_current") is not None
            and r["price_current"] <= summary["remaining"]
            and (r.get("appearances") is None or r["appearances"] >= RELIABLE_APPEARANCES_MIN)
        ]
        candidates.sort(key=lambda r: r.get("decision_score", 0), reverse=True)
        suggestions[role] = candidates[:limit_per_role]

    return {"summary": summary, "suggestions": suggestions}


def get_recent_form(conn, player_id: int, window: int = 5) -> dict:
    """Forma recente (spec sez. 16): media fantavoto sulle ultime `window`
    giornate disputate, separata dalla fantamedia stagionale. Torna vuoto
    finché non si sono accumulate abbastanza giornate — niente viene
    inventato per riempire il buco."""
    ratings = repository.get_recent_match_ratings(conn, player_id, limit=window)
    valid = [r["fantavoto"] for r in ratings if r["fantavoto"] is not None]
    avg_fantavoto = round(sum(valid) / len(valid), 2) if valid else None
    return {"ratings": ratings, "avg_fantavoto": avg_fantavoto, "window": window}


def get_price_history_by_date(conn, player_id: int) -> dict:
    """{scrape_date: {source: price_current}}, one point per source per day
    (later scrapes on the same day overwrite earlier ones for that day)."""
    rows = repository.get_price_history(conn, player_id)
    by_source_date = {}
    for row in rows:
        by_source_date[(row["source"], row["scrape_date"])] = row["price_current"]

    pivot: dict = {}
    for (source, scrape_date), price in by_source_date.items():
        pivot.setdefault(scrape_date, {})[source] = price
    return pivot


def find_player_by_name(conn, name: str):
    cursor = conn.execute(
        "SELECT * FROM players WHERE LOWER(canonical_name) = LOWER(?)", (name,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None
