from db.connection import init_db, get_connection
from db import repository
from dashboard.data_access import (
    get_ranked_role, search_and_sort, find_player_by_name, _merge_player_rows,
    get_price_history_by_date, get_squad_suggestions,
)


def test_get_ranked_role_includes_notes_and_roster_flag(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    p2 = repository.upsert_player(conn, "Dusan Vlahovic", "Juventus", "A", "Pu", None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, p2, "fantacalcio_it", "2026-08-22", 25, 22, "ok", 6.0, 6.0, 30)
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
    # weighted avg: (30*3 + 24*2) / 5 = 27.6
    assert player["price_current"] == 27.6
    assert player["price_initial"] == 30
    assert player["fantamedia"] == 6.5
    assert player["appearances"] == 20
    assert player["source"] == "fantacalcio_it+fantacalciopedia"


def test_merge_player_rows_uses_custom_weights_when_provided():
    rows = [
        {"player_id": 1, "source": "a", "price_current": 30, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
        {"player_id": 1, "source": "b", "price_current": 20, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"a": 1, "b": 1})

    assert merged[0]["price_current"] == 25.0


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
    assert player["price_current"] < 40


def test_merge_player_rows_confidence_low_for_single_source():
    rows = [
        {"player_id": 1, "source": "a", "price_current": 30, "price_initial": None,
         "fantamedia": None, "avg_rating": None, "status": None, "appearances": None},
    ]

    merged = _merge_player_rows(rows, weights={"a": 1})

    assert merged[0]["confidence"] == 40.0


def test_merge_player_rows_confidence_high_when_sources_agree():
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

    assert merged[0]["confidence"] > 90


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


def test_get_squad_suggestions_ranks_by_fantasy_value_not_cheapness(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    strong = repository.upsert_player(conn, "Strong Starter", "Inter", "A", "Pu", None)
    cheap_mediocre = repository.upsert_player(conn, "Cheap Mediocre", "Roma", "A", "Pu", None)
    # Strong player: high fantamedia, expensive but affordable. Mediocre
    # player: low fantamedia, dirt cheap (would win on Value for Money alone).
    repository.insert_quotation(conn, strong, "fantacalcio_it", "2026-08-22", 40, 40, "ok", 7.5, 7.5, 35)
    repository.insert_quotation(conn, cheap_mediocre, "fantacalcio_it", "2026-08-22", 1, 1, "ok", 5.8, 5.8, 20)

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
    repository.add_roster_entry(conn, expensive_star, 60, "2026-08-22")  # already owned

    ideal = get_ideal_squad(conn)

    assert any(p["canonical_name"] == "Expensive Star" for p in ideal["A"])
    conn.close()


def test_get_squad_suggestions_excludes_roster_and_unaffordable_players(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    owned = repository.upsert_player(conn, "Owned Striker", "Inter", "A", "Pu", None)
    affordable = repository.upsert_player(conn, "Cheap Striker", "Roma", "A", "Pu", None)
    expensive = repository.upsert_player(conn, "Expensive Striker", "Milan", "A", "Pu", None)
    repository.insert_quotation(conn, owned, "fantacalcio_it", "2026-08-22", 20, 20, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, affordable, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, expensive, "fantacalcio_it", "2026-08-22", 999, 999, "ok", 6.5, 6.3, 30)
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
    repository.insert_quotation(conn, backup, "fantacalcio_it", "2026-08-22", 1, 1, "ok", 6.0, 6.0, 1)
    repository.insert_quotation(conn, starter, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.2, 6.2, 35)
    repository.insert_quotation(conn, new_signing, "fantacalcio_it", "2026-08-22", 10, 10, "ok", 6.1, 6.1, None)

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
    repository.insert_quotation(conn, taken, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.insert_quotation(conn, free, "fantacalcio_it", "2026-08-22", 15, 15, "ok", 6.5, 6.3, 30)
    repository.add_opponent_pick(conn, taken, "Avversario 1", 20, "2026-08-22")

    result = get_squad_suggestions(conn)

    attackers = [c["canonical_name"] for c in result["suggestions"]["A"]]
    assert "Taken Striker" not in attackers
    assert "Free Striker" in attackers
    conn.close()


def test_get_source_weights_configurable_in_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    weights = repository.get_source_weights(conn)
    assert weights["fantacalcio_it"] == 3

    repository.set_source_weight(conn, "fantacalcio_it", 5)
    updated = repository.get_source_weights(conn)

    assert updated["fantacalcio_it"] == 5
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
    repository.add_opponent_pick(conn, p1, "Avversario 1", 40, "2026-08-22")

    ranked = get_ranked_role(conn, "A")

    assert ranked[0]["taken_by"] == "Avversario 1"
    conn.close()


def test_opponent_pick_rejects_duplicate_player(tmp_path):
    import sqlite3
    import pytest

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    repository.add_opponent_pick(conn, p1, "Avversario 1", 40, "2026-08-22")

    with pytest.raises(sqlite3.IntegrityError):
        repository.add_opponent_pick(conn, p1, "Avversario 2", 41, "2026-08-22")
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
