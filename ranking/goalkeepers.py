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


def build_goalkeeper_depth_chart(rows: list, expected_teams: dict | None = None) -> dict:
    """rows: get_ranked_role(conn, "P") output (already filtered to current
    Serie A teams and reliable appearances — see dashboard.data_access.
    _compute_ranked_role).

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
        # A keeper with no fantamedia has score=None (P0-002/TASK-002): can't
        # rank him against the rest of the team's keepers, so he doesn't
        # compete for starter/backup — same "don't guess" principle as the
        # rest of this module, just applied to score instead of appearances.
        rankable = [r for r in keepers if r.get("score") is not None]
        # portieri.md §8 forbids ranking by rating: appearances (Priorità 2
        # of the spec's hierarchy) decide who starts, score is only the
        # tie-break — otherwise a backup with no fantamedia but a high
        # avg_rating-derived score (P0-002) outranks the real starter
        # (TASK-004b/P1-021).
        ranked = sorted(
            rankable, key=lambda r: (r.get("appearances") or 0, r["score"]), reverse=True,
        )
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

    for team, is_promoted in (expected_teams or {}).items():
        if team not in by_team:
            teams.append({
                "team": team, "is_promoted": is_promoted,
                "starter": None, "backup": None,
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
