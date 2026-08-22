PENALIZED_STATUSES = {"infortunato", "squalificato"}


def compute_score(row: dict) -> float:
    base = row.get("fantamedia")
    if base is None:
        base = row.get("avg_rating")
    if base is None:
        base = 0.0

    appearances = row.get("appearances")
    reliability = (min(appearances, 38) / 38) if appearances is not None else 0.5

    penalty = 15 if row.get("status") in PENALIZED_STATUSES else 0

    return base * 10 + reliability * 5 - penalty


def rank_players(rows: list) -> list:
    scored = []
    for row in rows:
        enriched = dict(row)
        enriched["score"] = compute_score(row)
        scored.append(enriched)
    return sorted(scored, key=lambda r: r["score"], reverse=True)
