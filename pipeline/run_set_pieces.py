import logging
import os
from datetime import date

from db import repository
from db.connection import get_connection, init_db
from matching.player_matcher import match_name_to_player
from scrapers.fantacalcio_rigoristi import fetch_rigoristi

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "set_pieces.log")

SOURCE = "fantacalcio_it_rigoristi"


def run(conn) -> dict:
    entries = fetch_rigoristi()
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]

    today = date.today().isoformat()
    matched_rows = []
    unmatched = []

    for entry in entries:
        player = match_name_to_player(entry["player_name"], entry["team"], players)
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
