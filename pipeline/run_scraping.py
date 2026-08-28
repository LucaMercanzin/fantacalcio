import logging

from db import repository
from matching.player_matcher import match_records_with_confidence
from scrapers.photo_downloader import download_photo
from scrapers.wikipedia_photo import find_photo_url

logger = logging.getLogger(__name__)


def run_pipeline(scrapers: list, conn, photos_dir: str, scrape_date: str, skip_photos: bool = False) -> None:
    all_records = []
    for scraper in scrapers:
        try:
            all_records.extend(scraper.fetch())
        except Exception as exc:
            logger.error("Scraper %s failed: %s", scraper.__class__.__name__, exc)

    groups = match_records_with_confidence(all_records)

    for (canonical_name, team), records_with_confidence in groups.items():
        records = [record for record, _ in records_with_confidence]
        first = records[0]
        role_mantra = next((r.role_mantra for r in records if r.role_mantra), None)
        photo_record = next((r for r in records if r.photo_url), None)

        player_id = repository.upsert_player(
            conn, canonical_name, team, first.role_classic, role_mantra, None,
        )

        photo_url = photo_record.photo_url if photo_record else None
        if not photo_url and not skip_photos:
            photo_url = find_photo_url(canonical_name, team)

        if photo_url:
            local_path = download_photo(photo_url, player_id, photos_dir)
            if local_path:
                repository.upsert_player(
                    conn, canonical_name, team, first.role_classic, role_mantra,
                    local_path,
                )

        for record, confidence in records_with_confidence:
            repository.insert_quotation(
                conn, player_id, record.source, scrape_date,
                record.price_current, record.price_initial, record.status,
                record.fantamedia, record.avg_rating, record.appearances,
            )
            repository.upsert_player_source_match(
                conn, player_id, record.source, record.name, record.team,
                confidence, scrape_date,
            )
