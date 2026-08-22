import logging
from scrapers.photo_downloader import download_photo
from matching.player_matcher import match_records
from db import repository

logger = logging.getLogger(__name__)


def run_pipeline(scrapers: list, conn, photos_dir: str, scrape_date: str) -> None:
    all_records = []
    for scraper in scrapers:
        try:
            all_records.extend(scraper.fetch())
        except Exception as exc:
            logger.error("Scraper %s failed: %s", scraper.__class__.__name__, exc)

    groups = match_records(all_records)

    for (canonical_name, team), records in groups.items():
        first = records[0]
        photo_record = next((r for r in records if r.photo_url), None)

        player_id = repository.upsert_player(
            conn, canonical_name, team, first.role_classic, first.role_mantra, None,
        )

        if photo_record:
            local_path = download_photo(photo_record.photo_url, player_id, photos_dir)
            if local_path:
                repository.upsert_player(
                    conn, canonical_name, team, first.role_classic, first.role_mantra,
                    local_path,
                )

        for record in records:
            repository.insert_quotation(
                conn, player_id, record.source, scrape_date,
                record.price_current, record.price_initial, record.status,
                record.fantamedia, record.avg_rating, record.appearances,
            )
