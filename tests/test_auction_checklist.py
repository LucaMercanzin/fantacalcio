from ranking.auction_checklist import build_checklist, current_phase
from ranking.budget import compute_budget_summary


def _row(player_id, role_classic, role_mantra=None, appearances=None,
         goals=0, assists=0, price_paid=None, price_current=None):
    return {
        "player_id": player_id, "canonical_name": f"Player{player_id}",
        "role_classic": role_classic, "role_mantra": role_mantra,
        "appearances": appearances, "season_goals_scored": goals,
        "season_assists": assists, "price_paid": price_paid,
        "price_current": price_current,
    }


def test_checklist_all_false_or_manual_on_empty_roster():
    checklist = build_checklist([])

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho un portiere titolare affidabile?"] is False
    assert statuses["Ho stabilito un prezzo massimo per i giocatori?"] is None


def test_checklist_flags_reliable_starting_goalkeeper():
    rows = [_row(1, "P", "POR", appearances=30)]

    checklist = build_checklist(rows)

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho un portiere titolare affidabile?"] is True


def test_checklist_flags_overpay():
    rows = [_row(1, "D", "DC", appearances=20, price_paid=50, price_current=20)]

    checklist = build_checklist(rows)

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho evitato di pagare il nome?"] is False


def test_checklist_no_overpay_flag_when_within_ratio():
    rows = [_row(1, "D", "DC", appearances=20, price_paid=20, price_current=18)]

    checklist = build_checklist(rows)

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho evitato di pagare il nome?"] is True


def test_current_phase_portieri_when_no_goalkeepers_owned():
    summary = compute_budget_summary([])

    phase = current_phase(summary)

    assert phase["role"] == "P"
    assert phase["label"] == "Fase 1 — Portieri"


def test_current_phase_completamento_when_all_slots_full():
    roster = (
        [{"role_classic": "P", "price_paid": 1}] * 3
        + [{"role_classic": "D", "price_paid": 1}] * 8
        + [{"role_classic": "C", "price_paid": 1}] * 8
        + [{"role_classic": "A", "price_paid": 1}] * 6
    )
    summary = compute_budget_summary(roster)

    phase = current_phase(summary)

    assert phase["role"] is None
    assert phase["label"] == "Fase 5 — Completamento"
