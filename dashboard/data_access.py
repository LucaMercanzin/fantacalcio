from db import repository
from ranking.scorer import rank_players, compute_score

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


SOURCE_WEIGHTS = {
    "fantacalcio_it": 3, "fantacalciopedia": 2, "fantapazz": 1.5,
    "pianetafanta": 1.5,
}

AVERAGED_FIELDS = ("price_current", "price_initial", "fantamedia", "avg_rating")
FILLED_FIELDS = ("status", "appearances")


def _weighted_average(player_rows: list, field: str):
    weighted_sum = 0.0
    weight_total = 0.0
    for row in player_rows:
        value = row.get(field)
        if value is None:
            continue
        weight = SOURCE_WEIGHTS.get(row["source"], 1)
        weighted_sum += value * weight
        weight_total += weight
    return round(weighted_sum / weight_total, 2) if weight_total else None


def _merge_player_rows(rows: list) -> list:
    by_player = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row)

    merged = []
    for player_rows in by_player.values():
        result = dict(player_rows[0])
        for field in AVERAGED_FIELDS:
            result[field] = _weighted_average(player_rows, field)
        for field in FILLED_FIELDS:
            result[field] = next(
                (r[field] for r in player_rows if r.get(field) is not None), None
            )
        result["source"] = "+".join(r["source"] for r in player_rows)
        merged.append(result)

    return merged


def get_ranked_role(conn, role_classic: str) -> list:
    rows = repository.get_latest_quotations(conn, role_classic)
    rows = _merge_player_rows(rows)
    ranked = rank_players(rows)

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}

    for row in ranked:
        row["notes"] = repository.get_player_notes(conn, row["player_id"]) or ""
        row["is_in_roster"] = row["player_id"] in roster_player_ids
        row["is_promoted"] = row["team"] in PROMOTED_TEAMS
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


def get_player_detail(conn, player_id: int):
    rows = repository.get_latest_quotations_for_player(conn, player_id)
    if not rows:
        return None

    merged = _merge_player_rows(rows)[0]
    merged["score"] = compute_score(merged)

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}
    merged["notes"] = repository.get_player_notes(conn, player_id) or ""
    merged["is_in_roster"] = player_id in roster_player_ids
    merged["is_promoted"] = merged["team"] in PROMOTED_TEAMS
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


def find_player_by_name(conn, name: str):
    cursor = conn.execute(
        "SELECT * FROM players WHERE LOWER(canonical_name) = LOWER(?)", (name,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None
