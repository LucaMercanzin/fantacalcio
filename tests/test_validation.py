from db import repository
from db.connection import get_connection, init_db
from pipeline.validation import compute_field_coverage, validate_record
from scrapers.base import PlayerRecord

VALID_TEAMS = {"int", "rom", "mil"}  # normalize_team()-shaped, matching the real teams.code column


def _record(**overrides):
    fields = {
        "name": "Test Player", "team": "Inter", "role_classic": "A", "role_mantra": None,
        "price_current": 20, "price_initial": 18, "status": "ok", "fantamedia": 6.5,
        "avg_rating": 6.3, "appearances": 30, "photo_url": None, "source": "fantacalcio_it",
    }
    fields.update(overrides)
    return PlayerRecord(**fields)


def _seed_quotations(conn, source, rows):
    """rows: list of (canonical_name, fantamedia) — everything else fixed,
    only fantamedia varies so tests can control that field's coverage %."""
    for i, (name, fantamedia) in enumerate(rows):
        player_id = repository.upsert_player(conn, name, "Inter", "A", None, None)
        repository.insert_quotation(
            conn, player_id, source, "2026-08-24",
            price_current=20, price_initial=18, status="ok",
            fantamedia=fantamedia, avg_rating=6.0, appearances=30,
        )


def test_compute_field_coverage_computes_percentage_of_non_null_values(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_quotations(conn, "fantacalcio_it", [
        ("Player A", 6.5), ("Player B", 6.0), ("Player C", None), ("Player D", None),
    ])

    coverage = compute_field_coverage(conn)

    fantamedia_row = next(c for c in coverage if c["source"] == "fantacalcio_it" and c["field"] == "fantamedia")
    assert fantamedia_row["total_rows"] == 4
    assert fantamedia_row["non_null"] == 2
    assert fantamedia_row["coverage_pct"] == 50.0
    conn.close()


def test_compute_field_coverage_flags_a_declared_field_below_its_threshold(tmp_path):
    """fantacalciopedia *dichiara* la fantamedia: 1 riga su 5 (20%) sotto
    il pavimento del 35% è uno scraper che ha smesso di leggere la colonna,
    ed è esattamente il caso che deve suonare."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_quotations(conn, "fantacalciopedia", [
        ("Player A", 6.5), ("Player B", None), ("Player C", None),
        ("Player D", None), ("Player E", None),
    ])

    coverage = compute_field_coverage(conn)

    fantamedia_row = next(c for c in coverage if c["field"] == "fantamedia")
    assert fantamedia_row["provided"] is True
    assert fantamedia_row["below_threshold"] is True
    conn.close()


def test_compute_field_coverage_logs_an_error_for_flagged_pairs(tmp_path, caplog):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_quotations(conn, "fantacalciopedia", [("Player A", None), ("Player B", None)])

    with caplog.at_level("ERROR"):
        compute_field_coverage(conn)

    assert any("fantamedia" in message and "sotto soglia" in message for message in caplog.messages)
    conn.close()


def test_a_field_a_source_never_publishes_is_not_an_alarm(tmp_path):
    """BACKLOG-2026-08-31 §8. fantacalcio_it non ha mai pubblicato una
    fantamedia: il suo scraper scrive `fantamedia=None` come costante. Uno
    0% lì non è un guasto, è la definizione della fonte. Prima veniva
    segnalato a ogni run, ed era uno dei ~30 warning strutturali che
    rendevano illeggibili i pochi veri."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Player A", "Inter", "A", None, None)
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-24",
        price_current=20, price_initial=18, status=None,
        fantamedia=None, avg_rating=None, appearances=None,
    )

    coverage = compute_field_coverage(conn)

    fantamedia_row = next(c for c in coverage if c["field"] == "fantamedia")
    assert fantamedia_row["coverage_pct"] == 0.0
    assert fantamedia_row["provided"] is False
    assert fantamedia_row["below_threshold"] is False
    assert fantamedia_row["threshold"] is None
    price_row = next(c for c in coverage if c["field"] == "price_current")
    assert price_row["provided"] is True
    assert price_row["below_threshold"] is False


def test_an_unknown_source_is_checked_on_every_field(tmp_path):
    """Uno scraper nuovo non ancora dichiarato deve essere controllato su
    tutto: meglio un falso allarme che entrare in produzione senza nessun
    controllo di copertura."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_quotations(conn, "fonte_nuova", [("Player A", None), ("Player B", None)])

    coverage = compute_field_coverage(conn)

    fantamedia_row = next(c for c in coverage if c["field"] == "fantamedia")
    assert fantamedia_row["provided"] is True
    assert fantamedia_row["below_threshold"] is True
    conn.close()


def test_compute_field_coverage_tracks_stats_season_with_no_false_alarm(tmp_path):
    """TASK-008/P0-004 point 4: Monitoraggio's existing per-(source,field)
    coverage panel now also tracks stats_season/stats_competition — a
    source that never declares an exact season (only stats_competition)
    must not be flagged below_threshold for stats_season, since no source
    is expected to reach the normal 80% floor there (see COVERAGE_
    THRESHOLDS)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Player A", "Inter", "A", None, None)
    repository.insert_quotation(
        conn, player_id, "fantacalciopedia", "2026-08-24",
        price_current=None, price_initial=None, status=None,
        fantamedia=8.5, avg_rating=None, appearances=19,
        stats_season=None, stats_competition="serie_a",
    )

    coverage = compute_field_coverage(conn)

    season_row = next(c for c in coverage if c["field"] == "stats_season")
    competition_row = next(c for c in coverage if c["field"] == "stats_competition")
    assert season_row["coverage_pct"] == 0.0
    assert season_row["below_threshold"] is False
    assert competition_row["coverage_pct"] == 100.0
    conn.close()


def test_validate_record_passes_a_clean_record_through_unchanged():
    record = _record()

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned is record
    assert problems == []


def test_validate_record_discards_invalid_role_classic():
    record = _record(role_classic="X")

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned is None
    assert len(problems) == 1
    assert "role_classic" in problems[0]


def test_validate_record_discards_unrecognized_team():
    record = _record(team="Estero")

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned is None
    assert "team" in problems[0]


def test_validate_record_clears_but_keeps_out_of_range_fantamedia():
    """P0-003: a fantamedia outside the plausible Serie A range is cleared
    to None (never clamped to a fabricated value), but the record itself
    survives — every other field is still real."""
    record = _record(fantamedia=15.0)

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned is not None
    assert cleaned.fantamedia is None
    assert cleaned.avg_rating == record.avg_rating  # untouched
    assert any("fantamedia" in p for p in problems)


def test_validate_record_clears_invalid_role_mantra():
    record = _record(role_mantra="ZZ")

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned is not None
    assert cleaned.role_mantra is None
    assert any("role_mantra" in p for p in problems)


def test_validate_record_clears_out_of_range_avg_rating_and_appearances():
    record = _record(avg_rating=1.0, appearances=99)

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned.avg_rating is None
    assert cleaned.appearances is None
    assert len(problems) == 2


def test_validate_record_clears_non_positive_price():
    record = _record(price_current=0)

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned.price_current is None
    assert any("price_current" in p for p in problems)


def test_validate_record_accepts_none_for_every_optional_field():
    """None is always a valid value — it means the source didn't report
    that field, not that it's out of range."""
    record = _record(
        role_mantra=None, fantamedia=None, avg_rating=None,
        appearances=None, price_current=None,
    )

    cleaned, problems = validate_record(record, VALID_TEAMS)

    assert cleaned is record
    assert problems == []
