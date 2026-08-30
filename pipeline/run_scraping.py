import json
import logging
import os
import time

from consensus.engine import (
    _merge_player_rows,
    compute_listino_to_auction_factor,
    compute_source_scale_factors,
)
from db import repository
from matching.player_matcher import match_records_with_confidence
from pipeline.validation import validate_record
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
# transfer window. This check runs *after* run_pipeline's single commit
# (TASK-006), deliberately: a raised NewPlayerSurgeError means the run's
# data is already durably written and needs manual review, not that it
# should be discarded — see run_pipeline's own docstring.
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


def _validate_records(records: list, valid_team_codes: set) -> list:
    """TASK-005/S7: the single validation point every PlayerRecord passes
    through before it can reach matching or the database — nothing between
    a scraper and quotations checked role codes, plausible ranges, or a
    real team before this. Discarded records (invalid role_classic or
    unrecognized team — validate_record's only two discard reasons) never
    reach `records`; every other out-of-range field is cleared to None on
    its own record and kept, not silently clamped to a plausible-looking
    value."""
    validated = []
    discarded_by_source: dict = {}
    cleaned_by_source: dict = {}
    for record in records:
        cleaned, problems = validate_record(record, valid_team_codes)
        if cleaned is None:
            discarded_by_source[record.source] = discarded_by_source.get(record.source, 0) + 1
            for problem in problems:
                logger.warning("%s: %s (%s) scartato — %s", record.source, record.name, record.team, problem)
            continue
        if problems:
            cleaned_by_source[record.source] = cleaned_by_source.get(record.source, 0) + 1
            for problem in problems:
                logger.warning("%s: %s (%s) — %s", record.source, record.name, record.team, problem)
        validated.append(cleaned)

    if discarded_by_source or cleaned_by_source:
        logger.warning(
            "Validazione dati: scartati per fonte %s — ripuliti (campo azzerato) per fonte %s",
            discarded_by_source or "nessuno", cleaned_by_source or "nessuno",
        )
    return validated


def _materialize_consensus(conn, scrape_date: str) -> int:
    """TASK-013 point 3: writes the merged consensus (same computation the
    dashboard runs on every read, via consensus.engine) into player_consensus
    so a past date's consensus price/fantamedia can be answered directly
    from stored history instead of only ever being derivable "as of now"."""
    weights = repository.get_source_weights(conn)
    stats_weights = repository.get_source_stats_weights(conn)
    scale_factors = compute_source_scale_factors(repository.get_source_price_p99(conn))
    all_rows = repository.get_all_latest_quotations(conn)
    factor = compute_listino_to_auction_factor(all_rows, scale_factors)
    match_confidences = repository.get_all_match_confidences(conn)
    merged = _merge_player_rows(
        all_rows, weights, stats_weights=stats_weights, source_scale_factors=scale_factors,
        listino_to_auction_factor=factor, match_confidences=match_confidences,
    )
    for row in merged:
        repository.save_player_consensus(conn, row, scrape_date, commit=False)
    conn.commit()
    return len(merged)


def run_pipeline(scrapers: list, conn, photos_dir: str, scrape_date: str, skip_photos: bool = False) -> None:
    """TASK-006 points 3-4: every write below passes commit=False and the
    whole run is one transaction, committed once at the end — a crash or
    unhandled exception partway through rolls back everything instead of
    leaving whatever had already been individually committed (P1-016/S2/
    A6). scraping_runs records the outcome either way.

    NewPlayerSurgeError is deliberately raised *after* that commit, not
    treated as a rollback-worthy failure: it's an anomalous-but-real run
    flagged for manual review, not corrupt data (see its own docstring) —
    discarding the run's data would make that review impossible."""
    stats_weights = repository.get_source_stats_weights(conn)
    price_weights = repository.get_source_weights(conn)
    run_id = repository.start_scraping_run(
        conn, weights_json=json.dumps({"price": price_weights, "stats": stats_weights}),
    )
    sources_ok = 0
    sources_failed = 0

    try:
        players_before = repository.count_players(conn)
        valid_team_codes = repository.get_current_season_team_codes(conn)

        all_records = []
        for scraper in scrapers:
            try:
                all_records.extend(scraper.fetch())
                sources_ok += 1
            except Exception as exc:
                sources_failed += 1
                logger.error("Scraper %s failed: %s", scraper.__class__.__name__, exc)

        all_records = _validate_records(all_records, valid_team_codes)

        groups = match_records_with_confidence(all_records)

        records_written = 0
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
                    commit=False,
                )
            else:
                player_id = repository.upsert_player(
                    conn, canonical_name, team, role_classic, role_mantra, None,
                    commit=False,
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
                            local_path, commit=False,
                        )

            for record, confidence in records_with_confidence:
                repository.insert_quotation(
                    conn, player_id, record.source, scrape_date,
                    record.price_current, record.price_initial, record.status,
                    record.fantamedia, record.avg_rating, record.appearances,
                    commit=False,
                )
                repository.upsert_player_source_match(
                    conn, player_id, record.source, record.name, record.team,
                    confidence, scrape_date, commit=False,
                )
                records_written += 1

        conn.commit()
        repository.finish_scraping_run(
            conn, run_id, status="ok", sources_ok=sources_ok,
            sources_failed=sources_failed, records_written=records_written,
        )
    except Exception:
        conn.rollback()
        repository.finish_scraping_run(
            conn, run_id, status="failed", sources_ok=sources_ok,
            sources_failed=sources_failed, records_written=0,
        )
        raise

    # TASK-013: materialized *after* the run's own commit/finish_scraping_run
    # and outside that try/except — a consensus computation failure here must
    # not roll back scraping data that already landed successfully, nor get
    # this already-successful run mislabeled "failed" with records_written=0.
    try:
        _materialize_consensus(conn, scrape_date)
    except Exception:
        logger.exception("Materializzazione player_consensus fallita per %s", scrape_date)

    new_players = repository.count_players(conn) - players_before
    if players_before > 0 and new_players > NEW_PLAYER_SURGE_RATIO * players_before:
        raise NewPlayerSurgeError(
            f"{new_players} new players out of {players_before} previous "
            f"({new_players / players_before:.1%}, threshold "
            f"{NEW_PLAYER_SURGE_RATIO:.0%}) — likely a scraper outage "
            "changed which source's name/team won the match (P0-007), not "
            "a real transfer wave. Investigate before trusting this run."
        )
