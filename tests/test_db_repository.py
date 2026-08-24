from db.connection import init_db, get_connection
from db import repository


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert {"players", "quotations", "my_roster", "player_notes"} <= tables
    conn.close()


def test_upsert_player_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    id1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    id2 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    assert id1 == id2
    conn.close()


def test_insert_and_get_latest_quotations(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-01",
        price_current=35, price_initial=30, status="ok",
        fantamedia=6.8, avg_rating=6.5, appearances=30,
    )
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-10",
        price_current=38, price_initial=30, status="ok",
        fantamedia=6.8, avg_rating=6.5, appearances=30,
    )

    latest = repository.get_latest_quotations(conn, role_classic="A")

    assert len(latest) == 1
    assert latest[0]["price_current"] == 38
    conn.close()


def test_roster_add_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.add_roster_entry(conn, player_id, price_paid=40, date_added="2026-08-20")
    roster = repository.get_roster(conn)

    assert len(roster) == 1
    assert roster[0]["price_paid"] == 40
    conn.close()


def test_player_notes_upsert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.upsert_player_notes(conn, player_id, "Ottimo investimento", "2026-08-20")
    repository.upsert_player_notes(conn, player_id, "Aggiornato: preferire vice", "2026-08-21")

    notes = repository.get_player_notes(conn, player_id)

    assert notes == "Aggiornato: preferire vice"
    conn.close()


def test_transfermarkt_id_upsert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", "Pc", None)

    repository.upsert_transfermarkt_id(conn, player_id, 326029, "2026-08-24")

    assert repository.get_transfermarkt_id(conn, player_id) == 326029
    conn.close()


def test_replace_player_injuries(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Donyell Malen", "Roma", "A", "Pc", None)

    injuries = [
        {"season": "24/25", "injury_type": "Malato", "date_from": "26/02/2025",
         "date_to": "03/03/2025", "days_out": 6, "matches_missed": 1},
        {"season": "23/24", "injury_type": "Problemi al ginocchio", "date_from": "14/04/2024",
         "date_to": "29/04/2024", "days_out": 16, "matches_missed": 3},
    ]
    repository.replace_player_injuries(conn, player_id, injuries)

    stored = repository.get_player_injuries(conn, player_id)
    assert len(stored) == 2
    assert stored[0]["injury_type"] in {"Malato", "Problemi al ginocchio"}

    repository.replace_player_injuries(conn, player_id, injuries[:1])
    stored = repository.get_player_injuries(conn, player_id)
    assert len(stored) == 1
    conn.close()
