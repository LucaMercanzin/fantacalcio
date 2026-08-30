"""Classifies players within one role's already-ranked list (rank_players
output) into named tiers for quick scanning during the auction — the
counterpart to per-player scores: those answer "how good/risky/cheap is
this one player", tiers answer "which handful of players in this role
should I actually be looking at, and why".

Each player gets at most one tier — the first matching rule below, checked
in this order, wins — and only "available" players (not already mine, not
already taken by an opponent) are classified at all, since a tier is meant
to guide the *next* decision, not describe the whole role.

Thresholds are percentiles within the role's own population
(ranking.percentile.percentile_rank), so a "Top" difensore is compared
against other difensori, never against attaccanti.
"""

from ranking.percentile import percentile_rank

TOP = "top"
SEMI_TOP = "semi_top"
TITOLARE_FISSO = "titolare_fisso"
BASSO_PREZZO = "basso_prezzo"
SCOMMESSA = "scommessa"
DA_EVITARE = "da_evitare"

TIER_ORDER = [TOP, SEMI_TOP, TITOLARE_FISSO, BASSO_PREZZO, SCOMMESSA, DA_EVITARE]

TIER_LABELS = {
    TOP: "🏆 Top",
    SEMI_TOP: "⭐ Semi-top",
    TITOLARE_FISSO: "🛡️ Titolari fissi",
    BASSO_PREZZO: "💰 A basso prezzo",
    SCOMMESSA: "🎲 Scommesse",
    DA_EVITARE: "🚫 Da evitare",
}

TIER_DESCRIPTIONS = {
    TOP: "I migliori del ruolo: rendimento alto, rischio contenuto, presenze consolidate.",
    SEMI_TOP: "Un gradino sotto i top, ma comunque affidabili e forti.",
    TITOLARE_FISSO: "Giocano sempre (presenze quasi piene) e a basso rischio, "
                     "anche se non tra i più prolifici — sicurezza per la rosa.",
    BASSO_PREZZO: "Miglior rapporto qualità/prezzo del ruolo: rendono più di "
                   "quanto costano, senza essere già tra i big.",
    SCOMMESSA: "Poche presenze/dati (giovani, nuovi arrivi, rientri): potenziale "
               "incerto ma non già bocciato dai numeri.",
    DA_EVITARE: "Tra i peggiori del ruolo per rapporto qualità/prezzo/rischio. "
                "(Il rilevamento di infortuni/squalifiche non è ancora popolato dai dati: "
                "verifica sempre manualmente la disponibilità prima di scartare un giocatore.)",
}

PENALIZED_STATUSES = {"infortunato", "squalificato"}

# Below this many appearances (out of 38) a player is "unproven" — too little
# signal to trust as Top/Titolare fisso, but not automatically bad either.
UNPROVEN_MAX_APPEARANCES = 12
# At/above this many appearances a player has essentially played every game.
NAILED_ON_MIN_APPEARANCES = 34
# Above this many appearances a player counts as genuinely "proven" for Top.
PROVEN_MIN_APPEARANCES = 20


def classify_role(rows: list) -> dict:
    """rows: get_ranked_role's output for one role (already merged, scored,
    with is_in_roster/taken_by set). Returns {tier: [rows]}, each list
    sorted best-first by score, tiers with no matching player omitted.
    """
    available = [r for r in rows if not r.get("is_in_roster") and not r.get("taken_by")]
    if not available:
        return {}

    scores = sorted(r["score"] for r in available)
    decision_scores = sorted(
        r["decision_score"] for r in available if r.get("decision_score") is not None
    )
    prices = sorted(r["price_current"] for r in available if r.get("price_current"))
    median_price = prices[len(prices) // 2] if prices else None

    tiers: dict = {tier: [] for tier in TIER_ORDER}
    for r in available:
        appearances = r.get("appearances")
        risk = r.get("risk")
        risk = risk if risk is not None else 50.0
        score_pct = percentile_rank(r["score"], scores)
        decision_pct = (
            percentile_rank(r["decision_score"], decision_scores)
            if r.get("decision_score") is not None else 50.0
        )
        vfm_pct = r.get("value_for_money_percentile")
        vfm_pct = vfm_pct if vfm_pct is not None else 50.0
        price = r.get("price_current")

        proven = appearances is not None and appearances >= PROVEN_MIN_APPEARANCES
        nailed_on = appearances is not None and appearances >= NAILED_ON_MIN_APPEARANCES
        unproven = appearances is None or appearances < UNPROVEN_MAX_APPEARANCES

        if r.get("status") in PENALIZED_STATUSES or decision_pct <= 15:
            tiers[DA_EVITARE].append(r)
        elif score_pct >= 90 and risk < 50 and proven:
            tiers[TOP].append(r)
        elif score_pct >= 75 and risk < 60 and not unproven:
            tiers[SEMI_TOP].append(r)
        # score_pct >= 40 keeps this tier meaning "solid, always plays" —
        # without a quality floor, a genuinely weak player who only starts
        # because his team has no better options (nailed-on + low risk,
        # since compute_risk tracks reliability, not production) would
        # qualify just as easily as a real regular contributor.
        elif nailed_on and risk < 35 and score_pct >= 40:
            tiers[TITOLARE_FISSO].append(r)
        elif vfm_pct >= 80 and median_price is not None and price is not None and price <= median_price:
            tiers[BASSO_PREZZO].append(r)
        elif unproven:
            tiers[SCOMMESSA].append(r)
        # else: doesn't clearly fit a tier — deliberately left unclassified
        # rather than forced into the closest bucket, so each tier stays a
        # curated shortlist instead of a full partition of the role.

    for tier in tiers:
        tiers[tier].sort(key=lambda r: r["score"], reverse=True)
    return {tier: players for tier, players in tiers.items() if players}
