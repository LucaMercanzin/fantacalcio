import logging

from db import repository
from matching.player_matcher import match_records_with_confidence
from scrapers.photo_downloader import download_photo
from scrapers.wikipedia_photo import find_photo_url

logger = logging.getLogger(__name__)

# TASK-007/P0-007 point 5: a healthy run adds a handful of real transfers,
# not dozens of "new" players — a jump this big is almost always a scraper
# outage changing which source's name/team wins the match, not a real
# transfer window. NOTE: this check runs after the upserts below (no
# run-wide transaction to roll back into yet, see TASK-006 point 4/5,
# deferred) — a raised NewPlayerSurgeError means the run already wrote to
# the DB and needs manual review, it does not undo it.
NEW_PLAYER_SURGE_RATIO = 0.05


class NewPlayerSurgeError(Exception):
    """Raised when a run creates more new players than NEW_PLAYER_SURGE_RATIO
    of the pre-run total — almost always a dropped source changing which
    display name/team wins the match (P0-007), not a real transfer wave."""


def run_pipeline(scrapers: list, conn, photos_dir: str, scrape_date: str, skip_photos: bool = False) -> None:
    players_before = repository.count_players(conn)

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

    new_players = repository.count_players(conn) - players_before
    if players_before > 0 and new_players > NEW_PLAYER_SURGE_RATIO * players_before:
        raise NewPlayerSurgeError(
            f"{new_players} new players out of {players_before} previous "
            f"({new_players / players_before:.1%}, threshold "
            f"{NEW_PLAYER_SURGE_RATIO:.0%}) — likely a scraper outage "
            "changed which source's name/team won the match (P0-007), not "
            "a real transfer wave. Investigate before trusting this run."
        )
