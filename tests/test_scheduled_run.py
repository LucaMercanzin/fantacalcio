from datetime import date

import pytest

from db import repository
from db.connection import get_connection, init_db
from pipeline import scheduled_run
from pipeline.scheduled_run import Job, is_due, run_jobs, select_jobs


def _conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return get_connection(db_path)


def test_every_orphan_runner_is_registered():
    """Il motivo per cui sette tabelle erano a zero righe è che nessuno
    chiamava i loro runner (BACKLOG-2026-08-31 §5). Questo test è la guardia
    contro la ricomparsa dello stesso buco: un runner nuovo in pipeline/ che
    non entra in JOBS fa fallire la suite."""
    registered = {job.run.__module__ for job in scheduled_run.JOBS}
    assert registered == {
        "pipeline.scheduled_run",  # _run_quotations
        "pipeline.run_match_ratings",
        "pipeline.run_injuries",
        "pipeline.run_set_pieces",
        "pipeline.run_fantanalisi_valuations",
        "pipeline.run_player_advanced_stats",
        "pipeline.run_fixture_difficulty",
        "pipeline.run_team_strength",
        "pipeline.run_fcp_metrics",
        "pipeline.run_photos_transfermarkt",
        "pipeline.run_player_anagrafica",
        "pipeline.run_historical_prices",
    }


def test_quotations_run_first():
    """Ogni altro job si aggancia ai player_id creati dalle quotazioni."""
    assert scheduled_run.JOBS[0].name == "quotations"


def test_job_never_run_is_due():
    job = Job("x", 7, lambda conn: None, "")
    assert is_due(job, None, date(2026, 8, 31)) is True


def test_job_is_due_only_after_cadence_elapsed():
    job = Job("x", 7, lambda conn: None, "")
    assert is_due(job, "2026-08-25T03:00:00+02:00", date(2026, 8, 31)) is False
    assert is_due(job, "2026-08-24T03:00:00+02:00", date(2026, 8, 31)) is True


def test_only_still_respects_cadence_unless_forced():
    runs = {"injuries": {"last_success_at": "2026-08-31T03:00:00+02:00"}}
    today = date(2026, 8, 31)
    assert select_jobs(["injuries"], False, runs, today) == []
    forced = select_jobs(["injuries"], True, runs, today)
    assert [job.name for job, _ in forced] == ["injuries"]


def test_a_failing_job_does_not_stop_the_others(tmp_path):
    conn = _conn(tmp_path)
    calls = []

    def boom(conn):
        raise RuntimeError("Transfermarkt 503")

    def fine(conn):
        calls.append("fine")
        return {"written": 3}

    summary = run_jobs(conn, [
        (Job("boom", 1, boom, ""), "test"),
        (Job("fine", 1, fine, ""), "test"),
    ])

    assert calls == ["fine"]
    assert summary == {"ok": 1, "failed": 1}
    conn.close()


def test_failed_job_keeps_previous_success_and_stays_due(tmp_path):
    """Un job che fallisce non deve consumare la cadenza: altrimenti un
    errore di rete lo mette a tacere per tutta la finestra successiva."""
    conn = _conn(tmp_path)
    job = Job("flaky", 1, None, "")

    repository.record_pipeline_job_run(
        conn, "flaky", "2026-08-30T03:00:00+02:00", "ok",
        success_at="2026-08-30T03:05:00+02:00",
    )

    def boom(conn):
        raise RuntimeError("giù")

    run_jobs(conn, [(Job("flaky", 1, boom, ""), "test")])

    stored = repository.get_pipeline_job_runs(conn)["flaky"]
    assert stored["last_status"] == "failed"
    assert stored["last_success_at"] == "2026-08-30T03:05:00+02:00"
    assert is_due(job, stored["last_success_at"], date(2026, 8, 31)) is True
    conn.close()


def test_successful_job_records_success_and_becomes_not_due(tmp_path):
    conn = _conn(tmp_path)
    run_jobs(conn, [(Job("ok_job", 7, lambda conn: {"n": 1}, ""), "test")])

    stored = repository.get_pipeline_job_runs(conn)["ok_job"]
    assert stored["last_status"] == "ok"
    assert stored["last_detail"] == "{'n': 1}"
    assert is_due(Job("ok_job", 7, None, ""), stored["last_success_at"], date.today()) is False
    conn.close()


def test_only_rejects_an_unknown_job_name():
    with pytest.raises(SystemExit):
        scheduled_run._parse_args(["--only", "non-esiste"])


def test_a_job_left_running_by_a_dead_process_is_swept_at_startup(tmp_path):
    """`scheduled_run.py` è l'unico punto di ingresso e non gira in due
    istanze: se questo processo sta partendo adesso, nessun job di un
    processo precedente può essere ancora in corso. Senza questa pulizia un
    job ucciso resta 'running' per sempre — è successo due volte in un
    giorno (player_advanced_stats e injuries, 01/09/2026)."""
    conn = _conn(tmp_path)
    repository.record_pipeline_job_run(
        conn, "injuries", "2026-09-01T09:00:00+02:00", "running",
    )
    job_runs = repository.get_pipeline_job_runs(conn)

    assert scheduled_run.sweep_interrupted(conn, job_runs) == ["injuries"]

    stored = repository.get_pipeline_job_runs(conn)["injuries"]
    assert stored["last_status"] == "interrotto"
    # e l'istante di avvio resta, perché è l'unica traccia di quando è morto
    assert stored["last_started_at"] == "2026-09-01T09:00:00+02:00"
    conn.close()


def test_the_sweep_leaves_finished_jobs_alone(tmp_path):
    conn = _conn(tmp_path)
    repository.record_pipeline_job_run(
        conn, "set_pieces", "2026-09-01T09:00:00+02:00", "ok",
        success_at="2026-09-01T09:01:00+02:00",
    )
    job_runs = repository.get_pipeline_job_runs(conn)

    assert scheduled_run.sweep_interrupted(conn, job_runs) == []
    assert repository.get_pipeline_job_runs(conn)["set_pieces"]["last_status"] == "ok"
    conn.close()


def test_a_swept_job_is_still_due(tmp_path):
    """La pulizia dello stato non deve toccare la cadenza: un job ucciso non
    ha prodotto un successo, quindi resta da rifare."""
    conn = _conn(tmp_path)
    repository.record_pipeline_job_run(
        conn, "injuries", "2026-09-01T09:00:00+02:00", "running",
    )
    job_runs = repository.get_pipeline_job_runs(conn)
    scheduled_run.sweep_interrupted(conn, job_runs)

    due = [job.name for job, _ in select_jobs(None, False, job_runs, date(2026, 9, 1))]
    assert "injuries" in due
    conn.close()
