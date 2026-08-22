from db.connection import init_db, get_connection
from db import repository
from scrapers.base import BaseScraper, PlayerRecord
from pipeline.run_scraping import run_pipeline


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
            name="Lautaro", team="Inter", role_classic="A", role_mantra=None,
            price_current=37, price_initial=29, status="ok", fantamedia=None,
            avg_rating=6.7, appearances=None, photo_url=None,
            source="gazzetta",
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
    conn.close()
