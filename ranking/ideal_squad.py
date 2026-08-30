"""Motore della Rosa Ideale: costruisce la formazione ottimale
combinando i giocatori già in rosa con i migliori candidati liberi,
considerando disponibilità, forma recente e budget."""

from ranking.budget import ROLE_BUDGET_PCT


def compare_starters_to_lp(starters: dict, lp_squad: dict, formation: dict) -> dict:
    """A fair Rosa Ideale vs LP comparison needs the same base on both
    sides: the LP solver's own best `formation` slots per role, not its
    full 25-player squad (P1-015/TASK-030). Summing Rosa Ideale's 11
    starters + 7 bench (18) against the LP's all 25 meant the LP "won" by
    construction — 25 positive addends beat 18 regardless of pick quality,
    a comparison that couldn't fail and therefore didn't inform anything."""
    ideal_players = [p for role in starters for p in starters.get(role, [])]
    lp_starters = {
        role: sorted(lp_squad.get(role, []), key=lambda p: p["score"], reverse=True)[:count]
        for role, count in formation.items()
    }
    lp_players = [p for players in lp_starters.values() for p in players]

    def _totals(players: list) -> dict:
        return {
            "score": round(sum(p["score"] for p in players), 1),
            "cost": round(sum(p.get("price_current") or 0 for p in players), 1),
        }

    return {"ideal": _totals(ideal_players), "lp": _totals(lp_players)}


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

# Pesi per il punteggio aggiustato della rosa ideale — reliability e form
# sono moltiplicatori su decision_score (bande strette intorno a 1: al più
# +/-10% e +/-6%), non termini di qualità paralleli.
WEIGHT_FORM = 0.20
WEIGHT_RELIABILITY = 0.10

# Bonus/Malus per disponibilità
AVAILABILITY_PENALTY = {
    "infortunato": -25.0,
    "squalificato": -20.0,
    "in dubbio": -8.0,
}

# Numero minimo di presenze per essere considerato "affidabile"
RELIABLE_APPEARANCES = 10


def _reliability_factor(appearances: int | None) -> float:
    """0.0-1.0 in base alle presenze. None = 0.5, stesso default neutro usato
    da ranking.scorer.compute_score/compute_risk (P1-009/TASK-012 punto 5:
    prima qui era 0.70, un valore diverso per lo stesso "nessuna prova né a
    favore né contro" senza motivo)."""
    if appearances is None:
        return 0.5
    return min(appearances, 38) / 38.0


def _form_factor(recent_form: dict | None) -> float:
    """Moltiplicatore 0.5-1.3 basato sulla media fantavoto delle ultime
    partite. Se non ci sono dati sufficienti restituisce 1.0 (neutro)."""
    if not recent_form:
        return 1.0
    avg = recent_form.get("avg_fantavoto")
    if avg is None:
        return 1.0
    # fantavoto medio 6.0 = neutrale (fattore 1.0) — prima il punto neutro
    # della formula era ~7.1, per cui una forma solo nella media veniva
    # premiata quasi al massimo (P1-009/TASK-012 punto 3).
    return max(0.5, min(1.3, 1.0 + (avg - 6.0) / 7.5))


def compute_ideal_score(player: dict, recent_form: dict | None = None) -> float:
    """Punteggio complessivo per la rosa ideale.

    decision_score (valore + prezzo + rischio, ranking.scorer.
    compute_decision_score) è l'unico termine di qualità: sommargli di nuovo
    fantasy_value e il percentile value-for-money, come faceva una versione
    precedente di questa funzione, contava due volte lo stesso segnale
    (P1-008/TASK-012), visto che decision_score li incorpora già entrambi.
    Forma e affidabilità (presenze) restano moltiplicatori, non termini
    di qualità paralleli — bande strette intorno a 1 (+/-10% e +/-6%), così
    non possono da soli ribaltare un decision_score negativo in positivo.
    """
    decision_score = player.get("decision_score") or 0.0
    appearances = player.get("appearances")
    status = player.get("status")

    reliability = _reliability_factor(appearances)
    form = _form_factor(recent_form)

    adjusted = decision_score * (1 + reliability * WEIGHT_RELIABILITY) * (1 + (form - 1) * WEIGHT_FORM)

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
    # Per-role budget pool (ROLE_BUDGET_PCT — same 6/16/32/46 split the top
    # budget bar uses), not one pool shared across roles: a single draining
    # `remaining_budget` processed role-by-role in formation order let an
    # early, cheap role (P/D) starve a later, expensive one (A: attaccanti
    # routinely cost close to the entire budget on their own) — on the real
    # DB this left Attaccanti with 0 of 3 starters while P/D/C had already
    # spent 475 of ~476 available credits between them.
    #
    # Weighted only over roles this formation actually needs a starter for
    # (needed > 0), renormalized to sum to 1 — a role_weights entry that's
    # merely present in `formation` with needed=0 must not siphon off a
    # share of the budget nobody will ever spend from it.
    active_roles = [role for role, needed in formation.items() if needed > 0] or list(formation)
    role_weights = {role: ROLE_BUDGET_PCT.get(role, 1.0) for role in active_roles}
    weight_total = sum(role_weights.values()) or 1.0
    remaining_budget_by_role = {
        role: budget * (role_weights.get(role, 0.0) / weight_total)
        for role in formation
    }
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

        # completa con giocatori liberi rispettando il budget di *questo* ruolo
        for c in free_candidates:
            if len(selected) >= needed:
                break
            price = c.get("price_current") or 0
            if price <= remaining_budget_by_role[role] or c["player_id"] in roster_player_ids:
                selected.append(c)
                used_ids.add(c["player_id"])
                if c["player_id"] not in roster_player_ids:
                    remaining_budget_by_role[role] -= price

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
            if price <= remaining_budget_by_role[role]:
                selected.append(c)
                used_ids.add(c["player_id"])
                remaining_budget_by_role[role] -= price

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
        "remaining_budget": round(sum(remaining_budget_by_role.values()), 2),
        "covered_by_roster": covered_by_roster,
        "missing": {"starters": missing_starters, "bench": missing_bench},
        "unavailable_in_roster": unavailable_in_roster,
    }
