"""Flags positive and negative player correlations within the owned roster
(giocatori/rosa-ideale.md sez. 14-15): pairs on the same team that either
combine to produce bonuses together (assistman + goleador) or compete for
the same bonus pool (two players in the same tactical slot).

Deliberately scoped to D/C/A only — portieri titolare+secondo of the same
team is the DESIRED pairing (rosa-ideale.md sez. 14 "Portieri"), already the
explicit goal of ranking.goalkeepers.build_goalkeeper_depth_chart; flagging
it again here as a negative correlation would contradict that feature.
"""

# A player counts as a real goal/assist threat for correlation purposes
# above this many season goals/assists — low enough to catch a genuine
# secondary scorer, high enough that a single set piece won't trigger it.
GOAL_THREAT_MIN = 3
ASSIST_THREAT_MIN = 3

# role_mantra codes that are "the same tactical slot" for negative-
# correlation purposes — two players sharing one of these on the same team
# are competing for the same minutes/bonus pool. Deliberately a subset of
# ranking.tactical_profile.ROLE_MANTRA_BASE's keys: only the attacking-
# facing ones, since two "DC" centrali on the same team aren't competing
# for the same fantacalcio bonus the way two "PC" attaccanti are.
CONTESTED_ROLE_MANTRA = {"T", "W", "A", "PC", "E"}


def find_correlations(roster_rows: list) -> dict:
    """roster_rows: dashboard.data_access.get_roster_with_profile(conn)
    output, or any list of rows with player_id/canonical_name/team/
    role_classic/role_mantra/season_goals_scored/season_assists.

    Returns {"positive": [...], "negative": [...]}, each entry:
    {"player_a": row, "player_b": row, "reason": str}."""
    dc_a_rows = [r for r in roster_rows if r.get("role_classic") != "P"]

    positive = []
    negative = []
    for i, a in enumerate(dc_a_rows):
        for b in dc_a_rows[i + 1:]:
            if a["team"] != b["team"]:
                continue

            a_assists = a.get("season_assists") or 0
            b_assists = b.get("season_assists") or 0
            a_goals = a.get("season_goals_scored") or 0
            b_goals = b.get("season_goals_scored") or 0

            # elif, not two independent ifs: a pair that qualifies both ways
            # (both good scorers and assisters) would otherwise show up as
            # two near-identical cards for the same two players.
            if a_assists >= ASSIST_THREAT_MIN and b_goals >= GOAL_THREAT_MIN:
                positive.append({
                    "player_a": a, "player_b": b,
                    "reason": (
                        f"{a['canonical_name']} assist ({a_assists}) + "
                        f"{b['canonical_name']} gol ({b_goals}), stessa squadra"
                    ),
                })
            elif b_assists >= ASSIST_THREAT_MIN and a_goals >= GOAL_THREAT_MIN:
                positive.append({
                    "player_a": b, "player_b": a,
                    "reason": (
                        f"{b['canonical_name']} assist ({b_assists}) + "
                        f"{a['canonical_name']} gol ({a_goals}), stessa squadra"
                    ),
                })

            same_role_classic = a["role_classic"] == b["role_classic"]
            same_contested_mantra = (
                a.get("role_mantra") in CONTESTED_ROLE_MANTRA
                and a.get("role_mantra") == b.get("role_mantra")
            )
            if same_role_classic and same_contested_mantra:
                negative.append({
                    "player_a": a, "player_b": b,
                    "reason": (
                        f"{a['canonical_name']} e {b['canonical_name']}: stesso "
                        f"ruolo tattico ({a['role_mantra']}) nella stessa squadra, "
                        "competono per gli stessi bonus"
                    ),
                })

    return {"positive": positive, "negative": negative}
