from unittest.mock import Mock, patch

import requests

from scrapers.photo_downloader import download_photo


def test_download_photo_returns_none_when_no_url(tmp_path):
    result = download_photo(None, player_id=1, photos_dir=str(tmp_path))
    assert result is None


def test_download_photo_saves_file_and_returns_path(tmp_path):
    fake_response = Mock()
    fake_response.content = b"fake-image-bytes"
    fake_response.raise_for_status = Mock()

    with patch("scrapers.photo_downloader.base.get", return_value=fake_response):
        result = download_photo(
            "https://example.com/photo.png", player_id=42, photos_dir=str(tmp_path)
        )

    assert result == str(tmp_path / "42.jpg")
    with open(result, "rb") as f:
        assert f.read() == b"fake-image-bytes"


def test_download_photo_returns_none_on_request_failure(tmp_path):
    with patch(
        "scrapers.photo_downloader.base.get",
        side_effect=requests.ConnectionError("boom"),
    ):
        result = download_photo(
            "https://example.com/photo.png", player_id=42, photos_dir=str(tmp_path)
        )

    assert result is None
