"""Compares one player's core Fantacalcio metrics against the rest of his
role (statistiche giocatore sez. 24: "Confronto con il ruolo"). Pure
function over get_ranked_role's already-scored output — same bisect-based
percentile approach as ranking.tiers._percentile_rank, so a player is
always compared against role-mates only (a difensore never against
attaccanti)."""

import bisect

METRICS = {
    "fantamedia": "Fantamedia",
    "score": "Fantasy Value",
    "season_goals_scored": "Gol",
    "season_assists": "Assist",
    "appearances": "Presenze",
}


def _percentile_rank(value, sorted_values: list) -> float:
    if not sorted_values:
        return 50.0
    idx = bisect.bisect_left(sorted_values, value)
    return round(idx / len(sorted_values) * 100, 1)


def compute_role_comparison(role_rows: list, player_id) -> dict:
    player_row = next((r for r in role_rows if r["player_id"] == player_id), None)
    if player_row is None:
        return {}

    comparison = {}
    for key, label in METRICS.items():
        player_value = player_row.get(key)
        if player_value is None:
            continue
        values = [r[key] for r in role_rows if r.get(key) is not None]
        role_avg = round(sum(values) / len(values), 1) if values else None
        comparison[key] = {
            "label": label,
            "player": player_value,
            "role_avg": role_avg,
            "percentile": _percentile_rank(player_value, sorted(values)),
        }
    return comparison
