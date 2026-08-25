import os
from dashboard import components


def test_photo_data_uri_resolves_windows_style_path_on_any_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(components, "PHOTOS_DIR", str(tmp_path))
    photo_file = tmp_path / "1.jpg"
    photo_file.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

    windows_style_path = r"C:\Users\merca\projects\fantacalcio\data\photos\1.jpg"
    result = components._photo_data_uri(windows_style_path)

    assert result is not None
    assert result.startswith("data:image/jpeg;base64,")


def test_photo_data_uri_resolves_posix_style_path(tmp_path, monkeypatch):
    monkeypatch.setattr(components, "PHOTOS_DIR", str(tmp_path))
    photo_file = tmp_path / "42.jpg"
    photo_file.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

    result = components._photo_data_uri("/home/adminuser/data/photos/42.jpg")

    assert result is not None


def test_photo_data_uri_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(components, "PHOTOS_DIR", str(tmp_path))

    assert components._photo_data_uri(r"C:\some\path\999.jpg") is None


def test_photo_data_uri_returns_none_for_empty_path():
    assert components._photo_data_uri(None) is None
    assert components._photo_data_uri("") is None
