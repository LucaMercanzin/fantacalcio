import logging
import os
from datetime import date

from db import repository
from db.connection import get_connection, init_db
from matching.player_matcher import match_name_to_player
from scrapers.fantanalisi import FantanalisiScraper

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "fantanalisi_valuations.log")

SOURCE = "fantanalisi"


def run(conn) -> dict:
    records = FantanalisiScraper().fetch()
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]

    today = date.today().isoformat()
    matched = 0
    unmatched = []

    for record in records:
        player = match_name_to_player(record.name, record.team, players)
        if player is None:
            unmatched.append(record.name)
            logging.info("No match for %s (%s)", record.name, record.team)
            continue

        repository.insert_player_fantanalisi_valuation(
            conn, player["id"], record.fair_price_range, record.max_bid,
            record.tier_fantanalisi, record.risk_fantanalisi, SOURCE, today,
        )
        matched += 1

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
        "Fantanalisi valuations run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
