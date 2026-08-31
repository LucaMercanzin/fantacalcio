from datetime import date

import streamlit as st

from config import DEFAULT_FORMATION, TOTAL_CREDITS
from consensus.engine import (
    DEFAULT_LISTINO_TO_AUCTION_FACTOR,
    _merge_player_rows,
    compute_listino_to_auction_factor,
    compute_source_scale_factors,
)
from db import repository
from matching.player_matcher import normalize_team
from pipeline.validation import compute_field_coverage
from ranking.role_comparison import compute_role_comparison
from ranking.scorer import enrich_scores, rank_players
from ranking.tiers import classify_role

# The 20 real Serie A 2026/27 clubs — USER-VERIFIED, do not "correct".
# Venezia/Frosinone/Monza are the promoted sides for 2026/27 (verified against
# the current Serie A standings in docs/superpowers/plans/2026-08-27-portieri-
# depth-chart.md and by the project owner). The opus review's "P0-006" claimed
# Cremonese/Pisa/Verona belong here instead — that was a false positive and
# MUST NOT be reapplied to this list.
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
        # TASK-011b: ranking.scorer._starter_probability's fallback for a
        # player with no real `appearances` yet (a new arrival).
        row["predicted_appearances"] = metrics["predicted_appearances"]
    return rows


def _attach_tactical_profile_inputs(rows: list, conn) -> list:
    """Merges season goals/assists/goals-conceded (player_season_stats),
    set-piece hierarchy (player_set_pieces) and team defensive strength
    (team_strength) into each row — the data sources
    ranking.tactical_profile.compute_tactical_profile_score and
    ranking.goalkeeper_score.compute_goalkeeper_score need on top of
    role_mantra (already on the row from the players table join) and the
    predicted_goals/predicted_assists _attach_fcp_metrics adds above."""
    season_stats_by_player = repository.get_all_latest_player_season_stats(conn)
    set_pieces_by_player = repository.get_all_player_set_pieces(conn)
    # Keyed by normalize_team(), not the raw team_strength.team string:
    # players.team (this row's own "team") arrives here in whatever
    # casing/abbreviation its winning source used ("GEN"/"GENOA"/"Genoa"
    # all appear in the real DB), while team_strength stores the clean
    # full name — a raw-string lookup would miss most of them.
    team_strength_by_code = {
        normalize_team(team): row for team, row in repository.get_all_latest_team_strength(conn).items()
    }
    for row in rows:
        season_stats = season_stats_by_player.get(row["player_id"])
        row["season_goals_scored"] = season_stats["goals_scored"] if season_stats else None
        row["season_assists"] = season_stats["assists"] if season_stats else None
        row["season_goals_conceded"] = season_stats["goals_conceded"] if season_stats else None
        row["set_pieces"] = set_pieces_by_player.get(row["player_id"], [])
        # team_strength and quotations are scraped on separate runs/dates
        # (real DB: team_strength 2026-08-27 vs quotations 2026-08-26) — a
        # one-day-or-so mismatch, same caveat as TASK-008 for season/
        # competition context, not something this merge corrects for.
        team_strength = team_strength_by_code.get(normalize_team(row.get("team") or ""))
        row["team_xg"] = team_strength["xg"] if team_strength else None
        row["team_xga"] = team_strength["xga"] if team_strength else None
    return rows


def _build_player_rows(conn, rows: list, weights: dict, stats_weights: dict) -> list:
    """The single place that turns raw per-source quotation rows into fully
    merged player rows (consensus + FCP metrics + tactical-profile inputs).
    Both _compute_ranked_role and get_player_detail must go through this so
    the same player's Fantasy Value never differs between the role ranking
    and its own detail page (see P1-003 in OPUS_PROJECT_REVIEW.md)."""
    scale_factors = compute_source_scale_factors(repository.get_source_price_ceiling(conn))
    factor = compute_listino_to_auction_factor(repository.get_all_latest_quotations(conn), scale_factors)
    match_confidences = repository.get_all_match_confidences(conn)
    rows = _merge_player_rows(
        rows, weights, stats_weights=stats_weights, source_scale_factors=scale_factors,
        listino_to_auction_factor=factor, match_confidences=match_confidences,
    )
    rows = _attach_fcp_metrics(rows, conn)
    rows = _attach_tactical_profile_inputs(rows, conn)
    return rows


@st.cache_data(ttl=3600, show_spinner="Calcolo ranking...")
def _compute_ranked_role(
    _conn, role_classic: str, data_version: tuple, require_reliable_appearances: bool = True,
) -> tuple:
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

    require_reliable_appearances=False (get_goalkeeper_pool) skips the
    RELIABLE_APPEARANCES_MIN gate below. That gate is right for a role page
    with hundreds of outfield alternatives (hide deep-bench clutter), but a
    team only ever has 2-5 portieri total, so there's no clutter to prevent
    — and at the start of a season it silently erases exactly the keeper a
    depth chart most needs: one promoted to starter or back from loan, whose
    *last* season's appearances (low but known, e.g. 0-14) say nothing about
    this season's role. Verified on the real DB (2026-08-30): Lazio's whole
    entry disappeared from the depth chart because both Mandas (0 appearances
    — on loan all of 2025/26) and Motta (14, one short of the 15 threshold)
    were excluded here, before ever reaching scoring. rank_players' own
    estimate_fantamedia price-based fallback (TASK-011b) already scores a
    fantamedia-less keeper like Mandas once he isn't filtered out here first
    — no scoring change needed, only this gate.

    Returns (ranked, insufficient_data) — see ranking.scorer.rank_players.
    """
    weights = repository.get_source_weights(_conn)
    stats_weights = repository.get_source_stats_weights(_conn)
    rows = repository.get_latest_quotations(_conn, role_classic)
    rows = _build_player_rows(_conn, rows, weights, stats_weights)
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
            not require_reliable_appearances
            or (r.get("appearances") is not None and r["appearances"] >= RELIABLE_APPEARANCES_MIN)
            or (
                r.get("appearances") is None
                and (r.get("fantamedia") is not None or r.get("avg_rating") is not None)
            )
        )
    ]
    return rank_players(rows)


def _enrich_role_rows(conn, rows: list) -> list:
    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}
    taken_by = {p["player_id"]: p["opponent_name"] for p in repository.get_opponent_picks(conn)}
    notes_by_player = repository.get_all_player_notes(conn)
    for row in rows:
        row["notes"] = notes_by_player.get(row["player_id"]) or ""
        row["is_in_roster"] = row["player_id"] in roster_player_ids
        row["is_promoted"] = normalize_team(row["team"] or "") in PROMOTED_TEAM_CODES
        row["taken_by"] = taken_by.get(row["player_id"])
        row["team"] = normalize_team_name(row["team"])
    return rows


def _role_version(conn, role_classic: str) -> tuple:
    # The database file path guards against version-tuple collisions between
    # distinct databases that happen to be at the same row-count/id stage
    # (e.g. two freshly-created test databases each holding a handful of
    # rows) — real usage only ever points at one persistent .db file, so this
    # never affects production, only test isolation. id(conn) was tried first
    # but CPython can reuse a garbage-collected Connection's address for an
    # unrelated one within the same test run, causing exactly this collision.
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    return (db_path, repository.get_data_version(conn))


def get_ranked_role(conn, role_classic: str) -> list:
    ranked, _insufficient_data = _compute_ranked_role(conn, role_classic, _role_version(conn, role_classic))
    return _enrich_role_rows(conn, ranked)


def get_insufficient_data_players(conn, role_classic: str) -> list:
    """Players _compute_ranked_role could merge but couldn't score — no real
    fantamedia (P0-002/TASK-002). Excluded from get_ranked_role's ordering
    and from every tier (ranking.tiers.classify_role), but still worth
    showing somewhere rather than silently vanishing: "no data" must not
    read as "no problem" (TASK-004)."""
    _ranked, insufficient_data = _compute_ranked_role(conn, role_classic, _role_version(conn, role_classic))
    return _enrich_role_rows(conn, insufficient_data)


def get_goalkeeper_pool(conn) -> list:
    """Every portiere on a current Serie A team with >=MIN_SOURCES_REQUIRED
    sources, WITHOUT get_ranked_role's RELIABLE_APPEARANCES_MIN gate — see
    _compute_ranked_role's require_reliable_appearances docstring for why
    that gate is wrong for a depth chart specifically (portieri.md; the
    Lazio-disappears bug this fixes). Used only by
    dashboard.components.render_goalkeeper_depth_chart, never by the generic
    role pages, which keep the gate."""
    ranked, _insufficient_data = _compute_ranked_role(
        conn, "P", _role_version(conn, "P"), require_reliable_appearances=False,
    )
    return _enrich_role_rows(conn, ranked)


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


def get_fixture_difficulty(conn, team: str) -> dict:
    """Difficoltà calendario "prime 5 giornate" (0-100, più alto = più
    morbido) per team — normalize_team_name(row["team"]) prima di chiamare,
    la tabella è keyed sul nome canonico completo come team_strength."""
    all_teams = repository.get_all_latest_team_fixture_difficulty(conn)
    return all_teams.get(team)


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
    merged_rows = _build_player_rows(conn, rows, weights, stats_weights)
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
    # used to rank this player. score/value_for_money/tactical_profile_score
    # are population-relative too since TASK-011b (compute_score's tactical
    # nudge is centered on the role's observed median, not a flat constant —
    # see ranking.scorer.compute_neutral_tactical_profiles), so they need
    # the same override or the detail page silently disagrees with the role
    # page again (P1-003, the exact bug this pattern already exists to fix).
    role_match = next((r for r in role_rows if r["player_id"] == player_id), None)
    if role_match:
        merged["score"] = role_match["score"]
        merged["insufficient_data"] = role_match["insufficient_data"]
        merged["estimated"] = role_match["estimated"]
        merged["tactical_profile_score"] = role_match["tactical_profile_score"]
        merged["value_for_money"] = role_match["value_for_money"]
        merged["decision_score"] = role_match["decision_score"]
        merged["value_for_money_percentile"] = role_match["value_for_money_percentile"]

    tiers = classify_role(role_rows)
    merged["tier"] = next(
        (tier for tier, players in tiers.items()
         if any(p["player_id"] == player_id for p in players)),
        None,
    )

    merged["role_comparison"] = compute_role_comparison(role_rows, player_id)
    merged["advanced_stats"] = repository.get_latest_player_advanced_stats(conn, player_id)
    merged["fantanalisi_valuation"] = repository.get_latest_player_fantanalisi_valuation(
        conn, player_id,
    )

    return merged


# A table whose last write is older than this, relative to the freshest write
# seen anywhere in the DB, is "stale" (🟡) rather than "fresh" (🟢) — chosen
# because the scraping pipeline is expected to run at least this often; not
# derived from data, so revisit if the real run cadence turns out different.
TABLE_HEALTH_STALE_DAYS = 3


def _table_health_status(row: dict, reference_date) -> str:
    """🔴 the pipeline that owns this table has never written a row (P0-008:
    the case that used to be silently indistinguishable from "no problem").
    🟡 it has rows but either has no reliable freshness column or hasn't been
    refreshed in a while. 🟢 populated and recently refreshed."""
    if row["row_count"] == 0:
        return "red"
    if row["last_update"] is None or reference_date is None:
        return "yellow"
    try:
        last = date.fromisoformat(row["last_update"][:10])
    except ValueError:
        return "yellow"
    if (reference_date - last).days > TABLE_HEALTH_STALE_DAYS:
        return "yellow"
    return "green"


# Retuned for the IQR/median price_agreement formula (TASK-010 point 4):
# that formula is systematically less punishing than the old (max-min)/mean
# range for the typical 2-3-source player, so the old 50 threshold flagged
# far more players than "actually worth a manual look" — see the real-DB
# distribution check in the TASK-010 commit.
LOW_PRICE_AGREEMENT_THRESHOLD = 35


def get_monitoring_data(conn) -> dict:
    """Data-health snapshot for the admin monitoring page: per-source freshness/
    volume, price-agreement distribution, and which players currently have
    a flagged outlier source (see sections 6/7/9/172 of imperfezioni.md)."""
    weights = repository.get_source_weights(conn)
    stats_weights = repository.get_source_stats_weights(conn)
    source_stats = repository.get_source_stats(conn)
    scale_factors = compute_source_scale_factors(repository.get_source_price_ceiling(conn))

    rows = repository.get_all_latest_quotations(conn)
    factor = compute_listino_to_auction_factor(rows, scale_factors)
    match_confidences = repository.get_all_match_confidences(conn)
    merged = _merge_player_rows(
        rows, weights, stats_weights=stats_weights, source_scale_factors=scale_factors,
        listino_to_auction_factor=factor, match_confidences=match_confidences,
    )

    agreements = [m["price_agreement"] for m in merged if m.get("price_agreement") is not None]
    avg_confidence = round(sum(agreements) / len(agreements), 1) if agreements else None
    low_confidence_players = sorted(
        (m for m in merged if m.get("price_agreement") is not None
         and m["price_agreement"] < LOW_PRICE_AGREEMENT_THRESHOLD),
        key=lambda m: m["price_agreement"],
    )
    outlier_players = [m for m in merged if m.get("price_outlier_sources")]
    appearances_disagreement_players = [m for m in merged if m.get("appearances_disagreement")]

    table_health = repository.get_table_health(conn)
    reference_dates = [
        date.fromisoformat(h["last_update"][:10])
        for h in table_health if h["last_update"]
    ]
    reference_date = max(reference_dates) if reference_dates else None
    for h in table_health:
        h["status"] = _table_health_status(h, reference_date)

    field_coverage = compute_field_coverage(conn)

    return {
        "weights": weights,
        "stats_weights": stats_weights,
        "source_stats": source_stats,
        "total_players": len(merged),
        "avg_confidence": avg_confidence,
        "low_confidence_players": low_confidence_players,
        "outlier_players": outlier_players,
        "appearances_disagreement_players": appearances_disagreement_players,
        "table_health": table_health,
        "field_coverage": field_coverage,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_data_freshness_summary(_conn, data_version: tuple) -> dict:
    """The actual computation behind get_data_freshness_summary — split out
    so it's cached on data_version (repository.get_data_version) rather
    than recomputed on every page/rerun (DA5/TASK-028): reused across all 7
    pages' top banner within one data version, same pattern as
    _compute_ranked_role. reference_date/source counts are cheap SQL
    aggregates; valutati/esclusi reuse get_ranked_role/
    get_insufficient_data_players, themselves already cached per role, so
    visiting a role page and seeing this banner never pays for that role's
    ranking twice."""
    source_stats = repository.get_source_stats(_conn)
    reference_date = max((s["last_update"] for s in source_stats), default=None)
    sources_fresh = sum(1 for s in source_stats if s["last_update"] == reference_date)

    valutati = 0
    esclusi = 0
    for role in ROLE_ORDER:
        valutati += len(get_ranked_role(_conn, role))
        esclusi += len(get_insufficient_data_players(_conn, role))

    return {
        "reference_date": reference_date,
        "sources_fresh": sources_fresh,
        "sources_total": len(source_stats),
        "players_valutati": valutati,
        "players_esclusi": esclusi,
    }


def get_data_freshness_summary(conn) -> dict:
    """Sez. DA5/TASK-028: "dati al 26/08, 6 fonti su 6, 407 giocatori
    valutati, 396 esclusi per dati insufficienti" — shown at the top of
    every page (rendered from get_db_connection, same as the budget bar),
    not only on the separate Monitoraggio page a user mid-auction has no
    reason to open."""
    return _cached_data_freshness_summary(conn, repository.get_data_version(conn))


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
            and r["price_current"] <= summary["spendable"]
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


def get_ideal_formation(conn, formation_name: str = DEFAULT_FORMATION) -> dict:
    """Rosa Ideale schierata in campo: gli 11 titolari migliori per ruolo
    nella formazione data, dando priorità ai giocatori già in rosa (restano
    titolari) ed escludendo quelli presi dagli avversari — se un titolare
    viene preso da un avversario, il prossimo migliore libero per quel ruolo
    ne prende automaticamente il posto."""
    from ranking.budget import compute_budget_summary
    from ranking.ideal_squad import FORMATIONS, build_ideal_squad

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
        players_by_role, formation, summary["spendable"], roster_ids, taken_ids,
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
    from ranking.lp_optimizer import ROLE_SLOTS, build_optimal_squad

    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)
    taken_ids = {p["player_id"] for p in repository.get_opponent_picks(conn)}

    players_by_role = {role: get_ranked_role(conn, role) for role in ROLE_SLOTS}

    if mode == "from_scratch":
        return build_optimal_squad(
            players_by_role, TOTAL_CREDITS, [], taken_ids, mode="from_scratch",
        )
    return build_optimal_squad(
        players_by_role, summary["spendable"], roster, taken_ids, mode="constrained",
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


def _compute_league_inflation(conn) -> tuple:
    """Inflazione osservata sull'asta (ranking.auction_intelligence.
    compute_price_inflation) — un solo calcolo lega-wide, riusato sia da
    get_auction_intelligence (un giocatore) sia da get_decision_center
    (tutti i candidati, TASK-015): la stessa fonte di verità sull'inflazione
    per entrambi, non due calcoli leggermente diversi.

    Ritorna (inflation, purchases): purchases (price_paid/fair_price per
    acquisto registrato) è già quanto serve a compute_price_distribution,
    così get_auction_intelligence non deve ripetere l'aggregazione."""
    from ranking.auction_intelligence import compute_price_inflation

    weights = repository.get_source_weights(conn)
    stats_weights = repository.get_source_stats_weights(conn)
    scale_factors = compute_source_scale_factors(repository.get_source_price_ceiling(conn))
    all_rows = repository.get_all_latest_quotations(conn)
    factor = compute_listino_to_auction_factor(all_rows, scale_factors)
    all_merged = _merge_player_rows(
        all_rows, weights, stats_weights=stats_weights, source_scale_factors=scale_factors,
        listino_to_auction_factor=factor,
    )
    all_fair_prices = {r["player_id"]: r.get("price_current") for r in all_merged}

    transactions = get_purchase_history(conn)
    purchases = [
        {"price_paid": t["price_paid"], "fair_price": all_fair_prices.get(t["player_id"])}
        for t in transactions
    ]
    return compute_price_inflation(purchases), purchases


def get_auction_intelligence(conn, player_id: int, current_bid: float | None = None) -> dict:
    """Auction Intelligence Engine (spec sez. 84-99): quanto conviene
    realisticamente offrire per questo giocatore *adesso*, non un fair price
    statico. Costruita solo sui dati che l'app ha davvero durante un'asta
    vocale/in presenza — acquisti miei e "presi dagli avversari" registrati a
    mano — senza presupporre un feed live dei rilanci."""
    from ranking.auction_intelligence import (
        compute_all_opponent_models,
        compute_auction_timing,
        compute_dynamic_max_bid,
        compute_expected_auction_price,
        compute_price_distribution,
        compute_scarcity_tier,
    )
    from ranking.budget import compute_budget_summary

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

    if not fair_price:
        # P1-011/TASK-018: `(fair_price or 0) > 0` below used to be a
        # constant inside the comprehension (it doesn't depend on `r`), so a
        # missing fair_price on *this* player made alternatives_remaining=0
        # for everyone — the strongest possible "Scarsità Critica / BUY NOW"
        # signal, triggered by the one case where there's no price to act
        # on. Fail loudly instead: no price, no auction advice.
        return {
            "fair_price": None, "expected_auction_price": None, "max_bid": None,
            "inflation": {"inflation_pct": None}, "scarcity": None,
            "distribution": None,
            "timing": {"action": "no_data", "label": "Dati insufficienti",
                       "reason": "Prezzo di consenso non disponibile: nessun consiglio d'asta."},
            "opponents": [], "overbid": None,
            "budget_remaining": budget_remaining, "slot": slot,
        }

    role_rows = get_ranked_role(conn, role)
    alternatives_remaining = len([
        r for r in role_rows
        if r["player_id"] != player_id and not r.get("is_in_roster") and not r.get("taken_by")
        and (r.get("score") or 0) >= 0.85 * (player.get("score") or 0)
    ])
    scarcity = compute_scarcity_tier(alternatives_remaining)

    inflation, purchases = _compute_league_inflation(conn)
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


def get_value_index(conn, player_id: int):
    """Value Index (ranking.price_engine, TASK-015/P1-004): quanto rende
    questo giocatore per credito speso rispetto alla mediana del ruolo
    ancora disponibile — 100 = esattamente la mediana, 130 = 30% più
    efficiente. Non più un secondo "prezzo massimo" in crediti (rimosso:
    contraddiceva sistematicamente quello di Auction Intelligence, l'unica
    fonte rimasta per "quanto posso offrire"). None se il giocatore non
    esiste o non ha un prezzo."""
    from ranking.price_engine import compute_value_index

    player = get_player_detail(conn, player_id)
    if not player or player.get("price_current") is None:
        return None

    role_rows = get_ranked_role(conn, player["role_classic"])
    available = [r for r in role_rows if not r.get("is_in_roster") and not r.get("taken_by")]
    # Il giocatore valutato potrebbe già essere mio/preso da un avversario
    # (scheda consultata dopo l'acquisto): includilo comunque nel confronto,
    # altrimenti la mediana lo tratterebbe come inesistente.
    if not any(r["player_id"] == player_id for r in available):
        available = available + [player]

    median_vfm = _median([r.get("value_for_money") for r in available])
    return compute_value_index(player.get("value_for_money"), median_vfm)


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
    residuo, classificati in Compra/Differenziale/Attendi/Evita usando
    Auction Intelligence (scarsità + inflazione + max bid dinamico, TASK-015
    — non più il vecchio Price Engine, che dava un secondo "prezzo massimo"
    sistematicamente diverso da questo) + Marginal Squad Value. Stessa base
    di candidati di get_squad_suggestions (disponibili, non in rosa, non
    presi da avversari, prezzo entro il budget residuo, non chiari
    riserve senza minutaggio)."""
    from ranking.auction_intelligence import (
        compute_auction_timing,
        compute_dynamic_max_bid,
        compute_scarcity_tier,
    )
    from ranking.budget import compute_budget_summary
    from ranking.purchase_advisor import compute_marginal_squad_value
    from ranking.tiers import DA_EVITARE, TOP, classify_role

    roster = repository.get_roster(conn)
    summary = compute_budget_summary(roster)
    total_slots_remaining = sum(s["remaining"] for s in summary["slots"].values())
    inflation, _purchases = _compute_league_inflation(conn)
    inflation_pct = inflation["inflation_pct"]

    result = {bucket: [] for bucket in DECISION_BUCKETS}

    for role, slot in summary["slots"].items():
        role_rows = get_ranked_role(conn, role)
        available = [r for r in role_rows if not r.get("is_in_roster") and not r.get("taken_by")]
        if not available:
            continue

        tiers = classify_role(role_rows)
        da_evitare_ids = {r["player_id"] for r in tiers.get(DA_EVITARE, [])}
        top_ids = {r["player_id"] for r in tiers.get(TOP, [])}

        median_price = _median([r.get("price_current") for r in available])
        roster_role_scores = [r["score"] for r in role_rows if r.get("is_in_roster")]

        candidates = [
            r for r in available
            if r.get("price_current") is not None
            and (slot["remaining"] <= 0 or r["price_current"] <= summary["spendable"])
            and (r.get("appearances") is None or r["appearances"] >= RELIABLE_APPEARANCES_MIN)
        ]

        for r in candidates:
            player_id = r["player_id"]
            alternatives_remaining = len([
                o for o in available
                if o["player_id"] != player_id
                and (o.get("score") or 0) >= 0.85 * (r.get("score") or 0)
            ])
            scarcity_tier = compute_scarcity_tier(alternatives_remaining)
            timing = compute_auction_timing(
                slot["remaining"], scarcity_tier, inflation_pct,
                summary["remaining"], r["price_current"],
            )
            max_bid_info = compute_dynamic_max_bid(
                r["price_current"], summary["remaining"], total_slots_remaining,
                inflation_pct=inflation_pct, alternatives_remaining=alternatives_remaining,
            )
            marginal_value = compute_marginal_squad_value(r, slot, roster_role_scores)

            entry = {
                **r,
                "scarcity_tier": scarcity_tier,
                "marginal_squad_value": marginal_value,
                "auction_timing": timing,
                "auction_max_bid": max_bid_info.get("max_bid"),
            }

            if player_id in da_evitare_ids:
                entry["reason"] = "Nel tier 'Da evitare' del ruolo."
                result["evita"].append(entry)
            elif timing["action"] == "buy_now" and marginal_value > 0:
                entry["reason"] = (
                    f"{timing['reason']} Migliora davvero la tua rosa "
                    f"(+{format_count(marginal_value)} rispetto al tuo titolare più debole "
                    "in questo ruolo)."
                    if slot["remaining"] <= 0 else
                    f"{timing['reason']} Max bid stimato: {format_count(max_bid_info.get('max_bid'))}."
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
            elif timing["action"] == "wait":
                entry["reason"] = timing["reason"]
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
