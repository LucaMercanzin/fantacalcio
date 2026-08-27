"""fantasy_profile_score (giocatori/movimento.md sez. 15/18, giocatori/
rosa-ideale.md sez. 2/24): how much a player's REAL tactical role, not his
official role_classic, is worth to a fantacalcio squad.

Fantacalcio.it's own "Ruolo Mantra" taxonomy (role_mantra: por/dc/dd/ds/b/e/
m/c/t/w/a/pc) already encodes almost exactly the tactical profile the specs
describe — quinto offensivo = "e", trequartista = "t", mediano = "m",
seconda punta = "a" — so this module builds on that instead of needing new
xG/xA/shots scraping infrastructure that doesn't exist in this codebase.

Deliberately a SEPARATE score (like ranking.scorer.compute_player_quality/
compute_risk), not folded wholesale into Fantasy Value: only
ranking.scorer.compute_score applies a small, bounded nudge from it, and
only for difensori/centrocampisti — see that module's TACTICAL_PROFILE_WEIGHT.
"""

# 0-100 baseline per role_mantra code, calibrated from the explicit ordering
# in movimento.md sez. 18 (+++++ / ++++ / +++ / ++ / + / -). Deliberately
# leaves headroom below 100 for the production bonus below to lift a
# genuinely prolific player of any profile — a "DC" who scores 10 goals a
# season should still be able to outscore a "T" who never touches the ball
# in the final third.
ROLE_MANTRA_BASE = {
    "DC": 20,   # centrale puro
    "DD": 35,   # terzino destro
    "DS": 35,   # terzino sinistro
    "B": 30,    # braccetto
    "E": 45,    # quinto/esterno di centrocampo — top difensivo per lo spec
    "M": 10,    # mediano — "-" nello spec
    "C": 25,    # centrocampista centrale
    "T": 55,    # trequartista — top per lo spec
    "W": 50,    # ala/esterno offensivo
    "A": 50,    # attaccante di raccordo/seconda punta
    "PC": 40,   # punta centrale — il gol atteso lo spinge oltre coi bonus sotto
}

# Usato solo quando role_mantra manca (fonte non ancora scrappata per quel
# giocatore): baseline neutra per reparto, non penalizzante né premiante.
ROLE_CLASSIC_FALLBACK_BASE = {"D": 25, "C": 25, "A": 35}

GOALS_WEIGHT = 3.0
ASSISTS_WEIGHT = 2.5
SET_PIECE_RANK1_BONUS = 12.0
SET_PIECE_RANK2_BONUS = 5.0
SET_PIECE_CATEGORIES = {"rigori", "punizioni"}

# Tetto al contributo di gol+assist+piazzati, cosi' un singolo giocatore da
# 40 gol non manda la produzione a valori assurdi rispetto alla base
# tattica — coerente con lo stile "aggiustamento limitato" gia' usato in
# ranking.scorer (VALUE_ADJUSTMENT_WEIGHT).
PRODUCTION_CAP = 45.0


def _numeric_avg_from_range(text) -> float:
    """"12/15" -> 13.5. Fantacalciopedia's predicted_goals/predicted_assists
    format (see scrapers.fantacalciopedia.parse_detail). None/unparseable
    -> None."""
    if not text:
        return None
    parts = str(text).replace(",", ".").split("/")
    try:
        values = [float(p.strip()) for p in parts if p.strip()]
    except ValueError:
        return None
    return sum(values) / len(values) if values else None


def compute_tactical_profile_score(row: dict):
    """None for portieri (role_classic == "P") — clean sheets/gol subiti are
    already scored by ranking.scorer, a tactical/offensive profile doesn't
    apply. Otherwise 0-100."""
    role_classic = row.get("role_classic")
    if role_classic == "P":
        return None

    role_mantra = row.get("role_mantra")
    base = ROLE_MANTRA_BASE.get(role_mantra) if role_mantra else None
    if base is None:
        base = ROLE_CLASSIC_FALLBACK_BASE.get(role_classic, 20)

    goals = row.get("season_goals_scored")
    if goals is None:
        goals = _numeric_avg_from_range(row.get("predicted_goals"))
    assists = row.get("season_assists")
    if assists is None:
        assists = _numeric_avg_from_range(row.get("predicted_assists"))

    production = 0.0
    if goals is not None:
        production += goals * GOALS_WEIGHT
    if assists is not None:
        production += assists * ASSISTS_WEIGHT

    for set_piece in row.get("set_pieces") or []:
        if set_piece.get("category") not in SET_PIECE_CATEGORIES:
            continue
        if set_piece.get("rank") == 1:
            production += SET_PIECE_RANK1_BONUS
        elif set_piece.get("rank") == 2:
            production += SET_PIECE_RANK2_BONUS

    production = min(production, PRODUCTION_CAP)

    return round(max(0.0, min(100.0, base + production)), 1)
