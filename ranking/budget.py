ROLE_SLOTS = {"P": 3, "D": 8, "C": 8, "A": 6}


def compute_budget_summary(roster_rows: list, total_credits: int = 500) -> dict:
    spent = sum(row["price_paid"] for row in roster_rows)

    filled_by_role = {role: 0 for role in ROLE_SLOTS}
    for row in roster_rows:
        role = row["role_classic"]
        if role in filled_by_role:
            filled_by_role[role] += 1

    slots = {
        role: {
            "filled": filled_by_role[role],
            "total": total,
            "remaining": total - filled_by_role[role],
        }
        for role, total in ROLE_SLOTS.items()
    }

    return {
        "total_credits": total_credits,
        "spent": spent,
        "remaining": total_credits - spent,
        "slots": slots,
    }
