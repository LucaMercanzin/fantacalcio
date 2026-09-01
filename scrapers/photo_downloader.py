import logging
import os

import requests

from scrapers import base

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "FantacalcioDashboard/1.0 (https://github.com/LucaMercanzin/fantacalcio; "
                  "mercanzinluca05@gmail.com) python-requests"
}


def download_photo(photo_url, player_id: int, photos_dir: str):
    if not photo_url:
        return None

    os.makedirs(photos_dir, exist_ok=True)
    dest_path = os.path.join(photos_dir, f"{player_id}.jpg")

    try:
        response = base.get(photo_url, headers=HEADERS, timeout=15)
        with open(dest_path, "wb") as f:
            f.write(response.content)
        return dest_path
    except (OSError, requests.RequestException) as exc:
        logger.warning("Photo download failed for player %s: %s", player_id, exc)
        return None
