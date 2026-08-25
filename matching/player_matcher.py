import re
import unicodedata
from rapidfuzz import fuzz
from scrapers.base import PlayerRecord


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^a-zA-Z\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def normalize_team(team: str) -> str:
    """Reduce a team name/abbreviation to its first 3 letters, so sources
    using codes ("INT") match sources using full names ("Inter")."""
    normalized = re.sub(r"[^a-zA-Z]", "", team).lower()
    return normalized[:3]


def _group_records_with_confidence(records: list) -> dict:
    """Group records into players, keeping the fuzzy-match confidence (0-100)
    that justified adding each record to its group. The record that starts a
    new group gets confidence 100 — it *is* the group's identity, not a match
    against something else."""
    groups: dict = {}

    for record in records:
        team = normalize_team(record.team)
        norm_name = normalize_name(record.name)

        matched_key = None
        matched_confidence = 100.0
        for (existing_name, existing_team) in groups:
            if existing_team != team:
                continue
            similarity = max(
                fuzz.ratio(norm_name, existing_name),
                fuzz.partial_ratio(norm_name, existing_name),
            )
            if similarity >= 85:
                matched_key = (existing_name, existing_team)
                matched_confidence = float(similarity)
                break

        if matched_key:
            groups[matched_key].append((record, matched_confidence))
        else:
            groups[(norm_name, team)] = [(record, 100.0)]

    return groups


def match_records(records: list) -> dict:
    grouped = _group_records_with_confidence(records)

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


def match_name_to_player(name: str, team: str, players: list, threshold: int = 80):
    """Matches a bare (name, team) pair — as scraped from a page that doesn't
    expose our internal player_id, e.g. the rigoristi or voti pages — against
    a list of {"id", "canonical_name", "team"} dicts. Returns the best match
    dict, or None if nothing clears the threshold or the best match is too
    close to a second candidate to trust."""
    target_team = normalize_team(team)
    target_name = normalize_name(name)

    best_player = None
    best_score = 0
    second_best_score = 0
    for player in players:
        if normalize_team(player["team"]) != target_team:
            continue
        score = max(
            fuzz.ratio(target_name, normalize_name(player["canonical_name"])),
            fuzz.partial_ratio(target_name, normalize_name(player["canonical_name"])),
        )
        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_player = player
        elif score > second_best_score:
            second_best_score = score

    if not best_player or best_score < threshold:
        return None
    if best_score < NEAR_EXACT_SCORE and (best_score - second_best_score) < AMBIGUITY_MARGIN:
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
        score = max(
            fuzz.ratio(target_name, normalize_name(player["canonical_name"])),
            fuzz.partial_ratio(target_name, normalize_name(player["canonical_name"])),
        )
        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_player = player
        elif score > second_best_score:
            second_best_score = score

    if not best_player or best_score < threshold:
        return None
    if best_score < NEAR_EXACT_SCORE and (best_score - second_best_score) < AMBIGUITY_MARGIN:
        return None
    return best_player


def match_records_with_confidence(records: list) -> dict:
    """Same grouping as match_records, but each record keeps the match
    confidence that put it in its group — used to persist a review queue for
    uncertain matches (spec section 5) instead of silently trusting every
    fuzzy match forever."""
    grouped = _group_records_with_confidence(records)

    display_groups: dict = {}
    for recs in grouped.values():
        plain_records = [record for record, _ in recs]
        best_name = max((r.name for r in plain_records), key=len)
        best_team = max((r.team for r in plain_records), key=len)
        display_groups[(best_name, best_team)] = recs
    return display_groups
