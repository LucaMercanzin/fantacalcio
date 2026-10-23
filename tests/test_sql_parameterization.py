"""Query parametrizzate: valori utente sempre come parametri, mai nel testo SQL.

1. Guardia statica: ogni execute() costruito con f-string, concatenazione o
   chiamata viene confrontato con un elenco revisionato. Se compare un nuovo
   SQL dinamico il test fallisce: va verificato che l'interpolazione usi solo
   identificatori fissi (tabelle, colonne, costanti), mai input utente, e poi
   aggiunto qui.
2. Test di comportamento: stringhe tipo SQL-injection passate come valori
   restano testo e non alterano lo schema.
"""

import ast
import pathlib

from dashboard.data_access import find_player_by_name
from db import repository
from db.connection import get_connection, init_db

ROOT = pathlib.Path(__file__).resolve().parent.parent
SQL_METHODS = {"execute", "executemany", "executescript"}

# (file, tipo, nomi interpolati) revisionati: solo identificatori e costanti del codice.
REVIEWED_DYNAMIC_SQL = {
    ("db/connection.py", "fstring", ("table",)),
    ("db/connection.py", "fstring", ("column",)),
    ("db/connection.py", "fstring", ("', '.join(unique_cols)", "table")),
    ("db/connection.py", "fstring", ("table", "table")),
    ("db/repository.py", "fstring", ("date_column", "table")),
    ("db/repository.py", "fstring", ("table",)),
    ("db/repository.py", "concat", ("_EXCLUDE_HISTORICAL", "_EXCLUDE_INACTIVE", "_EXCLUDE_REJECTED_MATCHES")),
    ("db/repository.py", "concat", ("_COMPLETED_SEASON_APPEARANCES_MIN", "_EXCLUDE_HISTORICAL", "_EXCLUDE_INACTIVE", "_EXCLUDE_REJECTED_MATCHES")),
    ("db/repository.py", "concat", ("HISTORICAL_SOURCE_SUFFIX",)),
    ("db/repository.py", "concat", ("_EXCLUDE_HISTORICAL", "_EXCLUDE_REJECTED_MATCHES")),
}


def _dynamic_sql_sites():
    found = set()
    files = list((ROOT / "db").glob("*.py")) + list((ROOT / "dashboard").glob("*.py"))
    files += list((ROOT / "dashboard" / "pages").glob("*.py"))
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in SQL_METHODS and node.args):
                continue
            arg = node.args[0]
            rel = path.relative_to(ROOT).as_posix()
            if isinstance(arg, ast.JoinedStr):
                names = tuple(ast.unparse(v.value) for v in arg.values if isinstance(v, ast.FormattedValue))
                found.add((rel, "fstring", names))
            elif isinstance(arg, ast.BinOp):
                names = tuple(sorted({ast.unparse(n) for n in ast.walk(arg)
                                      if isinstance(n, (ast.Name, ast.Attribute))}))
                found.add((rel, "concat", names))
            elif isinstance(arg, ast.Call):
                found.add((rel, "call", (ast.unparse(arg.func),)))
    return found


def test_dynamic_sql_only_uses_reviewed_identifiers():
    unexpected = _dynamic_sql_sites() - REVIEWED_DYNAMIC_SQL
    assert not unexpected, f"SQL dinamico non revisionato: {sorted(unexpected)}"


def _db(tmp_path):
    db_path = str(tmp_path / "sql.db")
    init_db(db_path)
    return get_connection(db_path)


def test_injection_string_as_opponent_name_is_stored_as_text(tmp_path):
    conn = _db(tmp_path)
    player_id = repository.upsert_player(conn, "Osimhen Victor", "Napoli", "A", "Pu", None)
    payload = "x'); DROP TABLE opponent_picks; --"
    repository.add_opponent_pick(conn, player_id, payload, 30.0, "2026-10-17")

    stored = conn.execute(
        "SELECT opponent_name FROM opponent_picks WHERE player_id = ?", (player_id,)
    ).fetchone()[0]
    assert stored == payload
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "opponent_picks" in tables
    conn.close()


def test_injection_string_in_player_lookup_matches_nothing(tmp_path):
    conn = _db(tmp_path)
    repository.upsert_player(conn, "Osimhen Victor", "Napoli", "A", "Pu", None)
    assert find_player_by_name(conn, "' OR '1'='1") is None
    assert find_player_by_name(conn, "Osimhen Victor")["canonical_name"] == "Osimhen Victor"
    conn.close()


def test_roster_price_and_name_are_bound_parameters(tmp_path):
    conn = _db(tmp_path)
    player_id = repository.upsert_player(conn, "Leao Rafael", "Milan", "A", "Pu", None)
    repository.add_roster_entry(conn, player_id, 12.0, "2026-10-17")
    repository.add_roster_entry(conn, player_id, 15.0, "2026-10-18")  # upsert, non duplicato
    rows = conn.execute("SELECT price_paid FROM my_roster WHERE player_id = ?", (player_id,)).fetchall()
    assert [r[0] for r in rows] == [15.0]
    conn.close()
