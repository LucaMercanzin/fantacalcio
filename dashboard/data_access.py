import math
from datetime import date
import streamlit as st
from db import repository
from matching.player_matcher import normalize_team
from ranking.scorer import rank_players, enrich_scores
from ranking.tiers import classify_role
from ranking.role_comparison import compute_role_comparison

PROMOTED_TEAMS = {"VEN", "Venezia", "FRO", "Frosinone", "MON", "Monza"}
PROMOTED_TEAM_CODES = {normalize_team(t) for t in PROMOTED_TEAMS}

TEAM_ABBREV_TO_FULL = {
    "ATA": "Atalanta", "BOL": "Bologna", "CAG": "Cagliari", "COM": "Como",
    "FIO": "Fiorentina", "FRO": "Frosinone", "GEN": "Genoa", "INT": "Inter",
    "JUV": "Juventus", "LAZ": "Lazio", "LEC": "Lecce", "MIL": "Milan",
    "MON": "Monza", "NAP": "Napoli", "PAR": "Parma", "ROM": "Roma",
    "SAS": "Sassuolo", "TOR": "Torino", "UDI": "Udinese", "VEN": "Venezia",
}

# Same club, any spelling/casing a source uses ("COMO", "Como", "COM") all
# collapse to one normalize_team() code, so this is the single source of
# truth normalize_team_name() reads from — a source tagging a team in
# ALL-CAPS (seen from the 3-source consensus path) must land on the same
# canonical label as one tagging it in title case, or the same club renders
# as two different section headings downstream (e.g. the Portieri depth
# chart grouping by team).
TEAM_CODE_TO_FULL = {normalize_team(full): full for full in TEAM_ABBREV_TO_FULL.values()}

# The 20 real Serie A 2026/27 clubs, as 3-letter normalize_team() codes.
# A source can tag a player's team as "Estero" or "Serie Minori" once he's
# transferred out of Serie A (abroad or to a lower division) — he shouldn't
# keep showing up as biddable in a Serie A fantacalcio league just because an
# older scrape still has his last Serie A club on file.
VALID_SERIE_A_TEAM_CODES = {normalize_team(t) for t in TEAM_ABBREV_TO_FULL.values()}


def is_current_serie_a_team(team: str) -> bool:
    return normalize_team(team or "") in VALID_SERIE_A_TEAM_CODES


# A player confirmed by only one source is more likely stale/mismatched data
# than a real signal — require at least a second source before showing him
# as biddable.
MIN_SOURCES_REQUIRED = 2


def normalize_team_name(team: str) -> str:
    return TEAM_CODE_TO_FULL.get(normalize_team(team or ""), team)


def format_count(value) -> str:
    """Whole number when the value has no fractional part, otherwise at most
    one decimal — instead of pandas/Streamlit's default float formatting
    (e.g. "4.0000") that shows up in st.table whenever a column holds floats,
    even already-rounded ones."""
    if value is None:
        return "-"
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}"


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


MIN_REAL_PRICE_SOURCES = 2


def _price_rows(player_rows: list) -> list:
    """A single real-auction reading can be a fluke (e.g. one source
    reporting 92 credits for a goalkeeper off a thin early-season sample) —
    real sources are only trusted once at least two of them are present to
    cross-check each other. Below that, they're dropped entirely rather than
    blended in: their weight (100+) would still let one bad reading dominate
    even a handful of listino sources."""
    real_price_rows = [
        r for r in player_rows
        if r["source"] in REAL_PRICE_SOURCES and r.get("price_current") is not None
    ]
    if len(real_price_rows) >= MIN_REAL_PRICE_SOURCES:
        return real_price_rows
    listino_rows = [r for r in player_rows if r["source"] not in REAL_PRICE_SOURCES]
    return listino_rows if listino_rows else player_rows


def _weighted_average(player_rows: list, field: str, weights: dict,
                       stats_weights: dict, reference_date: date):
    if field == "price_current":
        player_rows = _price_rows(player_rows)
        active_weights = weights
    else:
        active_weights = stats_weights

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
        weight = active_weights.get(source, DEFAULT_SOURCE_WEIGHT)
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


def _merge_player_rows(rows: list, weights: dict = None, reference_date: date = None,
                        stats_weights: dict = None) -> list:
    weights = weights if weights is not None else DEFAULT_SOURCE_WEIGHTS
    # Falls back to the price weights when no stats weights are given (tests,
    # or any caller that doesn't care about the distinction) so a single
    # weights dict still behaves exactly as before.
    stats_weights = stats_weights if stats_weights is not None else weights
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
            avg, outliers = _weighted_average(
                player_rows, field, weights, stats_weights, reference_date,
            )
            result[field] = avg
            if field == "price_current":
                price_outliers = outliers
                price_values_by_source = {
                    row["source"]: row[field] for row in _price_rows(player_rows)
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


def _attach_fcp_metrics(rows: list, conn) -> list:
    """Merges each row's latest Fantacalciopedia detail-page metrics (see
    docs/superpowers/specs/2026-08-25-fcp-metrics-design.md) in place. A
    player never detail-scraped simply gets none of these keys, which
    compute_risk/enrich_scores already treat as "no signal"."""
    metrics_by_player = repository.get_all_latest_fcp_metrics(conn)
    for row in rows:
        metrics = metrics_by_player.get(row["player_id"])
        if not metrics:
            continue
        row["alg_fcp"] = metrics["alg_fcp"]
        row["punteggio_fcp"] = metrics["punteggio_fcp"]
        row["investment_stability_pct"] = metrics["investment_stability_pct"]
        row["injury_resistance_pct"] = metrics["injury_resistance_pct"]
        row["fcp_skills"] = metrics["skills"]
        row["predicted_goals"] = metrics["predicted_goals"]
        row["predicted_assists"] = metrics["predicted_assists"]
    return rows


def _attach_tactical_profile_inputs(rows: list, conn) -> list:
    """Merges season goals/assists (player_season_stats) and set-piece
    hierarchy (player_set_pieces) into each row — the two data sources
    ranking.tactical_profile.compute_tactical_profile_score needs on top of
    role_mantra (already on the row from the players table join) and the
    predicted_goals/predicted_assists _attach_fcp_metrics adds above."""
    season_stats_by_player = repository.get_all_latest_player_season_stats(conn)
    set_pieces_by_player = repository.get_all_player_set_pieces(conn)
    for row in rows:
        season_stats = season_stats_by_player.get(row["player_id"])
        row["season_goals_scored"] = season_stats["goals_scored"] if season_stats else None
        row["season_assists"] = season_stats["assists"] if season_stats else None
        row["set_pieces"] = set_pieces_by_player.get(row["player_id"], [])
    return rows


@st.cache_data(ttl=3600, show_spinner="Calcolo ranking...")
def _compute_ranked_role(_conn, role_classic: str, data_version: tuple) -> list:
    """The expensive part of get_ranked_role: SQL fetch + multi-source
    weighted consensus (recency decay, outlier detection) + FCP merge +
    Fantasy Value scoring/sorting. Deliberately excludes roster/opponent-picks/
    notes, which the caller overlays fresh every time: those change mid-auction
    and must never be served stale from this cache (see get_ranked_role below).

    Keyed on `data_version` (repository.get_data_version) rather than a
    blind TTL: the cache is reused as long as the underlying quotations/FCP/
    weights/match-review data hasn't actually changed, and recomputes
    immediately when it has — instead of guessing a "safe" number of seconds.
    `ttl=3600` is only a backstop against unbounded cache growth over a
    long-running process, not the primary invalidation mechanism.

    `_conn` (leading underscore) tells st.cache_data not to try hashing the
    sqlite3.Connection — same convention already used by
    components._cached_auction_intelligence. Freshness is entirely carried by
    `data_version` instead, which also makes this safe across tests that use
    different throwaway databases with the same role_classic: each gets its
    own version fingerprint, so results never leak between them.
    """
    weights = repository.get_source_weights(_conn)
    stats_weights = repository.get_source_stats_weights(_conn)
    rows = repository.get_latest_quotations(_conn, role_classic)
    rows = _merge_player_rows(rows, weights, stats_weights=stats_weights)
    rows = [
        r for r in rows
        if r.get("source_count", 0) >= MIN_SOURCES_REQUIRED
        and is_current_serie_a_team(r.get("team"))
        # Clear backups (e.g. a third-choice keeper) shouldn't clutter a
        # role page meant for players you could actually field. Unknown
        # appearances (a summer signing from another league) are kept only
        # if there's at least *some* other real signal (fantamedia/media
        # voto) — appearances AND fantamedia AND avg_rating all missing
        # means the listino sources have literally nothing on this player,
        # not "new signing", just a deep academy name with a placeholder price.
        and (
            (r.get("appearances") is not None and r["appearances"] >= RELIABLE_APPEARANCES_MIN)
            or (
                r.get("appearances") is None
                and (r.get("fantamedia") is not None or r.get("avg_rating") is not None)
            )
        )
    ]
    rows = _attach_fcp_metrics(rows, _conn)
    rows = _attach_tactical_profile_inputs(rows, _conn)
    return rank_players(rows)


def get_ranked_role(conn, role_classic: str) -> list:
    # The database file path guards against version-tuple collisions between
    # distinct databases that happen to be at the same row-count/id stage
    # (e.g. two freshly-created test databases each holding a handful of
    # rows) — real usage only ever points at one persistent .db file, so this
    # never affects production, only test isolation. id(conn) was tried first
    # but CPython can reuse a garbage-collected Connection's address for an
    # unrelated one within the same test run, causing exactly this collision.
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    version = (db_path, repository.get_data_version(conn))
    ranked = _compute_ranked_role(conn, role_classic, version)

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}
    taken_by = {p["player_id"]: p["opponent_name"] for p in repository.get_opponent_picks(conn)}

    for row in ranked:
        row["notes"] = repository.get_player_notes(conn, row["player_id"]) or ""
        row["is_in_roster"] = row["player_id"] in roster_player_ids
        row["is_promoted"] = normalize_team(row["team"] or "") in PROMOTED_TEAM_CODES
        row["taken_by"] = taken_by.get(row["player_id"])
        row["team"] = normalize_team_name(row["team"])

    return ranked


def get_roster_with_profile(conn) -> list:
    """Every owned player (repository.get_roster), enriched with the same
    profile fields get_ranked_role computes per role (team, role_mantra,
    score, tactical_profile_score, season_goals_scored, season_assists,
    appearances) plus price_paid from my_roster — the row shape
    ranking.correlation.find_correlations and ranking.auction_checklist.
    build_checklist both need. get_ranked_role's own is_in_roster flag is
    what identifies these rows; this just reuses it instead of a second
    query path against the players/quotations tables."""
    price_paid_by_player = {
        r["player_id"]: r["price_paid"] for r in repository.get_roster(conn)
    }
    owned = []
    for role in ("P", "D", "C", "A"):
        for row in get_ranked_role(conn, role):
            if row["is_in_roster"]:
                row = dict(row)
                row["price_paid"] = price_paid_by_player.get(row["player_id"])
                owned.append(row)
    return owned


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


def get_player_season_stats(conn, player_id: int) -> list:
    """Season-by-season presenze/gol/assist/media voto (repository.get_player_
    season_stats), most recent first — thin passthrough kept here so the
    dashboard layer never touches `repository` for player-detail data,
    consistent with every other get_* in this module."""
    return repository.get_player_season_stats(conn, player_id)


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
        "anagrafica": repository.get_player_anagrafica(conn, player_id),
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
    stats_weights = repository.get_source_stats_weights(conn)
    merged_rows = _attach_fcp_metrics(
        _merge_player_rows(rows, weights, stats_weights=stats_weights), conn,
    )
    merged = enrich_scores(merged_rows[0])

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}
    taken_by = {p["player_id"]: p["opponent_name"] for p in repository.get_opponent_picks(conn)}
    merged["notes"] = repository.get_player_notes(conn, player_id) or ""
    merged["is_in_roster"] = player_id in roster_player_ids
    merged["is_promoted"] = normalize_team(merged["team"] or "") in PROMOTED_TEAM_CODES
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

    # role_rows went through rank_players against the *whole* role, so its
    # decision_score/value_for_money_percentile are the real population-
    # relative ones — reuse them instead of the neutral (percentile=50)
    # fallback enrich_scores() set above with no population to compare
    # against, so the detail page always matches what role ranking actually
    # used to rank this player.
    role_match = next((r for r in role_rows if r["player_id"] == player_id), None)
    if role_match:
        merged["decision_score"] = role_match["decision_score"]
        merged["value_for_money_percentile"] = role_match["value_for_money_percentile"]

    tiers = classify_role(role_rows)
    merged["tier"] = next(
        (tier for tier, players in tiers.items()
         if any(p["player_id"] == player_id for p in players)),
        None,
    )

    merged["role_comparison"] = compute_role_comparison(role_rows, player_id)

    return merged


def get_monitoring_data(conn) -> dict:
    """Data-health snapshot for the admin monitoring page: per-source freshness/
    volume, consensus confidence distribution, and which players currently have
    a flagged outlier source (see sections 6/7/9/172 of imperfezioni.md)."""
    weights = repository.get_source_weights(conn)
    stats_weights = repository.get_source_stats_weights(conn)
    source_stats = repository.get_source_stats(conn)

    rows = repository.get_all_latest_quotations(conn)
    merged = _merge_player_rows(rows, weights, stats_weights=stats_weights)

    confidences = [m["confidence"] for m in merged if m.get("confidence") is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else None
    low_confidence_players = sorted(
        (m for m in merged if m.get("confidence") is not None and m["confidence"] < 50),
        key=lambda m: m["confidence"],
    )
    outlier_players = [m for m in merged if m.get("price_outlier_sources")]

    return {
        "weights": weights,
        "stats_weights": stats_weights,
        "source_stats": source_stats,
        "total_players": len(merged),
        "avg_confidence": avg_confidence,
        "low_confidence_players": low_confidence_players,
        "outlier_players": outlier_players,
    }


def get_match_review_queue(conn) -> list:
    """Uncertain entity matches (spec section 5): a fuzzy match below 95%
    similarity is queued for review instead of trusted silently forever.

    Deliberately separate from get_monitoring_data: this is a plain indexed
    query (repository.get_low_confidence_matches), not the ~800-player
    consensus merge — confirming/rejecting a match (Monitoraggio's
    🟢/🟡/🔴) must feel instant, not re-run the whole merge just to reflect
    one status change."""
    return repository.get_low_confidence_matches(conn, threshold=95.0)


# A player with a known appearance count below this (out of 38) either
# barely played last season or wasn't a nailed-on starter — not what "solido
# e titolare" means. Unknown appearances (None — e.g. summer signings) are
# kept, since there's no evidence either way for them.
RELIABLE_APPEARANCES_MIN = 15


def get_squad_suggestions(conn, limit_per_role: int = 5) -> dict:
    """Rosa Ideale Realistica (spec sez. 26): per ogni ruolo con slot ancora
    liberi, i migliori candidati non già in rosa e acquistabili col budget
    residuo. Ordinati per Fantasy Value — quanto rende in media a partita,
    non quanto costa poco — perché il criterio è "i più forti per una
    stagione intera", non l'affare più economico. Un giocatore forte ma caro
    deve comunque comparire qui se rientra nel budget residuo. Aggiornata
    automaticamente ad ogni variazione della rosa (sez. 27), perché legge
    sempre lo stato attuale."""
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
        candidates.sort(key=lambda r: r.get("score", 0), reverse=True)
        suggestions[role] = candidates[:limit_per_role]

    return {"summary": summary, "suggestions": suggestions}


def get_ideal_squad(conn, limit_per_role: int = 5) -> dict:
    """Rosa Ideale (spec sez. 25): i migliori giocatori per ruolo per Fantasy
    Value, senza vincoli di budget, rosa attuale o disponibilità in lega —
    la qualità teorica pura, utile come riferimento a prescindere da chi hai
    già preso o da quanto ti resta da spendere."""
    ideal = {}
    for role in ("P", "D", "C", "A"):
        ranked = get_ranked_role(conn, role)
        reliable = [
            r for r in ranked
            if r.get("appearances") is None or r["appearances"] >= RELIABLE_APPEARANCES_MIN
        ]
        ideal[role] = reliable[:limit_per_role]
    return ideal


def get_ideal_formation(conn, formation_name: str = "3-4-3") -> dict:
    """Rosa Ideale schierata in campo: gli 11 titolari migliori per ruolo
    nella formazione data, dando priorità ai giocatori già in rosa (restano
    titolari) ed escludendo quelli presi dagli avversari — se un titolare
    viene preso da un avversario, il prossimo migliore libero per quel ruolo
    ne prende automaticamente il posto."""
    from ranking.budget import compute_budget_summary
    from ranking.ideal_squad import build_ideal_squad, FORMATIONS

    formation = FORMATIONS[formation_name]
    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)
    roster_ids = {r["player_id"] for r in roster}
    taken_ids = {p["player_id"] for p in repository.get_opponent_picks(conn)}

    players_by_role = {
        role: [
            r for r in get_ranked_role(conn, role)
            if r.get("appearances") is None or r["appearances"] >= RELIABLE_APPEARANCES_MIN
        ]
        for role in formation
    }

    return build_ideal_squad(
        players_by_role, formation, summary["remaining"], roster_ids, taken_ids,
    )


def get_roster_fcp_chart_data(conn) -> list:
    """Solidità fantainvestimento / resistenza infortuni (Fantacalciopedia)
    per i giocatori in rosa, per il grafico affidabilità della propria
    squadra — righe senza dati FCP (non ancora scrappato in dettaglio)
    vengono escluse, non mostrate a zero."""
    roster = repository.get_roster(conn)
    metrics_by_player = repository.get_all_latest_fcp_metrics(conn)
    rows = []
    for player in roster:
        metrics = metrics_by_player.get(player["player_id"])
        if not metrics or metrics.get("investment_stability_pct") is None:
            continue
        rows.append({
            "Nome": player["canonical_name"],
            "Solidità investimento": metrics["investment_stability_pct"],
            "Resistenza infortuni": metrics["injury_resistance_pct"],
        })
    return rows


def get_optimal_squad_lp(conn, mode: str = "constrained") -> dict:
    """Rosa ottimale via solver LP (docs/superpowers/specs/2026-08-25-...):
    massimizza lo score totale rispettando budget e slot per ruolo. In modalità
    "constrained" tiene fissa la rosa attuale e ottimizza gli slot residui col
    budget rimanente; in "from_scratch" ignora la rosa e ottimizza tutti i 25
    slot con budget pieno — un riferimento teorico, non vincolato all'asta in
    corso."""
    from ranking.budget import compute_budget_summary
    from ranking.lp_optimizer import build_optimal_squad, ROLE_SLOTS

    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)
    roster_ids = {r["player_id"] for r in roster}
    roster_prices = {r["player_id"]: r["price_paid"] for r in roster}
    taken_ids = {p["player_id"] for p in repository.get_opponent_picks(conn)}

    players_by_role = {role: get_ranked_role(conn, role) for role in ROLE_SLOTS}

    if mode == "from_scratch":
        return build_optimal_squad(
            players_by_role, 500, set(), taken_ids, mode="from_scratch",
        )
    return build_optimal_squad(
        players_by_role, summary["remaining"], roster_ids, taken_ids,
        mode="constrained", roster_prices=roster_prices,
    )


ROLE_ORDER = ("P", "D", "C", "A")


def get_auction_price_trend(conn) -> dict:
    """Andamento del prezzo medio pagato in asta (spec sez. 88, Price
    Inflation/Deflation), combinando i miei acquisti e quelli segnati come
    presi dagli avversari — è l'unica traccia di "mercato" che l'app ha
    durante un'asta live, dato che non esiste una fonte esterna che pubblichi
    i prezzi in tempo reale di un'asta privata.

    Ordinato per data e ordine di inserimento: è un proxy dell'ordine
    cronologico reale, non garantito se più acquisti condividono la stessa
    data senza altra informazione temporale."""
    roster = repository.get_roster(conn)
    opponent_picks = repository.get_opponent_picks(conn)

    transactions = [
        {"date_added": r["date_added"], "id": r["id"], "price_paid": r["price_paid"],
         "role_classic": r["role_classic"], "canonical_name": r["canonical_name"],
         "player_id": r["player_id"], "team": r["team"], "source": "me", "opponent_name": None}
        for r in roster
    ] + [
        {"date_added": o["date_added"], "id": o["id"], "price_paid": o["price_paid"],
         "role_classic": o["role_classic"], "canonical_name": o["canonical_name"],
         "player_id": o["player_id"], "team": o["team"], "source": "opponent",
         "opponent_name": o["opponent_name"]}
        for o in opponent_picks
    ]
    transactions.sort(key=lambda t: (t["date_added"], t["id"]))

    running = []
    total, count = 0.0, 0
    role_totals = {role: 0.0 for role in ROLE_ORDER}
    role_counts = {role: 0 for role in ROLE_ORDER}
    for i, t in enumerate(transactions, start=1):
        price = t["price_paid"] or 0
        total += price
        count += 1
        role = t["role_classic"]
        if role in role_totals:
            role_totals[role] += price
            role_counts[role] += 1

        row = {"Acquisto": i, "Prezzo medio": round(total / count, 2)}
        for role in ROLE_ORDER:
            row[f"Prezzo medio {role}"] = (
                round(role_totals[role] / role_counts[role], 2) if role_counts[role] else None
            )
        running.append(row)

    return {"transactions": transactions, "running": running}


def get_purchase_history(conn, mine_only: bool = False) -> list:
    """Storico di tutti gli acquisti registrati (miei + avversari), più
    recenti prima. `mine_only` filtra ai soli giocatori presi da me."""
    trend = get_auction_price_trend(conn)
    transactions = trend["transactions"]
    if mine_only:
        transactions = [t for t in transactions if t["source"] == "me"]
    return sorted(transactions, key=lambda t: (t["date_added"], t["id"]), reverse=True)


def get_auction_intelligence(conn, player_id: int, current_bid: float = None) -> dict:
    """Auction Intelligence Engine (spec sez. 84-99): quanto conviene
    realisticamente offrire per questo giocatore *adesso*, non un fair price
    statico. Costruita solo sui dati che l'app ha davvero durante un'asta
    vocale/in presenza — acquisti miei e "presi dagli avversari" registrati a
    mano — senza presupporre un feed live dei rilanci."""
    from ranking.budget import compute_budget_summary
    from ranking.auction_intelligence import (
        compute_price_inflation, compute_expected_auction_price,
        compute_scarcity_tier, compute_dynamic_max_bid, compute_price_distribution,
        compute_all_opponent_models, compute_auction_timing,
    )

    player = get_player_detail(conn, player_id)
    if not player:
        return None
    fair_price = player.get("price_current")
    role = player["role_classic"]

    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)
    budget_remaining = summary["remaining"]
    slot = summary["slots"][role]
    total_slots_remaining = sum(s["remaining"] for s in summary["slots"].values())

    role_rows = get_ranked_role(conn, role)
    alternatives_remaining = len([
        r for r in role_rows
        if r["player_id"] != player_id and not r.get("is_in_roster") and not r.get("taken_by")
        and (fair_price or 0) > 0 and (r.get("score") or 0) >= 0.85 * (player.get("score") or 0)
    ])
    scarcity = compute_scarcity_tier(alternatives_remaining)

    # Fair price per player across *every* role, for the inflation calc below
    # — one cheap aggregate pass (like get_monitoring_data) instead of a full
    # get_ranked_role() per role, which would re-run ranking/FCP/roster joins
    # for ~700 players four more times on every single page load.
    weights = repository.get_source_weights(conn)
    stats_weights = repository.get_source_stats_weights(conn)
    all_rows = repository.get_all_latest_quotations(conn)
    all_merged = _merge_player_rows(all_rows, weights, stats_weights=stats_weights)
    all_fair_prices = {r["player_id"]: r.get("price_current") for r in all_merged}

    transactions = get_purchase_history(conn)
    purchases = [
        {"price_paid": t["price_paid"], "fair_price": all_fair_prices.get(t["player_id"])}
        for t in transactions
    ]
    inflation = compute_price_inflation(purchases)
    inflation_pct = inflation["inflation_pct"]

    expected_price = compute_expected_auction_price(fair_price, inflation_pct)
    max_bid = compute_dynamic_max_bid(
        fair_price, budget_remaining, total_slots_remaining,
        inflation_pct=inflation_pct, alternatives_remaining=alternatives_remaining,
    )

    price_ratios = [
        p["price_paid"] / p["fair_price"] for p in purchases
        if p["fair_price"] and p["fair_price"] > 0
    ]
    distribution = compute_price_distribution(fair_price, price_ratios)

    timing = compute_auction_timing(
        slot["remaining"], scarcity, inflation_pct, budget_remaining, fair_price,
    )

    opponents = compute_all_opponent_models(repository.get_opponent_picks(conn))

    overbid = None
    if current_bid and expected_price:
        overbid_pct = round((current_bid - expected_price) / expected_price * 100, 1)
        if overbid_pct > 15:
            overbid = {"overbid_pct": overbid_pct, "alert": True}
        else:
            overbid = {"overbid_pct": overbid_pct, "alert": False}

    return {
        "fair_price": fair_price,
        "expected_auction_price": expected_price,
        "max_bid": max_bid,
        "inflation": inflation,
        "scarcity": scarcity,
        "distribution": distribution,
        "timing": timing,
        "opponents": opponents,
        "overbid": overbid,
        "budget_remaining": budget_remaining,
        "slot": slot,
    }


def evaluate_player_purchase(conn, player_id: int, price: float) -> dict:
    """Valutazione 'ne vale la pena?' per `player_id` al prezzo ipotetico
    `price`: vedi ranking.purchase_advisor.evaluate_purchase per i criteri."""
    from ranking.budget import compute_budget_summary
    from ranking.purchase_advisor import evaluate_purchase

    player = get_player_detail(conn, player_id)
    if not player:
        return None

    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)
    slot = summary["slots"][player["role_classic"]]

    role_rows = get_ranked_role(conn, player["role_classic"])
    roster_role_scores = [r["score"] for r in role_rows if r.get("is_in_roster")]

    return evaluate_purchase(player, price, slot, roster_role_scores)


def get_team_strength(conn, team: str):
    """xG/xGA/PPDA più recenti per una squadra (scrapers.fantanalisi_squadre,
    dati Understat) — None se non ancora scrappata o senza storico Understat
    (es. neopromossa)."""
    return repository.get_all_latest_team_strength(conn).get(team)


def get_price_recommendation(conn, player_id: int) -> dict:
    """Price Engine (ranking.price_engine) per un singolo giocatore, alla sua
    quotazione attuale — fair price/prezzo massimo/BUY-PASS mostrati nella
    scheda giocatore. None se il giocatore non esiste o non ha un prezzo."""
    from ranking.scarcity import compute_scarcity
    from ranking.replacement import compute_replacement_advantage
    from ranking.price_engine import compute_price_recommendation as _compute

    player = get_player_detail(conn, player_id)
    if not player or player.get("price_current") is None:
        return None

    role_rows = get_ranked_role(conn, player["role_classic"])
    available = [r for r in role_rows if not r.get("is_in_roster") and not r.get("taken_by")]
    # Il giocatore valutato potrebbe già essere mio/preso da un avversario
    # (scheda consultata dopo l'acquisto): includilo comunque nel confronto,
    # altrimenti scarcity/replacement lo tratterebbero come inesistente.
    if not any(r["player_id"] == player_id for r in available):
        available = available + [player]

    median_vfm = _median([r.get("value_for_money") for r in available])
    scarcity = compute_scarcity(player, available)
    replacement_advantage = compute_replacement_advantage(player, available)

    return _compute(
        player["score"], player["price_current"], median_vfm,
        scarcity, replacement_advantage,
    )


DECISION_BUCKETS = ("evita", "buy", "differenziale", "attendi")

DECISION_BUCKET_LABELS = {
    "buy": "🟢 Compra",
    "differenziale": "🟢 Differenziale",
    "attendi": "🟡 Attendi",
    "evita": "🔴 Evita",
}


def _median(values: list):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def get_decision_center(conn, limit_per_bucket: int = 3) -> dict:
    """Decision Center (spec impossibile-analisi-avanzata.md sez. 8): per
    ogni ruolo, i migliori candidati disponibili e acquistabili col budget
    residuo, classificati in Compra/Differenziale/Attendi/Evita usando Price
    Engine + Scarcity + Replacement Level + Marginal Squad Value. Stessa base
    di candidati di get_squad_suggestions (disponibili, non in rosa, non
    presi da avversari, prezzo entro il budget residuo, non chiari
    riserve senza minutaggio)."""
    from ranking.budget import compute_budget_summary
    from ranking.tiers import classify_role, DA_EVITARE, TOP
    from ranking.scarcity import compute_scarcity
    from ranking.replacement import compute_replacement_advantage
    from ranking.price_engine import compute_price_recommendation, BUY as PRICE_BUY, BORDERLINE
    from ranking.purchase_advisor import compute_marginal_squad_value

    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)

    result = {bucket: [] for bucket in DECISION_BUCKETS}

    for role, slot in summary["slots"].items():
        role_rows = get_ranked_role(conn, role)
        available = [r for r in role_rows if not r.get("is_in_roster") and not r.get("taken_by")]
        if not available:
            continue

        tiers = classify_role(role_rows)
        da_evitare_ids = {r["player_id"] for r in tiers.get(DA_EVITARE, [])}
        top_ids = {r["player_id"] for r in tiers.get(TOP, [])}

        median_vfm = _median([r.get("value_for_money") for r in available])
        median_price = _median([r.get("price_current") for r in available])
        roster_role_scores = [r["score"] for r in role_rows if r.get("is_in_roster")]

        candidates = [
            r for r in available
            if r.get("price_current") is not None
            and (slot["remaining"] <= 0 or r["price_current"] <= summary["remaining"])
            and (r.get("appearances") is None or r["appearances"] >= RELIABLE_APPEARANCES_MIN)
        ]

        for r in candidates:
            player_id = r["player_id"]
            scarcity = compute_scarcity(r, available)
            replacement_advantage = compute_replacement_advantage(r, available)
            price_rec = compute_price_recommendation(
                r["score"], r["price_current"], median_vfm, scarcity, replacement_advantage,
            )
            marginal_value = compute_marginal_squad_value(r, slot, roster_role_scores)

            entry = {
                **r,
                "scarcity": scarcity,
                "replacement_advantage": replacement_advantage,
                "marginal_squad_value": marginal_value,
                **{f"price_{k}": v for k, v in price_rec.items()},
            }

            if player_id in da_evitare_ids:
                entry["reason"] = "Nel tier 'Da evitare' del ruolo."
                result["evita"].append(entry)
            elif price_rec["status"] == PRICE_BUY and marginal_value > 0:
                entry["reason"] = (
                    f"Prezzo entro il max consigliato ({format_count(price_rec['max_price'])}) "
                    f"e migliora davvero la tua rosa (+{format_count(marginal_value)} rispetto "
                    "al tuo titolare più debole in questo ruolo)."
                    if slot["remaining"] <= 0 else
                    f"Prezzo entro il max consigliato ({format_count(price_rec['max_price'])})."
                )
                result["buy"].append(entry)
            elif (
                r.get("value_for_money_percentile") is not None
                and r["value_for_money_percentile"] >= 80
                and median_price is not None and r["price_current"] <= median_price
                and player_id not in top_ids
            ):
                entry["reason"] = (
                    "Rapporto qualità/prezzo tra i migliori del ruolo, prezzo sotto la "
                    "mediana, non già tra i big più scontati — occasione, non ovvio."
                )
                result["differenziale"].append(entry)
            elif price_rec["status"] == BORDERLINE:
                entry["reason"] = (
                    f"Poco sopra il prezzo massimo consigliato "
                    f"({format_count(price_rec['max_price'])}): valutalo se il prezzo scende."
                )
                result["attendi"].append(entry)

    for bucket in DECISION_BUCKETS:
        result[bucket].sort(key=lambda r: r.get("decision_score", r["score"]), reverse=True)
        result[bucket] = result[bucket][:limit_per_bucket]

    return result


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
