import logging
import os
from datetime import date

from db.connection import init_db, get_connection
from db import repository
from matching.player_matcher import match_name_to_player
from scrapers.fantanalisi import FantanalisiScraper
from scrapers.fantanalisi_giocatore import FantanalisiGiocatoreScraper

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "player_advanced_stats.log")

SOURCE = "fantanalisi"


def run(conn) -> dict:
    records = FantanalisiScraper().fetch()
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]

    detail_urls_by_record = {
        record.detail_url: record for record in records if record.detail_url
    }
    percentiles_by_url = FantanalisiGiocatoreScraper().fetch_many(
        list(detail_urls_by_record.keys())
    )

    today = date.today().isoformat()
    matched = 0
    unmatched = []

    for detail_url, record in detail_urls_by_record.items():
        percentiles = percentiles_by_url.get(detail_url)
        if percentiles is None:
            logging.error("Detail fetch failed for %s", record.name)
            continue

        player = match_name_to_player(record.name, record.team, players)
        if player is None:
            unmatched.append(record.name)
            logging.info("No match for %s (%s)", record.name, record.team)
            continue

        repository.insert_player_advanced_stats(
            conn, player["id"], percentiles["xg90_percentile"],
            percentiles["xa90_percentile"], percentiles["shots90_percentile"],
            percentiles["key_passes90_percentile"], percentiles["involvement_percentile"],
            percentiles["minutes_percentile"], SOURCE, today,
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
        "Advanced stats run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
