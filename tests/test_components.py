from streamlit.testing.v1 import AppTest

from dashboard import components
from db import repository
from db.connection import get_connection, init_db


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
        "price_agreement": 80.0,
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


# AppTest.run() ha un timeout di default di 3 secondi, che queste pagine
# sfiorano già a riposo e superano quando la macchina è occupata (verificato
# 01/09/2026: la stessa pagina Portieri va in timeout mentre girano due
# scraper, e passa a macchina scarica). Un timeout generoso toglie di mezzo
# un fallimento che non dice niente sul codice — se una pagina diventasse
# davvero lenta, 30 secondi lo segnalerebbero comunque.
APP_TEST_TIMEOUT = 30


def _run_player_detail(conn, row):
    at = AppTest.from_function(
        _render_player_detail_script, kwargs={"conn": conn, "row": row},
    )
    at.run(timeout=APP_TEST_TIMEOUT)
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


def test_render_player_detail_flags_listino_converted_price(tmp_path):
    """DA6/TASK-029: a price converted from the listino (no real-auction
    source for this player) must look visibly different from a real
    auction-credit reading, not identical."""
    conn, row = _base_player_row(tmp_path, price_basis="listino_converted")

    at = _run_player_detail(conn, row)

    labels = [m.label for m in at.metric]
    assert "Quotazione ~" in labels
    assert "Quotazione" not in labels
    conn.close()


def test_render_player_detail_does_not_flag_real_auction_price(tmp_path):
    conn, row = _base_player_row(tmp_path, price_basis="auction")

    at = _run_player_detail(conn, row)

    labels = [m.label for m in at.metric]
    assert "Quotazione" in labels
    assert "Quotazione ~" not in labels
    conn.close()


def test_render_player_detail_flags_appearances_disagreement(tmp_path):
    """DA6/TASK-029: presenze discordi tra le fonti (TASK-011) devono
    essere segnalate, non mostrate uguali a un dato su cui le fonti
    concordano."""
    conn, row = _base_player_row(tmp_path, appearances_disagreement=True)

    at = _run_player_detail(conn, row)

    labels = [m.label for m in at.metric]
    assert "Presenze ⚠️" in labels
    assert "Presenze" not in labels
    conn.close()


def test_render_player_detail_does_not_flag_agreeing_appearances(tmp_path):
    conn, row = _base_player_row(tmp_path, appearances_disagreement=False)

    at = _run_player_detail(conn, row)

    labels = [m.label for m in at.metric]
    assert "Presenze" in labels
    assert "Presenze ⚠️" not in labels
    conn.close()


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
    at.run(timeout=APP_TEST_TIMEOUT)
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


def test_goalkeeper_page_lays_out_four_cards_per_row():
    """Stessa densità delle pagine degli altri ruoli (render_role_page,
    cols_per_row = 4): due squadre per riga, ognuna con titolare e riserva."""
    teams = [{"team": t} for t in ("Inter", "Como", "Roma", "Lazio", "Milan")]

    rows = components.goalkeeper_team_rows(teams)

    assert components.GOALKEEPER_TEAMS_PER_ROW * 2 == 4
    assert [len(r) for r in rows] == [2, 2, 1]  # l'ultima riga resta spaiata
    assert [t["team"] for t in rows[0]] == ["Inter", "Como"]


def test_goalkeeper_team_rows_handles_an_empty_chart():
    assert components.goalkeeper_team_rows([]) == []


def test_goalkeeper_depth_chart_renders_both_teams_of_a_row(tmp_path):
    """Smoke test sulla pagina vera: due squadre nella stessa riga devono
    comparire entrambe, con le loro quattro card."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    for team in ("Inter", "Como"):
        _seed_goalkeeper(conn, f"Starter {team}", team, 35)
        _seed_goalkeeper(conn, f"Backup {team}", team, 20)

    at = _run_goalkeeper_depth_chart_app(conn)

    assert not at.exception
    rendered = " ".join(m.value for m in at.markdown)
    for name in ("Starter Inter", "Backup Inter", "Starter Como", "Backup Como"):
        assert name in rendered
    conn.close()


def _seed_owned_pair(conn, team, assistman_goals_assists, goleador_goals_assists):
    a_id = repository.upsert_player(conn, "Assistman", team, "C", "E", None)
    b_id = repository.upsert_player(conn, "Goleador", team, "A", "PC", None)
    for pid in (a_id, b_id):
        repository.insert_quotation(conn, pid, "fantacalcio_it", "2026-08-22", 20, 15, "ok", 6.5, 6.5, 30)
        repository.insert_quotation(conn, pid, "fantapazz", "2026-08-22", 20, 15, "ok", 6.5, 6.5, 30)
        repository.add_roster_entry(conn, pid, 15.0, "2026-08-22")
    repository.upsert_player_season_stats(conn, a_id, "fantacalciopedia", [{
        "season": "2025-26", "appearances": 30, "goals_scored": assistman_goals_assists[0],
        "assists": assistman_goals_assists[1], "yellow_cards": 0, "red_cards": 0,
    }], "2026-08-22")
    repository.upsert_player_season_stats(conn, b_id, "fantacalciopedia", [{
        "season": "2025-26", "appearances": 30, "goals_scored": goleador_goals_assists[0],
        "assists": goleador_goals_assists[1], "yellow_cards": 0, "red_cards": 0,
    }], "2026-08-22")


def test_render_correlation_section_shows_positive_pair(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_owned_pair(conn, "Inter", assistman_goals_assists=(1, 6), goleador_goals_assists=(10, 0))

    def script(conn):
        from dashboard.components import render_correlation_section
        render_correlation_section(conn)

    at = AppTest.from_function(script, kwargs={"conn": conn})
    at.run(timeout=APP_TEST_TIMEOUT)

    assert not at.exception
    assert any("Assistman" in w.value and "Goleador" in w.value for w in at.markdown)
    conn.close()


def test_render_auction_checklist_section_runs_without_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    def script(conn):
        from dashboard.components import render_auction_checklist_section
        render_auction_checklist_section(conn)

    at = AppTest.from_function(script, kwargs={"conn": conn})
    at.run(timeout=APP_TEST_TIMEOUT)

    assert not at.exception
    assert any("Fase 1" in i.value for i in at.info)
    assert any("verifica manuale" in m.value for m in at.markdown)
    conn.close()


def test_render_player_detail_shows_verdetto_section(tmp_path):
    conn, row = _base_player_row(tmp_path, tier=None, risk=20.0,
                                  value_for_money_percentile=70.0)

    at = _run_player_detail(conn, row)

    assert any("Verdetto" in m.value for m in at.markdown)
    conn.close()


def test_render_player_detail_shows_anagrafica_when_present(tmp_path, monkeypatch):
    conn, row = _base_player_row(tmp_path)
    monkeypatch.setattr(
        "dashboard.components.get_player_extra",
        lambda conn, player_id: {
            "transfermarkt_id": None,
            "anagrafica": {
                "birth_date": "2003-02-26", "height_cm": 184, "foot": "destro",
                "nationality": "Germania", "shirt_number": 10,
            },
        },
    )

    at = _run_player_detail(conn, row)

    assert any("184 cm" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_omits_anagrafica_when_absent(tmp_path, monkeypatch):
    conn, row = _base_player_row(tmp_path)
    monkeypatch.setattr(
        "dashboard.components.get_player_extra",
        lambda conn, player_id: {"transfermarkt_id": None, "anagrafica": None},
    )

    at = _run_player_detail(conn, row)

    assert not any("cm" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_shows_advanced_stats_when_present(tmp_path):
    conn, row = _base_player_row(tmp_path, advanced_stats={
        "xg90_percentile": 53, "xa90_percentile": 43, "shots90_percentile": 22,
        "key_passes90_percentile": 63, "involvement_percentile": 34, "minutes_percentile": 43,
    })

    at = _run_player_detail(conn, row)

    assert any("xG/90" in p.proto.text for p in at.get("progress"))
    conn.close()


def test_render_player_detail_omits_advanced_stats_when_absent(tmp_path):
    conn, row = _base_player_row(tmp_path, advanced_stats=None)

    at = _run_player_detail(conn, row)

    assert not at.exception
    conn.close()


def test_render_player_detail_shows_fixture_difficulty_when_present(tmp_path, monkeypatch):
    conn, row = _base_player_row(tmp_path)
    monkeypatch.setattr(
        "dashboard.components.get_fixture_difficulty",
        lambda conn, team: {"difficulty_attack": 65, "difficulty_defense": 58},
    )

    at = _run_player_detail(conn, row)

    assert any("prime 5 giornate" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_shows_fantanalisi_valuation_when_present(tmp_path):
    conn, row = _base_player_row(tmp_path, fantanalisi_valuation={
        "fair_price_range": "≤168 · ≤216", "max_bid": "264", "tier": "1", "risk": "●",
    })

    at = _run_player_detail(conn, row)

    assert any("Valutazioni Fantanalisi" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_omits_fantanalisi_valuation_when_absent(tmp_path):
    conn, row = _base_player_row(tmp_path, fantanalisi_valuation=None)

    at = _run_player_detail(conn, row)

    assert not any("Valutazioni Fantanalisi" in c.value for c in at.caption)
    conn.close()
