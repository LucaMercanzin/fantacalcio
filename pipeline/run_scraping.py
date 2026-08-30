import logging
import os
import time

from db import repository
from matching.player_matcher import match_records_with_confidence
from scrapers.photo_downloader import download_photo
from scrapers.wikipedia_photo import find_photo_url

logger = logging.getLogger(__name__)

# Wikipedia photo lookup has no rate limiting of its own (S5): a full run
# used to fire ~800 synchronous requests in a row (one per player without a
# scraper-provided photo_url, every single run, even for players already
# photographed). Only paid for players that actually need a *new* lookup —
# see the existing-file check below — but still worth spacing out.
PHOTO_LOOKUP_THROTTLE_SECONDS = 0.3

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


def _consensus_role_classic(records: list, stats_weights: dict) -> tuple:
    """Weighted-majority vote across sources instead of "whichever record
    happened to be first in the match group" (P1-007/TASK-011):
    role_classic decides which of the 4 role pages a player shows up on and
    which slot he fills in the LP/Rosa Ideale, so an arbitrary pick has real
    downstream consequences, not just a cosmetic one.

    Deterministic tie-break: among roles tied on total weight, the
    alphabetically-first role code wins — re-running the same input always
    produces the same result, instead of depending on scraper iteration
    order.

    Returns (role_classic, disagreement) — disagreement is True when
    sources didn't all agree on the role, surfaced by the caller rather
    than silently resolved and forgotten (TASK-011 point 3)."""
    weight_by_role: dict = {}
    for record in records:
        weight = stats_weights.get(record.source, 1)
        weight_by_role[record.role_classic] = weight_by_role.get(record.role_classic, 0) + weight
    role_classic = max(sorted(weight_by_role), key=lambda role: weight_by_role[role])
    return role_classic, len(weight_by_role) > 1


def run_pipeline(scrapers: list, conn, photos_dir: str, scrape_date: str, skip_photos: bool = False) -> None:
    players_before = repository.count_players(conn)
    stats_weights = repository.get_source_stats_weights(conn)

    all_records = []
    for scraper in scrapers:
        try:
            all_records.extend(scraper.fetch())
        except Exception as exc:
            logger.error("Scraper %s failed: %s", scraper.__class__.__name__, exc)

    groups = match_records_with_confidence(all_records)

    for (canonical_name, team), records_with_confidence in groups.items():
        records = [record for record, _ in records_with_confidence]
        role_classic, role_disagreement = _consensus_role_classic(records, stats_weights)
        if role_disagreement:
            logger.warning(
                "%s (%s): fonti in disaccordo sul ruolo, scelto %s per voto "
                "pesato — %s",
                canonical_name, team, role_classic,
                ", ".join(f"{r.source}={r.role_classic}" for r in records),
            )
        role_mantra = next((r.role_mantra for r in records if r.role_mantra), None)
        photo_record = next((r for r in records if r.photo_url), None)

        # Looked up before writing anything (TASK-027/S5/S6): an existing
        # player who already has a local photo file needs neither a photo
        # lookup nor a second upsert_player call just to attach it — both
        # only matter for players who don't have one yet.
        existing_id = repository.get_player_id_by_identity(conn, canonical_name, team)
        existing_photo_path = (
            os.path.join(photos_dir, f"{existing_id}.jpg") if existing_id is not None else None
        )

        if existing_photo_path and os.path.exists(existing_photo_path):
            player_id = repository.upsert_player(
                conn, canonical_name, team, role_classic, role_mantra, existing_photo_path,
            )
        else:
            player_id = repository.upsert_player(
                conn, canonical_name, team, role_classic, role_mantra, None,
            )
            photo_url = photo_record.photo_url if photo_record else None
            if not photo_url and not skip_photos:
                time.sleep(PHOTO_LOOKUP_THROTTLE_SECONDS)
                photo_url = find_photo_url(canonical_name, team)

            if photo_url:
                local_path = download_photo(photo_url, player_id, photos_dir)
                if local_path:
                    repository.upsert_player(
                        conn, canonical_name, team, role_classic, role_mantra,
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
