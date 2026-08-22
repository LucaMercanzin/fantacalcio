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


def match_records(records: list) -> dict:
    groups: dict = {}

    for record in records:
        team = record.team
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
    for (_, team), recs in groups.items():
        best_name = max((r.name for r in recs), key=len)
        display_groups[(best_name, team)] = recs
    return display_groups
