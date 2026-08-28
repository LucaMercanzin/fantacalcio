"""Rules-based verdetto (statistiche giocatore sez. 23): turns the
already-computed separated scores (tier, risk, value_for_money_percentile,
tactical_profile_score) into a short, generated-not-hand-written summary. No
new data, no new score — a fixed decision table over numbers the scoring
pipeline already produces."""

from ranking.tiers import (
    TOP, SEMI_TOP, TITOLARE_FISSO, BASSO_PREZZO, SCOMMESSA, DA_EVITARE,
    PROVEN_MIN_APPEARANCES, NAILED_ON_MIN_APPEARANCES, UNPROVEN_MAX_APPEARANCES,
)

TIER_STARS = {
    TOP: 5, SEMI_TOP: 4, TITOLARE_FISSO: 3, BASSO_PREZZO: 3, SCOMMESSA: 2, DA_EVITARE: 1,
}

TIER_HEADLINES = {
    5: "Top player del ruolo.",
    4: "Semi-top, scelta solida.",
    3: "Titolare affidabile.",
    2: "Scommessa: potenziale incerto.",
    1: "Da evitare o da monitorare con cautela.",
}

RISK_LOW = 35.0
RISK_HIGH = 60.0
VFM_PCT_GOOD = 66.0
VFM_PCT_BAD = 20.0
TACTICAL_PROFILE_GOOD = 60.0
PENALIZED_STATUSES = {"infortunato", "squalificato"}


def compute_verdict(row: dict, set_pieces: list) -> dict:
    tier = row.get("tier")
    # No silent default to 3: a player who didn't clearly fit any tier
    # (classify_role leaves him unclassified on purpose, see tiers.py) must
    # not be presented as an average "Titolare affidabile" — that's a
    # specific, false claim about a player the system has no verdict on
    # (P2-003 in OPUS_PROJECT_REVIEW.md).
    stars = TIER_STARS.get(tier)

    strengths = []
    risks = []

    appearances = row.get("appearances")
    if appearances is not None and appearances >= NAILED_ON_MIN_APPEARANCES:
        strengths.append("Titolare quasi certo")
    elif appearances is not None and appearances >= PROVEN_MIN_APPEARANCES:
        strengths.append("Buona continuità di impiego")
    elif appearances is not None and appearances < UNPROVEN_MAX_APPEARANCES:
        risks.append("Poche presenze: rendimento ancora da confermare")

    for sp in set_pieces or []:
        if sp["rank"] == 1:
            strengths.append(f"Rigorista/battitore principale ({sp['category']})")

    risk = row.get("risk")
    if risk is not None and risk < RISK_LOW:
        strengths.append("Alta affidabilità")
    elif risk is not None and risk >= RISK_HIGH:
        risks.append("Rischio elevato (affidabilità bassa)")

    vfm_pct = row.get("value_for_money_percentile")
    if vfm_pct is not None and vfm_pct >= VFM_PCT_GOOD:
        strengths.append("Buon rapporto qualità/prezzo")
    elif vfm_pct is not None and vfm_pct < VFM_PCT_BAD:
        risks.append("Prezzo d'asta elevato rispetto al rendimento atteso")

    tactical = row.get("tactical_profile_score")
    if tactical is not None and tactical >= TACTICAL_PROFILE_GOOD:
        strengths.append("Profilo tattico offensivo favorevole")

    status = row.get("status")
    if status in PENALIZED_STATUSES:
        risks.append(f"Attualmente {status}")
    elif status is None:
        # status is not yet populated by any scraper (P0-008): "no risk
        # found" here would be a false reassurance, not an absence of
        # problems — say so instead of staying silent.
        risks.append("Disponibilità (infortunio/squalifica) non verificata: controlla manualmente")

    if not strengths:
        strengths.append("Nessun punto di forza particolare rilevato dai dati disponibili")

    return {
        "stars": stars,
        "headline": TIER_HEADLINES.get(stars, "Non classificabile: dati insufficienti per questo ruolo/tier"),
        "strengths": strengths,
        "risks": risks,
    }
