"""Auction-progress checklist and phase tracker (giocatori/rosa-ideale.md
sez. 26 "Strategia durante l'asta", sez. 28 "Checklist finale"): turns
signals already computed elsewhere (ranking.budget's slot-fill counts,
season goals/assists already on get_ranked_role's rows) into the spec's own
18-item checklist and 5-phase auction guide, instead of leaving the user to
cross-reference budget/roster against the spec by hand."""

from ranking.tiers import UNPROVEN_MAX_APPEARANCES

# Thresholds below are deliberately modest season totals (giocatori/
# rosa-ideale.md gives no exact numbers for sez. 28's checklist items) —
# enough to distinguish "this role is contributing" from "this role is
# empty", not a claim about what counts as "good" for a specific player.
OFFENSIVE_DEFENDER_MANTRA = {"E", "DD", "DS", "B"}
MIDFIELD_OFFENSIVE_MANTRA = {"T", "W", "A"}
MIN_OFFENSIVE_DEFENDERS = 2
MIN_OFFENSIVE_MIDFIELDERS = 3
MIN_MIDFIELD_GOALS = 3
MIN_MIDFIELD_ASSISTS = 3
MIN_STRIKER_GOALS = 8
MIN_STRIKER_ASSISTS_FOR_CREATOR = 3
MIN_VOTE_TAKERS = 15
MIN_DEPTH_TOTAL = 20
RELIABLE_APPEARANCES = 15

# 3-4-3 starting shape (matches dashboard.pages.5_La_Mia_Rosa's PITCH_ROWS)
# — sez. 28's last item ("posso schierare un 3-4-3 competitivo anche con
# 2-3 assenze?") needs each outfield role to have this many starters plus a
# depth buffer.
FORMATION_STARTERS = {"P": 1, "D": 3, "C": 4, "A": 3}
DEPTH_BUFFER = 2

# A player paid more than this multiple of today's quotation is a candidate
# for sez. 28's "ho evitato di pagare il nome?" — a real overpay signal
# using only price_paid (my_roster) vs price_current (today's consensus
# quotation), not a claim about what was reasonable at auction time.
OVERPAY_RATIO = 1.3


def _owned(rows, role):
    return [r for r in rows if r["role_classic"] == role]


def _appearances_ok(row):
    return (row.get("appearances") or 0) >= RELIABLE_APPEARANCES


def build_checklist(roster_rows: list) -> list:
    """roster_rows: dashboard.data_access.get_roster_with_profile(conn)
    output. Returns a list of {"text": str, "status": bool | None} in the
    same order as rosa-ideale.md sez. 28 — status is None when nothing in
    the schema can answer the item (shown as "verifica manuale" in the UI),
    never a guessed True/False."""
    p_rows = _owned(roster_rows, "P")
    d_rows = _owned(roster_rows, "D")
    c_rows = _owned(roster_rows, "C")
    a_rows = _owned(roster_rows, "A")

    offensive_defenders = [r for r in d_rows if r.get("role_mantra") in OFFENSIVE_DEFENDER_MANTRA]
    quinto_or_terzino = [r for r in d_rows if r.get("role_mantra") in {"E", "DD", "DS"}]
    reliable_centrali = [
        r for r in d_rows if r.get("role_mantra") == "DC" and _appearances_ok(r)
    ]
    offensive_midfielders = [r for r in c_rows if r.get("role_mantra") in MIDFIELD_OFFENSIVE_MANTRA]
    midfield_goals = sum(r.get("season_goals_scored") or 0 for r in c_rows)
    midfield_assists = sum(r.get("season_assists") or 0 for r in c_rows)
    striker_scorers = [r for r in a_rows if (r.get("season_goals_scored") or 0) >= MIN_STRIKER_GOALS]
    striker_creators = [r for r in a_rows if (r.get("season_assists") or 0) >= MIN_STRIKER_ASSISTS_FOR_CREATOR]
    vote_takers = [r for r in roster_rows if _appearances_ok(r)]
    scommesse = [
        r for r in roster_rows
        if r.get("appearances") is None or r["appearances"] < UNPROVEN_MAX_APPEARANCES
    ]
    overpaid = [
        r for r in roster_rows
        if r.get("price_paid") is not None and r.get("price_current")
        and r["price_paid"] > r["price_current"] * OVERPAY_RATIO
    ]
    bonus_role_count = sum(
        1 for group in (d_rows, c_rows, a_rows)
        if sum((r.get("season_goals_scored") or 0) + (r.get("season_assists") or 0) for r in group) > 0
    )
    formation_ready = all(
        len(_owned(roster_rows, role)) >= need + (DEPTH_BUFFER if role != "P" else 0)
        for role, need in FORMATION_STARTERS.items()
    )

    return [
        {"text": "Ho un portiere titolare affidabile?",
         "status": any(_appearances_ok(r) for r in p_rows)},
        {"text": "Ho una copertura adeguata in porta?",
         "status": len(p_rows) >= 2},
        {"text": "Ho almeno 2-3 difensori offensivi?",
         "status": len(offensive_defenders) >= MIN_OFFENSIVE_DEFENDERS},
        {"text": "Ho almeno un quinto/terzino listato difensore?",
         "status": len(quinto_or_terzino) >= 1},
        {"text": "Ho centrali affidabili per la copertura?",
         "status": len(reliable_centrali) >= 1},
        {"text": "Ho almeno 3-4 centrocampisti con produzione offensiva?",
         "status": len(offensive_midfielders) >= MIN_OFFENSIVE_MIDFIELDERS},
        {"text": "Ho almeno un centrocampista che gioca quasi da attaccante?",
         "status": len(offensive_midfielders) >= 1},
        {"text": "Ho abbastanza gol a centrocampo?",
         "status": midfield_goals >= MIN_MIDFIELD_GOALS},
        {"text": "Ho abbastanza assist a centrocampo?",
         "status": midfield_assists >= MIN_MIDFIELD_ASSISTS},
        {"text": "Ho una punta realmente da gol?",
         "status": len(striker_scorers) >= 1},
        {"text": "Ho almeno un attaccante capace di creare assist?",
         "status": len(striker_creators) >= 1},
        {"text": "Ho abbastanza titolari per affrontare le assenze?",
         "status": len(roster_rows) >= MIN_DEPTH_TOTAL},
        {"text": "Ho stabilito un prezzo massimo per i giocatori?",
         "status": None},
        {"text": "Ho evitato di pagare il nome?",
         "status": len(overpaid) == 0},
        {"text": "Ho distribuito i bonus tra più reparti?",
         "status": bonus_role_count >= 2},
        {"text": "Ho abbastanza giocatori che prendono voto?",
         "status": len(vote_takers) >= MIN_VOTE_TAKERS},
        {"text": "Ho alcune scommesse con alto potenziale?",
         "status": len(scommesse) >= 1},
        {"text": "Posso schierare un 3-4-3 competitivo anche con 2-3 assenze?",
         "status": formation_ready},
    ]


PHASE_LABELS = {
    "P": "Fase 1 — Portieri",
    "D": "Fase 2 — Difensori",
    "C": "Fase 3 — Centrocampisti",
    "A": "Fase 4 — Attaccanti",
}
PHASE_FOCUS = {
    "P": "Stabilisci coppia preferita e budget massimo (sez. 26).",
    "D": "Concentrati su quinti, terzini e difensori da bonus; evita di "
         "spendere troppo sui centrali puri.",
    "C": "Cerca gol + assist + posizione offensiva: la fase più importante "
         "per un 3-4-3.",
    "A": "Compra almeno una punta da gol, un secondo giocatore da bonus e "
         "un esterno/seconda punta.",
}


def current_phase(budget_summary: dict) -> dict:
    """budget_summary: ranking.budget.compute_budget_summary(roster) output.
    The first role (in P/D/C/A order, matching sez. 26's own phase order)
    with unfilled slots is the current phase; once all four are full it's
    sez. 26's Fase 5 — completamento with the leftover budget."""
    for role in ("P", "D", "C", "A"):
        if budget_summary["slots"][role]["remaining"] > 0:
            return {"role": role, "label": PHASE_LABELS[role], "focus": PHASE_FOCUS[role]}
    return {
        "role": None, "label": "Fase 5 — Completamento",
        "focus": "Usa i crediti rimanenti per titolari, coperture e scommesse.",
    }
