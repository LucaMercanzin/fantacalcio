from config import CURRENT_SEASON
from db import repository
from db.connection import get_connection, init_db
from pipeline.season_resolution import resolve_row, resolve_stats_seasons

# (season, appearances, avg_rating) — la forma delle ancore etichettate che
# fantacalciopedia pubblica sulla pagina di dettaglio.
ANCHORS = [("2025/26", 35, 6.39), ("2024/25", 32, 6.33), ("2023/24", 16, 5.94)]


def test_appearances_and_rating_together_identify_the_season():
    assert resolve_row(32, 6.33, ANCHORS) == ("2024/25", "matched:2")


def test_rating_rounding_does_not_break_the_match():
    """6,39 pubblicato come 6,4 su un'altra pagina è lo stesso numero."""
    assert resolve_row(35, 6.4, ANCHORS) == ("2025/26", "matched:2")


def test_appearances_alone_are_enough_when_unique():
    assert resolve_row(16, None, ANCHORS) == ("2023/24", "matched:1")


def test_two_seasons_with_the_same_numbers_stay_unknown():
    """Ambiguo deve restare NULL: scegliere a caso è peggio del non sapere."""
    ambiguous = [("2025/26", 30, 6.0), ("2024/25", 30, 6.0)]
    assert resolve_row(30, 6.0, ambiguous) == (None, None)
    assert resolve_row(30, None, ambiguous) == (None, None)


def test_no_anchors_at_all_stays_unknown():
    assert resolve_row(20, 6.5, []) == (None, None)


def test_rollover_is_inferred_only_with_a_completed_season_behind():
    """La pagina è appena passata alla stagione nuova: 1 presenza contro
    stagioni concluse da 35, 32 e 16. È l'unica inferenza ammessa e si
    dichiara come tale."""
    assert resolve_row(1, 9.5, ANCHORS) == (CURRENT_SEASON, "inferred:rollover")


def test_a_debutant_is_not_assumed_to_be_a_rollover():
    """Senza una stagione conclusa alle spalle non c'è nessun rollover da
    dedurre: potrebbe essere un esordiente qualunque."""
    assert resolve_row(1, 6.0, [("2025/26", 3, 6.0)]) == (None, None)


def test_unmatched_midrange_appearances_stay_unknown():
    """20 presenze non combaciano con nessuna stagione e non sono poche
    abbastanza da essere un rollover: nessuna conclusione."""
    assert resolve_row(20, 6.5, ANCHORS) == (None, None)


def test_row_without_appearances_stays_unknown():
    assert resolve_row(None, 6.5, ANCHORS) == (None, None)


def _seed(conn):
    player_id = repository.upsert_player(conn, "Tizio Caio", "Inter", "C", None, None)
    repository.upsert_player_season_stats(
        conn, player_id, "fantacalciopedia",
        [
            {"season": season, "appearances": apps, "avg_rating": rating,
             "assists": 0, "yellow_cards": 0, "red_cards": 0}
            for season, apps, rating in ANCHORS
        ],
        "2026-08-31",
    )
    return player_id


def test_resolve_fills_the_column_and_records_the_basis(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = _seed(conn)

    repository.insert_quotation(
        conn, player_id, "fantacalciopedia", "2026-08-26",
        10, None, None, 7.1, 6.39, 35,
    )
    result = resolve_stats_seasons(conn, "2026-08-26")

    row = conn.execute(
        "SELECT stats_season, stats_season_basis FROM quotations"
    ).fetchone()
    assert (row["stats_season"], row["stats_season_basis"]) == ("2025/26", "matched:2")
    assert result["resolved"] == 1
    conn.close()


def test_a_declared_season_is_never_overwritten(tmp_path):
    """fantacalcio_online scrive la stagione sulla pagina: quel dato vale
    più di qualunque riconoscimento fatto qui, anche se i numeri portano
    altrove."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = _seed(conn)

    repository.insert_quotation(
        conn, player_id, "fantacalcio_online", "2026-08-26",
        10, None, None, None, 6.33, 32, stats_season="2025/26",
    )
    resolve_stats_seasons(conn, "2026-08-26")

    row = conn.execute(
        "SELECT stats_season, stats_season_basis FROM quotations"
    ).fetchone()
    assert (row["stats_season"], row["stats_season_basis"]) == ("2025/26", "declared")
    conn.close()
