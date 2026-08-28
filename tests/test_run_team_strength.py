from unittest.mock import MagicMock, patch

from db import repository
from db.connection import get_connection, init_db
from pipeline import run_team_strength

FAKE_RECORDS = [
    {"team": "Atalanta", "xg": 1.81, "xga": 1.36, "ppda": 10.6},
    {"team": "Frosinone", "xg": None, "xga": None, "ppda": None},
]


def test_run_saves_records_and_counts_understat_coverage(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    fake_scraper = MagicMock()
    fake_scraper.fetch.return_value = FAKE_RECORDS
    with patch.object(run_team_strength, "FantanalisiSquadreScraper", return_value=fake_scraper):
        result = run_team_strength.run(conn)

    assert result == {"teams": 2, "with_understat_data": 1}
    latest = repository.get_all_latest_team_strength(conn)
    assert latest["Atalanta"]["xg"] == 1.81
    assert latest["Frosinone"]["xg"] is None
    conn.close()
