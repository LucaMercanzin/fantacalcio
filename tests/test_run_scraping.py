import pytest

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
