"""Source x field coverage matrix (TASK-023/P1-018/S8) and per-record
domain validation at scrape ingestion (TASK-005/S7/P1-005/P1-007/P0-003).

A markup change that silently zeroes out one field used to leave no trace
anywhere: fantacalcio_it's role_mantra selector returned None in production
for every one of its ~1,485 rows while the fixture-based scraper test
stayed green (fixture froze the old markup). Nothing counted how often each
source actually fills each field, so the drop was invisible until someone
went looking at the raw data.

compute_field_coverage answers "for this source, what % of its rows
actually have a value in this field" and flags any pair under its
configured threshold — logged as an error immediately and surfaced as a
row in Monitoraggio, instead of only being discoverable by manual query.

validate_record is the "single validation point every PlayerRecord must
pass" the audit asks for (TASK-005): before this, nothing between a
scraper and the database checked that a role code was one of P/D/C/A, that
fantamedia/avg_rating/appearances landed in a plausible range, or that the
team was one of the current season's real clubs — a scraper bug could
write literally anything straight into quotations."""

import logging
from dataclasses import replace

from db import repository
from matching.player_matcher import normalize_team
from ranking.tactical_profile import ROLE_MANTRA_BASE

logger = logging.getLogger(__name__)

VALID_ROLE_CLASSIC = {"P", "D", "C", "A"}
# ROLE_MANTRA_BASE's keys ARE the Mantra role vocabulary (DC/DD/DS/B/E/M/
# C/T/W/A/PC) — same single source of truth ranking.tactical_profile
# already uses, not a second hardcoded list that could drift from it.
VALID_ROLE_MANTRA = set(ROLE_MANTRA_BASE)
FANTAMEDIA_RANGE = (2.0, 9.5)
AVG_RATING_RANGE = (3.0, 9.0)
APPEARANCES_RANGE = (0, 38)


def validate_record(record, valid_team_codes: set, alias_map: dict | None = None) -> tuple:
    """Returns (cleaned_record, problems). problems is a list of short
    human-readable strings, empty when the record was already clean.

    cleaned_record is None when the record must be discarded outright —
    role_classic isn't one of P/D/C/A, or the team isn't one of the
    current season's real clubs (valid_team_codes: repository.
    get_current_season_team_codes, normalize_team()-keyed) — there's no
    salvageable player identity or role slot to file this under.
    Otherwise it's a copy of `record` with every other out-of-range field
    replaced by None, never a fabricated/clamped value — same "declare it,
    don't hide it" rule as the rest of the pipeline.

    alias_map (TASK-009/D9): passed through to normalize_team so a source
    spelling a club's official name ("AS Roma") doesn't get discarded here
    as an unrecognized team before it ever reaches matching."""
    problems = []

    if record.role_classic not in VALID_ROLE_CLASSIC:
        problems.append(f"role_classic non valido: {record.role_classic!r}")
        return None, problems

    if normalize_team(record.team or "", alias_map) not in valid_team_codes:
        problems.append(f"team non riconosciuta: {record.team!r}")
        return None, problems

    role_mantra = record.role_mantra
    if role_mantra is not None and role_mantra not in VALID_ROLE_MANTRA:
        problems.append(f"role_mantra non valido: {role_mantra!r}")
        role_mantra = None

    fantamedia = record.fantamedia
    if fantamedia is not None and not (FANTAMEDIA_RANGE[0] <= fantamedia <= FANTAMEDIA_RANGE[1]):
        problems.append(f"fantamedia fuori range: {fantamedia!r}")
        fantamedia = None

    avg_rating = record.avg_rating
    if avg_rating is not None and not (AVG_RATING_RANGE[0] <= avg_rating <= AVG_RATING_RANGE[1]):
        problems.append(f"avg_rating fuori range: {avg_rating!r}")
        avg_rating = None

    appearances = record.appearances
    if appearances is not None and not (APPEARANCES_RANGE[0] <= appearances <= APPEARANCES_RANGE[1]):
        problems.append(f"appearances fuori range: {appearances!r}")
        appearances = None

    price_current = record.price_current
    if price_current is not None and not price_current > 0:
        problems.append(f"price_current non positivo: {price_current!r}")
        price_current = None

    if not problems:
        return record, problems

    cleaned = replace(
        record, role_mantra=role_mantra, fantamedia=fantamedia,
        avg_rating=avg_rating, appearances=appearances, price_current=price_current,
    )
    return cleaned, problems

# Fields tracked per source. role_mantra is deliberately not here: it's
# stored once per player (players.role_mantra), not per source per
# quotation, so there's no per-source history to measure coverage against
# without a schema/pipeline change (see P1-018) — out of scope for this
# pass, tracked separately.
COVERAGE_FIELDS = (
    "price_current", "price_initial", "status", "fantamedia", "avg_rating", "appearances",
)

# Minimum expected non-null %, per field, below which a source's coverage
# for that field is flagged. status and price_initial are the two fields
# real sources most often skip entirely by design (not every listino
# publishes a starting/base price, and injury/suspension status isn't
# universally tracked), hence the lower floor; the rest are core fields a
# working scraper should fill on nearly every row it returns.
DEFAULT_COVERAGE_THRESHOLD = 80.0
COVERAGE_THRESHOLDS = {
    "status": 30.0,
    "price_initial": 50.0,
}


def compute_field_coverage(conn) -> list:
    """One entry per (source, field): how many of that source's latest
    quotations (repository.get_all_latest_quotations — the same rows the
    consensus merge itself consumes, not the full historical table) have a
    non-null value, against that field's configured threshold."""
    rows = repository.get_all_latest_quotations(conn)
    by_source: dict = {}
    for row in rows:
        by_source.setdefault(row["source"], []).append(row)

    coverage = []
    for source, source_rows in sorted(by_source.items()):
        total = len(source_rows)
        for field in COVERAGE_FIELDS:
            non_null = sum(1 for r in source_rows if r.get(field) is not None)
            pct = round(100 * non_null / total, 1) if total else 0.0
            threshold = COVERAGE_THRESHOLDS.get(field, DEFAULT_COVERAGE_THRESHOLD)
            below_threshold = pct < threshold
            if below_threshold:
                logger.error(
                    "Copertura %s.%s sotto soglia: %.1f%% (soglia %.1f%%, %d/%d righe)",
                    source, field, pct, threshold, non_null, total,
                )
            coverage.append({
                "source": source,
                "field": field,
                "total_rows": total,
                "non_null": non_null,
                "coverage_pct": pct,
                "threshold": threshold,
                "below_threshold": below_threshold,
            })
    return coverage
