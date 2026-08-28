import logging
import os
import time
from datetime import date

from db import repository
from db.connection import get_connection, init_db
from scrapers.photo_downloader import download_photo
from scrapers.transfermarkt import fetch_photo_url, search_player_id

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
PHOTOS_DIR = os.path.join(BASE_DIR, "data", "photos")
LOG_PATH = os.path.join(BASE_DIR, "data", "photos_transfermarkt.log")

REQUEST_DELAY_SECONDS = 1.0

# Wikipedia's free-text search misses a lot of squad players outright, so
# most of the roster is stuck with an initial-letter placeholder. Transfermarkt
# covers essentially every professional footballer and returns a portrait for
# almost all of them — used here specifically to backfill the *important*
# half of the player pool (by real-auction price) that a user would actually
# recognize by photo during an auction.
TOP_FRACTION = 0.5


def _players_needing_photos(conn) -> list:
    """Top TOP_FRACTION of all players by current consensus price, still
    missing a photo — cheapest way to get 'photos for the players people
    actually care about' without touching all ~800 rows."""
    from dashboard.data_access import (
        get_ranked_role,
    )

    all_rows = []
    for role in ("P", "D", "C", "A"):
        all_rows.extend(get_ranked_role(conn, role))

    all_rows.sort(key=lambda r: r.get("price_current") or 0, reverse=True)
    cutoff = max(1, int(len(all_rows) * TOP_FRACTION))
    top_half = all_rows[:cutoff]

    return [r for r in top_half if not r.get("photo_path")]


def run(conn, photos_dir: str = PHOTOS_DIR) -> dict:
    targets = _players_needing_photos(conn)
    downloaded, skipped = 0, 0

    for row in targets:
        player_id = row["player_id"]
        transfermarkt_id = repository.get_transfermarkt_id(conn, player_id)

        if transfermarkt_id is None:
            try:
                transfermarkt_id = search_player_id(row["canonical_name"], row["team"])
            except Exception as exc:
                logging.error("Search failed for %s: %s", row["canonical_name"], exc)
                skipped += 1
                continue
            if transfermarkt_id is None:
                logging.info("No Transfermarkt match for %s", row["canonical_name"])
                skipped += 1
                continue
            repository.upsert_transfermarkt_id(
                conn, player_id, transfermarkt_id, date.today().isoformat(),
            )
            time.sleep(REQUEST_DELAY_SECONDS)

        try:
            photo_url = fetch_photo_url(transfermarkt_id)
        except Exception as exc:
            logging.error("Photo fetch failed for %s: %s", row["canonical_name"], exc)
            skipped += 1
            continue

        local_path = download_photo(photo_url, player_id, photos_dir)
        if local_path:
            repository.upsert_player(
                conn, row["canonical_name"], row["team"], row["role_classic"],
                row.get("role_mantra"), local_path,
            )
            downloaded += 1
            logging.info("Photo saved for %s", row["canonical_name"])
        else:
            skipped += 1

        time.sleep(REQUEST_DELAY_SECONDS)

    return {"targets": len(targets), "downloaded": downloaded, "skipped": skipped}


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
        "Transfermarkt photos run complete: %d/%d downloaded (%d skipped)",
        result["downloaded"], result["targets"], result["skipped"],
    )


if __name__ == "__main__":
    main()
