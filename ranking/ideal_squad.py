"""Motore della Rosa Ideale: costruisce la formazione ottimale
combinando i giocatori già in rosa con i migliori candidati liberi,
considerando disponibilità, forma recente e budget."""


# Formazioni classiche supportate (P, D, C, A)
FORMATIONS = {
    "3-4-3": {"P": 1, "D": 3, "C": 4, "A": 3},
    "3-5-2": {"P": 1, "D": 3, "C": 5, "A": 2},
    "4-3-3": {"P": 1, "D": 4, "C": 3, "A": 3},
    "4-4-2": {"P": 1, "D": 4, "C": 4, "A": 2},
    "4-5-1": {"P": 1, "D": 4, "C": 5, "A": 1},
    "5-3-2": {"P": 1, "D": 5, "C": 3, "A": 2},
    "5-4-1": {"P": 1, "D": 5, "C": 4, "A": 1},
}

# Pesi per il punteggio aggiustato della rosa ideale
WEIGHT_FANTASY_VALUE = 0.35
WEIGHT_DECISION_SCORE = 0.25
WEIGHT_FORM = 0.20
WEIGHT_RELIABILITY = 0.10
WEIGHT_VALUE_FOR_MONEY = 0.10

# Bonus/Malus per disponibilità
AVAILABILITY_PENALTY = {
    "infortunato": -25.0,
    "squalificato": -20.0,
    "in dubbio": -8.0,
}

# Numero minimo di presenze per essere considerato "affidabile"
RELIABLE_APPEARANCES = 10


def _reliability_factor(appearances: int | None) -> float:
    """0.0–1.0 in base alle presenze; None = neutrale (0.7)."""
    if appearances is None:
        return 0.70
    return min(appearances, 38) / 38.0


def _form_factor(recent_form: dict | None) -> float:
    """Restituisce un moltiplicatore 0.5–1.3 basato sulla media fantavoto
    delle ultime partite.  Se non ci sono dati sufficienti restituisce 1.0."""
    if not recent_form:
        return 1.0
    avg = recent_form.get("avg_fantavoto")
    if avg is None:
        return 1.0
    # fantavoto medio ~ 6 = neutrale, >7.5 = ottimo, <4.5 = pessimo
    return max(0.5, min(1.3, 0.5 + (avg / 7.5)))


def compute_ideal_score(player: dict, recent_form: dict | None = None) -> float:
    """Punteggio complessivo per la rosa ideale.

    Combina:
    - Fantasy Value (base del ranking)
    - Decision Score (valore + prezzo + rischio)
    - Forma recente (ultime giornate)
    - Affidabilità (presenze)
    - Value for Money
    - Penalità per infortunio / squalifica / dubbio
    """
    fantasy_value = player.get("score") or 0.0
    decision_score = player.get("decision_score") or 0.0
    # Population-relative percentile (0-100), not the raw value_for_money
    # ratio: that ratio is unbounded and inflates sharply for cheap players
    # (see ranking.scorer.compute_decision_score), which would double-count
    # the same distortion here on top of decision_score already factoring it
    # in correctly. Missing (e.g. a row built outside rank_players) => 50,
    # neutral.
    vfm_percentile = player.get("value_for_money_percentile")
    if vfm_percentile is None:
        vfm_percentile = 50.0
    appearances = player.get("appearances")
    status = player.get("status")

    reliability = _reliability_factor(appearances)
    form = _form_factor(recent_form)

    base = (
        fantasy_value * WEIGHT_FANTASY_VALUE
        + decision_score * WEIGHT_DECISION_SCORE
        + vfm_percentile * WEIGHT_VALUE_FOR_MONEY
    )
    adjusted = base * (1 + reliability * WEIGHT_RELIABILITY) * (1 + (form - 1) * WEIGHT_FORM)

    # applica penalità disponibilità
    penalty = AVAILABILITY_PENALTY.get(status, 0.0)
    adjusted += penalty

    return round(adjusted, 2)


# Numero di panchinari consigliati per ruolo per avere copertura
BENCH_COVERAGE = {"P": 2, "D": 2, "C": 2, "A": 1}


def build_ideal_squad(
    players_by_role: dict[str, list[dict]],
    formation: dict[str, int],
    budget: float,
    roster_player_ids: set[int],
    taken_ids: set[int],
    recent_form_by_player: dict[int, dict] | None = None,
) -> dict:
    """Costruisce la rosa ideale (titolari + panchina).

    Args:
        players_by_role: mappatura ruolo -> lista giocatori già rankati.
        formation: dizionario ruolo -> numero di titolari richiesti.
        budget: crediti rimanenti da spendere.
        roster_player_ids: ID dei giocatori già in rosa.
        taken_ids: ID dei giocatori presi dagli avversari.
        recent_form_by_player: {player_id: form_dict} opzionale.

    Returns:
        dict con chiavi:
        - starters:  {ruolo: [giocatori]}
        - bench:     {ruolo: [giocatori]}
        - total_cost: costo stimato dei giocatori mancanti
        - covered_by_roster: quanti slot già coperti dalla rosa attuale
        - missing:   quanti acquisti mancano
        - unavailable: giocatori in rosa ma esclusi per infortunio/squalifica
    """
    recent_form_by_player = recent_form_by_player or {}

    # Calcola ideal_score per tutti i giocatori liberi e in rosa
    scored_by_role: dict[str, list[dict]] = {}
    for role, players in players_by_role.items():
        scored = []
        for p in players:
            p = dict(p)  # copia per non sporcare l'originale
            form = recent_form_by_player.get(p["player_id"])
            p["ideal_score"] = compute_ideal_score(p, form)
            scored.append(p)
        # ordina per ideal_score discendente
        scored.sort(key=lambda x: x["ideal_score"], reverse=True)
        scored_by_role[role] = scored

    starters: dict[str, list[dict]] = {r: [] for r in formation}
    bench: dict[str, list[dict]] = {r: [] for r in formation}
    remaining_budget = budget
    used_ids: set[int] = set()
    covered_by_roster = 0
    unavailable_in_roster: list[dict] = []

    # --- 1. Titolari ---
    for role, needed in formation.items():
        candidates = scored_by_role.get(role, [])
        # prima cerca tra i giocatori GIÀ in rosa
        roster_candidates = [c for c in candidates if c["player_id"] in roster_player_ids]
        free_candidates = [c for c in candidates if c["player_id"] not in roster_player_ids | taken_ids]

        selected = []
        # prendi dalla rosa attuale finché serve e sono disponibili
        for c in roster_candidates:
            if len(selected) >= needed:
                break
            if c.get("status") in ("infortunato", "squalificato"):
                # segnalo ma non lo uso tra i titolari
                unavailable_in_roster.append(c)
                continue
            selected.append(c)
            used_ids.add(c["player_id"])
            covered_by_roster += 1

        # completa con giocatori liberi rispettando budget
        for c in free_candidates:
            if len(selected) >= needed:
                break
            price = c.get("price_current") or 0
            if price <= remaining_budget or c["player_id"] in roster_player_ids:
                selected.append(c)
                used_ids.add(c["player_id"])
                if c["player_id"] not in roster_player_ids:
                    remaining_budget -= price

        starters[role] = selected

    # --- 2. Panchina ---
    for role, needed in BENCH_COVERAGE.items():
        if role not in formation:
            continue
        candidates = scored_by_role.get(role, [])
        # escludi già usati
        candidates = [c for c in candidates if c["player_id"] not in used_ids]
        # prima rosa, poi liberi
        roster_candidates = [c for c in candidates if c["player_id"] in roster_player_ids]
        free_candidates = [c for c in candidates if c["player_id"] not in roster_player_ids | taken_ids]

        selected = []
        for c in roster_candidates:
            if len(selected) >= needed:
                break
            selected.append(c)
            used_ids.add(c["player_id"])
            covered_by_roster += 1

        for c in free_candidates:
            if len(selected) >= needed:
                break
            price = c.get("price_current") or 0
            if price <= remaining_budget:
                selected.append(c)
                used_ids.add(c["player_id"])
                remaining_budget -= price

        bench[role] = selected

    # --- 3. Riepilogo ---
    missing_starters = sum(
        formation[r] - len(starters[r]) for r in formation
    )
    missing_bench = sum(
        BENCH_COVERAGE[r] - len(bench[r]) for r in BENCH_COVERAGE if r in formation
    )

    # costo stimato dei giocatori mancanti
    total_cost = 0.0
    for role in formation:
        for p in starters[role]:
            if p["player_id"] not in roster_player_ids:
                total_cost += p.get("price_current") or 0
        for p in bench[role]:
            if p["player_id"] not in roster_player_ids:
                total_cost += p.get("price_current") or 0

    return {
        "formation": formation,
        "starters": starters,
        "bench": bench,
        "total_cost": round(total_cost, 2),
        "remaining_budget": round(remaining_budget, 2),
        "covered_by_roster": covered_by_roster,
        "missing": {"starters": missing_starters, "bench": missing_bench},
        "unavailable_in_roster": unavailable_in_roster,
    }
