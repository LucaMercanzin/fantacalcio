from scrapers import transfermarkt
from scrapers.transfermarkt import fetch_photo_url


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_fetch_photo_url_extracts_og_image(monkeypatch):
    html = (
        '<html><head>'
        '<meta property="og:image" content="https://img.a.transfermarkt.technology/'
        'portrait/big/406625-1695024988.jpg?lm=4711" />'
        '</head></html>'
    )
    monkeypatch.setattr(
        transfermarkt.base, "get", lambda *a, **k: _FakeResponse(html)
    )

    url = fetch_photo_url(406625)

    assert url == "https://img.a.transfermarkt.technology/portrait/big/406625-1695024988.jpg?lm=4711"


def test_fetch_photo_url_none_when_missing(monkeypatch):
    monkeypatch.setattr(
        transfermarkt.base, "get", lambda *a, **k: _FakeResponse("<html></html>")
    )

    assert fetch_photo_url(123) is None
