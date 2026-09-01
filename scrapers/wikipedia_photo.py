import logging

import requests

from scrapers import base

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://it.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "FantacalcioDashboard/1.0 (https://github.com/LucaMercanzin/fantacalcio; "
                  "mercanzinluca05@gmail.com) python-requests"
}


def find_photo_url(player_name: str, team: str, timeout: int = 10):
    try:
        search_resp = base.get(WIKIPEDIA_API, params={
            "action": "query",
            "list": "search",
            "srsearch": f"{player_name} calciatore {team}",
            "format": "json",
            "srlimit": 1,
        }, headers=HEADERS, timeout=timeout)
        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        page_id = results[0]["pageid"]

        image_resp = base.get(WIKIPEDIA_API, params={
            "action": "query",
            "pageids": page_id,
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": 300,
            "format": "json",
        }, headers=HEADERS, timeout=timeout)
        pages = image_resp.json().get("query", {}).get("pages", {})
        page = pages.get(str(page_id), {})
        thumbnail = page.get("thumbnail")
        return thumbnail["source"] if thumbnail else None
    except (KeyError, TypeError, ValueError, requests.RequestException) as exc:
        logger.warning("Wikipedia photo lookup failed for %s: %s", player_name, exc)
        return None
