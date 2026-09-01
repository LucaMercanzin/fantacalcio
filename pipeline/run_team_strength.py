import logging
import os
from datetime import date

from db.connection import get_connection, init_db
from scrapers.fantanalisi_squadre import FantanalisiSquadreScraper, save_team_strength

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "team_strength.log")

SOURCE = "fantanalisi"


def run(conn) -> dict:
    records = FantanalisiSquadreScraper().fetch()
    today = date.today().isoformat()
    saved = save_team_strength(conn, records, source=SOURCE, scrape_date=today)
    with_data = sum(1 for r in records if r["xg"] is not None)
    return {"teams": saved, "with_understat_data": with_data}


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
    logger.info(
        "Team strength run complete: %d squadre, %d con dati Understat",
        result["teams"], result["with_understat_data"],
    )


if __name__ == "__main__":
    main()
