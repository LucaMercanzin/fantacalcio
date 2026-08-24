import logging
import os
from datetime import date
from rapidfuzz import fuzz
from db.connection import init_db, get_connection
from db import repository
from matching.player_matcher import normalize_name, normalize_team
from scrapers.fantacalcio_rigoristi import fetch_rigoristi

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "set_pieces.log")

SOURCE = "fantacalcio_it_rigoristi"
MATCH_THRESHOLD = 80


def match_entry_to_player(entry: dict, players: list):
    """Entries only carry a surname (e.g. "Scamacca"), not the fantacalcio_id
    of our own players table (that scraper doesn't capture IDs yet — see
    entity-matching notes), so match by normalized team + fuzzy name like the
    rest of the pipeline does."""
    entry_team = normalize_team(entry["team"])
    entry_name = normalize_name(entry["player_name"])

    best_player = None
    best_score = 0
    for player in players:
        if normalize_team(player["team"]) != entry_team:
            continue
        score = max(
            fuzz.ratio(entry_name, normalize_name(player["canonical_name"])),
            fuzz.partial_ratio(entry_name, normalize_name(player["canonical_name"])),
        )
        if score > best_score:
            best_score = score
            best_player = player

    if best_player and best_score >= MATCH_THRESHOLD:
        return best_player
    return None


def run(conn) -> dict:
    entries = fetch_rigoristi()
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]

    today = date.today().isoformat()
    matched_rows = []
    unmatched = []

    for entry in entries:
        player = match_entry_to_player(entry, players)
        if player is None:
            unmatched.append(entry)
            logging.info("No match for %s (%s)", entry["player_name"], entry["team"])
            continue
        matched_rows.append((player["id"], entry["category"], entry["rank"], today))

    repository.replace_player_set_pieces(conn, SOURCE, matched_rows)
    return {"matched": len(matched_rows), "unmatched": unmatched}


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    result = run(conn)
    conn.close()
    logging.info(
        "Set pieces run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
