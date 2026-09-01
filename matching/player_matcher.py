import re
import unicodedata

from rapidfuzz import fuzz


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^a-zA-Z\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def normalize_team(team: str, alias_map: dict | None = None) -> str:
    """Reduce a team name/abbreviation to its first 3 letters, so sources
    using codes ("INT") match sources using full names ("Inter").

    alias_map (TASK-009/D9): letters-only-lowercase full name -> team code,
    consulted *before* the 3-letter truncation below — a plain truncation
    gets club-name variants like "Hellas Verona"/"AS Roma"/"ACF Fiorentina"
    wrong (their prefix, not the club, wins the first 3 letters). Optional
    and defaults to None so every existing call site keeps today's behavior
    unchanged; repository.get_team_aliases(conn) loads the real map for
    callers that have a connection (matching happens during the scraping
    pipeline, which does)."""
    normalized = re.sub(r"[^a-zA-Z]", "", team).lower()
    if alias_map and normalized in alias_map:
        return alias_map[normalized]
    return normalized[:3]


MATCH_THRESHOLD = 85


def _initials_conflict(norm_a: str, norm_b: str) -> bool:
    """True when two names share a surname but their abbreviated given-name
    tokens point at different people — e.g. "martinez l" (Lautaro Martinez)
    vs "martinez jo" (Josep Martinez), two actual Inter teammates that
    fuzz.partial_ratio scores >90% similar because both are short and share
    the "martinez" prefix. Only fires when there's a shared long token to
    anchor on and at least one short (initial-like) token on each side to
    compare — otherwise it stays out of the way and lets the fuzzy score
    decide, e.g. exact duplicates or missing-initial cases."""
    tokens_a = norm_a.split()
    tokens_b = norm_b.split()
    long_a = {t for t in tokens_a if len(t) > 3}
    long_b = {t for t in tokens_b if len(t) > 3}
    if not (long_a & long_b):
        return False
    short_a = [t for t in tokens_a if len(t) <= 3 and t not in long_b]
    short_b = [t for t in tokens_b if len(t) <= 3 and t not in long_a]
    if not short_a or not short_b:
        return False
    return not any(a[0] == b[0] for a in short_a for b in short_b)


def _is_ambiguous(best_score: float, second_best_score: float) -> bool:
    """TASK-009 point 3: a *tie* for best candidate is refused even at/above
    NEAR_EXACT_SCORE — the near-exact bypass below assumes the best score
    being that close to 100 makes it trustworthy on its own, which stops
    being true the moment a second candidate ties it exactly (e.g. two
    players who truly share a normalized name): there's no basis left to
    prefer one over the other, so this must resolve to "ambiguous" same as
    a merely-close second-best would below NEAR_EXACT_SCORE."""
    if best_score == second_best_score:
        return True
    return best_score < NEAR_EXACT_SCORE and (best_score - second_best_score) < AMBIGUITY_MARGIN


def _group_records_with_confidence(records: list, alias_map: dict | None = None) -> dict:
    """Group records into players, keeping the fuzzy-match confidence (0-100)
    that justified adding each record to its group. The record that starts a
    new group gets confidence 100 — it *is* the group's identity, not a match
    against something else.

    Picks the *best* matching existing group (same team), not just the first
    one to clear the threshold, and applies the same ambiguity guard as
    match_name_to_player: two teammates sharing a surname (e.g. "Martinez L."
    the striker and "Martinez Jo." the goalkeeper) can both score >85 against
    each other via partial_ratio, so a close second-best candidate makes the
    match untrustworthy — start a new group instead of silently merging two
    different players.

    records is sorted before grouping (TASK-009 point 4): which record
    "arrives first" and starts a group used to depend on scraper iteration
    order (all_records.extend per scraper in pipeline/run_scraping.py) — a
    dropped/reordered source could then change which display name/team wins
    a group between runs. Sorting by (team, name, source) first makes the
    grouping result depend only on the records themselves."""
    groups: dict = {}
    # Quali fonti hanno già un record in ciascun gruppo (TASK-030). Tenuto a
    # parte invece che ricavato da `groups` a ogni confronto perché il ciclo
    # sotto è già quadratico nel numero di giocatori di una squadra.
    sources_in_group: dict = {}

    sorted_records = sorted(
        records, key=lambda r: (normalize_team(r.team, alias_map), normalize_name(r.name), r.source),
    )
    for record in sorted_records:
        team = normalize_team(record.team, alias_map)
        norm_name = normalize_name(record.name)

        best_key = None
        best_score = 0.0
        second_best_score = 0.0
        for (existing_name, existing_team) in groups:
            if existing_team != team:
                continue
            # Una fonte elenca ogni giocatore una volta sola: se in questo
            # gruppo c'è già un record della stessa fonte, questo record è
            # un'altra persona, per quanto simile sia il nome. È l'unico
            # segnale *strutturale* disponibile qui — non una somiglianza da
            # soppesare, ma un fatto sulla pagina scrappata — ed è quello che
            # separa i casi che la sola distanza fra stringhe non separa.
            #
            # Sui record veri del 01/09/2026 questa condizione da sola spacca
            # 11 gruppi che fondevano due giocatori diversi, otto dei quali
            # mescolando anche i ruoli: Jones Curtis con Stones all'Inter,
            # Anguissa con Lang al Napoli, Mancini Gianluca con Mannini
            # Mattia alla Roma, Kaba con Ndaba e Ilic con Stulic al Lecce,
            # Calvani con Calò e Cittadini con Fini al Frosinone, Gabellini
            # con Pellini al Torino, Bella-Kotchap con Haps al Venezia, Nuno
            # Tavares con Fares alla Lazio — e al Milan il difensore
            # Terracciano Filippo con il portiere Terracciano, che finiva a
            # comparire come riserva in porta con dentro le quotazioni di due
            # persone.
            #
            # Il verso dell'errore è quello sicuro: sbagliando si creano due
            # righe per un giocatore solo — visibile, e recuperabile con
            # scripts/diagnose_missing_prices.py — invece di una riga sola con
            # dentro i dati di due persone, che nessuno nota.
            if record.source in sources_in_group[(existing_name, existing_team)]:
                continue
            if _initials_conflict(norm_name, existing_name):
                continue
            similarity = max(
                fuzz.ratio(norm_name, existing_name),
                fuzz.partial_ratio(norm_name, existing_name),
            )
            if similarity > best_score:
                second_best_score = best_score
                best_score = similarity
                best_key = (existing_name, existing_team)
            elif similarity > second_best_score:
                second_best_score = similarity

        matched_key = None
        matched_confidence = 100.0
        if best_key and best_score >= MATCH_THRESHOLD and not _is_ambiguous(best_score, second_best_score):
            matched_key = best_key
            matched_confidence = best_score

        if matched_key:
            groups[matched_key].append((record, matched_confidence))
            sources_in_group[matched_key].add(record.source)
        else:
            groups[(norm_name, team)] = [(record, 100.0)]
            sources_in_group[(norm_name, team)] = {record.source}

    return groups


def match_records(records: list, alias_map: dict | None = None) -> dict:
    grouped = _group_records_with_confidence(records, alias_map)

    display_groups: dict = {}
    for recs in grouped.values():
        plain_records = [record for record, _ in recs]
        best_name = max((r.name for r in plain_records), key=len)
        best_team = max((r.team for r in plain_records), key=len)
        display_groups[(best_name, best_team)] = plain_records
    return display_groups


# If the best and second-best candidate are within this many points of each
# other, treat the match as ambiguous and refuse it rather than guess — this
# is exactly the situation two teammates who share a surname produce (e.g.
# "Martinez L." and "Martinez Jo." on the same team), where picking the
# higher-scoring one by a hair is as likely to be wrong as right.
AMBIGUITY_MARGIN = 8
NEAR_EXACT_SCORE = 98  # bypasses the margin check — this close, it's safe


def match_name_to_player(name: str, team: str, players: list, threshold: int = 80,
                          alias_map: dict | None = None):
    """Matches a bare (name, team) pair — as scraped from a page that doesn't
    expose our internal player_id, e.g. the rigoristi or voti pages — against
    a list of {"id", "canonical_name", "team"} dicts. Returns the best match
    dict, or None if nothing clears the threshold or the best match is too
    close to a second candidate to trust."""
    target_team = normalize_team(team, alias_map)
    target_name = normalize_name(name)

    best_player = None
    best_score = 0
    second_best_score = 0
    for player in players:
        if normalize_team(player["team"], alias_map) != target_team:
            continue
        norm_candidate = normalize_name(player["canonical_name"])
        if _initials_conflict(target_name, norm_candidate):
            continue
        score = max(
            fuzz.ratio(target_name, norm_candidate),
            fuzz.partial_ratio(target_name, norm_candidate),
        )
        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_player = player
        elif score > second_best_score:
            second_best_score = score

    if not best_player or best_score < threshold:
        return None
    if _is_ambiguous(best_score, second_best_score):
        return None
    return best_player


def match_name_to_player_any_team(name: str, players: list, threshold: int = 92):
    """Like match_name_to_player, but ignores team entirely — for matching a
    player against a *past* season's record where he may have played for a
    different club than his current one. Team is the strongest signal
    against false positives, so dropping it needs a much higher name-only
    threshold to stay safe (92 vs. the normal 80)."""
    target_name = normalize_name(name)

    best_player = None
    best_score = 0
    second_best_score = 0
    for player in players:
        norm_candidate = normalize_name(player["canonical_name"])
        if _initials_conflict(target_name, norm_candidate):
            continue
        score = max(
            fuzz.ratio(target_name, norm_candidate),
            fuzz.partial_ratio(target_name, norm_candidate),
        )
        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_player = player
        elif score > second_best_score:
            second_best_score = score

    if not best_player or best_score < threshold:
        return None
    if _is_ambiguous(best_score, second_best_score):
        return None
    return best_player


def match_records_with_confidence(records: list, alias_map: dict | None = None) -> dict:
    """Same grouping as match_records, but each record keeps the match
    confidence that put it in its group — used to persist a review queue for
    uncertain matches (spec section 5) instead of silently trusting every
    fuzzy match forever."""
    grouped = _group_records_with_confidence(records, alias_map)

    display_groups: dict = {}
    for recs in grouped.values():
        plain_records = [record for record, _ in recs]
        best_name = max((r.name for r in plain_records), key=len)
        best_team = max((r.team for r in plain_records), key=len)
        display_groups[(best_name, best_team)] = recs
    return display_groups
