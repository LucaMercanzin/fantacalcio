from config import ROLE_SLOTS, TOTAL_CREDITS

# Re-exported so existing `from ranking.budget import ROLE_SLOTS` call sites
# keep working unchanged — config.py is the single source of truth now
# (TASK-019/A4), this module no longer redefines it.
ROLE_SLOTS = ROLE_SLOTS

# Studied split for a classic 500-credit, 3-8-8-6 auction league: goals and
# assists (the biggest fantasy bonuses) come almost entirely from
# centrocampisti/attaccanti, so conventional Italian fantacalcio auction
# strategy front-loads the budget there and keeps portieri/difensori
# comparatively cheap (a backup goalkeeper or squad defender is rarely worth
# bidding up). Percentages sum to 1.0; at 500 credits this is P=30, D=80,
# C=160, A=230.
ROLE_BUDGET_PCT = {"P": 0.06, "D": 0.16, "C": 0.32, "A": 0.46}


def compute_budget_summary(roster_rows: list, total_credits: int = TOTAL_CREDITS) -> dict:
    spent = sum(row["price_paid"] for row in roster_rows)

    filled_by_role = {role: 0 for role in ROLE_SLOTS}
    spent_by_role = {role: 0.0 for role in ROLE_SLOTS}
    for row in roster_rows:
        role = row["role_classic"]
        if role in filled_by_role:
            filled_by_role[role] += 1
            spent_by_role[role] += row["price_paid"]

    slots = {
        role: {
            "filled": filled_by_role[role],
            "total": total,
            "remaining": total - filled_by_role[role],
            "spent": spent_by_role[role],
        }
        for role, total in ROLE_SLOTS.items()
    }

    remaining = total_credits - spent
    total_slots_remaining = sum(s["remaining"] for s in slots.values())
    return {
        "total_credits": total_credits,
        "spent": spent,
        "remaining": remaining,
        "slots": slots,
        # P1-012/TASK-018: "remaining" alone lets a single candidate cost the
        # entire remaining budget, leaving 0 for every other still-empty
        # slot — reserve at least 1 credit (the real minimum bid) for each
        # of those *other* slots first. Filter callers ("what can I afford
        # right now") should use this, not "remaining" (kept as-is for the
        # plain budget display).
        "spendable": max(0, remaining - max(0, total_slots_remaining - 1)),
    }


def compute_role_budget_plan(summary: dict) -> dict:
    """Per-role budget targets from ROLE_BUDGET_PCT, live-adjusted for what's
    already been spent in each role: a role's remaining target is its
    studied initial share minus what it has already cost (negative if that
    role ran over its share). These targets always sum exactly to
    summary["remaining"] — the initial shares sum to total_credits by
    construction and spent-by-role sums to total spent, so this is a
    per-role breakdown of the same real remaining budget, not a separate
    pool. Also reports the average per still-empty slot in that role, the
    number that actually matters for "what can I bid" during the auction.
    """
    total_credits = summary["total_credits"]
    plan = {}
    for role, pct in ROLE_BUDGET_PCT.items():
        slot = summary["slots"][role]
        initial_target = round(total_credits * pct)
        remaining_target = initial_target - slot["spent"]
        remaining_slots = slot["remaining"]
        avg_per_slot = (
            round(remaining_target / remaining_slots, 1) if remaining_slots > 0 else None
        )
        plan[role] = {
            "initial_target": initial_target,
            "spent": slot["spent"],
            "remaining_target": remaining_target,
            "remaining_slots": remaining_slots,
            "avg_per_remaining_slot": avg_per_slot,
            "over_budget": remaining_target < 0,
        }
    return plan
