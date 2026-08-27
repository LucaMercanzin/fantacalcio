"""Scarcity Score: quanto è difficile sostituire un giocatore con
un'alternativa comparabile ancora disponibile nel suo ruolo (spec
impossibile-analisi-avanzata.md sez. 6) — calcolabile oggi da decision_score,
nessun dato di tracking/xG richiesto."""

import math

# Un'alternativa conta come "comparabile" se il suo decision_score è almeno
# il 90% di quello del giocatore — non serve essere identici, solo abbastanza
# vicini da poter essere una vera scelta alternativa in asta.
COMPARABLE_RATIO = 0.9

# Decadimento esponenziale invece di soglie lineari arbitrarie: la differenza
# tra 0 e 1 alternativa comparabile conta molto di più della differenza tra
# 10 e 11 — a 4 alternative comparabili la scarsità è già scesa a ~37/100.
DECAY_SCALE = 4.0


def compute_scarcity(player_row: dict, available_role_rows: list) -> float:
    """available_role_rows: righe del ruolo già filtrate per "disponibile"
    (non in rosa, non presa da un avversario) — stessa lista usata da
    ranking.tiers.classify_role."""
    threshold = (player_row.get("decision_score") or 0.0) * COMPARABLE_RATIO
    comparable = [
        r for r in available_role_rows
        if r["player_id"] != player_row["player_id"]
        and (r.get("decision_score") or 0.0) >= threshold
    ]
    return round(100 * math.exp(-len(comparable) / DECAY_SCALE), 1)
