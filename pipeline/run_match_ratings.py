import logging

logger = logging.getLogger(__name__)

import logging
import os
from datetime import date

from db import repository
from db.connection import get_connection, init_db
from matching.player_matcher import match_name_to_player
from scrapers.fantacalcio_voti import fetch_voti

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "match_ratings.log")

SOURCE = "fantacalcio_it_voti"


def run(conn) -> dict:
    """Stores the latest played giornata's per-match ratings. Running this
    weekly (once each new giornata is played) is what builds up the "ultime
    N partite" history over time â€” there's no way to backfill past giornate
    from this page alone, only to accumulate forward from whenever this
    pipeline starts running."""
    page = fetch_voti()
    if page["giornata"] is None or page["season"] is None:
        logger.error("Could not parse giornata/season from voti page title; aborting.")
        return {"matched": 0, "unmatched": [], "skipped_reason": "unparseable_page"}

    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]
    today = date.today().isoformat()
    matched = 0
    unmatched = []

    for entry in page["entries"]:
        player = match_name_to_player(entry["player_name"], entry["team"], players)
        if player is None:
            unmatched.append(entry)
            logger.info("No match for %s (%s)", entry["player_name"], entry["team"])
            continue
        repository.upsert_match_rating(
            conn, player["id"], page["season"], page["giornata"],
            entry["voto"], entry["fantavoto"], SOURCE, today,
        )
        matched += 1

    return {
        "matched": matched, "unmatched": unmatched,
        "giornata": page["giornata"], "season": page["season"],
    }


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
        "Match ratings run complete: giornata %s, %d matched, %d unmatched",
        result.get("giornata"), result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
