from ranking.budget import compute_budget_summary, compute_role_budget_plan


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
    assert summary["slots"]["A"] == {"filled": 2, "total": 6, "remaining": 4, "spent": 70}
    assert summary["slots"]["P"] == {"filled": 1, "total": 3, "remaining": 2, "spent": 10}
    assert summary["slots"]["D"] == {"filled": 0, "total": 8, "remaining": 8, "spent": 0.0}
    assert summary["slots"]["C"] == {"filled": 0, "total": 8, "remaining": 8, "spent": 0.0}
    # P1-012/TASK-018: 22 slots remain empty (25 total - 3 filled); spendable
    # reserves 1 credit for each of the 21 *other* than the one being priced.
    assert summary["remaining"] - summary["spendable"] == 21


def test_compute_budget_summary_spendable_reserves_a_credit_per_empty_slot():
    """TASK-018/P1-012: with a full 500-credit budget and 25 empty slots,
    "remaining" alone would let a single candidate cost the whole budget,
    leaving 0 credits for the other 24 (real leagues require >=1 credit per
    player) — spendable must reserve for them."""
    summary = compute_budget_summary([])

    assert summary["remaining"] == 500
    assert summary["spendable"] == 500 - 24


def test_compute_budget_summary_spendable_is_never_negative():
    # Overspent role (shouldn't happen in practice, but spendable must not
    # go negative if it does).
    roster_rows = [{"role_classic": "A", "price_paid": 499}]

    summary = compute_budget_summary(roster_rows)

    assert summary["spendable"] >= 0


def test_compute_role_budget_plan_targets_sum_to_remaining():
    roster_rows = [{"role_classic": "A", "price_paid": 40}]
    summary = compute_budget_summary(roster_rows)

    plan = compute_role_budget_plan(summary)

    assert sum(p["remaining_target"] for p in plan.values()) == summary["remaining"]
    # 46% of 500 = 230 initial target for attaccanti, minus the 40 already spent
    assert plan["A"]["initial_target"] == 230
    assert plan["A"]["remaining_target"] == 190
    assert plan["A"]["remaining_slots"] == 5
    assert plan["A"]["avg_per_remaining_slot"] == 38.0
    assert plan["A"]["over_budget"] is False


def test_compute_role_budget_plan_flags_over_budget_role():
    roster_rows = [{"role_classic": "P", "price_paid": 50}]  # way over the 30-credit P share
    summary = compute_budget_summary(roster_rows)

    plan = compute_role_budget_plan(summary)

    assert plan["P"]["remaining_target"] == -20
    assert plan["P"]["over_budget"] is True
    # still sums correctly even when one role is negative
    assert sum(p["remaining_target"] for p in plan.values()) == summary["remaining"]
