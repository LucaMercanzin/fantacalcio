import os

import pytest

import pipeline.run_scraping as run_scraping_module
from db import repository
from db.connection import get_connection, init_db
from pipeline.run_scraping import NewPlayerSurgeError, run_pipeline
from scrapers.base import BaseScraper, PlayerRecord


class FakeScraperA(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Lautaro Martinez", team="Inter", role_classic="A", role_mantra=None,
            price_current=38, price_initial=30, status="ok", fantamedia=6.8,
            avg_rating=6.5, appearances=30, photo_url="https://example.com/l.jpg",
            source="fantacalcio_it",
        )]


class FailingScraper(BaseScraper):
    def fetch(self):
        raise RuntimeError("site is down")


class FakeScraperB(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Martinez L.", team="Inter", role_classic="A", role_mantra=None,
            price_current=37, price_initial=29, status="ok", fantamedia=None,
            avg_rating=6.7, appearances=None, photo_url=None,
            source="gazzetta",
        )]


class FakeScraperWithMantra(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Martinez L.", team="Inter", role_classic="A", role_mantra=None,
            price_current=37, price_initial=29, status="ok", fantamedia=None,
            avg_rating=6.7, appearances=None, photo_url=None,
            source="gazzetta",
        )]


class FakeScraperMantraSource(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Lautaro Martinez", team="Inter", role_classic="A", role_mantra="PC",
            price_current=38, price_initial=30, status="ok", fantamedia=6.8,
            avg_rating=6.5, appearances=30, photo_url=None,
            source="fantacalcio_it",
        )]


def test_run_pipeline_merges_sources_and_survives_failures(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    photos_dir = str(tmp_path / "photos")

    run_pipeline(
        scrapers=[FakeScraperA(), FailingScraper(), FakeScraperB()],
        conn=conn,
        photos_dir=photos_dir,
        scrape_date="2026-08-22",
    )

    latest = repository.get_latest_quotations(conn, role_classic="A")
    sources = {row["source"] for row in latest}

    assert sources == {"fantacalcio_it", "gazzetta"}
    assert len({row["player_id"] for row in latest}) == 1

    player_id = latest[0]["player_id"]
    matches = repository.get_low_confidence_matches(conn, threshold=100.0)
    gazzetta_match = next(m for m in matches if m["source"] == "gazzetta")
    assert gazzetta_match["player_id"] == player_id
    assert gazzetta_match["source_name"] == "Martinez L."
    assert gazzetta_match["confidence"] < 100.0
    assert not any(m["source"] == "fantacalcio_it" for m in matches)
    conn.close()


def test_run_pipeline_keeps_role_mantra_even_when_first_source_lacks_it(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FakeScraperWithMantra(), FakeScraperMantraSource()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    row = conn.execute("SELECT role_mantra FROM players").fetchone()
    assert row["role_mantra"] == "PC"
    conn.close()


class FakeScraperManyNewPlayers(BaseScraper):
    def fetch(self):
        return [
            PlayerRecord(
                name=f"New Player {chr(65 + i)}", team="Inter", role_classic="A",
                role_mantra=None, price_current=10, price_initial=10, status="ok",
                fantamedia=6.0, avg_rating=6.0, appearances=20, photo_url=None,
                source="fantacalcio_it",
            )
            for i in range(3)
        ]


def test_run_pipeline_raises_on_new_player_surge(tmp_path):
    """TASK-007/P0-007 point 5: a run adding far more "new" players than the
    existing total is almost always a dropped source changing which name won
    the match, not a real transfer wave — it should stop with an error
    instead of silently accepting the surge."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    # 1 existing player; the run below adds 3 new ones (300% > the 5%
    # threshold, whatever the previous total).
    repository.upsert_player(conn, "Existing Player", "Roma", "A", None, None)

    with pytest.raises(NewPlayerSurgeError):
        run_pipeline(
            scrapers=[FakeScraperManyNewPlayers()],
            conn=conn,
            photos_dir=str(tmp_path / "photos"),
            scrape_date="2026-08-22",
            skip_photos=True,
        )
    conn.close()


class FakeScraperRoleA(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Nico Gonzalez", team="Roma", role_classic="A", role_mantra=None,
            price_current=20, price_initial=18, status="ok", fantamedia=6.2,
            avg_rating=6.0, appearances=25, photo_url=None,
            source="fantacalcio_it",
        )]


class FakeScraperRoleAAgain(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Nico Gonzalez", team="Roma", role_classic="A", role_mantra=None,
            price_current=19, price_initial=18, status="ok", fantamedia=6.1,
            avg_rating=6.0, appearances=24, photo_url=None,
            source="fantapazz",
        )]


class FakeScraperRoleC(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Nico Gonzalez", team="Roma", role_classic="C", role_mantra=None,
            price_current=15, price_initial=14, status="ok", fantamedia=6.0,
            avg_rating=5.9, appearances=26, photo_url=None,
            source="pianetafanta",
        )]


def test_run_pipeline_picks_role_classic_by_weighted_majority_not_first_source(tmp_path):
    """P1-007/TASK-011: two sources agreeing on "A" must outvote a single
    disagreeing source on "C", even though "C" is the first source fetched
    (fake scraper order below puts FakeScraperRoleC first)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FakeScraperRoleC(), FakeScraperRoleA(), FakeScraperRoleAAgain()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    row = conn.execute("SELECT role_classic FROM players").fetchone()
    assert row["role_classic"] == "A"
    conn.close()


def test_run_pipeline_role_classic_tie_break_is_deterministic(tmp_path):
    """Equal weight on both sides: the alphabetically-first role code wins,
    so re-running the same input always produces the same result."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FakeScraperRoleC(), FakeScraperRoleA()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    row = conn.execute("SELECT role_classic FROM players").fetchone()
    assert row["role_classic"] == "A"
    conn.close()


def test_run_pipeline_logs_warning_on_role_classic_disagreement(tmp_path, caplog):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    with caplog.at_level("WARNING"):
        run_pipeline(
            scrapers=[FakeScraperRoleC(), FakeScraperRoleA(), FakeScraperRoleAAgain()],
            conn=conn,
            photos_dir=str(tmp_path / "photos"),
            scrape_date="2026-08-22",
            skip_photos=True,
        )

    assert any("disaccordo sul ruolo" in message for message in caplog.messages)
    conn.close()


class FakeScraperNoPhoto(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Existing Keeper", team="Roma", role_classic="P", role_mantra=None,
            price_current=10, price_initial=10, status="ok", fantamedia=6.0,
            avg_rating=6.0, appearances=20, photo_url=None,
            source="fantacalcio_it",
        )]


def test_run_pipeline_skips_photo_lookup_when_local_file_already_exists(tmp_path, monkeypatch):
    """TASK-027/S5: find_photo_url used to run for every player without a
    scraper-provided photo_url on every single run — even players already
    photographed from a previous run."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    photos_dir = str(tmp_path / "photos")
    os.makedirs(photos_dir)

    player_id = repository.upsert_player(conn, "Existing Keeper", "Roma", "P", None, None)
    with open(os.path.join(photos_dir, f"{player_id}.jpg"), "wb") as f:
        f.write(b"fake-jpeg-bytes")

    lookup_calls = []
    sleep_calls = []
    monkeypatch.setattr(
        run_scraping_module, "find_photo_url",
        lambda name, team: lookup_calls.append((name, team)),
    )
    monkeypatch.setattr(run_scraping_module.time, "sleep", lambda s: sleep_calls.append(s))

    run_pipeline(
        scrapers=[FakeScraperNoPhoto()],
        conn=conn,
        photos_dir=photos_dir,
        scrape_date="2026-08-27",
    )

    assert lookup_calls == []
    assert sleep_calls == []  # no lookup happened, so nothing to throttle
    row = conn.execute("SELECT photo_path FROM players WHERE id = ?", (player_id,)).fetchone()
    assert row["photo_path"] == os.path.join(photos_dir, f"{player_id}.jpg")
    conn.close()


def test_run_pipeline_throttles_before_a_real_photo_lookup(tmp_path, monkeypatch):
    """TASK-027/S5: a genuine lookup (new player, no local file yet) must
    still be spaced out — no rate limiting existed before this."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    sleep_calls = []
    monkeypatch.setattr(run_scraping_module, "find_photo_url", lambda name, team: None)
    monkeypatch.setattr(run_scraping_module.time, "sleep", lambda s: sleep_calls.append(s))

    run_pipeline(
        scrapers=[FakeScraperNoPhoto()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-27",
    )

    assert sleep_calls == [run_scraping_module.PHOTO_LOOKUP_THROTTLE_SECONDS]
    conn.close()


def test_run_pipeline_does_not_raise_for_a_reasonable_new_player_count(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    for i in range(100):
        # Two-letter suffix, not a digit: identity_key normalizes on letters
        # only, so a digit suffix would collapse most of these 100 names
        # into a handful of distinct identity_key values (TASK-007/P0-007).
        suffix = chr(65 + i // 26) + chr(65 + i % 26)
        repository.upsert_player(conn, f"Existing Player {suffix}", "Roma", "A", None, None)

    # 3 new players out of 100 existing (3%) stays under the 5% threshold.
    run_pipeline(
        scrapers=[FakeScraperManyNewPlayers()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )
    conn.close()


class FakeScraperInvalidTeam(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Foreign Player", team="Estero", role_classic="A", role_mantra=None,
            price_current=20, price_initial=18, status="ok", fantamedia=6.5,
            avg_rating=6.3, appearances=30, photo_url=None,
            source="fantacalcio_it",
        )]


class FakeScraperOutOfRangeFantamedia(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Existing Keeper", team="Roma", role_classic="P", role_mantra=None,
            price_current=15, price_initial=14, status="ok", fantamedia=99.0,
            avg_rating=6.3, appearances=30, photo_url=None,
            source="fantacalcio_it",
        )]


def test_run_pipeline_discards_records_for_a_team_not_in_the_current_season(tmp_path):
    """TASK-005/S7: a scraper reporting a foreign/lower-league team (or a
    typo'd one) used to sail straight into quotations — validate_record
    checks it against repository.get_current_season_team_codes first."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FakeScraperInvalidTeam()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    assert repository.count_players(conn) == 0
    conn.close()


def test_run_pipeline_clears_out_of_range_fantamedia_but_keeps_the_player(tmp_path):
    """P0-003: an implausible fantamedia (99.0) is cleared, not written
    straight into quotations — but a valid team/role means the rest of the
    record still gets stored."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FakeScraperOutOfRangeFantamedia()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    assert repository.count_players(conn) == 1
    row = conn.execute("SELECT fantamedia FROM quotations").fetchone()
    assert row["fantamedia"] is None
    conn.close()


class FakeScraperTwoPlayers(BaseScraper):
    def fetch(self):
        return [
            PlayerRecord(
                name="Player One", team="Inter", role_classic="A", role_mantra=None,
                price_current=20, price_initial=18, status="ok", fantamedia=6.5,
                avg_rating=6.3, appearances=30, photo_url=None, source="fantacalcio_it",
            ),
            PlayerRecord(
                name="Player Two", team="Roma", role_classic="A", role_mantra=None,
                price_current=15, price_initial=14, status="ok", fantamedia=6.0,
                avg_rating=6.0, appearances=25, photo_url=None, source="fantacalcio_it",
            ),
        ]


def test_run_pipeline_writes_nothing_on_a_crash_partway_through(tmp_path, monkeypatch):
    """TASK-006 points 3-4: the whole run is one transaction — a failure
    partway through (simulated here on the second player's quotation
    insert) must roll back everything, including the first player's
    already-processed writes, not leave a partial dataset."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    real_insert_quotation = repository.insert_quotation
    call_count = {"n": 0}

    def failing_insert_quotation(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated crash mid-run")
        return real_insert_quotation(*args, **kwargs)

    monkeypatch.setattr(repository, "insert_quotation", failing_insert_quotation)

    with pytest.raises(RuntimeError, match="simulated crash mid-run"):
        run_pipeline(
            scrapers=[FakeScraperTwoPlayers()],
            conn=conn,
            photos_dir=str(tmp_path / "photos"),
            scrape_date="2026-08-22",
            skip_photos=True,
        )

    assert repository.count_players(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM quotations").fetchone()[0] == 0
    run = conn.execute("SELECT status FROM scraping_runs").fetchone()
    assert run["status"] == "failed"
    conn.close()


def test_run_pipeline_records_a_successful_scraping_run(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FakeScraperTwoPlayers()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    run = conn.execute("SELECT * FROM scraping_runs").fetchone()
    assert run["status"] == "ok"
    assert run["sources_ok"] == 1
    assert run["sources_failed"] == 0
    assert run["records_written"] == 2
    assert run["started_at"] is not None
    assert run["finished_at"] is not None
    conn.close()


def test_run_pipeline_records_a_failed_source_in_the_scraping_run(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FailingScraper(), FakeScraperTwoPlayers()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    run = conn.execute("SELECT * FROM scraping_runs").fetchone()
    assert run["status"] == "ok"
    assert run["sources_ok"] == 1
    assert run["sources_failed"] == 1
    conn.close()


def test_run_pipeline_twice_leaves_the_same_row_counts(tmp_path):
    """Acceptance criteria: two consecutive runs on the same input leave
    the DB identical — the ON CONFLICT upserts (TASK-006 points 1-2) mean
    a re-run updates existing rows in place instead of duplicating them."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    for _ in range(2):
        run_pipeline(
            scrapers=[FakeScraperTwoPlayers()],
            conn=conn,
            photos_dir=str(tmp_path / "photos"),
            scrape_date="2026-08-22",
            skip_photos=True,
        )

    assert repository.count_players(conn) == 2
    assert conn.execute("SELECT COUNT(*) FROM quotations").fetchone()[0] == 2
    conn.close()
