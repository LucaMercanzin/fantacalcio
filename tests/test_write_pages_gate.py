"""Le pagine che scrivono mostrano le azioni disabilitate senza accesso.
Le pagine con dati personali, avversari o foto non mostrano nulla senza accesso.

Usa una COPIA di data/fantacalcio.db (tmp_path): il file tracciato non viene mai
modificato. Se il DB non esiste il test viene saltato.
"""

import pathlib
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from dashboard import access
from dashboard import common
from dashboard.access import ENV_NAME, GRANTED_KEY, MIN_ITERATIONS, hash_password

ROOT = pathlib.Path(__file__).resolve().parent.parent
REAL_DB = ROOT / "data" / "fantacalcio.db"
ROSA = str(ROOT / "dashboard" / "pages" / "5_La_Mia_Rosa.py")
MONITOR = str(ROOT / "dashboard" / "pages" / "7_Monitoraggio.py")
READ_PAGES = {
    "portieri": "1_Portieri.py",
    "difensori": "2_Difensori.py",
    "centrocampisti": "3_Centrocampisti.py",
    "attaccanti": "4_Attaccanti.py",
    "rosa": "5_La_Mia_Rosa.py",
    "dettaglio": "6_Dettaglio_Giocatore.py",
}


@pytest.fixture
def db_copy(tmp_path, monkeypatch):
    if not REAL_DB.exists():
        pytest.skip("data/fantacalcio.db non presente")
    copy = tmp_path / "fantacalcio.db"
    shutil.copy2(REAL_DB, copy)
    monkeypatch.setattr(common, "DB_PATH", str(copy))
    monkeypatch.setattr(access, "_read_secret_value", lambda: None)
    monkeypatch.delenv(ENV_NAME, raising=False)
    return copy


def _buttons(at, label):
    return [b for b in at.button if b.label == label]


def test_rosa_page_without_secret_is_fail_closed(db_copy):
    at = AppTest.from_file(ROSA, default_timeout=300).run()
    assert not at.exception
    assert any("non e' configurata" in w.value for w in at.warning)
    assert not [t for t in at.text_input if t.key in ("read-password-rosa", "write-password-rosa")]
    assert not _buttons(at, "Registra acquisto")
    assert not _buttons(at, "Rimuovi")
    assert not [s for s in at.subheader if s.value == "Giocatori acquistati"]


def test_rosa_page_locked_with_secret_shows_only_login(db_copy, monkeypatch):
    monkeypatch.setenv(ENV_NAME, hash_password("correct-test-pw", iterations=MIN_ITERATIONS))
    at = AppTest.from_file(ROSA, default_timeout=300).run()
    assert not at.exception
    assert [t for t in at.text_input if t.key == "read-password-rosa"]
    assert not _buttons(at, "Registra acquisto")
    assert not _buttons(at, "Rimuovi")
    assert not [s for s in at.subheader if s.value == "Giocatori acquistati"]


def test_rosa_page_with_access_enables_writes(db_copy, monkeypatch):
    monkeypatch.setenv(ENV_NAME, hash_password("correct-test-pw", iterations=MIN_ITERATIONS))
    at = AppTest.from_file(ROSA, default_timeout=300)
    at.session_state[GRANTED_KEY] = True
    at.run()
    assert not at.exception
    submit = _buttons(at, "Registra acquisto")
    assert submit and not any(b.disabled for b in submit)
    assert [b for b in at.button if b.label == "Esci"]


@pytest.mark.parametrize("scope, filename", sorted(READ_PAGES.items()))
def test_protected_read_pages_show_only_login_without_access(db_copy, monkeypatch, scope, filename):
    monkeypatch.setenv(ENV_NAME, hash_password("correct-test-pw", iterations=MIN_ITERATIONS))
    path = str(ROOT / "dashboard" / "pages" / filename)
    at = AppTest.from_file(path, default_timeout=300).run()
    assert not at.exception
    assert [t for t in at.text_input if t.key == f"read-password-{scope}"]
    assert [b.label for b in at.button] == ["Sblocca pagina"]


@pytest.mark.parametrize("scope, filename", sorted(READ_PAGES.items()))
def test_protected_read_pages_fail_closed_without_secret(db_copy, scope, filename):
    path = str(ROOT / "dashboard" / "pages" / filename)
    at = AppTest.from_file(path, default_timeout=300).run()
    assert not at.exception
    assert any("non e' configurata" in w.value for w in at.warning)
    assert not at.button
    assert not at.text_input


@pytest.mark.parametrize("scope, filename", sorted(READ_PAGES.items()))
def test_protected_read_pages_render_with_access(db_copy, monkeypatch, scope, filename):
    monkeypatch.setenv(ENV_NAME, hash_password("correct-test-pw", iterations=MIN_ITERATIONS))
    path = str(ROOT / "dashboard" / "pages" / filename)
    at = AppTest.from_file(path, default_timeout=300)
    at.session_state[GRANTED_KEY] = True
    at.run()
    assert not at.exception
    assert [b for b in at.button if b.label == "Esci"]
    assert not [t for t in at.text_input if t.key == f"read-password-{scope}"]


def test_monitoraggio_page_without_access_disables_writes(db_copy):
    at = AppTest.from_file(MONITOR, default_timeout=300).run()
    assert not at.exception
    save = _buttons(at, "Salva")
    assert save and all(b.disabled for b in save)
    review = [b for b in at.button if b.key and str(b.key).startswith(("confirm-", "unsure-", "reject-"))]
    assert all(b.disabled for b in review)


def test_privacy_page_renders_without_exception():
    at = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "8_Privacy.py"), default_timeout=60).run()
    assert not at.exception
    assert any("Privacy" in t.value for t in at.title)
