from db import repository
from ranking.scorer import rank_players

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


def _merge_player_rows(rows: list) -> list:
    merged = {}
    for row in rows:
        pid = row["player_id"]
        if pid not in merged:
            merged[pid] = dict(row)
            merged[pid]["sources"] = [row["source"]]
            continue
        existing = merged[pid]
        existing["sources"].append(row["source"])
        for field in ("price_current", "price_initial", "status", "fantamedia",
                      "avg_rating", "appearances"):
            if existing.get(field) is None and row.get(field) is not None:
                existing[field] = row[field]

    for player in merged.values():
        player["source"] = "+".join(player["sources"])

    return list(merged.values())


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


def find_player_by_name(conn, name: str):
    cursor = conn.execute(
        "SELECT * FROM players WHERE LOWER(canonical_name) = LOWER(?)", (name,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None
