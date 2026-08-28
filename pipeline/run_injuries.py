import logging

logger = logging.getLogger(__name__)

import logging
import os
import time
from datetime import date

from db import repository
from db.connection import get_connection, init_db
from scrapers.transfermarkt import fetch_injuries, search_player_id

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "injuries.log")

REQUEST_DELAY_SECONDS = 1.5


def run(conn) -> None:
    cursor = conn.execute("SELECT id, canonical_name, team FROM players")
    players = [dict(row) for row in cursor.fetchall()]

    for player in players:
        player_id = player["id"]
        transfermarkt_id = repository.get_transfermarkt_id(conn, player_id)

        if transfermarkt_id is None:
            try:
                transfermarkt_id = search_player_id(player["canonical_name"], player["team"])
            except Exception as exc:
                logger.error("Search failed for %s: %s", player["canonical_name"], exc)
                continue
            if transfermarkt_id is None:
                logger.info("No Transfermarkt match for %s", player["canonical_name"])
                continue
            repository.upsert_transfermarkt_id(
                conn, player_id, transfermarkt_id, date.today().isoformat(),
            )
            time.sleep(REQUEST_DELAY_SECONDS)

        try:
            injuries = fetch_injuries(transfermarkt_id)
        except Exception as exc:
            logger.error("Injuries fetch failed for %s: %s", player["canonical_name"], exc)
            continue

        repository.replace_player_injuries(conn, player_id, injuries)
        time.sleep(REQUEST_DELAY_SECONDS)


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    run(conn)
    conn.close()
    logger.info("Injuries run complete")


if __name__ == "__main__":
    main()
