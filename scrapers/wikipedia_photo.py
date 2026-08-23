import requests

WIKIPEDIA_API = "https://it.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "FantacalcioDashboard/1.0 (https://github.com/LucaMercanzin/fantacalcio; "
                  "mercanzinluca05@gmail.com) python-requests"
}


def find_photo_url(player_name: str, team: str, timeout: int = 10):
    try:
        search_resp = requests.get(WIKIPEDIA_API, params={
            "action": "query",
            "list": "search",
            "srsearch": f"{player_name} calciatore {team}",
            "format": "json",
            "srlimit": 1,
        }, headers=HEADERS, timeout=timeout)
        search_resp.raise_for_status()
        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        page_id = results[0]["pageid"]

        image_resp = requests.get(WIKIPEDIA_API, params={
            "action": "query",
            "pageids": page_id,
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": 300,
            "format": "json",
        }, headers=HEADERS, timeout=timeout)
        image_resp.raise_for_status()
        pages = image_resp.json().get("query", {}).get("pages", {})
        page = pages.get(str(page_id), {})
        thumbnail = page.get("thumbnail")
        return thumbnail["source"] if thumbnail else None
    except Exception:
        return None
