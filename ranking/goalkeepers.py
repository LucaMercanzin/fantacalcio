"""Groups get_ranked_role(conn, "P")'s already-filtered, already-ranked
portieri into a per-team titolare/riserva depth chart (giocatori/
portieri.md): exactly 1st + 2nd choice per team, teams ordered with
neopromosse last.

Note on gerarchia (portieri.md sez. 7): "Priorità 1 — gerarchia esplicita
della fonte" would mean an explicitly scraped 1./2./3. ordering per team;
nothing in this codebase scrapes that today, so this ranks by `score`
(itself driven by fantamedia/avg_rating/appearances/status) within team as
the best available proxy — a genuinely-explicit-hierarchy source would be a
separate scraper addition, not something this module can source on its own.
"""


def build_goalkeeper_depth_chart(rows: list) -> dict:
    """rows: get_ranked_role(conn, "P") output (already filtered to current
    Serie A teams and reliable appearances — see dashboard.data_access.
    _compute_ranked_role)."""
    by_team: dict = {}
    for row in rows:
        by_team.setdefault(row["team"], []).append(row)

    teams = []
    warnings = []
    for team, keepers in by_team.items():
        ranked = sorted(keepers, key=lambda r: r["score"], reverse=True)
        starter = ranked[0] if len(ranked) >= 1 else None
        backup = ranked[1] if len(ranked) >= 2 else None
        if backup is None:
            warnings.append(team)
        teams.append({
            "team": team,
            "is_promoted": bool(keepers[0].get("is_promoted")),
            "starter": starter,
            "backup": backup,
        })

    non_promoted = sorted(
        (t for t in teams if not t["is_promoted"]), key=lambda t: t["team"],
    )
    promoted = sorted(
        (t for t in teams if t["is_promoted"]), key=lambda t: t["team"],
    )
    warnings.sort()

    return {"teams": non_promoted + promoted, "warnings": warnings}
