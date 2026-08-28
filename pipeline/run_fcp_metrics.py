import logging
import os
import time
from datetime import date

from db import repository
from db.connection import get_connection, init_db
from matching.player_matcher import match_name_to_player
from scrapers.fantacalciopedia import FantaCalciopediaScraper, fetch_detail

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "fcp_metrics.log")

REQUEST_DELAY_SECONDS = 5


def run(conn) -> dict:
    records = FantaCalciopediaScraper().fetch()
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]

    today = date.today().isoformat()
    matched = 0
    unmatched = []

    for record in records:
        if not record.detail_url:
            continue

        player = match_name_to_player(record.name, record.team, players)
        if player is None:
            unmatched.append(record.name)
            logging.info("No match for %s (%s)", record.name, record.team)
            continue

        try:
            detail = fetch_detail(record.detail_url)
        except Exception as exc:
            logging.error("Detail fetch failed for %s: %s", record.name, exc)
            continue

        repository.save_fcp_metrics(
            conn, player["id"], today,
            alg_fcp=detail.alg_fcp,
            punteggio_fcp=detail.punteggio_fcp,
            investment_stability_pct=detail.investment_stability_pct,
            injury_resistance_pct=detail.injury_resistance_pct,
            predicted_appearances=detail.predicted_appearances,
            predicted_goals=detail.predicted_goals,
            predicted_assists=detail.predicted_assists,
            skills=detail.skills,
        )
        if detail.season_stats:
            # Same detail page fetch as the FCP metrics above — no extra
            # request, no extra sleep.
            repository.upsert_player_season_stats(
                conn, player["id"], "fantacalciopedia", detail.season_stats, today,
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
        "FCP metrics run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
