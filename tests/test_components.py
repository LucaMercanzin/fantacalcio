import os
from streamlit.testing.v1 import AppTest
from dashboard import components
from db.connection import init_db, get_connection
from db import repository


def _base_player_row(tmp_path, **overrides):
    """Minimal row + a real (empty-schema) sqlite3 connection, enough for
    render_player_detail to run end-to-end without crashing on the
    conn-backed lookups (set pieces, injuries, price history, ...), all of
    which return empty results gracefully for a player_id with no rows."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    row = {
        "player_id": 1,
        "canonical_name": "Test Player",
        "role_classic": "C",
        "role_mantra": "M",
        "team": "Inter",
        "photo_path": None,
        "is_promoted": False,
        "is_in_roster": True,  # short-circuits render_purchase_evaluator
        "taken_by": None,
        "rank_in_role": None,
        "score": 75.0,
        "price_current": 20,
        "price_initial": 18,
        "fantamedia": 6.5,
        "avg_rating": 6.3,
        "appearances": 30,
        "status": "ok",
        "source": "fantacalcio_it",
        "player_quality": 70.0,
        "value_for_money": 3.5,
        "risk": 20.0,
        "confidence": 80.0,
        "price_outlier_sources": None,
        "alg_fcp": None,
        "fcp_skills": None,
        "notes": None,
        "tactical_profile_score": None,
    }
    row.update(overrides)
    return conn, row


def _render_player_detail_script(conn, row):
    # AppTest.from_function() re-execs this function's *source* as a
    # standalone script (see streamlit.testing.v1.AppTest.from_function),
    # so it needs its own import rather than relying on this test module's.
    from dashboard import components
    components.render_player_detail(conn, row)


def _run_player_detail(conn, row):
    at = AppTest.from_function(
        _render_player_detail_script, kwargs={"conn": conn, "row": row},
    )
    at.run()
    assert not at.exception
    return at


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


def test_render_player_detail_shows_profilo_tattico_metric_when_score_present(tmp_path):
    conn, row = _base_player_row(tmp_path, tactical_profile_score=72.0)

    at = _run_player_detail(conn, row)

    labels = [m.label for m in at.metric]
    assert "Profilo tattico" in labels
    tactical_metric = next(m for m in at.metric if m.label == "Profilo tattico")
    assert tactical_metric.value == "72/100"
    conn.close()


def test_render_player_detail_omits_profilo_tattico_metric_when_score_is_none(tmp_path):
    conn, row = _base_player_row(tmp_path, role_classic="P", role_mantra="POR",
                                  tactical_profile_score=None)

    at = _run_player_detail(conn, row)

    labels = [m.label for m in at.metric]
    assert "Profilo tattico" not in labels


def test_render_player_detail_shows_green_semaforo_for_high_vfm_percentile(tmp_path):
    conn, row = _base_player_row(tmp_path, value_for_money_percentile=80.0)

    at = _run_player_detail(conn, row)

    assert any("🟢" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_shows_red_semaforo_for_low_vfm_percentile(tmp_path):
    conn, row = _base_player_row(tmp_path, value_for_money_percentile=10.0)

    at = _run_player_detail(conn, row)

    assert any("🔴" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_shows_role_comparison_section(tmp_path):
    conn, row = _base_player_row(tmp_path, role_comparison={
        "fantamedia": {"label": "Fantamedia", "player": 8.0, "role_avg": 6.5, "percentile": 92.0},
    })

    at = _run_player_detail(conn, row)

    assert any("Confronto con il ruolo" in m.value for m in at.markdown)
    conn.close()


def test_render_player_detail_omits_role_comparison_section_when_empty(tmp_path):
    conn, row = _base_player_row(tmp_path, role_comparison={})

    at = _run_player_detail(conn, row)

    assert not any("Confronto con il ruolo" in m.value for m in at.markdown)
    conn.close()


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


def test_render_player_detail_shows_verdetto_section(tmp_path):
    conn, row = _base_player_row(tmp_path, tier=None, risk=20.0,
                                  value_for_money_percentile=70.0)

    at = _run_player_detail(conn, row)

    assert any("Verdetto" in m.value for m in at.markdown)
    conn.close()
