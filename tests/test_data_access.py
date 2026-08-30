import itertools
from datetime import date

from dashboard.data_access import (
    DEFAULT_LISTINO_TO_AUCTION_FACTOR,
    TEAM_ABBREV_TO_FULL,
    _merge_player_rows,
    compute_listino_to_auction_factor,
    compute_source_scale_factors,
    find_player_by_name,
    get_auction_intelligence,
    get_match_review_queue,
    get_monitoring_data,
    get_optimal_squad_lp,
    get_player_detail,
    get_price_history_by_date,
    get_price_recommendation,
    get_ranked_role,
    get_roster_with_profile,
    get_squad_suggestions,
    search_and_sort,
)
from db import repository
from db.connection import get_connection, init_db
from ranking.price_engine import BORDERLINE, BUY, PASS


def test_compute_ranked_role_merges_season_stats_and_set_pieces(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Calhanoglu", "Inter", "C", "M", None)
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-27",
        price_current=20, price_initial=18, status="ok",
        fantamedia=6.5, avg_rating=6.5, appearances=30,
    )
    repository.insert_quotation(
        conn, player_id, "fantanalisi", "2026-08-27",
        price_current=21, price_initial=19, status="ok",
        fantamedia=6.4, avg_rating=6.4, appearances=30,
    )
    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        {"season": "2025/26", "appearances": 30, "goals_scored": 6, "goals_conceded": None,
         "assists": 5, "avg_rating": 6.5, "yellow_cards": 2, "red_cards": 0},
    ], scraped_at="2026-08-27")
    repository.replace_player_set_pieces(conn, "fantacalcio_it", [
        (player_id, "rigori", 1, "2026-08-27"),
    ])

    rows = get_ranked_role(conn, "C")

    row = next(r for r in rows if r["player_id"] == player_id)
    assert row["season_goals_scored"] == 6
    assert row["season_assists"] == 5
    assert {sp["category"] for sp in row["set_pieces"]} == {"rigori"}
    conn.close()


def test_compute_ranked_role_merges_goals_conceded_and_team_xga_for_portieri(tmp_path):
    """TASK-025b/P2-020: season_goals_conceded and team_xga were scraped and
    stored but never reached the merged row a goalkeeper's score is built
    from. team_strength is matched by normalize_team(), not the raw string,
    since players.team can be a different casing/abbreviation ("INT") than
    team_strength.team ("Inter")."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Sommer", "INT", "P", "Por", None)
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-27",
        price_current=15, price_initial=14, status="ok",
        fantamedia=6.2, avg_rating=6.3, appearances=32,
    )
    repository.insert_quotation(
        conn, player_id, "fantacalciopedia", "2026-08-27",
        price_current=14, price_initial=13, status="ok",
        fantamedia=6.1, avg_rating=6.2, appearances=32,
    )
    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        {"season": "2025/26", "appearances": 32, "goals_scored": None, "goals_conceded": 28,
         "assists": None, "avg_rating": 6.3, "yellow_cards": 1, "red_cards": 0},
    ], scraped_at="2026-08-27")
    repository.insert_team_strength(conn, "Inter", xg=2.1, xga=0.95, ppda=9.5,
                                     source="fantanalisi_squadre", scrape_date="2026-08-27")

    rows = get_ranked_role(conn, "P")

    row = next(r for r in rows if r["player_id"] == player_id)
    assert row["season_goals_conceded"] == 28
    assert row["team_xg"] == 2.1
    assert row["team_xga"] == 0.95
    conn.close()


def test_get_player_detail_score_matches_ranked_role(tmp_path):
    """P1-003: get_player_detail used to skip _attach_tactical_profile_inputs,
    so a player's Fantasy Value differed between the role ranking page and
    their own detail page whenever season goals/assists or set pieces fed
    into compute_tactical_profile_score."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Dimarco", "Inter", "D", "Ds", None)
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-27",
        price_current=30, price_initial=28, status="ok",
        fantamedia=6.5, avg_rating=6.5, appearances=30,
    )
    repository.insert_quotation(
        conn, player_id, "fantapazz", "2026-08-27",
        price_current=31, price_initial=29, status="ok",
        fantamedia=6.4, avg_rating=6.4, appearances=30,
    )
    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        {"season": "2025/26", "appearances": 30, "goals_scored": 5, "goals_conceded": None,
         "assists": 8, "avg_rating": 6.5, "yellow_cards": 2, "red_cards": 0},
    ], scraped_at="2026-08-27")
    repository.replace_player_set_pieces(conn, "fantacalcio_it", [
        (player_id, "rigori", 1, "2026-08-27"),
    ])

    ranked_score = next(r for r in get_ranked_role(conn, "D") if r["player_id"] == player_id)["score"]
    detail_score = get_player_detail(conn, player_id)["score"]

    assert detail_score == ranked_score
    conn.close()


def test_get_ranked_role_includes_notes_and_roster_flag(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    p2 = repository.upsert_player(conn, "Dusan Vlahovic", "Juventus", "A", "Pu", None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, p1, "fantapazz", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, p2, "fantacalcio_it", "2026-08-22", 25, 22, "ok", 6.0, 6.0, 30)
    repository.insert_quotation(conn, p2, "fantapazz", "2026-08-22", 25, 22, "ok", 6.0, 6.0, 30)
    repository.upsert_player_notes(conn, p1, "Top pick", "2026-08-22")
    repository.add_roster_entry(conn, p2, 25, "2026-08-22")

    ranked = get_ranked_role(conn, "A")

    assert ranked[0]["canonical_name"] == "Lautaro Martinez"
    assert ranked[0]["notes"] == "Top pick"
    assert ranked[0]["is_in_roster"] is False
    vlahovic = next(r for r in ranked if r["canonical_name"] == "Dusan Vlahovic")
    assert vlahovic["notes"] == ""
    assert vlahovic["is_in_roster"] is True
    conn.close()


def test_get_ranked_role_normalizes_team_name_case_insensitively(tmp_path):
    """A source tagging a club in ALL-CAPS ("COMO") must land on the same
    canonical team label as one tagging it in title case ("Como") — a raw
    casing mismatch previously slipped through normalize_team_name and split
    one club into two team sections downstream (e.g. the Portieri depth
    chart)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Player One", "COMO", "P", None, None)
    p2 = repository.upsert_player(conn, "Player Two", "Como", "P", None, None)
    for pid in (p1, p2):
        repository.insert_quotation(conn, pid, "fantacalcio_it", "2026-08-22", 5, 1, "ok", 6.0, 6.0, 30)
        repository.insert_quotation(conn, pid, "fantapazz", "2026-08-22", 5, 1, "ok", 6.0, 6.0, 30)

    ranked = get_ranked_role(conn, "P")

    assert {r["team"] for r in ranked} == {"Como"}
    conn.close()


def test_get_ranked_role_excludes_single_source_players(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    confirmed = repository.upsert_player(conn, "Confirmed Player", "Inter", "A", "Pu", None)
    single = repository.upsert_player(conn, "Single Source Player", "Roma", "A", "Pu", None)
    repository.insert_quotation(conn, confirmed, "fantacalcio_it", "2026-08-22", 30, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, confirmed, "fantapazz", "2026-08-22", 30, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, single, "fantacalcio_it", "2026-08-22", 20, 20, "ok", 6.5, 6.3, 30)

    ranked = get_ranked_role(conn, "A")

    names = [r["canonical_name"] for r in ranked]
    assert "Confirmed Player" in names
    assert "Single Source Player" not in names
    conn.close()


def test_get_ranked_role_excludes_clear_backups_by_appearances(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    starter = repository.upsert_player(conn, "Starter Keeper", "Inter", "P", "Por", None)
    third_choice = repository.upsert_player(conn, "Third Choice Keeper", "Inter", "P", "Por", None)
    new_signing = repository.upsert_player(conn, "New Signing Keeper", "Roma", "P", "Por", None)
    for pid, appearances in ((starter, 35), (third_choice, 2), (new_signing, None)):
        repository.insert_quotation(conn, pid, "fantacalcio_it", "2026-08-22", 10, 10, "ok", 6.0, 6.0, appearances)
        repository.insert_quotation(conn, pid, "fantapazz", "2026-08-22", 10, 10, "ok", 6.0, 6.0, appearances)

    ranked = get_ranked_role(conn, "P")

    names = [r["canonical_name"] for r in ranked]
    assert "Starter Keeper" in names
    assert "Third Choice Keeper" not in names
    assert "New Signing Keeper" in names
    conn.close()


def test_get_ranked_role_excludes_players_with_zero_real_signal(tmp_path):
    """No appearances, no fantamedia, no avg_rating: a deep academy name
    with just a placeholder listino price, not a genuine new signing worth
    tracking."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    starter = repository.upsert_player(conn, "Starter Keeper", "Inter", "P", "Por", None)
    scrub = repository.upsert_player(conn, "Academy Scrub", "Roma", "P", "Por", None)
    repository.insert_quotation(conn, starter, "fantacalcio_it", "2026-08-22", 10, 10, "ok", 6.0, 6.0, 35)
    repository.insert_quotation(conn, starter, "fantapazz", "2026-08-22", 10, 10, "ok", 6.0, 6.0, 35)
    repository.insert_quotation(conn, scrub, "fantacalcio_it", "2026-08-22", 1, 1, None, None, None, None)
    repository.insert_quotation(conn, scrub, "fantapazz", "2026-08-22", 1, 1, None, None, None, None)

    ranked = get_ranked_role(conn, "P")

    names = [r["canonical_name"] for r in ranked]
    assert "Starter Keeper" in names
    assert "Academy Scrub" not in names
    conn.close()


def test_get_ranked_role_excludes_players_no_longer_in_serie_a(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    in_serie_a = repository.upsert_player(conn, "Serie A Player", "Inter", "A", "Pu", None)
    transferred = repository.upsert_player(conn, "Transferred Player", "Estero", "A", "Pu", None)
    for pid in (in_serie_a, transferred):
        repository.insert_quotation(conn, pid, "fantacalcio_it", "2026-08-22", 30, 30, "ok", 7.0, 6.8, 30)
        repository.insert_quotation(conn, pid, "fantapazz", "2026-08-22", 30, 30, "ok", 7.0, 6.8, 30)

    ranked = get_ranked_role(conn, "A")

    names = [r["canonical_name"] for r in ranked]
    assert "Serie A Player" in names
    assert "Transferred Player" not in names
    conn.close()


def test_get_ranked_role_merges_fcp_metrics(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, p1, "fantapazz", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.save_fcp_metrics(
        conn, p1, "2026-08-22", alg_fcp=97, punteggio_fcp=75,
        investment_stability_pct=60, injury_resistance_pct=60,
        predicted_appearances="30+", predicted_goals="12/15",
        predicted_assists="3/5", skills=["Titolare", "Goleador"],
    )

    ranked = get_ranked_role(conn, "A")

    lautaro = next(r for r in ranked if r["canonical_name"] == "Lautaro Martinez")
    assert lautaro["alg_fcp"] == 97
    assert lautaro["fcp_skills"] == ["Titolare", "Goleador"]
    conn.close()


def test_get_optimal_squad_lp_fills_all_role_slots(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    # Since TASK-001, price_current is rescaled per-source to a canonical
    # ceiling derived from that source's own 99th percentile (see
    # compute_source_scale_factors): a uniform price across every candidate
    # would make each of them individually *be* that 99th percentile, so
    # every single one would rescale to the ceiling — the whole squad would
    # cost far more than the budget. Two affordable "filler" candidates per
    # slot (cheap, decent fantamedia) plus one unaffordable, low-value
    # "decoy" per role keeps the fixture realistic (most players cheap, a
    # few pricier) while still giving the LP an obviously-better feasible
    # choice for every role.
    role_counts = {"P": 3, "D": 8, "C": 8, "A": 6}
    # Real Serie A clubs, cycling: is_current_serie_a_team (TASK-003) would
    # reject a fake team name outright, and TASK-016's MAX_PLAYERS_PER_CLUB=3
    # cap applies across the whole squad, so every player (33 total across
    # all 4 roles) needs a distinct-enough club — 20 real clubs cycled over
    # 33 players gives at most 2 per club, safely under the cap of 3.
    teams = itertools.cycle(TEAM_ABBREV_TO_FULL.values())
    for role, count in role_counts.items():
        for i in range(count):
            # A letter suffix, not a digit: identity_key normalizes on
            # letters only (matching.player_matcher.normalize_name), so
            # "Filler 0"/"Filler 1" would collide into the same player
            # (TASK-007/P0-007) instead of giving the LP `count` real
            # candidates for this role.
            pid = repository.upsert_player(
                conn, f"{role} Filler {chr(65 + i)}", next(teams), role, None, None,
            )
            for source in ("fantacalcio_it", "fantapazz"):
                repository.insert_quotation(
                    conn, pid, source, "2026-08-22",
                    price_current=1, price_initial=1, status="ok",
                    fantamedia=6.0, avg_rating=6.0, appearances=30,
                )
        for i in range(2):
            pid = repository.upsert_player(
                conn, f"{role} Decoy {chr(65 + i)}", next(teams), role, None, None,
            )
            for source in ("fantacalcio_it", "fantapazz"):
                repository.insert_quotation(
                    conn, pid, source, "2026-08-22",
                    price_current=1000, price_initial=1000, status="ok",
                    fantamedia=1.0, avg_rating=1.0, appearances=30,
                )

    result = get_optimal_squad_lp(conn, mode="from_scratch")

    assert result["status"] == "optimal"
    for role, count in role_counts.items():
        assert len(result["squad"][role]) == count
        assert all("Filler" in p["canonical_name"] for p in result["squad"][role])
    conn.close()


def test_search_and_sort_filters_by_name():
    rows = [
        {"canonical_name": "Lautaro Martinez", "team": "Inter", "price_current": 38},
        {"canonical_name": "Dusan Vlahovic", "team": "Juventus", "price_current": 25},
    ]

    result = search_and_sort(rows, query="lautaro", sort_by="rank")

    assert len(result) == 1
    assert result[0]["canonical_name"] == "Lautaro Martinez"


def test_search_and_sort_sorts_by_team():
    rows = [
        {"canonical_name": "Lautaro Martinez", "team": "Inter", "price_current": 38},
        {"canonical_name": "Dusan Vlahovic", "team": "Juventus", "price_current": 25},
    ]

    result = search_and_sort(rows, query="", sort_by="team")

    assert [r["team"] for r in result] == ["Inter", "Juventus"]


def test_search_and_sort_sorts_by_price_descending():
    rows = [
        {"canonical_name": "Lautaro Martinez", "team": "Inter", "price_current": 38},
        {"canonical_name": "Dusan Vlahovic", "team": "Juventus", "price_current": 45},
    ]

    result = search_and_sort(rows, query="", sort_by="price")

    assert [r["canonical_name"] for r in result] == ["Dusan Vlahovic", "Lautaro Martinez"]


def test_search_and_sort_team_sort_keeps_promoted_teams_in_place():
    rows = [
        {"canonical_name": "Player Fio", "team": "Fiorentina", "price_current": 10, "is_promoted": False},
        {"canonical_name": "Player Fro", "team": "Frosinone", "price_current": 10, "is_promoted": True},
        {"canonical_name": "Player Gen", "team": "Genoa", "price_current": 10, "is_promoted": False},
    ]

    result = search_and_sort(rows, query="", sort_by="team")

    assert [r["team"] for r in result] == ["Fiorentina", "Frosinone", "Genoa"]


def test_search_and_sort_rank_sort_pushes_promoted_teams_last():
    rows = [
        {"canonical_name": "Player Fro", "team": "Frosinone", "price_current": 10, "is_promoted": True},
        {"canonical_name": "Player Ata", "team": "Atalanta", "price_current": 10, "is_promoted": False},
    ]

    result = search_and_sort(rows, query="", sort_by="rank")

    assert [r["team"] for r in result] == ["Atalanta", "Frosinone"]


def test_merge_player_rows_computes_weighted_average_price():
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 30,
         "price_initial": 30, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantacalciopedia", "price_current": 24,
         "price_initial": None, "fantamedia": 6.5, "avg_rating": None,
         "status": None, "appearances": 20},
    ]

    merged = _merge_player_rows(rows)

    assert len(merged) == 1
    player = merged[0]
    # weighted avg of the listino family: (30*3 + 24*2) / 5 = 27.6, then
    # converted to auction-credit terms (no real-auction source here) via
    # DEFAULT_LISTINO_TO_AUCTION_FACTOR (P0-001/TASK-001).
    assert player["price_listino"] == 27.6
    assert player["price_basis"] == "listino_converted"
    assert player["price_current"] == round(27.6 * DEFAULT_LISTINO_TO_AUCTION_FACTOR, 2)
    assert player["price_initial"] == 30
    assert player["fantamedia"] == 6.5
    assert player["appearances"] == 20
    assert player["source"] == "fantacalcio_it+fantacalciopedia"


def test_merge_player_rows_averages_appearances_instead_of_picking_first_source():
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "price_current": None,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": 10},
        {"player_id": 1, "source": "fantacalciopedia", "price_current": None,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": 20},
    ]

    merged = _merge_player_rows(
        rows, stats_weights={"fantacalcio_it": 3, "fantacalciopedia": 2},
    )

    # weighted avg = (10*3 + 20*2) / 5 = 14, not "10" (whichever source
    # happened to be first) or a plain unweighted mean of 15 (P1-006/TASK-011).
    assert merged[0]["appearances"] == 14
    assert merged[0]["appearances_disagreement"] is True


def test_merge_player_rows_no_appearances_disagreement_when_sources_close():
    rows = [
        {"player_id": 1, "source": "a", "price_current": None,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": 18},
        {"player_id": 1, "source": "b", "price_current": None,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": 19},
    ]

    merged = _merge_player_rows(rows, stats_weights={"a": 1, "b": 1})

    assert merged[0]["appearances"] == 18  # round(18.5) rounds to even (18)
    assert merged[0]["appearances_disagreement"] is False


def test_merge_player_rows_uses_custom_weights_when_provided():
    rows = [
        {"player_id": 1, "source": "a", "price_current": 30, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
        {"player_id": 1, "source": "b", "price_current": 20, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"a": 1, "b": 1})

    assert merged[0]["price_listino"] == 25.0
    assert merged[0]["price_current"] == round(25.0 * DEFAULT_LISTINO_TO_AUCTION_FACTOR, 2)


def test_merge_player_rows_flags_and_downweights_outlier_source():
    rows = [
        {"player_id": 1, "source": "a", "price_current": 30, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
        {"player_id": 1, "source": "b", "price_current": 31, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
        {"player_id": 1, "source": "c", "price_current": 60, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"a": 1, "b": 1, "c": 1})
    player = merged[0]

    assert player["price_outlier_sources"] == ["c"]
    # consensus should stay close to the agreeing sources, not be pulled to
    # the midpoint, because "c" got its weight cut.
    assert player["price_listino"] < 40
    assert player["price_current"] == round(player["price_listino"] * DEFAULT_LISTINO_TO_AUCTION_FACTOR, 2)


def test_merge_player_rows_price_agreement_low_for_single_source():
    rows = [
        {"player_id": 1, "source": "a", "price_current": 30, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"a": 1})

    assert merged[0]["price_agreement"] == 40.0


def test_merge_player_rows_price_agreement_high_when_sources_agree():
    rows = [
        {"player_id": 1, "source": "a", "price_current": 30, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
        {"player_id": 1, "source": "b", "price_current": 31, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
        {"player_id": 1, "source": "c", "price_current": 30, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
        {"player_id": 1, "source": "d", "price_current": 29, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"a": 1, "b": 1, "c": 1, "d": 1})

    assert merged[0]["price_agreement"] > 90


def test_merge_player_rows_price_agreement_uses_iqr_not_raw_range():
    """P1-001/TASK-010: a single wild outlier must not dominate the
    agreement score the way a (max-min)/mean range would — IQR/median
    ignores the tails, so 4 close sources plus 1 outlier still score high
    (the old range-based formula would score this ~0)."""
    rows = [
        {"player_id": 1, "source": s, "price_current": price, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None}
        for s, price in [("a", 29), ("b", 30), ("c", 30), ("d", 31), ("e", 90)]
    ]
    weights = {s: 1 for s in ("a", "b", "c", "d", "e")}

    merged = _merge_player_rows(rows, weights=weights)

    assert merged[0]["price_agreement"] > 80


def test_merge_player_rows_data_confidence_combines_signals():
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 30,
         "price_initial": None, "fantamedia": 6.5, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantacalciopedia", "price_current": 31,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"fantacalcio_it": 1, "fantacalciopedia": 1})

    assert merged[0]["data_confidence"] is not None
    assert 0 <= merged[0]["data_confidence"] <= 100

    no_fantamedia_rows = [dict(r) for r in rows]
    for r in no_fantamedia_rows:
        r["fantamedia"] = None
    no_fantamedia_merged = _merge_player_rows(
        no_fantamedia_rows, weights={"fantacalcio_it": 1, "fantacalciopedia": 1},
    )

    # missing a real fantamedia reading should never score higher than
    # having one, all else equal — a real reading is corroborating evidence.
    assert no_fantamedia_merged[0]["data_confidence"] < merged[0]["data_confidence"]


def test_merge_player_rows_decays_stale_quotations_toward_fresh_ones():
    from datetime import date

    rows = [
        {"player_id": 1, "source": "a", "price_current": 20, "scrape_date": "2026-07-01",
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "b", "price_current": 40, "scrape_date": "2026-08-24",
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(
        rows, weights={"a": 1, "b": 1}, reference_date=date(2026, 8, 24),
    )

    # "a" is 54 days stale, so it should pull the consensus toward "b" (40)
    # much more than a plain 50/50 average (30) would.
    assert merged[0]["price_current"] > 30


def test_merge_player_rows_price_ignores_estimated_sources_when_real_data_exists():
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 30,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantapazz", "price_current": 28,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 140,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantanalisi", "price_current": 140,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(
        rows, weights={"fantacalcio_it": 3, "fantapazz": 1.5, "fantacalcio_online": 100, "fantanalisi": 20},
    )

    # The "listino" sources (30, 28) must not pull the price down at all —
    # only the real-auction sources count once at least two of them agree.
    assert merged[0]["price_current"] == 140
    assert merged[0]["price_auction"] == 140
    assert merged[0]["price_basis"] == "auction"


def test_merge_player_rows_price_auction_never_exceeds_the_total_budget():
    """A single player can never actually cost more than the entire
    auction budget (TOTAL_CREDITS) — found while writing TASK-022's domain
    tests: compute_source_scale_factors calibrates to each source's own
    p99, not its max, so the very top scorers could land above the
    canonical ceiling once rescaled."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 650,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantanalisi", "price_current": 620,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(
        rows, weights={"fantacalcio_online": 1, "fantanalisi": 1},
    )

    assert merged[0]["price_current"] == 500
    assert merged[0]["price_auction"] == 500


def test_merge_player_rows_price_falls_back_to_estimated_when_no_real_source():
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 30,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"fantacalcio_it": 3})

    assert merged[0]["price_listino"] == 30
    assert merged[0]["price_basis"] == "listino_converted"
    assert merged[0]["price_current"] == round(30 * DEFAULT_LISTINO_TO_AUCTION_FACTOR, 2)


def test_merge_player_rows_price_falls_back_when_only_one_real_source():
    """One real-auction reading can be a fluke (e.g. a single early-season
    sample) — it shouldn't single-handedly override the listino consensus."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 92,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 16,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantapazz", "price_current": 26,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(
        rows, weights={"fantacalcio_online": 100, "fantacalcio_it": 3, "fantapazz": 1.5},
    )

    # The single real-auction source is excluded outright (below
    # MIN_REAL_PRICE_SOURCES), so price_current is the listino consensus
    # converted to auction-credit terms, not anywhere near the raw 92.
    assert merged[0]["price_basis"] == "listino_converted"
    assert 16 <= merged[0]["price_listino"] <= 26
    assert merged[0]["price_current"] == round(merged[0]["price_listino"] * DEFAULT_LISTINO_TO_AUCTION_FACTOR, 2)


def test_merge_player_rows_uses_separate_weights_for_price_and_stats():
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 140,
         "price_initial": None, "fantamedia": None, "avg_rating": 6.0,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantanalisi", "price_current": 140,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 30,
         "price_initial": None, "fantamedia": 7.0, "avg_rating": 6.8,
         "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(
        rows,
        weights={"fantacalcio_online": 100, "fantanalisi": 20, "fantacalcio_it": 3},
        stats_weights={"fantacalcio_online": 1, "fantanalisi": 1, "fantacalcio_it": 3},
    )
    player = merged[0]

    # Price: two real-auction sources agree, so they win outright over listino.
    assert player["price_current"] == 140
    assert player["price_basis"] == "auction"
    # avg_rating: with stats weights 1 vs 3, fantacalcio_it's 6.8 dominates
    # instead of being drowned out by fantacalcio_online's high price weight.
    assert player["avg_rating"] == round((6.0 * 1 + 6.8 * 3) / 4, 2)


def test_compute_source_scale_factors_rescales_to_family_canonical_ceiling():
    """P0-001/TASK-001: each source's raw price_current lives on its own
    scale (confirmed on the real DB: fantacalcio_it p99=28, fantanalisi
    p99=248, both nominally different "families"). The factor must bring
    each source's own p99 exactly to its family's canonical ceiling."""
    factors = compute_source_scale_factors({
        "fantacalcio_it": 28,       # listino family -> ceiling 40
        "fantacalcio_online": 115,  # auction family -> ceiling 500
    })

    assert factors["fantacalcio_it"] == 40 / 28
    assert factors["fantacalcio_online"] == 500 / 115


def test_merge_player_rows_price_scale_factors_make_sources_commensurable():
    """Two real-auction sources reporting very different raw magnitudes for
    the same player (100 vs 50) are actually in full agreement once each is
    rescaled by its own source's scale factor: 100 is half of that source's
    p99 (200), 50 is half of the other source's p99 (100) — both say "this
    player is worth half of what I ever report" — so the merge must treat
    them as agreeing (both -> 250), not as one being roughly double the
    other."""
    rows = [
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 100,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
        {"player_id": 1, "source": "fantanalisi", "price_current": 50,
         "price_initial": None, "fantamedia": None, "avg_rating": None,
         "status": None, "appearances": None},
    ]
    scale_factors = compute_source_scale_factors({
        "fantacalcio_online": 200, "fantanalisi": 100,
    })

    merged = _merge_player_rows(
        rows, weights={"fantacalcio_online": 1, "fantanalisi": 1},
        source_scale_factors=scale_factors,
    )
    player = merged[0]

    assert player["price_basis"] == "auction"
    assert player["price_outlier_sources"] == []
    assert player["price_current"] == 250.0


def test_compute_listino_to_auction_factor_falls_back_with_few_samples():
    # Too few players with both scales to trust an empirical median.
    rows = [
        {"player_id": 1, "source": "fantacalcio_it", "price_current": 20},
        {"player_id": 1, "source": "fantacalcio_online", "price_current": 100},
    ]
    factor = compute_listino_to_auction_factor(rows, scale_factors={})
    assert factor == DEFAULT_LISTINO_TO_AUCTION_FACTOR


def test_compute_listino_to_auction_factor_uses_empirical_median():
    """Not the naive AUCTION_CANONICAL_CEILING/LISTINO_CANONICAL_CEILING=12.5:
    that overvalued cheap listino-only players so badly the LP optimizer's
    cheapest possible 25-player squad exceeded the entire 500-credit budget
    (found while investigating TASK-016). Each of these 20 synthetic players
    has auction=2x listino (after scaling) on both sources — the median
    empirical ratio must reflect that 2x, not the domain constant."""
    rows = []
    for pid in range(1, 21):
        rows.append({"player_id": pid, "source": "fantacalcio_it", "price_current": 10})
        rows.append({"player_id": pid, "source": "fantacalcio_online", "price_current": 20})

    factor = compute_listino_to_auction_factor(rows, scale_factors={})

    assert factor == 2.0


def test_get_squad_suggestions_ranks_by_fantasy_value_not_cheapness(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    strong = repository.upsert_player(conn, "Strong Starter", "Inter", "A", "Pu", None)
    cheap_mediocre = repository.upsert_player(conn, "Cheap Mediocre", "Roma", "A", "Pu", None)
    # A separately-priced reference so per-source p99 (compute_source_scale_
    # factors, TASK-001) isn't set by "Strong Starter" itself — otherwise its
    # own raw price rescales to exactly the canonical ceiling and, converted
    # to auction credits, lands right at the full 500-credit budget instead
    # of a realistic mid-price.
    reference = repository.upsert_player(conn, "Reference Filler", "Milan", "A", "Pu", None)
    # Strong player: high fantamedia, expensive but affordable. Mediocre
    # player: low fantamedia, dirt cheap (would win on Value for Money alone).
    repository.insert_quotation(conn, strong, "fantacalcio_it", "2026-08-22", 40, 40, "ok", 7.5, 7.5, 35)
    repository.insert_quotation(conn, strong, "fantapazz", "2026-08-22", 40, 40, "ok", 7.5, 7.5, 35)
    repository.insert_quotation(conn, cheap_mediocre, "fantacalcio_it", "2026-08-22", 1, 1, "ok", 5.8, 5.8, 20)
    repository.insert_quotation(conn, cheap_mediocre, "fantapazz", "2026-08-22", 1, 1, "ok", 5.8, 5.8, 20)
    repository.insert_quotation(conn, reference, "fantacalcio_it", "2026-08-22", 999, 999, "ok", 5.0, 5.0, 30)
    repository.insert_quotation(conn, reference, "fantapazz", "2026-08-22", 999, 999, "ok", 5.0, 5.0, 30)

    result = get_squad_suggestions(conn)

    attackers = [c["canonical_name"] for c in result["suggestions"]["A"]]
    assert attackers[0] == "Strong Starter"
    conn.close()


def test_get_ideal_squad_ignores_budget_and_roster(tmp_path):
    from dashboard.data_access import get_ideal_squad

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    expensive_star = repository.upsert_player(conn, "Expensive Star", "Inter", "A", "Pu", None)
    repository.insert_quotation(conn, expensive_star, "fantacalcio_it", "2026-08-22", 60, 60, "ok", 8.0, 8.0, 36)
    repository.insert_quotation(conn, expensive_star, "fantapazz", "2026-08-22", 60, 60, "ok", 8.0, 8.0, 36)
    repository.add_roster_entry(conn, expensive_star, 60, "2026-08-22")  # already owned

    ideal = get_ideal_squad(conn)

    assert any(p["canonical_name"] == "Expensive Star" for p in ideal["A"])
    conn.close()


def test_get_ideal_squad_excludes_players_with_too_few_appearances(tmp_path):
    from dashboard.data_access import get_ideal_squad

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    one_game_wonder = repository.upsert_player(conn, "One Game Wonder", "Napoli", "P", "Pu", None)
    solid_starter = repository.upsert_player(conn, "Solid Starter", "Atalanta", "P", "Pu", None)
    # Single appearance with a decent rating shouldn't outrank a real
    # season's worth of starts just because the fantamedia looks similar.
    repository.insert_quotation(conn, one_game_wonder, "fantacalcio_it", "2026-08-22", 1, 1, "ok", 6.0, 6.0, 1)
    repository.insert_quotation(conn, one_game_wonder, "fantapazz", "2026-08-22", 1, 1, "ok", 6.0, 6.0, 1)
    repository.insert_quotation(conn, solid_starter, "fantacalcio_it", "2026-08-22", 20, 20, "ok", 5.6, 5.6, 37)
    repository.insert_quotation(conn, solid_starter, "fantapazz", "2026-08-22", 20, 20, "ok", 5.6, 5.6, 37)

    ideal = get_ideal_squad(conn)

    names = [p["canonical_name"] for p in ideal["P"]]
    assert "One Game Wonder" not in names
    assert "Solid Starter" in names
    conn.close()


def test_get_squad_suggestions_excludes_roster_and_unaffordable_players(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    owned = repository.upsert_player(conn, "Owned Striker", "Inter", "A", "Pu", None)
    affordable = repository.upsert_player(conn, "Cheap Striker", "Roma", "A", "Pu", None)
    expensive = repository.upsert_player(conn, "Expensive Striker", "Milan", "A", "Pu", None)
    repository.insert_quotation(conn, owned, "fantacalcio_it", "2026-08-22", 20, 20, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, owned, "fantapazz", "2026-08-22", 20, 20, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, affordable, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, affordable, "fantapazz", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, expensive, "fantacalcio_it", "2026-08-22", 999, 999, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, expensive, "fantapazz", "2026-08-22", 999, 999, "ok", 6.5, 6.3, 30)
    repository.add_roster_entry(conn, owned, 20, "2026-08-22")

    result = get_squad_suggestions(conn)

    attackers = [c["canonical_name"] for c in result["suggestions"]["A"]]
    assert "Owned Striker" not in attackers
    assert "Expensive Striker" not in attackers
    assert "Cheap Striker" in attackers
    conn.close()


def test_get_squad_suggestions_excludes_clear_backups_but_keeps_unknown_appearances(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    backup = repository.upsert_player(conn, "Backup Keeper", "Inter", "P", "Por", None)
    starter = repository.upsert_player(conn, "Starter Keeper", "Roma", "P", "Por", None)
    new_signing = repository.upsert_player(conn, "New Signing Keeper", "Milan", "P", "Por", None)
    # A separately-priced reference so per-source p99 (compute_source_scale_
    # factors, TASK-001) isn't set by "Starter Keeper" itself — otherwise its
    # own raw price rescales to exactly the canonical ceiling and, converted
    # to auction credits, lands right at the full 500-credit budget.
    reference = repository.upsert_player(conn, "Reference Filler", "Napoli", "P", "Por", None)
    repository.insert_quotation(conn, backup, "fantacalcio_it", "2026-08-22", 1, 1, "ok", 6.0, 6.0, 1)
    repository.insert_quotation(conn, backup, "fantapazz", "2026-08-22", 1, 1, "ok", 6.0, 6.0, 1)
    repository.insert_quotation(conn, starter, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.2, 6.2, 35)
    repository.insert_quotation(conn, starter, "fantapazz", "2026-08-22", 15, 15, "ok", 6.2, 6.2, 35)
    repository.insert_quotation(conn, new_signing, "fantacalcio_it", "2026-08-22", 10, 10, "ok", 6.1, 6.1, None)
    repository.insert_quotation(conn, new_signing, "fantapazz", "2026-08-22", 10, 10, "ok", 6.1, 6.1, None)
    repository.insert_quotation(conn, reference, "fantacalcio_it", "2026-08-22", 999, 999, "ok", 5.0, 5.0, 30)
    repository.insert_quotation(conn, reference, "fantapazz", "2026-08-22", 999, 999, "ok", 5.0, 5.0, 30)

    result = get_squad_suggestions(conn)

    keepers = [c["canonical_name"] for c in result["suggestions"]["P"]]
    assert "Backup Keeper" not in keepers
    assert "Starter Keeper" in keepers
    assert "New Signing Keeper" in keepers
    conn.close()


def test_get_squad_suggestions_excludes_opponent_picks(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    taken = repository.upsert_player(conn, "Taken Striker", "Inter", "A", "Pu", None)
    free = repository.upsert_player(conn, "Free Striker", "Roma", "A", "Pu", None)
    # A separately-priced reference so per-source p99 (compute_source_scale_
    # factors, TASK-001) isn't set by "Taken/Free Striker" themselves —
    # otherwise their own raw price rescales to exactly the canonical
    # ceiling and, converted to auction credits, lands right at the full
    # 500-credit budget.
    reference = repository.upsert_player(conn, "Reference Filler", "Milan", "A", "Pu", None)
    repository.insert_quotation(conn, taken, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, taken, "fantapazz", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, free, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, free, "fantapazz", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, reference, "fantacalcio_it", "2026-08-22", 999, 999, "ok", 5.0, 5.0, 30)
    repository.insert_quotation(conn, reference, "fantapazz", "2026-08-22", 999, 999, "ok", 5.0, 5.0, 30)
    repository.add_opponent_pick(conn, taken, "Avversario 1", 20, "2026-08-22")

    result = get_squad_suggestions(conn)

    attackers = [c["canonical_name"] for c in result["suggestions"]["A"]]
    assert "Taken Striker" not in attackers
    assert "Free Striker" in attackers
    conn.close()


def test_get_auction_intelligence_returns_no_data_without_a_fair_price(tmp_path):
    """P1-011/TASK-018: `(fair_price or 0) > 0` used to be a constant inside
    the alternatives_remaining comprehension, so a missing fair_price on the
    evaluated player made alternatives_remaining=0 for every candidate — the
    strongest possible scarcity signal ("BUY NOW"), triggered by the one
    case where there's no price to act on. It must instead fail loudly."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    no_price = repository.upsert_player(conn, "No Price Striker", "Roma", "A", "Pu", None)
    # fantamedia present (so the player exists/ranks) but no price_current
    # from any source: get_player_detail's price_current stays None.
    repository.insert_quotation(
        conn, no_price, "fantacalcio_it", "2026-08-22",
        price_current=None, price_initial=None, status="ok",
        fantamedia=6.5, avg_rating=6.5, appearances=30,
    )

    info = get_auction_intelligence(conn, no_price)

    assert info["fair_price"] is None
    assert info["scarcity"] is None
    assert info["max_bid"] is None
    assert info["timing"]["action"] == "no_data"
    conn.close()


def test_get_source_weights_configurable_in_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    weights = repository.get_source_weights(conn)
    assert weights["fantacalcio_online"] == 45

    repository.set_source_weight(conn, "fantacalcio_online", 5)
    updated = repository.get_source_weights(conn)

    assert updated["fantacalcio_online"] == 5
    conn.close()


def test_get_monitoring_data_has_no_match_review_queue_key(tmp_path):
    """get_match_review_queue is deliberately split out — it must stay a
    separate, cheap call so confirming/rejecting a match doesn't force a
    full re-run of the ~800-player consensus merge just to update one row."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    data = get_monitoring_data(conn)

    assert "match_review_queue" not in data
    conn.close()


def test_get_monitoring_data_flags_never_populated_table_as_red(tmp_path):
    """TASK-004/P0-008: a table no pipeline has ever written to (e.g.
    player_injuries, still 0 rows in production) must show as 🔴 in
    Monitoraggio, not be silently absent from the health list."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    data = get_monitoring_data(conn)
    injuries_health = next(h for h in data["table_health"] if h["table"] == "player_injuries")

    assert injuries_health["row_count"] == 0
    assert injuries_health["status"] == "red"
    conn.close()


def test_get_monitoring_data_flags_freshly_written_table_as_green(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Dimarco", "Inter", "D", "Ds", None)
    today = date.today().isoformat()
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", today,
        price_current=30, price_initial=28, status="ok",
        fantamedia=6.5, avg_rating=6.5, appearances=30,
    )

    data = get_monitoring_data(conn)
    quotations_health = next(h for h in data["table_health"] if h["table"] == "quotations")

    assert quotations_health["row_count"] == 1
    assert quotations_health["status"] == "green"
    conn.close()


def test_get_match_review_queue_lists_low_confidence_matches(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    repository.upsert_player_source_match(
        conn, player_id, "fantacalcio_it", "Martinez L.", "Inter", 90.0, "2026-08-22",
    )

    queue = get_match_review_queue(conn)

    assert len(queue) == 1
    assert queue[0]["canonical_name"] == "Lautaro Martinez"
    assert queue[0]["review_status"] is None
    conn.close()


def test_get_price_history_by_date_pivots_by_source_and_date(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-01", 35, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, p1, "fantapazz", "2026-08-01", 33, 30, "ok", None, None, None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-10", 38, 30, "ok", 7.0, 6.8, 31)
    # a second scrape on the same day should overwrite the first for that day
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-10", 39, 30, "ok", 7.0, 6.8, 31)

    history = get_price_history_by_date(conn, p1)

    assert history["2026-08-01"] == {"fantacalcio_it": 35, "fantapazz": 33}
    assert history["2026-08-10"] == {"fantacalcio_it": 39}
    conn.close()


def test_opponent_pick_marks_player_taken_in_ranked_role(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, p1, "fantapazz", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.add_opponent_pick(conn, p1, "Avversario 1", 40, "2026-08-22")

    ranked = get_ranked_role(conn, "A")

    assert ranked[0]["taken_by"] == "Avversario 1"
    conn.close()


def test_opponent_pick_upserts_on_duplicate_player(tmp_path):
    """P1-017/TASK-020: re-marking a player updates the existing pick
    (correcting a typo) instead of raising — see also
    tests/test_db_repository.py::test_add_opponent_pick_upserts_instead_of_raising."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    repository.add_opponent_pick(conn, p1, "Avversario 1", 40, "2026-08-22")

    repository.add_opponent_pick(conn, p1, "Avversario 2", 41, "2026-08-22")

    picks = repository.get_opponent_picks(conn)
    assert len(picks) == 1
    assert picks[0]["opponent_name"] == "Avversario 2"
    conn.close()


def test_get_recent_form_averages_fantavoto_and_ignores_missing(tmp_path):
    from dashboard.data_access import get_recent_form

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.upsert_match_rating(conn, player_id, "2026/27", 1, 7.0, 8.5, "src", "2026-08-24")
    repository.upsert_match_rating(conn, player_id, "2026/27", 2, None, None, "src", "2026-08-24")
    repository.upsert_match_rating(conn, player_id, "2026/27", 3, 6.0, 6.0, "src", "2026-08-24")

    form = get_recent_form(conn, player_id, window=5)

    assert form["avg_fantavoto"] == 7.25
    assert len(form["ratings"]) == 3
    conn.close()


def test_get_recent_form_empty_when_no_giornate_played(tmp_path):
    from dashboard.data_access import get_recent_form

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    form = get_recent_form(conn, player_id)

    assert form["ratings"] == []
    assert form["avg_fantavoto"] is None
    conn.close()


def test_get_auction_price_trend_computes_running_average_across_me_and_opponents(tmp_path):
    from dashboard.data_access import get_auction_price_trend

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    mine = repository.upsert_player(conn, "My Striker", "Inter", "A", "Pu", None)
    theirs = repository.upsert_player(conn, "Their Striker", "Roma", "A", "Pu", None)
    repository.add_roster_entry(conn, mine, 20, "2026-08-22")
    repository.add_opponent_pick(conn, theirs, "Avversario 1", 40, "2026-08-23")

    trend = get_auction_price_trend(conn)

    running = trend["running"]
    assert len(running) == 2
    assert running[0]["Prezzo medio"] == 20.0
    assert running[1]["Prezzo medio"] == 30.0
    assert running[1]["Prezzo medio A"] == 30.0
    assert running[1]["Prezzo medio P"] is None
    conn.close()


def test_get_auction_price_trend_orders_by_date_then_insertion(tmp_path):
    from dashboard.data_access import get_auction_price_trend

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "First", "Inter", "A", "Pu", None)
    p2 = repository.upsert_player(conn, "Second", "Roma", "A", "Pu", None)
    repository.add_roster_entry(conn, p1, 50, "2026-08-22")
    repository.add_roster_entry(conn, p2, 10, "2026-08-22")

    trend = get_auction_price_trend(conn)

    prices = [t["price_paid"] for t in trend["transactions"]]
    assert prices == [50, 10]
    conn.close()


def test_format_count():
    from dashboard.data_access import format_count

    assert format_count(None) == "-"
    assert format_count(4.0) == "4"
    assert format_count(4.5) == "4.5"
    assert format_count(4) == "4"


def test_find_player_by_name_case_insensitive(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    found = find_player_by_name(conn, "lautaro martinez")

    assert found is not None
    assert found["canonical_name"] == "Lautaro Martinez"
    conn.close()


def test_find_player_by_name_returns_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    found = find_player_by_name(conn, "Nobody")

    assert found is None
    conn.close()


def test_get_roster_with_profile_merges_price_paid_and_role_mantra(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Owned Player", "Inter", "D", "E", None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)
    repository.insert_quotation(conn, p1, "fantapazz", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)
    repository.add_roster_entry(conn, p1, 12.0, "2026-08-22")

    owned = get_roster_with_profile(conn)

    assert len(owned) == 1
    assert owned[0]["player_id"] == p1
    assert owned[0]["role_mantra"] == "E"
    assert owned[0]["price_paid"] == 12.0
    conn.close()


def test_get_roster_with_profile_excludes_players_not_owned(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    not_owned = repository.upsert_player(conn, "Free Player", "Milan", "A", "PC", None)
    repository.insert_quotation(conn, not_owned, "fantacalcio_it", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)
    repository.insert_quotation(conn, not_owned, "fantapazz", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)

    owned = get_roster_with_profile(conn)

    assert owned == []
    conn.close()


def test_get_player_detail_includes_tier(tmp_path):
    from ranking.tiers import TOP

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    star = repository.upsert_player(conn, "Star Player", "Inter", "A", None, None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, star, source, "2026-08-22", 30, 30, "ok", 8.0, 8.0, 35)
    for i in range(15):
        # A letter suffix, not a digit: identity_key normalizes on letters
        # only (matching.player_matcher.normalize_name), so "Filler0"/
        # "Filler1" would collide into the same player (TASK-007/P0-007).
        filler = repository.upsert_player(conn, f"Filler{chr(65 + i)}", "Inter", "A", None, None)
        for source in ("fantacalcio_it", "fantapazz"):
            repository.insert_quotation(conn, filler, source, "2026-08-22", 10, 10, "ok", 5.5, 5.5, 25)

    detail = get_player_detail(conn, star)

    assert detail["tier"] == TOP
    conn.close()


def test_get_player_detail_tier_is_none_for_player_already_in_roster(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Owned Player", "Inter", "A", None, None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, p1, source, "2026-08-22", 30, 30, "ok", 8.0, 8.0, 35)
    repository.add_roster_entry(conn, p1, 30, "2026-08-22")

    detail = get_player_detail(conn, p1)

    assert detail["tier"] is None
    conn.close()


def test_get_player_detail_includes_role_comparison(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Player One", "Inter", "A", None, None)
    p2 = repository.upsert_player(conn, "Player Two", "Inter", "A", None, None)
    for pid, fm in ((p1, 8.0), (p2, 6.0)):
        for source in ("fantacalcio_it", "fantapazz"):
            repository.insert_quotation(conn, pid, source, "2026-08-22", 20, 20, "ok", fm, fm, 30)

    detail = get_player_detail(conn, p1)

    assert detail["role_comparison"]["fantamedia"]["player"] == 8.0
    conn.close()


def test_get_player_detail_includes_advanced_stats(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Player One", "Inter", "A", None, None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, p1, source, "2026-08-22", 20, 20, "ok", 7.0, 7.0, 30)
    repository.insert_player_advanced_stats(
        conn, p1, 53, 43, 22, 63, 34, 43, "fantanalisi", "2026-08-27",
    )

    detail = get_player_detail(conn, p1)

    assert detail["advanced_stats"]["xg90_percentile"] == 53
    conn.close()


def test_get_player_detail_includes_fantanalisi_valuation(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Player One", "Inter", "A", None, None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, p1, source, "2026-08-22", 20, 20, "ok", 7.0, 7.0, 30)
    repository.insert_player_fantanalisi_valuation(
        conn, p1, "≤168 · ≤216", "264", "1", "●", "fantanalisi", "2026-08-27",
    )

    detail = get_player_detail(conn, p1)

    assert detail["fantanalisi_valuation"]["tier"] == "1"
    conn.close()


def _rankable_midfielder(conn, name: str, price: float, fantamedia: float) -> int:
    pid = repository.upsert_player(conn, name, "Inter", "C", "M", None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, pid, source, "2026-08-22", price, price, "ok", fantamedia, fantamedia, 30)
    return pid


def test_get_price_recommendation_returns_fresh_buy_or_borderline(tmp_path):
    """Price Engine covers the single-player sheet path end to end (audit: it
    was only covered through the Decision Center, never per player)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    pid = _rankable_midfielder(conn, "Zielinski", 6.0, 7.2)

    result = get_price_recommendation(conn, pid)

    assert result is not None
    assert result["status"] in {BUY, BORDERLINE, PASS}
    assert isinstance(result["fair_price"], (int, float))
    assert isinstance(result["max_price"], (int, float))
    conn.close()


def test_get_price_recommendation_none_without_player_or_price(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    assert get_price_recommendation(conn, 999999) is None

    pid = repository.upsert_player(conn, "No Price", "Inter", "C", "M", None)
    assert get_price_recommendation(conn, pid) is None
    conn.close()


def test_get_auction_intelligence_maps_every_market_signal(tmp_path):
    """Auction Intelligence covers the full live-auction sheet: fair price,
    inflation, opponents, budget and slot summary (audit: only the low-level
    auction_intelligence helpers were tested, never this composition)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    pid = _rankable_midfielder(conn, "Frattesi", 22.0, 6.9)

    result = get_auction_intelligence(conn, pid)

    assert result is not None
    # Not ==22.0: since TASK-001, price_current is rescaled per-source
    # against that source's own 99th percentile (compute_source_scale_
    # factors) — with Frattesi as the *only* priced player in this test DB,
    # his own price is that percentile, so he rescales to the family
    # ceiling. This test is about the full Auction Intelligence composition
    # wiring up correctly, not about pinning a specific fair_price number.
    assert isinstance(result["fair_price"], (int, float)) and result["fair_price"] > 0
    assert result["budget_remaining"] == 500.0
    # ranking.budget.compute_budget_summary's per-role slot dict has no
    # "role" key of its own (the caller already knows which role it asked
    # for) — total=8 confirms it's the "C" (centrocampisti) slot, per
    # ranking.lp_optimizer.ROLE_SLOTS.
    assert result["slot"]["total"] == 8
    assert result["inflation"]["inflation_pct"] is None  # no purchases yet
    for key in ("expected_auction_price", "max_bid", "scarcity", "distribution", "timing", "opponents"):
        assert key in result
    conn.close()


def test_get_auction_intelligence_none_for_unknown_player(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    assert get_auction_intelligence(conn, 999999) is None
    conn.close()
