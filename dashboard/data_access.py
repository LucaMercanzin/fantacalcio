from db import repository
from ranking.scorer import rank_players

PROMOTED_TEAMS = {"VEN", "Venezia", "FRO", "Frosinone", "MON", "Monza"}


def get_ranked_role(conn, role_classic: str) -> list:
    rows = repository.get_latest_quotations(conn, role_classic)
    ranked = rank_players(rows)

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}

    for row in ranked:
        row["notes"] = repository.get_player_notes(conn, row["player_id"]) or ""
        row["is_in_roster"] = row["player_id"] in roster_player_ids
        row["is_promoted"] = row["team"] in PROMOTED_TEAMS

    return ranked


def search_and_sort(rows: list, query: str, sort_by: str) -> list:
    filtered = rows
    if query:
        query_lower = query.lower()
        filtered = [r for r in rows if query_lower in r["canonical_name"].lower()]

    if sort_by == "team":
        filtered = sorted(filtered, key=lambda r: r["team"])
    elif sort_by == "price":
        filtered = sorted(filtered, key=lambda r: r["price_current"] or 0, reverse=True)

    non_promoted = [r for r in filtered if not r.get("is_promoted")]
    promoted = [r for r in filtered if r.get("is_promoted")]
    return non_promoted + promoted


def find_player_by_name(conn, name: str):
    cursor = conn.execute(
        "SELECT * FROM players WHERE LOWER(canonical_name) = LOWER(?)", (name,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None
