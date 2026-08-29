"""Replacement Level / Replacement Advantage (spec
impossibile-analisi-avanzata.md sez. 7): quanto è realmente migliore questo
giocatore rispetto al livello di "replacement" del suo ruolo — il
sports-analytics term of art per talento liberamente disponibile: il primo
escluso se ogni squadra della lega riempisse i propri slot coi migliori
disponibili, non il singolo miglior avversario (P1-008). Con quest'ultima
definizione l'advantage sarebbe negativo per chiunque non fosse il #1 del
ruolo — mai un segnale utile."""

from config import LEAGUE_TEAMS, ROLE_SLOTS


def compute_replacement_level(role: str, available_role_rows: list,
                               league_teams: int = LEAGUE_TEAMS) -> float:
    """The Nth-best score among available players in this role,
    N = ROLE_SLOTS[role] * league_teams — the score of the best player who'd
    be left on the table once every team in the league has filled that
    role's slots with its best options."""
    scores = sorted(
        (r["score"] for r in available_role_rows if r.get("score") is not None),
        reverse=True,
    )
    if not scores:
        return 0.0
    idx = ROLE_SLOTS[role] * league_teams
    return scores[idx] if idx < len(scores) else scores[-1]


def compute_replacement_advantage(player_row: dict, available_role_rows: list,
                                   league_teams: int = LEAGUE_TEAMS) -> float:
    fantasy_value = player_row.get("score") or 0.0
    role = player_row["role_classic"]
    replacement_level = compute_replacement_level(role, available_role_rows, league_teams)
    return round(fantasy_value - replacement_level, 1)
