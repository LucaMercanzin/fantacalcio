import os
from scrapers.transfermarkt import parse_injuries, search_player_id

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def test_parse_injuries_extracts_records():
    html = _read_fixture("transfermarkt_injuries_sample.html")

    records = parse_injuries(html)

    assert len(records) >= 10
    first = records[0]
    assert first["season"] == "24/25"
    assert first["injury_type"] == "Malato"
    assert first["date_from"] == "26/02/2025"
    assert first["date_to"] == "03/03/2025"
    assert first["days_out"] == 6
    assert first["matches_missed"] == 1


def test_parse_injuries_handles_missing_table():
    assert parse_injuries("<html><body>no table here</body></html>") == []


def test_search_player_id_finds_match(monkeypatch):
    html = _read_fixture("transfermarkt_search_sample.html")

    class FakeResponse:
        text = html
        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "scrapers.transfermarkt.requests.get", lambda *a, **k: FakeResponse()
    )

    player_id = search_player_id("Donyell Malen")
    assert player_id == 326029
