"""Auction Intelligence Engine (spec sezioni 84-97): il prezzo di un
giocatore durante un'asta reale non è un numero fisso — dipende da quanto
si sta pagando finora rispetto al valore stimato (inflazione), da quante
alternative restano per quel ruolo (scarsità), da quanto budget/slot restano
a te e agli avversari.

Feasibility note: la nostra asta è vocale/in presenza, quindi l'unico segnale
sugli avversari è quello che l'utente registra a posteriori ("Presi dagli
avversari": chi, quanto, quando). Questo modulo lavora solo con quel dato —
niente feed live dei rilanci — assumendo che tutte le squadre della lega
seguano le stesse regole (stesso budget, stessi slot per ruolo) di
ranking.budget.ROLE_SLOTS/total_credits, l'unica assunzione ragionevole senza
un feed esterno.
"""

import statistics

from ranking.budget import ROLE_SLOTS

TOTAL_SLOTS = sum(ROLE_SLOTS.values())

# Un'inflazione/deflazione osservata sposta le stime future, ma non 1:1:
# un'asta può normalizzarsi, quindi smorziamo l'effetto invece di proiettarlo
# in pieno sul prossimo giocatore.
INFLATION_SENSITIVITY = 0.7
INFLATION_CLAMP = (-30.0, 60.0)

# Quanto in più del fair price si è disposti a spingersi quando restano
# pochissime alternative valide per il ruolo.
SCARCITY_PREMIUM = {0: 0.25, 1: 0.15, 2: 0.08, 3: 0.03}

# "Massimo teorico" (riserva 1 credito per ogni altro slot rimasto) è un
# limite matematico, non uno che qualcuno spende davvero fino in fondo.
REALISTIC_BUDGET_FACTOR = 0.78

MIN_PURCHASES_FOR_INFLATION = 3
MIN_PURCHASES_FOR_DISTRIBUTION = 5


def compute_price_inflation(purchases: list) -> dict:
    """purchases: [{"price_paid": float, "fair_price": float}, ...] — ogni
    acquisto già registrato (mio o di un avversario) con il fair price
    (quotazione consensus) del giocatore al momento della query.

    Ritorna inflation_pct positivo se si sta pagando più del fair price
    medio, negativo se meno (deflazione). None se non ci sono abbastanza
    dati per fidarsi del segnale.
    """
    valid = [p for p in purchases if p.get("fair_price")]
    if len(valid) < MIN_PURCHASES_FOR_INFLATION:
        return {"inflation_pct": None, "sample_size": len(valid)}

    avg_fair = sum(p["fair_price"] for p in valid) / len(valid)
    avg_paid = sum(p["price_paid"] for p in valid) / len(valid)
    if avg_fair == 0:
        return {"inflation_pct": None, "sample_size": len(valid)}

    inflation_pct = round((avg_paid - avg_fair) / avg_fair * 100, 1)
    return {
        "inflation_pct": inflation_pct,
        "avg_fair_price": round(avg_fair, 2),
        "avg_price_paid": round(avg_paid, 2),
        "sample_size": len(valid),
    }


def compute_expected_auction_price(fair_price: float, inflation_pct) -> float:
    """Quanto probabilmente costerà, non il tetto massimo consigliato."""
    if not fair_price:
        return None
    pct = inflation_pct if inflation_pct is not None else 0.0
    pct = max(INFLATION_CLAMP[0], min(INFLATION_CLAMP[1], pct))
    return round(fair_price * (1 + (pct * INFLATION_SENSITIVITY) / 100), 1)


def compute_scarcity_tier(alternatives_remaining: int) -> dict:
    """alternatives_remaining: quanti giocatori comparabili (stesso ruolo,
    Fantasy Value simile) sono ancora liberi. Meno ce ne sono, più il
    giocatore in questione diventa prezioso indipendentemente dal suo fair
    price assoluto."""
    premium = SCARCITY_PREMIUM.get(alternatives_remaining, 0.0)
    if alternatives_remaining <= 1:
        label = "Critica"
    elif alternatives_remaining <= 3:
        label = "Alta"
    elif alternatives_remaining <= 6:
        label = "Media"
    else:
        label = "Bassa"
    return {"alternatives_remaining": alternatives_remaining, "premium": premium, "label": label}


def compute_max_theoretical_bid(budget_remaining: float, slots_remaining: int) -> float:
    """Limite matematico: riserva almeno 1 credito per ognuno degli altri
    slot ancora da riempire (compreso quello di questo acquisto)."""
    if slots_remaining <= 0:
        return 0.0
    return max(0.0, budget_remaining - (slots_remaining - 1))


def compute_dynamic_max_bid(fair_price: float, budget_remaining: float,
                             slots_remaining: int, inflation_pct=None,
                             alternatives_remaining: int | None = None) -> dict:
    """Il Maximum Bid vero (spec sez. 85): parte dal fair price, sale con
    l'inflazione osservata e con la scarsità di alternative, ma non supera
    mai quanto è realmente disponibile per quello slot."""
    if not fair_price:
        return {"max_bid": None, "capped_by_budget": False}

    pct = inflation_pct if inflation_pct is not None else 0.0
    pct = max(0.0, min(INFLATION_CLAMP[1], pct))  # solo l'inflazione alza il tetto, mai la deflazione
    scarcity = compute_scarcity_tier(alternatives_remaining) if alternatives_remaining is not None else None
    premium = scarcity["premium"] if scarcity else 0.0

    uncapped = fair_price * (1 + pct / 100 * INFLATION_SENSITIVITY + premium)
    theoretical = compute_max_theoretical_bid(budget_remaining, slots_remaining)
    realistic_cap = theoretical * REALISTIC_BUDGET_FACTOR if theoretical else 0.0

    max_bid = max(fair_price, min(uncapped, theoretical)) if theoretical else fair_price
    return {
        "max_bid": round(max_bid, 1),
        "uncapped_estimate": round(uncapped, 1),
        "theoretical_budget_cap": round(theoretical, 1),
        "realistic_budget_cap": round(realistic_cap, 1),
        "capped_by_budget": uncapped > theoretical,
        "scarcity": scarcity,
    }


def compute_price_distribution(fair_price: float, price_ratios: list) -> dict:
    """price_ratios: rapporti (price_paid / fair_price) osservati sugli
    acquisti storici (miei + avversari). Proietta quella distribuzione sul
    fair price di *questo* giocatore per stimare un range di prezzo
    plausibile invece di un singolo numero."""
    if not fair_price or len(price_ratios) < MIN_PURCHASES_FOR_DISTRIBUTION:
        return None

    sorted_ratios = sorted(price_ratios)

    def _pct(p):
        return statistics.quantiles(sorted_ratios, n=100, method="inclusive")[p - 1]

    p25, median, p75, p90 = (
        _pct(25), statistics.median(sorted_ratios), _pct(75), _pct(90),
    )
    return {
        "expected_price": round(fair_price * statistics.mean(sorted_ratios), 1),
        "p25": round(fair_price * p25, 1),
        "median": round(fair_price * median, 1),
        "p75": round(fair_price * p75, 1),
        "p90": round(fair_price * p90, 1),
        "sample_size": len(price_ratios),
    }


def compute_opponent_budget_model(opponent_name: str, picks: list,
                                   total_credits: int = 500) -> dict:
    """picks: le righe di get_opponent_picks già filtrate per questo
    avversario. Assume le sue stesse regole di lega (stesso budget/slot per
    ruolo) — l'unica ipotesi sensata senza un feed live del suo budget reale."""
    spent = sum(p["price_paid"] for p in picks)
    players_bought = len(picks)
    budget_remaining = total_credits - spent
    slots_remaining = max(TOTAL_SLOTS - players_bought, 0)

    filled_by_role = {role: 0 for role in ROLE_SLOTS}
    for p in picks:
        role = p.get("role_classic")
        if role in filled_by_role:
            filled_by_role[role] += 1
    roles_missing = {role: total - filled_by_role[role] for role, total in ROLE_SLOTS.items()}

    theoretical_max = compute_max_theoretical_bid(budget_remaining, slots_remaining)
    avg_price_paid = round(spent / players_bought, 1) if players_bought else None

    return {
        "opponent_name": opponent_name,
        "spent": spent,
        "players_bought": players_bought,
        "budget_remaining": budget_remaining,
        "slots_remaining": slots_remaining,
        "roles_missing": roles_missing,
        "avg_price_paid": avg_price_paid,
        "theoretical_max_bid": round(theoretical_max, 1),
        "realistic_max_bid": round(theoretical_max * REALISTIC_BUDGET_FACTOR, 1),
    }


def compute_rival_threat_score(model: dict, league_avg_price_paid: float,
                                league_max_budget_remaining: float) -> float:
    """0-100: quanto un avversario è pericoloso per i prossimi acquisti,
    combinando quanto budget gli resta e quanto sta pagando finora rispetto
    alla media della lega (un avversario aggressivo alza il prezzo di tutto
    quello che chiama)."""
    if league_max_budget_remaining <= 0:
        budget_component = 0.0
    else:
        budget_component = max(0.0, min(1.0, model["budget_remaining"] / league_max_budget_remaining))

    if not league_avg_price_paid or not model.get("avg_price_paid"):
        aggressiveness_component = 0.5  # nessun dato ancora: neutro, non zero
    else:
        aggressiveness_component = max(0.0, min(1.5, model["avg_price_paid"] / league_avg_price_paid)) / 1.5

    score = 100 * (0.6 * budget_component + 0.4 * aggressiveness_component)
    return round(score, 1)


def compute_all_opponent_models(opponent_picks: list, total_credits: int = 500) -> list:
    """opponent_picks: repository.get_opponent_picks(conn) — tutte le righe,
    tutti gli avversari insieme. Raggruppa per nome e calcola threat score
    relativo tra loro."""
    by_opponent: dict = {}
    for pick in opponent_picks:
        by_opponent.setdefault(pick["opponent_name"], []).append(pick)

    models = [
        compute_opponent_budget_model(name, picks, total_credits)
        for name, picks in by_opponent.items()
    ]
    if not models:
        return []

    paid_values = [m["avg_price_paid"] for m in models if m["avg_price_paid"]]
    league_avg_price_paid = sum(paid_values) / len(paid_values) if paid_values else None
    league_max_budget_remaining = max((m["budget_remaining"] for m in models), default=0)

    for model in models:
        model["threat_score"] = compute_rival_threat_score(
            model, league_avg_price_paid, league_max_budget_remaining,
        )
    return sorted(models, key=lambda m: m["threat_score"], reverse=True)


AUCTION_TIMING_LABELS = {
    "buy_now": "🟢 BUY NOW",
    "wait": "⏳ WAIT",
    "pass": "🔴 PASS",
    "save_budget": "💰 SAVE BUDGET",
}


def compute_auction_timing(slot_remaining: int, scarcity_tier: dict,
                            inflation_pct, budget_remaining: float,
                            fair_price: float) -> dict:
    """Output semplice (spec sez. 90/104): BUY NOW / WAIT / PASS / SAVE
    BUDGET, con il motivo principale."""
    if slot_remaining <= 0:
        return {"action": "pass", "label": AUCTION_TIMING_LABELS["pass"],
                "reason": "Ruolo già coperto: nessuno slot libero."}

    if fair_price and budget_remaining < fair_price * 0.5:
        return {"action": "save_budget", "label": AUCTION_TIMING_LABELS["save_budget"],
                "reason": "Budget residuo troppo basso rispetto al fair price: "
                          "rischi di restare senza credito per altri ruoli."}

    scarcity_label = scarcity_tier["label"] if scarcity_tier else "Media"
    pct = inflation_pct or 0.0

    if scarcity_label in ("Critica", "Alta"):
        return {"action": "buy_now", "label": AUCTION_TIMING_LABELS["buy_now"],
                "reason": f"Scarsità {scarcity_label.lower()}: poche alternative valide "
                          "restano per questo ruolo, rischi di restare senza."}

    if pct > 20:
        return {"action": "wait", "label": AUCTION_TIMING_LABELS["wait"],
                "reason": f"Asta in forte inflazione (+{pct:.0f}%): meglio aspettare "
                          "un momento più favorevole o un'alternativa meno contesa."}

    return {"action": "wait", "label": AUCTION_TIMING_LABELS["wait"],
            "reason": "Nessuna urgenza: alternative ancora disponibili e prezzi in linea."}
