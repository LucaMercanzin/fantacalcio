import logging
import os
import time
from datetime import date
from db.connection import init_db, get_connection
from db import repository
from scrapers.transfermarkt import search_player_id, fetch_player_profile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "player_anagrafica.log")

REQUEST_DELAY_SECONDS = 1.5


def run(conn) -> dict:
    cursor = conn.execute("SELECT id, canonical_name, team FROM players")
    players = [dict(row) for row in cursor.fetchall()]

    today = date.today().isoformat()
    matched = 0
    unmatched = []

    for player in players:
        player_id = player["id"]
        transfermarkt_id = repository.get_transfermarkt_id(conn, player_id)

        if transfermarkt_id is None:
            try:
                transfermarkt_id = search_player_id(player["canonical_name"], player["team"])
            except Exception as exc:
                logging.error("Search failed for %s: %s", player["canonical_name"], exc)
                unmatched.append(player["canonical_name"])
                continue
            if transfermarkt_id is None:
                logging.info("No Transfermarkt match for %s", player["canonical_name"])
                unmatched.append(player["canonical_name"])
                continue
            repository.upsert_transfermarkt_id(conn, player_id, transfermarkt_id, today)
            time.sleep(REQUEST_DELAY_SECONDS)

        try:
            profile = fetch_player_profile(transfermarkt_id)
        except Exception as exc:
            logging.error("Profile fetch failed for %s: %s", player["canonical_name"], exc)
            continue

        repository.upsert_player_anagrafica(
            conn, player_id, profile["birth_date"], profile["height_cm"],
            profile["foot"], profile["nationality"], profile["shirt_number"], today,
        )
        matched += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return {"matched": matched, "unmatched": unmatched}


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
        "Player anagrafica run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
