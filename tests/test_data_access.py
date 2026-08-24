from db.connection import init_db, get_connection
from db import repository
from dashboard.data_access import (
    get_ranked_role, search_and_sort, find_player_by_name, _merge_player_rows,
    get_price_history_by_date,
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
