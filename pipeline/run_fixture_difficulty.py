import logging
import os
from datetime import date

from db.connection import get_connection, init_db
from scrapers.fantanalisi_calendario import (
    FantanalisiCalendarioScraper,
    save_fixture_difficulty,
)


logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "fixture_difficulty.log")

SOURCE = "fantanalisi"


def run(conn) -> dict:
    result = FantanalisiCalendarioScraper().fetch()
    today = date.today().isoformat()
    saved = save_fixture_difficulty(
        conn, result["attack"], result["defense"], source=SOURCE, scrape_date=today,
    )
    return {"teams": saved}


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
    logger.info("Fixture difficulty run complete: %d squadre", result["teams"])


if __name__ == "__main__":
    main()
