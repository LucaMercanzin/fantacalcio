from db import repository
from db.connection import get_connection, init_db
from pipeline.validation import compute_field_coverage


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


def test_compute_field_coverage_flags_pair_below_its_threshold(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    # 1 out of 5 has fantamedia (20%) — well under the 80% default floor.
    _seed_quotations(conn, "fantacalcio_it", [
        ("Player A", 6.5), ("Player B", None), ("Player C", None),
        ("Player D", None), ("Player E", None),
    ])

    coverage = compute_field_coverage(conn)

    fantamedia_row = next(c for c in coverage if c["field"] == "fantamedia")
    assert fantamedia_row["below_threshold"] is True
    price_current_row = next(c for c in coverage if c["field"] == "price_current")
    assert price_current_row["below_threshold"] is False  # every row has one
    conn.close()


def test_compute_field_coverage_logs_an_error_for_flagged_pairs(tmp_path, caplog):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_quotations(conn, "fantacalcio_it", [("Player A", None), ("Player B", None)])

    with caplog.at_level("ERROR"):
        compute_field_coverage(conn)

    assert any("fantamedia" in message and "sotto soglia" in message for message in caplog.messages)
    conn.close()


def test_compute_field_coverage_uses_a_lower_floor_for_status_and_price_initial(tmp_path):
    """status/price_initial aren't published by every source by design, so
    they get a lower threshold than the rest of the fields — at the same
    40% coverage level, a core field (fantamedia) is flagged but status
    (30% floor) is not."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    rows = [("Player A", 6.0, "ok"), ("Player B", 6.5, "ok")] + [
        (f"Player {c}", None, None) for c in "CDE"
    ]
    for name, fantamedia, status in rows:
        player_id = repository.upsert_player(conn, name, "Inter", "A", None, None)
        repository.insert_quotation(
            conn, player_id, "pianetafanta", "2026-08-24",
            price_current=20, price_initial=18, status=status,
            fantamedia=fantamedia, avg_rating=6.0, appearances=30,
        )

    coverage = compute_field_coverage(conn)

    status_row = next(c for c in coverage if c["field"] == "status")
    fantamedia_row = next(c for c in coverage if c["field"] == "fantamedia")
    assert status_row["coverage_pct"] == 40.0
    assert fantamedia_row["coverage_pct"] == 40.0
    assert status_row["below_threshold"] is False
    assert fantamedia_row["below_threshold"] is True
    conn.close()
