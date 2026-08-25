import logging
import os
import time
from rapidfuzz import fuzz
from db.connection import init_db, get_connection
from db import repository
from matching.player_matcher import (
    match_name_to_player, match_name_to_player_any_team, normalize_name,
)
from scrapers.fantacalcio_it import fetch_season_prices

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "historical_prices.log")

SOURCE = "fantacalcio_it_storico"
REQUEST_DELAY_SECONDS = 1.5

# One archived season snapshot per year is enough for a meaningful "andamento
# quotazione negli anni" trend without hammering the site — extend this list
# manually if more history is wanted later (the site archives back to
# 2015/16).
DEFAULT_SEASONS = ["2025/26", "2024/25", "2023/24", "2022/23", "2021/22"]


def _season_start_date(season: str) -> str:
    start_year = season.split("/")[0]
    return f"{start_year}-08-01"


def _match_score(record_name: str, canonical_name: str) -> float:
    a, b = normalize_name(record_name), normalize_name(canonical_name)
    return max(fuzz.ratio(a, b), fuzz.partial_ratio(a, b))


def run(conn, seasons: list = None) -> dict:
    seasons = seasons if seasons is not None else DEFAULT_SEASONS
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]

    results = {}
    for season in seasons:
        try:
            records = fetch_season_prices(season)
        except Exception as exc:
            logging.error("Fetch failed for season %s: %s", season, exc)
            results[season] = {"matched": 0, "unmatched": 0, "error": str(exc)}
            continue

        scrape_date = _season_start_date(season)
        repository.clear_quotations_for_source_and_date(conn, SOURCE, scrape_date)

        # Multiple source records can legitimately match the same one of our
        # players (e.g. two teammates sharing a surname, like "Martinez L."
        # and "Martinez Jo." both fuzzy-matching "Lautaro Martinez" against a
        # thin same-team candidate pool) — keep only the best-scoring record
        # per player instead of overwriting silently in scrape order.
        best_per_player: dict = {}
        unmatched = 0
        for record in records:
            player = match_name_to_player(record.name, record.team, players)
            if player is None:
                player = match_name_to_player_any_team(record.name, players)
            if player is None:
                unmatched += 1
                continue
            score = _match_score(record.name, player["canonical_name"])
            existing = best_per_player.get(player["id"])
            if existing is not None:
                unmatched += 1  # one of the two candidates is always discarded
            if existing is None or score > existing[0]:
                best_per_player[player["id"]] = (score, record)

        for player_id, (score, record) in best_per_player.items():
            repository.insert_quotation(
                conn, player_id, SOURCE, scrape_date,
                record.price_current, record.price_initial, record.status,
                record.fantamedia, record.avg_rating, record.appearances,
            )

        matched = len(best_per_player)
        results[season] = {"matched": matched, "unmatched": unmatched}
        logging.info("Season %s: %d matched, %d unmatched", season, matched, unmatched)
        time.sleep(REQUEST_DELAY_SECONDS)

    return results


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
    logging.info("Historical prices run complete")


if __name__ == "__main__":
    main()
