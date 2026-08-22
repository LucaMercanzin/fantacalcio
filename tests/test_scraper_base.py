import pytest
from scrapers.base import BaseScraper, PlayerRecord


def test_player_record_holds_expected_fields():
    record = PlayerRecord(
        name="Lautaro Martinez", team="Inter", role_classic="A", role_mantra="Pu",
        price_current=38, price_initial=30, status="ok", fantamedia=6.8,
        avg_rating=6.5, appearances=30, photo_url="http://example.com/p.jpg",
        source="fantacalcio_it",
    )
    assert record.name == "Lautaro Martinez"
    assert record.source == "fantacalcio_it"


def test_base_scraper_fetch_is_abstract():
    class IncompleteScraper(BaseScraper):
        pass

    with pytest.raises(TypeError):
        IncompleteScraper()
