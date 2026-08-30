"""Compares one player's core Fantacalcio metrics against the rest of his
role (statistiche giocatore sez. 24: "Confronto con il ruolo"). Pure
function over get_ranked_role's already-scored output — uses the same
ranking.percentile.percentile_rank as ranking.tiers, so a player is always
compared against role-mates only (a difensore never against attaccanti)."""

from ranking.percentile import percentile_rank

METRICS = {
    "fantamedia": "Fantamedia",
    "score": "Fantasy Value",
    "season_goals_scored": "Gol",
    "season_assists": "Assist",
    "appearances": "Presenze",
}


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
            "percentile": percentile_rank(player_value, sorted(values)),
        }
    return comparison
