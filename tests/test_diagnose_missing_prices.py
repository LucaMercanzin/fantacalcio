"""La regola che decide "queste due righe sono la stessa persona" è la parte
pericolosa di scripts/diagnose_missing_prices.py: un prototipo fuzzy che
faceva questo lavoro dentro la pipeline è già stato provato e revertito
perché univa giocatori diversi (vedi db/repository.upsert_player). Questi
test bloccano la regola dove è stretta."""

from db import repository
from db.connection import get_connection, init_db, merge_players
from scripts.diagnose_missing_prices import find_split_identity

NEW = {"id": 900, "canonical_name": "Nkunku", "team": "MIL"}


def test_short_name_matches_the_older_full_name_in_the_same_team():
    others = [{"id": 59, "canonical_name": "Nkunku Christopher", "team": "Milan"}]
    assert find_split_identity(NEW, others)["id"] == 59


def test_a_different_team_is_a_different_person():
    others = [{"id": 59, "canonical_name": "Nkunku Christopher", "team": "Roma"}]
    assert find_split_identity(NEW, others) is None


def test_two_candidates_in_the_same_team_make_the_rule_refuse():
    """È il caso su cui il prototipo fuzzy sbagliava: con due omonimi la
    regola deve fallire, non scegliere."""
    others = [
        {"id": 59, "canonical_name": "Nkunku Christopher", "team": "Milan"},
        {"id": 60, "canonical_name": "Nkunku Jean", "team": "Milan"},
    ]
    assert find_split_identity(NEW, others) is None


def test_a_similar_but_different_surname_is_not_a_prefix():
    """Prefisso sui token, non distanza di edit: 'Nkunke' non è 'Nkunku'."""
    others = [{"id": 59, "canonical_name": "Nkunke Christopher", "team": "Milan"}]
    assert find_split_identity(NEW, others) is None


def test_a_middle_name_insertion_is_not_a_prefix():
    """'Di Gregorio' ⊂ 'Di Gregorio Michele' sì; 'Gregorio Michele' no."""
    others = [{"id": 59, "canonical_name": "Christopher Nkunku", "team": "Milan"}]
    assert find_split_identity(NEW, others) is None


def test_a_newer_candidate_is_never_chosen():
    """La storia sta sulla riga vecchia: si unisce nella più vecchia."""
    others = [{"id": 950, "canonical_name": "Nkunku Christopher", "team": "Milan"}]
    assert find_split_identity(NEW, others) is None


def test_merge_moves_quotations_and_deletes_the_duplicate(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    keep = repository.upsert_player(conn, "Nkunku Christopher", "Milan", "A", None, None)
    dup = repository.upsert_player(conn, "Nkunku", "MIL", "A", None, None)
    repository.insert_quotation(conn, keep, "fantapazz", "2026-08-26", 52, None, None, None, None, None)
    repository.insert_quotation(conn, dup, "fantacalcio_it", "2026-08-31", 13, None, None, None, None, None)

    merge_players(conn, keep, dup)
    conn.commit()

    sources = {r["source"] for r in conn.execute(
        "SELECT source FROM quotations WHERE player_id = ?", (keep,))}
    assert sources == {"fantapazz", "fantacalcio_it"}
    assert conn.execute("SELECT COUNT(*) FROM players WHERE id = ?", (dup,)).fetchone()[0] == 0
    conn.close()


def test_merge_drops_a_colliding_child_row_instead_of_failing(tmp_path):
    """Stesso (source, scrape_date) su entrambe le righe: la UNIQUE di
    quotations impedisce di spostarla, vince il dato già su keep."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    keep = repository.upsert_player(conn, "Nkunku Christopher", "Milan", "A", None, None)
    dup = repository.upsert_player(conn, "Nkunku", "MIL", "A", None, None)
    repository.insert_quotation(conn, keep, "fantacalcio_it", "2026-08-31", 13, None, None, None, None, None)
    repository.insert_quotation(conn, dup, "fantacalcio_it", "2026-08-31", 99, None, None, None, None, None)

    merge_players(conn, keep, dup)
    conn.commit()

    rows = conn.execute(
        "SELECT price_current FROM quotations WHERE player_id = ?", (keep,)).fetchall()
    assert [r["price_current"] for r in rows] == [13]
    conn.close()
