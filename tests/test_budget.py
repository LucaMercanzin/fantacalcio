from ranking.budget import compute_budget_summary


def test_compute_budget_summary_tracks_spent_and_slots():
    roster_rows = [
        {"role_classic": "A", "price_paid": 40},
        {"role_classic": "A", "price_paid": 30},
        {"role_classic": "P", "price_paid": 10},
    ]

    summary = compute_budget_summary(roster_rows)

    assert summary["total_credits"] == 500
    assert summary["spent"] == 80
    assert summary["remaining"] == 420
    assert summary["slots"]["A"] == {"filled": 2, "total": 6, "remaining": 4}
    assert summary["slots"]["P"] == {"filled": 1, "total": 3, "remaining": 2}
    assert summary["slots"]["D"] == {"filled": 0, "total": 8, "remaining": 8}
    assert summary["slots"]["C"] == {"filled": 0, "total": 8, "remaining": 8}
