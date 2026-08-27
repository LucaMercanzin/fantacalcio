"""Price Engine (spec impossibile-analisi-avanzata.md sez. 3): fair price,
prezzo consigliato, prezzo massimo, BUY/PASS — da Fantasy Value, prezzo di
mercato, scarsità e replacement advantage che già calcoliamo altrove
(ranking.scarcity, ranking.replacement). Nessun dato di tracking/xG richiesto.

I coefficienti sotto sono scelte esplicite e documentate, non derivate da un
fit sui dati (richiederebbe uno storico multi-stagione di risultati reali
d'asta che non abbiamo) — un punto di partenza ragionevole, regolabile in
futuro se si rivela sbagliato osservando aste vere.
"""

# scarsità massima (100) -> fino a +25% sopra il fair price: vale la pena
# pagare un premio per un giocatore senza alternative comparabili.
SCARCITY_PREMIUM_MAX = 0.25

# un replacement advantage di 20+ punti di score (differenza dal miglior
# alternativo) è già "molto meglio delle alternative" -> premio pieno.
REPLACEMENT_ADVANTAGE_SCALE = 20.0
REPLACEMENT_PREMIUM_MAX = 0.15

# oltre il 5% sopra il max_price è chiaramente PASS, non solo "borderline".
PASS_MARGIN = 1.05

BUY = "BUY"
BORDERLINE = "BORDERLINE"
PASS = "PASS"


def compute_fair_price(score: float, median_value_for_money: float):
    """Prezzo a cui questo giocatore renderebbe quanto un giocatore "medio"
    del ruolo per credito speso (la mediana di value_for_money tra i
    disponibili del ruolo). None se non c'è una mediana valida (ruolo senza
    prezzi noti)."""
    if not median_value_for_money:
        return None
    return round(score / median_value_for_money * 10, 1)


def compute_max_price(fair_price: float, scarcity: float, replacement_advantage: float) -> float:
    replacement_norm = max(0.0, min(1.0, replacement_advantage / REPLACEMENT_ADVANTAGE_SCALE))
    scarcity_norm = max(0.0, min(1.0, scarcity / 100))
    premium = SCARCITY_PREMIUM_MAX * scarcity_norm + REPLACEMENT_PREMIUM_MAX * replacement_norm
    return round(fair_price * (1 + premium), 1)


def compute_price_recommendation(
    score: float, price_current, median_value_for_money: float,
    scarcity: float, replacement_advantage: float,
) -> dict:
    """Ritorna fair_price/recommended_min/max_price/status. status è None
    (nessuna raccomandazione) quando manca un prezzo di mercato con cui
    confrontarsi."""
    fair_price = compute_fair_price(score, median_value_for_money)
    if fair_price is None:
        return {"fair_price": None, "recommended_min": None, "max_price": None, "status": None}

    max_price = compute_max_price(fair_price, scarcity, replacement_advantage)
    recommended_min = round(fair_price * 0.95, 1)

    status = None
    if price_current is not None:
        if price_current <= max_price:
            status = BUY
        elif price_current > max_price * PASS_MARGIN:
            status = PASS
        else:
            status = BORDERLINE

    return {
        "fair_price": fair_price,
        "recommended_min": recommended_min,
        "max_price": max_price,
        "status": status,
    }
