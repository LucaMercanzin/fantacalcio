import os
from streamlit.testing.v1 import AppTest

from dashboard import components
from db.connection import init_db, get_connection
from db import repository


def test_photo_data_uri_resolves_windows_style_path_on_any_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(components, "PHOTOS_DIR", str(tmp_path))
    photo_file = tmp_path / "1.jpg"
    photo_file.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

    windows_style_path = r"C:\Users\merca\projects\fantacalcio\data\photos\1.jpg"
    result = components._photo_data_uri(windows_style_path)

    assert result is not None
    assert result.startswith("data:image/jpeg;base64,")


def test_photo_data_uri_resolves_posix_style_path(tmp_path, monkeypatch):
    monkeypatch.setattr(components, "PHOTOS_DIR", str(tmp_path))
    photo_file = tmp_path / "42.jpg"
    photo_file.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

    result = components._photo_data_uri("/home/adminuser/data/photos/42.jpg")

    assert result is not None


def test_photo_data_uri_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(components, "PHOTOS_DIR", str(tmp_path))

    assert components._photo_data_uri(r"C:\some\path\999.jpg") is None


def test_photo_data_uri_returns_none_for_empty_path():
    assert components._photo_data_uri(None) is None
    assert components._photo_data_uri("") is None


def _seed_goalkeeper(conn, name, team, appearances):
    player_id = repository.upsert_player(conn, name, team, "P", "Por", None)
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-22", 10, 10, "ok", 6.0, 6.0, appearances,
    )
    repository.insert_quotation(
        conn, player_id, "fantapazz", "2026-08-22", 10, 10, "ok", 6.0, 6.0, appearances,
    )
    return player_id


def _run_goalkeeper_depth_chart_app(conn):
    def script(conn):
        from dashboard.components import render_goalkeeper_depth_chart
        render_goalkeeper_depth_chart(conn)

    at = AppTest.from_function(script, kwargs={"conn": conn})
    at.run()
    return at


def test_render_goalkeeper_depth_chart_groups_by_team_and_warns_for_single_keeper_team(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_goalkeeper(conn, "Starter Inter", "Inter", 35)
    _seed_goalkeeper(conn, "Backup Inter", "Inter", 20)
    _seed_goalkeeper(conn, "Solo Como", "Como", 35)

    at = _run_goalkeeper_depth_chart_app(conn)

    assert not at.exception
    assert any("Inter" in m.value for m in at.markdown)
    assert any("Como" in m.value for m in at.markdown)
    assert any("Como" in w.value for w in at.warning)
    conn.close()
