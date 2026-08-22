import logging
import os
from datetime import date
from db.connection import init_db, get_connection
from scrapers.fantacalcio_it import FantacalcioItScraper
from scrapers.gazzetta import GazzettaScraper
from pipeline.run_scraping import run_pipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
PHOTOS_DIR = os.path.join(BASE_DIR, "data", "photos")
LOG_PATH = os.path.join(BASE_DIR, "data", "scraping.log")


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    scrapers = [FantacalcioItScraper(), GazzettaScraper()]
    run_pipeline(scrapers, conn, PHOTOS_DIR, date.today().isoformat())
    conn.close()
    logging.info("Scraping run complete")


if __name__ == "__main__":
    main()
