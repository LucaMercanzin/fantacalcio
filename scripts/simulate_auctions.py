"""Simula N aste complete contro il pool di giocatori reale, per validare che
tutti i calcoli (prezzi, tier, budget, optimizer LP) reggano su tanti scenari
diversi invece che sul singolo stato attuale della rosa.

Il database reale viene aperto UNA SOLA VOLTA, in sola lettura, per caricare
il pool di giocatori già scored/rankeed (get_ranked_role: score, decision_score,
risk, value_for_money sono intrinseci al giocatore, non dipendono da chi lo
possiede — vedi ranking/scorer.py). Tutte le aste simulate girano poi
interamente in memoria: la asta reale in corso e la rosa dell'utente in
fantacalcio.db non vengono mai toccate.

Ogni asta simulata: N_TEAMS squadre (indice 0 = "Io", le altre "avversari"),
budget 500, slot 3-8-8-6. Ad ogni turno la squadra di turno sceglie un ruolo
ancora scoperto e acquista un giocatore disponibile che può permettersi
(prezzo random attorno alla quotazione, con vincolo di lasciare almeno 1
credito per ogni slot ancora da riempire). Gli avversari scelgono con
selezione casuale pesata sul Fantasy Value (score); "Io" scelgo sempre il
miglior decision_score disponibile, come farebbe il motore di raccomandazione
dell'app (get_squad_suggestions/purchase_advisor).

Uso: python scripts/simulate_auctions.py [--runs 1000] [--teams 8] [--seed 42]
     [--lp-sample 50]
"""

import argparse
import os
import random
import statistics
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import ROLE_SLOTS, TOTAL_CREDITS
from dashboard.data_access import get_ranked_role
from db.connection import get_connection
from ranking.budget import (
    ROLE_BUDGET_PCT,
    compute_budget_summary,
    compute_role_budget_plan,
)
from ranking.lp_optimizer import build_optimal_squad
from ranking.tiers import TIER_LABELS, TIER_ORDER, classify_role

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fantacalcio.db")


def load_pool() -> dict:
    """Un solo accesso in sola lettura al db reale: get_ranked_role non scrive
    mai (solo repository.get_roster/get_opponent_picks/get_player_notes, tutte
    letture). Il pool caricato qui è condiviso, read-only, da tutte le run."""
    conn = get_connection(DB_PATH)
    try:
        pool = {role: get_ranked_role(conn, role) for role in ROLE_SLOTS}
    finally:
        conn.close()
    for rows in pool.values():
        for r in rows:
            # Azzerato: lo stato "posseduto/preso" della singola run simulata
            # sostituisce quello (eventualmente vuoto) del db reale.
            r["is_in_roster"] = False
            r["taken_by"] = None
    return pool


class Team:
    __slots__ = ("budget", "idx", "roster", "roster_ids")

    def __init__(self, idx: int):
        self.idx = idx
        self.budget = float(TOTAL_CREDITS)
        self.roster = {role: [] for role in ROLE_SLOTS}
        self.roster_ids = set()

    def open_roles(self) -> list:
        return [r for r in ROLE_SLOTS if len(self.roster[r]) < ROLE_SLOTS[r]]

    def remaining_slots(self) -> int:
        return sum(ROLE_SLOTS[r] - len(self.roster[r]) for r in ROLE_SLOTS)

    def max_affordable(self) -> float:
        # Deve restare almeno 1 credito per ogni slot ancora da riempire DOPO
        # questo acquisto (regola standard d'asta fantacalcio).
        return self.budget - (self.remaining_slots() - 1)


def _pick_price(price_current: float, max_affordable: float) -> float:
    price = round(price_current * random.uniform(0.85, 1.25))
    price = max(1, price)
    return min(price, int(max_affordable))


def _my_role_priority(team: "Team") -> list:
    """Ordina i ruoli ancora aperti dando priorità a quello più 'indietro'
    rispetto al piano budget studiato (stessa logica della barra budget
    dell'app, ranking.budget.compute_role_budget_plan) — evita che 'Io' si
    concentri su un solo ruolo (es. Attaccanti, dove i decision_score sono
    sistematicamente più alti) lasciando troppi slot scoperti altrove."""
    open_roles = team.open_roles()
    if not open_roles:
        return []
    roster_rows = [
        {"role_classic": role, "price_paid": p["price_paid"]}
        for role in ROLE_SLOTS for p in team.roster[role]
    ]
    summary = compute_budget_summary(roster_rows, TOTAL_CREDITS)
    plan = compute_role_budget_plan(summary)
    open_roles.sort(
        key=lambda r: plan[r]["avg_per_remaining_slot"] or 0, reverse=True,
    )
    return open_roles


def simulate_one_auction(pool: dict, n_teams: int) -> dict:
    teams = [Team(i) for i in range(n_teams)]
    taken: dict = {}  # player_id -> team_idx
    active = [True] * n_teams

    # Snapshot di 'Io' a metà asta (non a fine asta, dove per costruzione il
    # budget residuo è sempre troppo scarso per gli slot rimasti — vedi
    # max_affordable: un team si ferma esattamente quando budget < slot
    # rimanenti, quindi l'LP a fine asta è quasi sempre strutturalmente
    # infeasible). Serve per un test LP più rappresentativo di un uso normale
    # a metà asta, con margine di manovra reale.
    snapshot_target = random.randint(3, sum(ROLE_SLOTS.values()) - 1)
    mid_snapshot = None

    guard = 0
    max_iterations = n_teams * sum(ROLE_SLOTS.values()) * 4  # safety net
    while any(active) and guard < max_iterations:
        guard += 1
        for i in range(n_teams):
            if not active[i]:
                continue
            team = teams[i]
            open_roles = team.open_roles()
            if not open_roles:
                active[i] = False
                continue
            max_afford = team.max_affordable()
            if max_afford < 1:
                active[i] = False
                continue

            if i == 0:
                open_roles = _my_role_priority(team)
            else:
                random.shuffle(open_roles)
            picked = False
            for role in open_roles:
                candidates = [
                    r for r in pool[role]
                    if r["player_id"] not in taken
                    and r.get("price_current") is not None
                    and r["price_current"] <= max_afford
                ]
                if not candidates:
                    continue

                if i == 0:
                    candidates.sort(key=lambda r: r.get("decision_score", r["score"]), reverse=True)
                    chosen = candidates[0]
                else:
                    weights = [max(c.get("score", 0.1), 0.1) ** 2 for c in candidates]
                    chosen = random.choices(candidates, weights=weights, k=1)[0]

                price_paid = _pick_price(chosen["price_current"], max_afford)
                team.budget -= price_paid
                team.roster[role].append({**chosen, "price_paid": price_paid})
                team.roster_ids.add(chosen["player_id"])
                taken[chosen["player_id"]] = i
                picked = True

                if i == 0 and mid_snapshot is None and len(team.roster_ids) >= snapshot_target:
                    mid_snapshot = {
                        "budget": team.budget,
                        # Each entry already has player_id/role_classic/
                        # price_paid/canonical_name/team - the exact shape
                        # build_optimal_squad's roster_rows expects
                        # (TASK-017), same as repository.get_roster's output.
                        "roster_rows": [
                            p for role in ROLE_SLOTS for p in team.roster[role]
                        ],
                    }
                break

            if not picked:
                active[i] = False

    return {"teams": teams, "taken": taken, "iterations": guard,
             "stalled": guard >= max_iterations, "mid_snapshot": mid_snapshot}


def check_run(pool: dict, result: dict) -> dict:
    """Invarianti + raccolta dati per il report aggregato. Non solleva mai:
    ogni eccezione viene catturata e registrata come anomalia, così una run
    che rompe un calcolo non interrompe le altre 999."""
    anomalies = []
    teams = result["teams"]
    taken = result["taken"]

    for t in teams:
        if t.budget < 0:
            anomalies.append(f"team {t.idx}: budget negativo ({t.budget})")

    if len(taken) != sum(len(t.roster[r]) for t in teams for r in ROLE_SLOTS):
        anomalies.append("giocatore assegnato a più di una squadra")

    tier_sizes = {role: {tier: 0 for tier in TIER_ORDER} for role in ROLE_SLOTS}
    try:
        for role in ROLE_SLOTS:
            rows = []
            for r in pool[role]:
                row = dict(r)
                owner = taken.get(row["player_id"])
                row["is_in_roster"] = owner == 0
                row["taken_by"] = f"avversario_{owner}" if owner not in (None, 0) else None
                rows.append(row)
            tiers = classify_role(rows)
            for tier, players in tiers.items():
                tier_sizes[role][tier] = len(players)
    except Exception as exc:
        anomalies.append(f"classify_role ha sollevato un'eccezione: {exc!r}")

    my_roster_rows = [
        {"role_classic": role, "price_paid": p["price_paid"]}
        for role in ROLE_SLOTS for p in teams[0].roster[role]
    ]
    summary = compute_budget_summary(my_roster_rows, TOTAL_CREDITS)
    if summary["spent"] > TOTAL_CREDITS:
        anomalies.append(f"speso totale ({summary['spent']}) supera il budget")
    plan = compute_role_budget_plan(summary)

    my_score_total = sum(
        p.get("score", 0) for role in ROLE_SLOTS for p in teams[0].roster[role]
    )

    return {
        "anomalies": anomalies,
        "tier_sizes": tier_sizes,
        "role_spend": {r: summary["slots"][r]["spent"] for r in ROLE_SLOTS},
        "total_spent": summary["spent"],
        "my_score_total": my_score_total,
        "my_slots_filled": sum(summary["slots"][r]["filled"] for r in ROLE_SLOTS),
        "plan_over_budget": {r: plan[r]["over_budget"] for r in ROLE_SLOTS},
    }


def check_lp(pool: dict, result: dict) -> str:
    """Esegue l'optimizer LP sullo stato di 'Io' a metà asta (mid_snapshot:
    budget/rosa più realistici di quelli di fine asta, vedi simulate_one_
    auction). Ritorna 'optimal', 'infeasible' o 'exception:<msg>'."""
    snapshot = result["mid_snapshot"]
    if snapshot is None:
        return "skipped:no_snapshot"
    # taken_by_others usa lo stato FINALE degli avversari (non quello vero a
    # metà asta, che non viene registrato) — leggermente pessimistico: esclude
    # anche giocatori che a quel punto erano ancora liberi ma verranno presi
    # dopo. Rende il test più severo, non più permissivo, quindi resta un
    # controllo valido su "l'LP non crasha mai e riporta uno stato pulito".
    taken_by_others = {pid for pid, owner in result["taken"].items() if owner != 0}
    try:
        lp_result = build_optimal_squad(
            pool, snapshot["budget"], snapshot["roster_rows"], taken_by_others,
            mode="constrained",
        )
        return lp_result["status"]
    except Exception as exc:
        return f"exception:{exc!r}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--teams", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lp-sample", type=int, default=50,
                         help="Su quante run (a campione) eseguire anche il solver LP "
                              "(costoso): il resto valida solo tier/budget.")
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"Carico il pool giocatori dal db reale ({DB_PATH})...")
    t0 = time.time()
    pool = load_pool()
    print(f"Pool caricato in {time.time() - t0:.1f}s: "
          + ", ".join(f"{role}={len(rows)}" for role, rows in pool.items()))

    lp_run_indices = set(
        random.sample(range(args.runs), min(args.lp_sample, args.runs))
    )

    all_anomalies = []
    stalled_runs = 0
    role_spend_pct = {r: [] for r in ROLE_SLOTS}
    score_totals = []
    slots_filled = []
    tier_size_samples = {role: {tier: [] for tier in TIER_ORDER} for role in ROLE_SLOTS}
    lp_statuses = []

    t0 = time.time()
    for run_idx in range(args.runs):
        result = simulate_one_auction(pool, args.teams)
        if result["stalled"]:
            stalled_runs += 1

        check = check_run(pool, result)
        if check["anomalies"]:
            all_anomalies.append((run_idx, check["anomalies"]))

        for role in ROLE_SLOTS:
            pct = (check["role_spend"][role] / check["total_spent"] * 100
                   if check["total_spent"] else 0)
            role_spend_pct[role].append(pct)
            for tier in TIER_ORDER:
                tier_size_samples[role][tier].append(check["tier_sizes"][role][tier])

        score_totals.append(check["my_score_total"])
        slots_filled.append(check["my_slots_filled"])

        if run_idx in lp_run_indices:
            lp_statuses.append(check_lp(pool, result))

        if (run_idx + 1) % 100 == 0:
            print(f"  ...{run_idx + 1}/{args.runs} run completate "
                  f"({time.time() - t0:.0f}s)")

    elapsed = time.time() - t0
    print(f"\nCompletate {args.runs} run in {elapsed:.0f}s "
          f"({elapsed / args.runs * 1000:.0f}ms/run).\n")

    print("=" * 70)
    print("REPORT SIMULAZIONE ASTE")
    print("=" * 70)

    print(f"\nAnomalie/crash: {len(all_anomalies)} / {args.runs} run")
    for run_idx, anomalies in all_anomalies[:15]:
        print(f"  run {run_idx}: {anomalies}")
    if len(all_anomalies) > 15:
        print(f"  ... e altre {len(all_anomalies) - 15}")

    print(f"\nRun 'stallate' (esaurita safety net iterazioni): {stalled_runs} / {args.runs}")

    print(f"\nSlot riempiti da 'Io' (su 25 totali): "
          f"media {statistics.mean(slots_filled):.1f}, "
          f"min {min(slots_filled)}, max {max(slots_filled)}")

    print(f"\nFantasy Value totale rosa 'Io': "
          f"media {statistics.mean(score_totals):.1f}, "
          f"dev.std {statistics.pstdev(score_totals):.1f}")

    print("\nSpesa per ruolo — media simulata vs piano studiato (sez. budget.py):")
    for role in ROLE_SLOTS:
        studied = ROLE_BUDGET_PCT[role] * 100
        observed = statistics.mean(role_spend_pct[role])
        print(f"  {role}: osservato {observed:.1f}%  vs  studiato {studied:.1f}%")

    lp_exceptions = []
    if lp_statuses:
        n = len(lp_statuses)
        n_optimal = lp_statuses.count("optimal")
        n_infeasible = lp_statuses.count("infeasible")
        n_skipped = sum(1 for s in lp_statuses if s.startswith("skipped:"))
        lp_exceptions = [s for s in lp_statuses if s.startswith("exception:")]
        print(f"\nOptimizer LP (campione {n} run, snapshot a metà asta): "
              f"optimal={n_optimal}, infeasible={n_infeasible}, "
              f"skipped={n_skipped}, exception={len(lp_exceptions)}")
        for exc in lp_exceptions[:10]:
            print(f"  {exc}")

    print("\nDimensione media dei tier per ruolo (su tutte le run):")
    for role in ROLE_SLOTS:
        parts = [
            f"{TIER_LABELS[tier]}={statistics.mean(tier_size_samples[role][tier]):.1f}"
            for tier in TIER_ORDER
        ]
        print(f"  {role}: " + ", ".join(parts))

    print("\n" + "=" * 70)
    ok = not all_anomalies and stalled_runs == 0 and not lp_exceptions
    print("ESITO: " + ("OK — nessuna anomalia rilevata." if ok
                        else "ATTENZIONE — vedi anomalie/run stallate/eccezioni LP sopra."))
    print("=" * 70)


if __name__ == "__main__":
    main()
