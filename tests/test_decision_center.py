from dashboard.data_access import DECISION_BUCKETS, get_decision_center
from db import repository
from db.connection import get_connection, init_db


def _add_player(conn, name, price, fantamedia, appearances=32, status="ok", team="Roma"):
    pid = repository.upsert_player(conn, name, team, "A", "Pu", None)
    repository.insert_quotation(
        conn, pid, "fantacalcio_it", "2026-08-22",
        price_current=price, price_initial=price, status=status,
        fantamedia=fantamedia, avg_rating=fantamedia, appearances=appearances,
    )
    repository.insert_quotation(
        conn, pid, "fantapazz", "2026-08-22",
        price_current=price, price_initial=price, status=status,
        fantamedia=fantamedia, avg_rating=fantamedia, appearances=appearances,
    )
    return pid


def _build_role_population(conn):
    # A spread of "average" attackers so percentile-based tiers/scarcity have
    # something to compare against.
    for i in range(10):
        _add_player(conn, f"Average {i}", price=15 + i, fantamedia=6.0 + i * 0.05)

    bargain = _add_player(conn, "Cheap Standout", price=3, fantamedia=7.6)
    injured = _add_player(conn, "Injured Star", price=40, fantamedia=7.8, status="infortunato")
    # A separately-priced reference so per-source p99 (compute_source_scale_
    # factors, TASK-001) isn't set by "Injured Star" itself — otherwise its
    # own raw price rescales to exactly the canonical ceiling and, converted
    # to auction credits, lands right at the full 500-credit budget, making
    # it (spuriously) unaffordable and dropped from every bucket (P1-012/
    # TASK-018: candidates are now filtered on the budget actually left
    # after reserving 1 credit per still-empty slot, not the raw total).
    _add_player(conn, "Reference Filler", price=999, fantamedia=5.0)
    return bargain, injured


def test_decision_center_returns_all_buckets(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _build_role_population(conn)

    result = get_decision_center(conn)

    assert set(result.keys()) == set(DECISION_BUCKETS)
    for bucket in DECISION_BUCKETS:
        assert isinstance(result[bucket], list)
    conn.close()


def test_cheap_high_scoring_player_is_a_buy(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    bargain, _ = _build_role_population(conn)

    result = get_decision_center(conn)

    buy_ids = {r["player_id"] for r in result["buy"]}
    assert bargain in buy_ids
    conn.close()


def test_injured_player_is_flagged_evita(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _, injured = _build_role_population(conn)

    result = get_decision_center(conn)

    evita_ids = {r["player_id"] for r in result["evita"]}
    assert injured in evita_ids
    conn.close()


def test_entries_carry_price_engine_and_marginal_value_fields(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _build_role_population(conn)

    result = get_decision_center(conn)
    any_entry = next(r for bucket in result.values() for r in bucket)

    for key in ("scarcity", "replacement_advantage", "marginal_squad_value",
                "price_fair_price", "price_max_price", "price_status", "reason"):
        assert key in any_entry
    conn.close()
