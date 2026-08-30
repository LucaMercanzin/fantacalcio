"""Source x field coverage matrix (TASK-023/P1-018/S8).

A markup change that silently zeroes out one field used to leave no trace
anywhere: fantacalcio_it's role_mantra selector returned None in production
for every one of its ~1,485 rows while the fixture-based scraper test
stayed green (fixture froze the old markup). Nothing counted how often each
source actually fills each field, so the drop was invisible until someone
went looking at the raw data.

compute_field_coverage answers "for this source, what % of its rows
actually have a value in this field" and flags any pair under its
configured threshold — logged as an error immediately and surfaced as a
row in Monitoraggio, instead of only being discoverable by manual query."""

import logging

from db import repository

logger = logging.getLogger(__name__)

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
