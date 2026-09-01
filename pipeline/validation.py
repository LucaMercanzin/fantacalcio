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
    "stats_season", "stats_competition",
)

# Quali campi ogni fonte pubblica davvero (BACKLOG-2026-08-31 §8).
#
# **Perché questa tabella esiste.** Prima c'erano soglie per campo e basta,
# uguali per tutte le fonti, e il risultato era che a ogni run partivano
# ~30 warning su 48 controlli: `fantacalcio_it.fantamedia 0.0%`,
# `fantanalisi.appearances 0.0%`, e così via. Nessuno di quei warning
# segnalava un guasto — fantacalcio_it non ha *mai* pubblicato una
# fantamedia, il suo scraper scrive `fantamedia=None` come costante. Erano
# warning strutturali, quindi permanenti, quindi rumore: e un allarme che
# suona sempre è un allarme che non si legge più.
#
# Dichiarando cosa una fonte fornisce, uno 0% smette di essere ambiguo:
# su un campo non dichiarato è la normalità e non viene nemmeno guardato,
# su un campo dichiarato è uno scraper rotto e va urlato. È il controllo
# che prima non esisteva, sepolto sotto quelli che non servivano.
#
# Ricavata leggendo i sei scraper: un campo entra qui solo se il codice può
# assegnargli un valore vero, non se è `None` costante. `status` non compare
# per nessuno perché nessuna delle sei fonti lo popola oggi.
SOURCE_PROVIDED_FIELDS = {
    "fantacalcio_it": {"price_current", "price_initial"},
    "fantacalcio_online": {
        "price_current", "avg_rating", "appearances", "stats_season", "stats_competition",
    },
    "fantacalciopedia": {"fantamedia", "appearances", "stats_competition"},
    "fantanalisi": {"price_current"},
    "fantapazz": {"price_current"},
    "pianetafanta": {"price_current", "price_initial"},
}

# Minimum expected non-null %, below which a *declared* field is flagged.
# Una fonte nuova, non ancora in SOURCE_PROVIDED_FIELDS, viene controllata
# su tutti i campi: meglio qualche falso allarme che uno scraper nuovo che
# entra in produzione senza nessun controllo di copertura.
DEFAULT_COVERAGE_THRESHOLD = 80.0

# Soglie per (fonte, campo), per i casi in cui la copertura parziale è la
# normalità documentata della pagina e non un guasto. Le tre di
# fantacalcio_online e quella di fantacalciopedia hanno la stessa causa: le
# celle statistiche sono vuote per i giocatori senza storico di Serie A (i
# "NUOVO"), che a fine agosto sono il 40-50% di una lista che comprende le
# rose complete. Il pavimento serve a distinguere quel 45-57% fisiologico
# da uno scraper che ha smesso di leggere la colonna e restituisce 0%.
COVERAGE_THRESHOLDS = {
    ("fantacalcio_online", "price_current"): 35.0,
    ("fantacalcio_online", "avg_rating"): 40.0,
    ("fantacalcio_online", "appearances"): 40.0,
    ("fantacalciopedia", "fantamedia"): 35.0,
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
        # Una fonte sconosciuta (scraper nuovo) non ha una dichiarazione:
        # si controlla tutto, invece di non controllare niente.
        provided_fields = SOURCE_PROVIDED_FIELDS.get(source)
        for field in COVERAGE_FIELDS:
            non_null = sum(1 for r in source_rows if r.get(field) is not None)
            pct = round(100 * non_null / total, 1) if total else 0.0
            provided = provided_fields is None or field in provided_fields
            threshold = (
                COVERAGE_THRESHOLDS.get((source, field), DEFAULT_COVERAGE_THRESHOLD)
                if provided else None
            )
            below_threshold = provided and pct < threshold
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
                # None = la fonte non fornisce questo campo, quindi non c'è
                # una soglia da rispettare. Distinto da 0.0, che vorrebbe
                # dire "fornito, e qualsiasi copertura va bene".
                "threshold": threshold,
                "provided": provided,
                "below_threshold": below_threshold,
            })
    return coverage
