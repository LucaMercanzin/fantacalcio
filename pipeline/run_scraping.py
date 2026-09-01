import json
import logging
import os
import time
from datetime import date

from consensus.engine import (
    _merge_player_rows,
    compute_league_price_scale,
    compute_listino_to_auction_factor,
    compute_source_scale_factors,
    group_by_player,
)
from db import repository
from matching.player_matcher import match_records_with_confidence, normalize_team
from pipeline.season_resolution import resolve_stats_seasons
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


def _validate_records(records: list, valid_team_codes: set, alias_map: dict | None = None) -> list:
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
        cleaned, problems = validate_record(record, valid_team_codes, alias_map)
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
    scale_factors = compute_source_scale_factors(repository.get_source_price_ceiling(conn))
    all_rows = repository.get_all_latest_quotations(conn)
    factor = compute_listino_to_auction_factor(all_rows, scale_factors)
    league_price_scale = compute_league_price_scale(
        all_rows, weights, date.fromisoformat(scrape_date), scale_factors, factor,
    )
    match_confidences = repository.get_all_match_confidences(conn)
    # stats_rows_by_player: la dashboard lo passa da sempre (dashboard/
    # data_access._build_player_rows), questa funzione no — e il docstring
    # qui sopra dichiarava comunque "la stessa computazione che la dashboard
    # fa a ogni lettura". Non era vero: senza questo argomento le statistiche
    # vengono lette dalle righe più recenti invece che dall'ultima stagione
    # *conclusa* (repository.get_latest_stats_quotations, la guardia contro
    # il rollover di fine agosto), e `player_consensus` finiva con 84
    # fantamedia dove l'app ne mostrava 253 sugli stessi dati. Una tabella
    # storica che non corrisponde a ciò che l'utente vede è peggio che non
    # averla: è un secondo numero che sembra ufficiale.
    stats_rows_by_player = group_by_player(repository.get_latest_stats_quotations(conn))
    merged = _merge_player_rows(
        all_rows, weights, stats_weights=stats_weights, source_scale_factors=scale_factors,
        listino_to_auction_factor=factor, match_confidences=match_confidences,
        league_price_scale=league_price_scale, stats_rows_by_player=stats_rows_by_player,
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

    An anomalous-but-real surge is preserved for manual review, but its run
    is marked ``quarantined`` and downstream consensus is not materialized.
    This keeps the evidence without advertising untrusted data as successful."""
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
        alias_map = repository.get_team_aliases(conn)

        all_records = []
        for scraper in scrapers:
            try:
                all_records.extend(scraper.fetch())
                sources_ok += 1
            except Exception as exc:
                sources_failed += 1
                logger.error("Scraper %s failed: %s", scraper.__class__.__name__, exc)

        all_records = _validate_records(all_records, valid_team_codes, alias_map)

        groups = match_records_with_confidence(all_records, alias_map)

        records_written = 0
        seen_player_ids = set()
        transferred_player_ids = set()
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
            existing_id = repository.get_player_id_by_identity(conn, canonical_name, team, alias_map)
            if existing_id is None:
                # TASK-004c/P0-010: identity_key includes team, so a genuine
                # transfer misses the lookup above just like a new player
                # would. Told apart here by normalized name, and only acted
                # on when exactly one existing player shares it — 2+
                # candidates is ambiguous (which one moved, if either?) and
                # falls through to upsert_player's normal new-player path
                # rather than risk merging two different people.
                candidates = repository.get_players_by_normalized_name(conn, canonical_name)
                if len(candidates) == 1 and (
                    normalize_team(candidates[0]["team"], alias_map) != normalize_team(team, alias_map)
                ):
                    transfer_candidate = candidates[0]
                    repository.update_player_team(
                        conn, transfer_candidate["id"], team, commit=False, alias_map=alias_map,
                    )
                    repository.record_player_transfer(
                        conn, transfer_candidate["id"], transfer_candidate["team"], team,
                        scrape_date, commit=False,
                    )
                    transferred_player_ids.add(transfer_candidate["id"])
                    existing_id = transfer_candidate["id"]
            existing_photo_path = (
                os.path.join(photos_dir, f"{existing_id}.jpg") if existing_id is not None else None
            )

            if existing_photo_path and os.path.exists(existing_photo_path):
                player_id = repository.upsert_player(
                    conn, canonical_name, team, role_classic, role_mantra, existing_photo_path,
                    commit=False, alias_map=alias_map,
                )
            else:
                player_id = repository.upsert_player(
                    conn, canonical_name, team, role_classic, role_mantra, None,
                    commit=False, alias_map=alias_map,
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
                            local_path, commit=False, alias_map=alias_map,
                        )

            seen_player_ids.add(player_id)

            for record, confidence in records_with_confidence:
                repository.insert_quotation(
                    conn, player_id, record.source, scrape_date,
                    record.price_current, record.price_initial, record.status,
                    record.fantamedia, record.avg_rating, record.appearances,
                    commit=False,
                    stats_season=record.stats_season, stats_competition=record.stats_competition,
                )
                repository.upsert_player_source_match(
                    conn, player_id, record.source, record.name, record.team,
                    confidence, scrape_date, commit=False,
                )
                records_written += 1

        # TASK-004c point 3: last_seen_scrape_date/active reflect this run's
        # actual coverage. Absence marking only runs on a *complete* run
        # (every source ok) — a single dropped scraper would otherwise mark
        # every player that source alone covers as gone, exactly the P0-007
        # failure mode NEW_PLAYER_SURGE_RATIO already guards on the other
        # side (surge of new players vs. surge of "removed" ones).
        repository.mark_players_seen(conn, seen_player_ids, scrape_date, commit=False)
        players_removed = (
            repository.mark_players_not_seen_inactive(conn, scrape_date, commit=False)
            if sources_failed == 0 else None
        )
        players_added = repository.count_players(conn) - players_before
        players_transferred = len(transferred_player_ids)
        players_unchanged = len(seen_player_ids) - players_added - players_transferred

        new_players = players_added
        surge_detected = (
            players_before > 0
            and new_players > NEW_PLAYER_SURGE_RATIO * players_before
        )

        conn.commit()
        repository.finish_scraping_run(
            conn, run_id, status="quarantined" if surge_detected else "ok",
            sources_ok=sources_ok,
            sources_failed=sources_failed, records_written=records_written,
            players_added=players_added, players_removed=players_removed,
            players_transferred=players_transferred, players_unchanged=players_unchanged,
        )
        # TASK-004c point 4: end-of-run report, logged here; the same counts
        # are also on scraping_runs for Monitoraggio, and the detail behind
        # them stays queryable directly (player_transfers, players.active).
        logger.info(
            "Report giocatori: ADDED=%s REMOVED=%s TRANSFERRED=%s UNCHANGED=%s",
            players_added, players_removed if players_removed is not None else "n/d (run incompleto)",
            players_transferred, players_unchanged,
        )
    except Exception:
        conn.rollback()
        repository.finish_scraping_run(
            conn, run_id, status="failed", sources_ok=sources_ok,
            sources_failed=sources_failed, records_written=0,
        )
        raise

    if surge_detected:
        raise NewPlayerSurgeError(
            f"{new_players} new players out of {players_before} previous "
            f"({new_players / players_before:.1%}, threshold "
            f"{NEW_PLAYER_SURGE_RATIO:.0%}) — likely a scraper outage "
            "changed which source's name/team won the match (P0-007), not "
            "a real transfer wave. Run quarantined; investigate before trusting it."
        )

    # BACKLOG-2026-08-31 §6: prima del consenso, non dopo — _stats_eligible_
    # rows legge stats_season per scartare le righe della stagione appena
    # cominciata, quindi le stagioni vanno riconosciute mentre il consenso è
    # ancora da calcolare. Fuori dal try/except del run per la stessa ragione
    # del consenso: è un arricchimento, non un dato da cui dipende lo scrape.
    try:
        resolve_stats_seasons(conn, scrape_date)
    except Exception:
        logger.exception("Risoluzione stats_season fallita per %s", scrape_date)

    # TASK-013: materialized *after* the run's own commit/finish_scraping_run
    # and outside that try/except — a consensus computation failure here must
    # not roll back scraping data that already landed successfully, nor get
    # this already-successful run mislabeled "failed" with records_written=0.
    try:
        _materialize_consensus(conn, scrape_date)
    except Exception:
        logger.exception("Materializzazione player_consensus fallita per %s", scrape_date)

