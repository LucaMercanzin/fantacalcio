"""Scarcity Score: quanto è difficile sostituire un giocatore con
un'alternativa comparabile ancora disponibile nel suo ruolo (spec
impossibile-analisi-avanzata.md sez. 6) — calcolabile oggi da score
(Fantasy Value), nessun dato di tracking/xG richiesto.

Nota (P1-009): il progetto ha anche una seconda nozione di scarsità,
ranking.auction_intelligence.compute_scarcity_tier (via alternatives_
remaining), usata da get_auction_intelligence. Le due NON sono state
unificate qui deliberatamente: alimentano due sistemi di prezzo distinti
(Price Engine vs Auction Intelligence) la cui eventuale unificazione è
TASK-015, esplicitamente marcato "da confermare con l'utente prima di
implementare" nel piano di remediation. Questo modulo corregge solo il
difetto matematico che lo rendeva morto (comparabilità su rapporto invece
che differenza, decadimento non tarato sulla dimensione del ruolo, nessun
filtro di acquistabilità)."""

import math

# Un'alternativa conta come "comparabile" se il suo score differisce dal
# giocatore in questione per al più questa soglia — una differenza assoluta,
# non un rapporto: score/decision_score non hanno uno zero significativo (e
# possono essere negativi), quindi "il 90% del suo valore" non è una nozione
# coerente di vicinanza. ~3 punti di score equivalgono a ~0.3 di fantamedia,
# abbastanza vicini da poter essere una vera scelta alternativa in asta.
COMPARABLE_SCORE_GAP = 3.0


def compute_scarcity(player_row: dict, available_role_rows: list,
                      slots_remaining: int, spendable: float = None) -> float:
    """available_role_rows: righe del ruolo già filtrate per "disponibile"
    (non in rosa, non presa da un avversario) — stessa lista usata da
    ranking.tiers.classify_role.

    slots_remaining: quanti slot di questo ruolo restano da riempire
    (ranking.budget.compute_budget_summary(...)["slots"][role]["remaining"])
    — tara il decadimento sulla reale ampiezza della rosa residua invece di
    una costante fissa (P1-009: con DECAY_SCALE=4 fisso, un ruolo da 150
    candidati aveva decine di "comparabili" e quindi scarsità ~0 per
    chiunque non fosse nei primissimi posti).

    spendable: se indicato (ranking.budget.compute_budget_summary(...)
    ["spendable"]), esclude dalle alternative comparabili i giocatori che in
    pratica non potresti permetterti — altrimenti compute_scarcity conta
    anche alternative irraggiungibili col budget residuo."""
    player_score = player_row.get("score")
    if player_score is None:
        return 0.0
    comparable = [
        r for r in available_role_rows
        if r["player_id"] != player_row["player_id"]
        and r.get("score") is not None
        and abs(r["score"] - player_score) <= COMPARABLE_SCORE_GAP
        and (spendable is None or (r.get("price_current") or 0) <= spendable)
    ]
    decay_scale = max(slots_remaining, 1)
    return round(100 * math.exp(-len(comparable) / decay_scale), 1)
