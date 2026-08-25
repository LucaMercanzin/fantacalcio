"""Valutazione 'ne vale la pena?' per un giocatore ad un prezzo ipotetico.

Risponde alle quattro domande che l'utente si fa prima di rilanciare in asta:
- vale il prezzo che sto per pagare?
- è troppo caro?
- anche a poco mi è inutile (ho già di meglio / ruolo pieno)?
- devo spingere fino in fondo (ultimo slot buono) o non ha senso spendere?
"""

from ranking.scorer import compute_value_for_money

VERDICT_HEADLINES = {
    "ruolo_pieno": "Ruolo già coperto: inutile a qualsiasi prezzo.",
    "inutile_hai_di_meglio": "Inutile alla tua rosa anche a poco prezzo.",
    "affare": "Affare: a questo prezzo rende più della sua quotazione.",
    "prezzo_giusto": "Prezzo giusto, in linea con il suo valore reale.",
    "caro": "Un po' caro rispetto a quanto rende.",
    "troppo_caro": "Troppo caro: stai pagando molto più di quanto rende.",
    "sconosciuto": "Dati insufficienti per un confronto preciso.",
}

# Sopra/sotto questi rapporti tra value-for-money al prezzo proposto e al
# prezzo di quotazione, il giudizio cambia categoria.
RATIO_THRESHOLDS = {"affare": 1.15, "prezzo_giusto": 0.85, "caro": 0.6}


def evaluate_purchase(player: dict, price: float, slot: dict,
                       roster_role_scores: list) -> dict:
    """Args:
        player: riga giocatore arricchita (score, value_for_money, price_current,
            rank_in_role, role_classic...).
        price: prezzo ipotetico che l'utente sta valutando.
        slot: {"filled", "total", "remaining"} per il ruolo del giocatore
            (da ranking.budget.compute_budget_summary).
        roster_role_scores: Fantasy Value dei giocatori già in rosa per quel ruolo.
    """
    fantasy_value = player.get("score") or 0.0
    reasons: list = []

    if slot["remaining"] <= 0:
        return {
            "verdict": "ruolo_pieno",
            "headline": VERDICT_HEADLINES["ruolo_pieno"],
            "reasons": ["Hai già tutti gli slot per questo ruolo occupati."],
            "all_in_recommended": False,
            "value_for_money_at_price": None,
            "value_for_money_at_listed": player.get("value_for_money"),
        }

    if roster_role_scores and slot["remaining"] <= 1:
        weakest_owned = min(roster_role_scores)
        if fantasy_value <= weakest_owned:
            reasons.append(
                f"Hai già titolari più forti in questo ruolo (Fantasy Value minimo "
                f"posseduto {weakest_owned:.1f} contro {fantasy_value:.1f} di questo giocatore): "
                "non ti serve nemmeno a poco prezzo."
            )
            return {
                "verdict": "inutile_hai_di_meglio",
                "headline": VERDICT_HEADLINES["inutile_hai_di_meglio"],
                "reasons": reasons,
                "all_in_recommended": False,
                "value_for_money_at_price": compute_value_for_money(fantasy_value, price),
                "value_for_money_at_listed": player.get("value_for_money"),
            }

    vfm_listed = player.get("value_for_money")
    vfm_at_price = compute_value_for_money(fantasy_value, price)

    ratio = vfm_at_price / vfm_listed if (vfm_at_price is not None and vfm_listed) else None

    if ratio is None:
        verdict = "sconosciuto"
    elif ratio >= RATIO_THRESHOLDS["affare"]:
        verdict = "affare"
    elif ratio >= RATIO_THRESHOLDS["prezzo_giusto"]:
        verdict = "prezzo_giusto"
    elif ratio >= RATIO_THRESHOLDS["caro"]:
        verdict = "caro"
    else:
        verdict = "troppo_caro"

    all_in_recommended = False
    if (
        slot["remaining"] <= 1
        and player.get("rank_in_role") is not None
        and player["rank_in_role"] <= 3
        and verdict in ("caro", "troppo_caro")
    ):
        all_in_recommended = True
        reasons.append(
            "È uno degli ultimi slot liberi per questo ruolo e questo giocatore è tra i "
            "migliori disponibili: se non spendi quanto serve rischi di restare senza un "
            "titolare di livello — o lo prendi al prezzo giusto, o rinunci del tutto."
        )

    return {
        "verdict": verdict,
        "headline": VERDICT_HEADLINES[verdict],
        "reasons": reasons,
        "all_in_recommended": all_in_recommended,
        "value_for_money_at_price": vfm_at_price,
        "value_for_money_at_listed": vfm_listed,
    }
