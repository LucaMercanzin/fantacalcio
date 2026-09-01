"""Groups dashboard.data_access.get_goalkeeper_pool(conn)'s already-ranked
portieri into a per-team titolare/riserva depth chart (giocatori/
portieri.md): exactly 1st + 2nd choice per team, teams ordered with
neopromosse last.

Deliberately NOT get_ranked_role(conn, "P") (used by every other role page):
that applies RELIABLE_APPEARANCES_MIN, a gate meant to hide deep-bench
outfield clutter that instead erases exactly the keeper this chart most
needs at the start of a season — one promoted to starter or back from loan,
whose last season's appearances are low but known. See get_goalkeeper_pool's
docstring for the verified real-DB case (Lazio) this fixes.

Note on gerarchia (portieri.md sez. 7): "Priorità 1 — gerarchia esplicita
della fonte" would mean an explicitly scraped 1./2./3. ordering per team;
nothing in this codebase scrapes that today, so this ranks by `score`
(itself driven by fantamedia/avg_rating/appearances/status) within team as
the best available proxy — a genuinely-explicit-hierarchy source would be a
separate scraper addition, not something this module can source on its own.
"""


# Rapporto fra la quotazione più alta e la seconda della stessa squadra oltre
# il quale è il prezzo a decidere chi para.
#
# **Perché il prezzo, e perché proprio 2×.** La spec (portieri.md §7) mette al
# primo posto la "gerarchia esplicita della fonte", che però nessuno scrappa
# oggi; al secondo posto elenca cinque segnali fra cui le presenze. Ordinare
# per sole presenze si è rotto in modo grave sui dati reali del 01/09/2026,
# perché le presenze sono quelle della stagione scorsa, spesso in un'altra
# squadra o in Serie B: Mrozek all'Udinese (1,0 crediti, 33 presenze)
# risultava titolare davanti a Okoye (11,1 crediti), e al Napoli
# Milinkovic-Savic (4,8) davanti a **Meret** (26,2) — cioè esattamente il caso
# che portieri.md §18 nomina come da non sbagliare.
#
# La quotazione, invece, è il giudizio aggregato di sei fonti su chi giocherà,
# ed è il segnale più netto che esista per i portieri: una riserva vale 1
# credito, un titolare da 10 a 35. Non è "ordinare per rating" — quello che
# §8 vieta — è leggere la gerarchia dove il mercato l'ha già scritta.
#
# 2× è una soglia di *decisione*, non una taratura: separa i divari
# inequivocabili (Napoli 5,5×, Inter 6,9×, Udinese 11×, Lazio 8×) dai casi in
# cui i due portieri costano quasi uguale e il prezzo non sta dicendo niente
# (Sassuolo 1,7×, Parma 1,6×, Torino 1,5×). Sotto soglia si torna alle
# presenze, che restano il miglior segnale disponibile quando il mercato non
# si sbilancia.
DECISIVE_PRICE_RATIO = 2.0


def _rank_keepers(keepers: list) -> tuple:
    """(portieri ordinati, criterio usato). Il criterio viene restituito e non
    tenuto per sé perché "perché questo è il titolare" è una domanda che si
    pone davanti alla card, non nel codice."""
    # A keeper with no fantamedia has score=None (P0-002/TASK-002): can't
    # rank him against the rest of the team's keepers, so he doesn't
    # compete for starter/backup — same "don't guess" principle as the
    # rest of this module, just applied to score instead of appearances.
    rankable = [r for r in keepers if r.get("score") is not None]

    by_appearances = sorted(
        rankable, key=lambda r: (r.get("appearances") or 0, r["score"]), reverse=True,
    )

    priced = sorted(
        (r for r in rankable if (r.get("price_current") or 0) > 0),
        key=lambda r: (r["price_current"], r.get("appearances") or 0, r["score"]),
        reverse=True,
    )
    if len(priced) >= 2 and priced[0]["price_current"] >= (
        DECISIVE_PRICE_RATIO * priced[1]["price_current"]
    ):
        # I portieri senza quotazione restano in coda nell'ordine per
        # presenze: non hanno un prezzo da confrontare, non che valgano zero.
        unpriced = [r for r in by_appearances if r not in priced]
        return priced + unpriced, "prezzo"

    return by_appearances, "presenze"


def build_goalkeeper_depth_chart(rows: list, expected_teams: dict | None = None) -> dict:
    """rows: dashboard.data_access.get_goalkeeper_pool(conn) output (already
    filtered to current Serie A teams and ranked — see there for why it
    skips the reliable-appearances gate get_ranked_role applies).

    expected_teams: optional {team_full_name: is_promoted} for every team
    that should have a section even when the scrape has zero identifiable
    keepers for it (e.g. every source's data fails the reliability filters
    for that club). Without it, such a team is silently absent instead of
    surfaced — the same "warn, don't invent" principle as a missing backup,
    just for a missing starter too (portieri.md sez. 13)."""
    by_team: dict = {}
    for row in rows:
        by_team.setdefault(row["team"], []).append(row)

    teams = []
    warnings = []
    missing = []
    for team, keepers in by_team.items():
        ranked, basis = _rank_keepers(keepers)
        starter = ranked[0] if len(ranked) >= 1 else None
        backup = ranked[1] if len(ranked) >= 2 else None
        if backup is None:
            warnings.append(team)
        teams.append({
            "team": team,
            "is_promoted": bool(keepers[0].get("is_promoted")),
            "starter": starter,
            "backup": backup,
            "starter_basis": basis if starter is not None else None,
        })

    for team, is_promoted in (expected_teams or {}).items():
        if team not in by_team:
            teams.append({
                "team": team, "is_promoted": is_promoted,
                "starter": None, "backup": None, "starter_basis": None,
            })
            missing.append(team)

    non_promoted = sorted(
        (t for t in teams if not t["is_promoted"]), key=lambda t: t["team"],
    )
    promoted = sorted(
        (t for t in teams if t["is_promoted"]), key=lambda t: t["team"],
    )
    warnings.sort()
    missing.sort()

    # portieri.md §13 anti-error checks: don't just compute the chart, count
    # what it actually contains so a wrong total (not 20 teams, not 40
    # keepers) or a player picked for two teams (a matching bug, not a real
    # goalkeeper duplication) is visible instead of silently shipped.
    selected_ids = [
        entry[slot]["player_id"]
        for entry in teams for slot in ("starter", "backup")
        if entry[slot] is not None
    ]
    duplicates = sorted({pid for pid in selected_ids if selected_ids.count(pid) > 1})

    return {
        "teams": non_promoted + promoted,
        "warnings": warnings,
        "missing": missing,
        "n_teams": len(teams),
        "n_goalkeepers": len(selected_ids),
        "duplicates": duplicates,
    }
