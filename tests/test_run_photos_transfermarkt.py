import os

from db import repository
from db.connection import get_connection, init_db
from pipeline import run_photos_transfermarkt


def _fake_download(url, player_id, photos_dir):
    if not url:
        return None
    os.makedirs(photos_dir, exist_ok=True)
    path = os.path.join(photos_dir, f"{player_id}.jpg")
    with open(path, "wb") as f:
        f.write(b"fake")
    return path


def _setup_two_players(conn):
    expensive = repository.upsert_player(conn, "Expensive Star", "Inter", "A", "Pu", None)
    cheap = repository.upsert_player(conn, "Cheap Bench Player", "Roma", "A", "Pu", None)
    for pid, price in ((expensive, 200), (cheap, 5)):
        repository.insert_quotation(conn, pid, "fantacalcio_it", "2026-08-22", price, price, "ok", 6.0, 6.0, 30)
        repository.insert_quotation(conn, pid, "fantapazz", "2026-08-22", price, price, "ok", 6.0, 6.0, 30)
    return expensive, cheap


def test_run_downloads_photo_for_top_half_only(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    expensive, cheap = _setup_two_players(conn)

    monkeypatch.setattr(run_photos_transfermarkt, "TOP_FRACTION", 0.5)
    monkeypatch.setattr(run_photos_transfermarkt, "search_player_id", lambda name, team: 999)
    monkeypatch.setattr(run_photos_transfermarkt, "fetch_photo_url", lambda tm_id: "https://example.com/photo.jpg")
    monkeypatch.setattr(run_photos_transfermarkt, "download_photo", _fake_download)
    monkeypatch.setattr(run_photos_transfermarkt.time, "sleep", lambda s: None)

    photos_dir = str(tmp_path / "photos")
    result = run_photos_transfermarkt.run(conn, photos_dir=photos_dir)

    assert result["downloaded"] == 1
    repository.get_player_extra(conn, expensive) if hasattr(repository, "get_player_extra") else None
    cur = conn.execute("SELECT photo_path FROM players WHERE id = ?", (expensive,))
    assert cur.fetchone()["photo_path"] is not None
    cur = conn.execute("SELECT photo_path FROM players WHERE id = ?", (cheap,))
    assert cur.fetchone()["photo_path"] is None
    conn.close()


def test_run_reuses_known_transfermarkt_id(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    expensive, _ = _setup_two_players(conn)
    repository.upsert_transfermarkt_id(conn, expensive, 12345, "2026-08-24")

    search_calls = []
    monkeypatch.setattr(
        run_photos_transfermarkt, "search_player_id",
        lambda name, team: search_calls.append(1) or 999,
    )
    monkeypatch.setattr(run_photos_transfermarkt, "TOP_FRACTION", 0.5)
    monkeypatch.setattr(run_photos_transfermarkt, "fetch_photo_url", lambda tm_id: "https://example.com/photo.jpg")
    monkeypatch.setattr(run_photos_transfermarkt, "download_photo", _fake_download)
    monkeypatch.setattr(run_photos_transfermarkt.time, "sleep", lambda s: None)

    run_photos_transfermarkt.run(conn, photos_dir=str(tmp_path / "photos"))

    assert search_calls == []
    conn.close()


def test_run_skips_players_who_already_have_a_photo(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _expensive, _ = _setup_two_players(conn)
    repository.upsert_player(conn, "Expensive Star", "Inter", "A", "Pu", "existing.jpg")

    monkeypatch.setattr(run_photos_transfermarkt, "TOP_FRACTION", 0.5)
    calls = []
    monkeypatch.setattr(
        run_photos_transfermarkt, "search_player_id",
        lambda name, team: calls.append(1) or 999,
    )
    monkeypatch.setattr(run_photos_transfermarkt, "fetch_photo_url", lambda tm_id: "https://example.com/photo.jpg")
    monkeypatch.setattr(run_photos_transfermarkt, "download_photo", _fake_download)
    monkeypatch.setattr(run_photos_transfermarkt.time, "sleep", lambda s: None)

    run_photos_transfermarkt.run(conn, photos_dir=str(tmp_path / "photos"))

    assert calls == []
    conn.close()
