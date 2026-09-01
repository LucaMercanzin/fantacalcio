from ranking.goalkeepers import build_goalkeeper_depth_chart


def _row(player_id, team, score, is_promoted=False, appearances=None):
    return {
        "player_id": player_id, "canonical_name": f"Player{player_id}",
        "team": team, "score": score, "is_promoted": is_promoted,
        "appearances": appearances,
    }


def test_groups_by_team_starter_and_backup():
    rows = [
        _row(1, "Napoli", 70.0),
        _row(2, "Napoli", 50.0),
        _row(3, "Inter", 65.0),
        _row(4, "Inter", 60.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    assert napoli["starter"]["player_id"] == 1
    assert napoli["backup"]["player_id"] == 2
    assert chart["warnings"] == []


def test_third_choice_keeper_excluded_from_depth_chart():
    rows = [
        _row(1, "Napoli", 70.0),
        _row(2, "Napoli", 50.0),
        _row(3, "Napoli", 30.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    ids = {napoli["starter"]["player_id"], napoli["backup"]["player_id"]}
    assert ids == {1, 2}


def test_warns_when_team_has_only_one_identifiable_keeper():
    rows = [_row(1, "Como", 55.0)]

    chart = build_goalkeeper_depth_chart(rows)

    como = next(t for t in chart["teams"] if t["team"] == "Como")
    assert como["starter"]["player_id"] == 1
    assert como["backup"] is None
    assert chart["warnings"] == ["Como"]


def test_expected_team_with_no_identifiable_keeper_gets_a_warning_not_silence():
    rows = [_row(1, "Napoli", 70.0), _row(2, "Napoli", 50.0)]

    chart = build_goalkeeper_depth_chart(
        rows, expected_teams={"Napoli": False, "Lazio": False},
    )

    lazio = next(t for t in chart["teams"] if t["team"] == "Lazio")
    assert lazio["starter"] is None
    assert lazio["backup"] is None
    assert chart["missing"] == ["Lazio"]
    assert chart["warnings"] == []


def test_promoted_teams_sorted_last():
    rows = [
        _row(1, "Venezia", 60.0, is_promoted=True),
        _row(2, "Venezia", 50.0, is_promoted=True),
        _row(3, "Atalanta", 60.0),
        _row(4, "Atalanta", 50.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    team_order = [t["team"] for t in chart["teams"]]
    assert team_order == ["Atalanta", "Venezia"]


def test_appearances_outrank_score_for_starter_selection():
    """TASK-004b / P1-021: portieri.md §8 forbids ranking by rating; a keeper
    with fewer appearances must not beat one with more, even with a higher
    score (e.g. a backup with no fantamedia scored on avg_rating alone)."""
    rows = [
        _row(1, "Como", 66.5, appearances=None),  # no real fantamedia (P0-002)
        _row(2, "Como", 60.7, appearances=37),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    como = next(t for t in chart["teams"] if t["team"] == "Como")
    assert como["starter"]["player_id"] == 2
    assert como["backup"]["player_id"] == 1


def test_score_is_only_a_tie_break_when_appearances_are_equal():
    rows = [
        _row(1, "Napoli", 50.0, appearances=30),
        _row(2, "Napoli", 70.0, appearances=30),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    assert napoli["starter"]["player_id"] == 2


def test_anti_error_counts_exposed_per_portieri_md_section_13():
    rows = [
        _row(1, "Napoli", 70.0), _row(2, "Napoli", 50.0),
        _row(3, "Como", 55.0),
    ]

    chart = build_goalkeeper_depth_chart(
        rows, expected_teams={"Napoli": False, "Como": False, "Lazio": False},
    )

    assert chart["n_teams"] == 3
    assert chart["n_goalkeepers"] == 3
    assert chart["duplicates"] == []


def test_anti_error_flags_duplicate_player_across_slots():
    rows = [
        _row(1, "Napoli", 70.0), _row(2, "Napoli", 50.0),
        _row(1, "Inter", 65.0),  # same player_id matched under two teams
    ]

    chart = build_goalkeeper_depth_chart(rows)

    assert chart["duplicates"] == [1]


def _priced(player_id, team, score, price, appearances=None):
    row = _row(player_id, team, score, appearances=appearances)
    row["price_current"] = price
    return row


def test_price_decides_the_starter_when_the_gap_is_decisive():
    """portieri.md §18 nomina Meret come il caso da non sbagliare, e sui dati
    del 01/09/2026 era sbagliato: Milinkovic-Savic (4,8 crediti, 27 presenze
    della stagione scorsa) risultava titolare davanti a Meret (26,2). Le
    presenze vengono dall'anno prima, spesso in un'altra squadra; la
    quotazione è il giudizio di sei fonti su chi giocherà adesso."""
    rows = [
        _priced(1, "Napoli", 54.8, 4.8, appearances=27),
        _priced(2, "Napoli", 40.7, 26.2, appearances=11),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    assert napoli["starter"]["player_id"] == 2
    assert napoli["backup"]["player_id"] == 1
    assert napoli["starter_basis"] == "prezzo"


def test_a_narrow_price_gap_falls_back_to_appearances():
    """Due portieri che costano quasi uguale non stanno dicendo niente sulla
    gerarchia: sotto 2× si torna alle presenze (Sassuolo 1,7×, Parma 1,6×,
    Torino 1,5× sui dati reali)."""
    rows = [
        _priced(1, "Sassuolo", 55.8, 3.8, appearances=32),
        _priced(2, "Sassuolo", 35.8, 6.5, appearances=6),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    sassuolo = next(t for t in chart["teams"] if t["team"] == "Sassuolo")
    assert sassuolo["starter"]["player_id"] == 1
    assert sassuolo["starter_basis"] == "presenze"


def test_the_ratio_boundary_is_inclusive():
    rows = [
        _priced(1, "Genoa", 60.0, 5.0, appearances=30),
        _priced(2, "Genoa", 40.0, 10.0, appearances=0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    genoa = next(t for t in chart["teams"] if t["team"] == "Genoa")
    assert genoa["starter"]["player_id"] == 2  # esattamente 2x decide
    assert genoa["starter_basis"] == "prezzo"


def test_a_keeper_without_a_price_is_not_treated_as_worthless():
    """Nessuna quotazione significa "non confrontabile", non "vale zero": va
    in coda nell'ordine per presenze, non davanti a chi un prezzo ce l'ha."""
    rows = [
        _priced(1, "Lecce", 62.1, 9.7, appearances=38),
        _priced(2, "Lecce", 55.9, 1.0, appearances=38),
        _row(3, "Lecce", 70.0, appearances=38),  # senza price_current
    ]

    chart = build_goalkeeper_depth_chart(rows)

    lecce = next(t for t in chart["teams"] if t["team"] == "Lecce")
    assert lecce["starter"]["player_id"] == 1
    assert lecce["backup"]["player_id"] == 2


def test_prices_are_ignored_entirely_when_only_one_keeper_has_one():
    """Un solo prezzo non è un rapporto: non c'è niente da confrontare."""
    rows = [
        _priced(1, "Torino", 45.0, 6.3, appearances=None),
        _row(2, "Torino", 51.1, appearances=28),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    torino = next(t for t in chart["teams"] if t["team"] == "Torino")
    assert torino["starter"]["player_id"] == 2
    assert torino["starter_basis"] == "presenze"
