"""Solver a programmazione lineare per la rosa ottimale (25 giocatori,
3-8-8-6, budget 500 crediti), alternativa a ranking/ideal_squad.py.

Massimizza la somma di expected_points (Fantasy Value normalizzato per ruolo,
pesato per probabilità di essere titolare) dei giocatori selezionati,
rispettando budget, slot per ruolo e un tetto di giocatori per club — a
differenza dell'euristica greedy di ideal_squad.py, garantisce l'ottimo
matematico per i vincoli dati.
"""

import pulp

ROLE_SLOTS = {"P": 3, "D": 8, "C": 8, "A": 6}

# Oltre questo numero di presenze un giocatore è considerato titolare fisso
# (stesso valore di ranking.scorer.compute_score) — usato per pesare
# expected_points, non per filtrare candidati.
FULL_SEASON_APPEARANCES = 38

# Un giocatore senza dato presenze (neo-arrivato, mai schierato) non deve
# essere né escluso né trattato come titolare certo: stessa fallback 0.5 già
# usata da ranking.scorer.compute_score/compute_risk per lo stesso caso.
DEFAULT_APPEARANCES_RELIABILITY = 0.5

# Rischio di concentrazione: se il club di 4+ titolari crolla (infortuni,
# cambio modulo, squadra in crisi), affonda mezza rosa in un colpo solo. Non
# una regola del gioco — una guardia di rischio (P0-005/TASK-016).
MAX_PLAYERS_PER_CLUB = 3


def _appearances_reliability(player: dict) -> float:
    appearances = player.get("appearances")
    if appearances is None:
        return DEFAULT_APPEARANCES_RELIABILITY
    return min(appearances, FULL_SEASON_APPEARANCES) / FULL_SEASON_APPEARANCES


def _zscore_by_role(candidates_by_role: dict) -> dict:
    """{player_id: z-score of `score` within its own role's candidate pool}.

    score/Fantasy Value is not comparable across roles by construction (a
    portiere's fantamedia sits ~1.5 points below an attaccante's for
    regulation reasons, not skill) — summing raw scores across all 25
    selected players in the LP's objective structurally favored whichever
    role happens to run hottest on the raw scale (P0-005). Standardizing
    each role to its own mean/stdev before any cross-role sum removes that
    bias."""
    z_scores: dict = {}
    for candidates in candidates_by_role.values():
        scores = [p.get("score") or 0 for p in candidates]
        if not scores:
            continue
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = variance ** 0.5
        for p in candidates:
            raw = p.get("score") or 0
            z_scores[p["player_id"]] = (raw - mean) / std if std else 0.0
    return z_scores


def _infeasible_reason(players_by_role: dict, fixed_ids: set, taken_ids: set,
                        roster_by_id: dict, budget: float) -> str:
    """Best-effort diagnosis for why the solver couldn't find a feasible
    squad (P1-013/TASK-017 point 4) — checked in the same order a person
    troubleshooting it would: not enough candidates to fill a role at all,
    a role with candidates but none priced, or (if neither of those) the
    budget itself. Not a certificate of infeasibility (the true cause of an
    LP failing can be a subtler interaction of constraints), just the most
    likely explanation to show the user instead of a bare "infeasible"."""
    min_cost_total = 0.0
    for role, needed_total in ROLE_SLOTS.items():
        already_filled = sum(1 for r in roster_by_id.values() if r["role_classic"] == role)
        slots_to_fill = max(needed_total - already_filled, 0)
        candidates = [
            p for p in players_by_role.get(role, [])
            if p["player_id"] not in fixed_ids and p["player_id"] not in taken_ids
        ]
        priced = [p for p in candidates if p.get("price_current") is not None]
        if len(priced) < slots_to_fill:
            if len(candidates) < slots_to_fill:
                return (
                    f"Non ci sono abbastanza candidati per il ruolo {role}: "
                    f"servono {slots_to_fill}, disponibili {len(candidates)}."
                )
            return (
                f"Il ruolo {role} ha candidati sufficienti ma nessun prezzo "
                f"per {slots_to_fill - len(priced)} di essi (dati insufficienti)."
            )
        min_cost_total += sum(sorted(p["price_current"] for p in priced)[:slots_to_fill])
    if min_cost_total > budget:
        return (
            f"Budget insufficiente: anche scegliendo i giocatori più economici "
            f"per ogni ruolo servirebbero almeno {round(min_cost_total, 1)} crediti, "
            f"ne restano {round(budget, 1)}."
        )
    return "Nessuna rosa valida trovata con i vincoli attuali (budget, slot, prezzi)."


def build_optimal_squad(
    players_by_role: dict,
    budget: float,
    roster_rows: list,
    taken_ids: set,
    mode: str = "constrained",
) -> dict:
    """Costruisce la rosa che massimizza gli expected_points totali dato il
    budget.

    Args:
        players_by_role: ruolo -> lista di dict con almeno player_id, score,
            price_current, role_classic, team, appearances (e i campi da
            riportare in output).
        budget: crediti disponibili per gli acquisti liberi. In modalità
            "constrained" deve già essere il residuo (budget totale - speso).
        roster_rows: giocatori già in rosa — dict con almeno player_id,
            role_classic, price_paid, canonical_name, team (la forma di
            repository.get_roster). In modalità "constrained" sono la fonte
            di verità su chi è fisso e su quale slot occupano: un giocatore
            in rosa può essere assente da players_by_role (scartato dai
            filtri di get_ranked_role — source_count, appearances, team)
            senza per questo smettere di essere in rosa e di costare quanto
            pagato (P1-013/TASK-017). In modalità "from_scratch" è ignorata.
        taken_ids: id esclusi dalla selezione (presi da altri).
        mode: "constrained" (rispetta la rosa attuale, riempie gli slot
            liberi) o "from_scratch" (ignora la rosa attuale, ottimizza da
            zero i 25 slot con budget pieno).

    Returns:
        dict con "squad" (ruolo -> lista giocatori selezionati, inclusi i
        fissi di rosa), "total_cost", "total_score" (somma del Fantasy Value
        grezzo, non degli expected_points usati internamente per ottimizzare
        — è il numero che il resto del prodotto mostra e confronta),
        "status" ("optimal"/"infeasible"), "reason" (solo se infeasible),
        "roster_not_in_pool" (id dei giocatori in rosa esclusi dalle liste
        ranked — score/price_current non disponibili per loro nell'output).
    """
    roster_by_id = {r["player_id"]: r for r in roster_rows} if mode == "constrained" else {}
    fixed_ids = set(roster_by_id)

    problem = pulp.LpProblem("rosa_ottimale", pulp.LpMaximize)

    candidates_by_role: dict = {}
    variables: dict = {}
    seen_candidate_ids: set = set()
    for role, players in players_by_role.items():
        candidates = []
        for p in players:
            if p["player_id"] in fixed_ids or p["player_id"] in taken_ids:
                continue
            if p.get("price_current") is None:
                continue
            # Roles are disjoint by construction (one role_classic per
            # player) — a repeat here means the caller built players_by_role
            # incorrectly, not a real data case to silently paper over
            # (P1-013/TASK-017 point 3).
            assert p["player_id"] not in seen_candidate_ids, (
                f"player_id {p['player_id']} appears in more than one role's candidate list"
            )
            seen_candidate_ids.add(p["player_id"])
            candidates.append(p)
        candidates_by_role[role] = candidates
        for p in candidates:
            variables[p["player_id"]] = pulp.LpVariable(f"x_{p['player_id']}", cat="Binary")

    z_scores = _zscore_by_role(candidates_by_role)
    expected_points = {
        pid: z * _appearances_reliability(p)
        for candidates in candidates_by_role.values()
        for p in candidates
        for pid in [p["player_id"]]
        for z in [z_scores[pid]]
    }

    problem += pulp.lpSum(
        variables[p["player_id"]] * expected_points[p["player_id"]]
        for candidates in candidates_by_role.values()
        for p in candidates
    )

    for role, needed_total in ROLE_SLOTS.items():
        candidates = candidates_by_role.get(role, [])
        already_filled = sum(1 for r in roster_by_id.values() if r["role_classic"] == role)
        slots_to_fill = max(needed_total - already_filled, 0)
        problem += pulp.lpSum(variables[p["player_id"]] for p in candidates) == slots_to_fill

    problem += pulp.lpSum(
        variables[p["player_id"]] * p["price_current"]
        for candidates in candidates_by_role.values()
        for p in candidates
    ) <= budget

    by_club: dict = {}
    for candidates in candidates_by_role.values():
        for p in candidates:
            if p.get("team"):
                by_club.setdefault(p["team"], []).append(p)
    for club_players in by_club.values():
        problem += pulp.lpSum(
            variables[p["player_id"]] for p in club_players
        ) <= MAX_PLAYERS_PER_CLUB

    problem.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[problem.status] != "Optimal":
        reason = _infeasible_reason(players_by_role, fixed_ids, taken_ids, roster_by_id, budget)
        return {"squad": {role: [] for role in ROLE_SLOTS}, "total_cost": 0.0,
                "total_score": 0.0, "status": "infeasible", "reason": reason}

    squad: dict = {role: [] for role in ROLE_SLOTS}
    total_cost = 0.0
    total_score = 0.0
    roster_not_in_pool = []

    pool_by_id = {p["player_id"]: p for players in players_by_role.values() for p in players}
    for pid, r in roster_by_id.items():
        role = r["role_classic"]
        pool_entry = pool_by_id.get(pid)
        if pool_entry is not None:
            squad[role].append(pool_entry)
            total_score += pool_entry.get("score") or 0
        else:
            # Not in the ranked pool (filtered out by get_ranked_role) —
            # still in the roster and still costs what was paid; surfaced
            # rather than hidden (P1-013/TASK-017 point 4).
            roster_not_in_pool.append(pid)
            squad[role].append({
                "player_id": pid,
                "canonical_name": r.get("canonical_name"),
                "team": r.get("team"),
                "role_classic": role,
                "score": None,
                "price_current": None,
            })
        total_cost += r["price_paid"]

    for role, candidates in candidates_by_role.items():
        for p in candidates:
            if pulp.value(variables[p["player_id"]]) > 0.5:
                squad[role].append(p)
                total_cost += p["price_current"]
                total_score += p.get("score") or 0

    return {
        "squad": squad,
        "total_cost": round(total_cost, 2),
        "total_score": round(total_score, 2),
        "status": "optimal",
        "roster_not_in_pool": roster_not_in_pool,
    }
