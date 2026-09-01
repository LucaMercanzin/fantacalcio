from unittest.mock import Mock, patch

import requests

from scrapers.wikipedia_photo import find_photo_url


def _mock_response(json_data):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json.return_value = json_data
    return resp


def test_find_photo_url_returns_none_when_no_search_results():
    search_resp = _mock_response({"query": {"search": []}})
    with patch("scrapers.wikipedia_photo.base.get", return_value=search_resp):
        assert find_photo_url("Nome Cognome", "Team") is None


def test_find_photo_url_returns_image_from_page():
    search_resp = _mock_response({"query": {"search": [{"pageid": 123}]}})
    image_resp = _mock_response({
        "query": {"pages": {"123": {"thumbnail": {"source": "https://example.com/p.jpg"}}}}
    })
    with patch("scrapers.wikipedia_photo.base.get", side_effect=[search_resp, image_resp]):
        assert find_photo_url("Nome Cognome", "Team") == "https://example.com/p.jpg"


def test_find_photo_url_returns_none_when_page_has_no_image():
    search_resp = _mock_response({"query": {"search": [{"pageid": 123}]}})
    image_resp = _mock_response({"query": {"pages": {"123": {}}}})
    with patch("scrapers.wikipedia_photo.base.get", side_effect=[search_resp, image_resp]):
        assert find_photo_url("Nome Cognome", "Team") is None


def test_find_photo_url_returns_none_on_request_failure():
    with patch(
        "scrapers.wikipedia_photo.base.get",
        side_effect=requests.ConnectionError("boom"),
    ):
        assert find_photo_url("Nome Cognome", "Team") is None
