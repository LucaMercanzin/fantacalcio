"""Replacement Level / Replacement Advantage (spec
impossibile-analisi-avanzata.md sez. 7): quanto è realmente migliore questo
giocatore rispetto alla migliore alternativa disponibile nel suo ruolo.

Semplificazione dichiarata: "migliore alternativa" = il più alto Fantasy
Value tra gli altri disponibili nel ruolo, senza filtrare per prezzo/budget
residuo — una versione "solo alternative realisticamente acquistabili"
è rimandabile a un secondo giro se questo segnale si rivela troppo grezzo."""


def compute_replacement_level(player_row: dict, available_role_rows: list) -> float:
    others = [
        r["score"] for r in available_role_rows
        if r["player_id"] != player_row["player_id"]
    ]
    return max(others) if others else 0.0


def compute_replacement_advantage(player_row: dict, available_role_rows: list) -> float:
    fantasy_value = player_row.get("score") or 0.0
    return round(fantasy_value - compute_replacement_level(player_row, available_role_rows), 1)
