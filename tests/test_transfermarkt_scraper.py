import os

from scrapers.transfermarkt import (
    parse_injuries,
    parse_player_profile,
    search_player_id,
)

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
        "scrapers.transfermarkt.base.get", lambda *a, **k: FakeResponse()
    )

    player_id = search_player_id("Donyell Malen")
    assert player_id == 326029


def test_search_player_id_uses_surname_only_for_canonical_name_order(monkeypatch):
    """Il sito non trova nulla per 'Cognome Nome' per intero (ordine dei
    nostri canonical_name), ma trova risultati per il solo cognome — la
    query deve provare prima il cognome, non l'intera stringa."""
    html = _read_fixture("transfermarkt_search_sample.html")
    empty_html = "<html><body>nessun risultato</body></html>"
    queries_seen = []

    class FakeResponse:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass

    def fake_get(url, params=None, **kwargs):
        query = params["query"]
        queries_seen.append(query)
        # Full "Cognome Nome" string returns nothing; surname alone works.
        return FakeResponse(empty_html if query == "Malen Donyell" else html)

    monkeypatch.setattr("scrapers.transfermarkt.base.get", fake_get)

    player_id = search_player_id("Malen Donyell")

    assert player_id == 326029
    assert queries_seen[0] == "Malen"


def test_parse_player_profile_extracts_anagrafica():
    html = _read_fixture("transfermarkt_profile_sample.html")

    profile = parse_player_profile(html)

    assert profile["birth_date"] == "2003-02-26"
    assert profile["height_cm"] == 184
    assert profile["foot"] == "destro"
    assert profile["nationality"] == "Germania"
    assert profile["shirt_number"] == 10


def test_parse_player_profile_handles_missing_fields_gracefully():
    profile = parse_player_profile("<html><body>Pagina senza profilo</body></html>")

    assert profile == {
        "birth_date": None, "height_cm": None, "foot": None,
        "nationality": None, "shirt_number": None,
    }
