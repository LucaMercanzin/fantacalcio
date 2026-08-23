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


def match_records(records: list) -> dict:
    groups: dict = {}

    for record in records:
        team = normalize_team(record.team)
        norm_name = normalize_name(record.name)

        matched_key = None
        for (existing_name, existing_team) in groups:
            if existing_team != team:
                continue
            similarity = max(
                fuzz.ratio(norm_name, existing_name),
                fuzz.partial_ratio(norm_name, existing_name),
            )
            if similarity >= 85:
                matched_key = (existing_name, existing_team)
                break

        if matched_key:
            groups[matched_key].append(record)
        else:
            groups[(norm_name, team)] = [record]

    display_groups: dict = {}
    for recs in groups.values():
        best_name = max((r.name for r in recs), key=len)
        best_team = max((r.team for r in recs), key=len)
        display_groups[(best_name, best_team)] = recs
    return display_groups
