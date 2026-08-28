"""Solver a programmazione lineare per la rosa ottimale (25 giocatori,
3-8-8-6, budget 500 crediti), alternativa a ranking/ideal_squad.py.

Massimizza la somma di Fantasy Value (score) dei giocatori selezionati,
rispettando budget e slot per ruolo — a differenza dell'euristica greedy di
ideal_squad.py, garantisce l'ottimo matematico per i vincoli dati.
"""

import pulp

ROLE_SLOTS = {"P": 3, "D": 8, "C": 8, "A": 6}


def build_optimal_squad(
    players_by_role: dict,
    budget: float,
    roster_player_ids: set,
    taken_ids: set,
    mode: str = "constrained",
    roster_prices: dict | None = None,
) -> dict:
    """Costruisce la rosa che massimizza lo score totale dato il budget.

    Args:
        players_by_role: ruolo -> lista di dict con almeno player_id, score,
            price_current, role_classic (e i campi da riportare in output).
        budget: crediti disponibili per gli acquisti liberi. In modalità
            "constrained" deve già essere il residuo (budget totale - speso).
        roster_player_ids: id dei giocatori già in rosa. In modalità
            "constrained" restano fissi nella rosa e occupano uno slot del
            loro ruolo; in modalità "from_scratch" sono ignorati.
        taken_ids: id esclusi dalla selezione (presi da altri).
        mode: "constrained" (rispetta la rosa attuale, riempie gli slot
            liberi) o "from_scratch" (ignora la rosa attuale, ottimizza da
            zero i 25 slot con budget pieno).
        roster_prices: {player_id: price_paid}, richiesto in modalità
            "constrained" per contabilizzare correttamente il costo totale.

    Returns:
        dict con "squad" (ruolo -> lista giocatori selezionati, inclusi i
        fissi di rosa), "total_cost", "total_score", "status"
        ("optimal"/"infeasible").
    """
    roster_prices = roster_prices or {}
    fixed_ids = roster_player_ids if mode == "constrained" else set()

    problem = pulp.LpProblem("rosa_ottimale", pulp.LpMaximize)

    candidates_by_role: dict = {}
    variables: dict = {}
    for role, players in players_by_role.items():
        candidates = [
            p for p in players
            if p["player_id"] not in fixed_ids
            and p["player_id"] not in taken_ids
            and p.get("price_current") is not None
        ]
        candidates_by_role[role] = candidates
        for p in candidates:
            variables[p["player_id"]] = pulp.LpVariable(f"x_{p['player_id']}", cat="Binary")

    problem += pulp.lpSum(
        variables[p["player_id"]] * (p.get("score") or 0)
        for candidates in candidates_by_role.values()
        for p in candidates
    )

    for role, needed_total in ROLE_SLOTS.items():
        candidates = candidates_by_role.get(role, [])
        already_filled = sum(
            1 for pid in fixed_ids
            for p in players_by_role.get(role, []) if p["player_id"] == pid
        )
        slots_to_fill = max(needed_total - already_filled, 0)
        problem += pulp.lpSum(variables[p["player_id"]] for p in candidates) == slots_to_fill

    problem += pulp.lpSum(
        variables[p["player_id"]] * p["price_current"]
        for candidates in candidates_by_role.values()
        for p in candidates
    ) <= budget

    problem.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[problem.status] != "Optimal":
        return {"squad": {role: [] for role in ROLE_SLOTS}, "total_cost": 0.0,
                "total_score": 0.0, "status": "infeasible"}

    squad: dict = {role: [] for role in ROLE_SLOTS}
    total_cost = 0.0
    total_score = 0.0

    for role, players in players_by_role.items():
        for p in players:
            if p["player_id"] in fixed_ids:
                squad[role].append(p)
                total_cost += roster_prices.get(p["player_id"], 0)
                total_score += p.get("score") or 0

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
    }
