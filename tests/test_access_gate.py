"""Test del cancello di accesso alle scritture (dashboard/access.py).

Le parti pure (hash, attesa crescente) sono testate direttamente. Il comportamento
a schermo (form, messaggi, logout) e' testato con streamlit.testing.AppTest su uno
script minimo che usa require_write_access.
"""

import hmac

import pytest
from streamlit.testing.v1 import AppTest

from dashboard import access
from dashboard.access import (
    ENV_NAME,
    GRANTED_KEY,
    MAX_CANDIDATE_LENGTH,
    MIN_ITERATIONS,
    delay_for_failures,
    hash_password,
    record_failure,
    seconds_blocked,
    verify_password,
)

CORRECT = "correct-test-pw"
GATE_SCRIPT = """
import streamlit as st
from dashboard.access import require_write_access
allowed = require_write_access("test")
st.write("ALLOWED" if allowed else "DENIED")
"""


@pytest.fixture
def stored_hash():
    # Iterazioni ridotte solo per velocita' nei test; il default e' 600000.
    return hash_password(CORRECT, iterations=MIN_ITERATIONS)


@pytest.fixture
def no_secrets_file(monkeypatch):
    """Isola il test da un eventuale .streamlit/secrets.toml locale."""
    monkeypatch.setattr(access, "_read_secret_value", lambda: None)
    monkeypatch.delenv(ENV_NAME, raising=False)


def _button(at, label):
    return [b for b in at.button if b.label == label][0]


def _output(at):
    return at.markdown[-1].value if at.markdown else ""


def _written(at):
    return [m.value for m in at.markdown]


# --- parti pure -----------------------------------------------------------

def test_hash_has_expected_format_and_verifies(stored_hash):
    parts = stored_hash.split("$")
    assert parts[0] == "pbkdf2_sha256"
    assert parts[1] == str(MIN_ITERATIONS)
    assert len(parts[2]) == 32 and len(parts[3]) == 64
    assert verify_password(CORRECT, stored_hash) is True


def test_verify_rejects_wrong_empty_and_oversized_candidates(stored_hash):
    assert verify_password("wrong-test-pw", stored_hash) is False
    assert verify_password("", stored_hash) is False
    assert verify_password("x" * (MAX_CANDIDATE_LENGTH + 1), stored_hash) is False
    assert verify_password(None, stored_hash) is False


def test_verify_rejects_malformed_or_weak_stored_hashes():
    assert verify_password(CORRECT, "garbage") is False
    assert verify_password(CORRECT, "") is False
    assert verify_password(CORRECT, "pbkdf2_sha256$10$00$00") is False  # iterazioni troppo basse
    assert verify_password(CORRECT, "md5$600000$00$00") is False
    assert verify_password(CORRECT, None) is False


def test_compare_uses_hmac_compare_digest(stored_hash, monkeypatch):
    calls = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(access.hmac, "compare_digest", spy)
    assert verify_password(CORRECT, stored_hash) is True
    assert len(calls) == 1


def test_invalid_configured_hash_is_ignored_fail_closed(monkeypatch):
    monkeypatch.setattr(access, "_read_secret_value", lambda: None)
    monkeypatch.setenv(ENV_NAME, "non-un-hash")
    assert access.get_configured_hash() is None


def test_configured_hash_prefers_secrets_then_env(monkeypatch, stored_hash):
    other = hash_password("altra", iterations=MIN_ITERATIONS)
    monkeypatch.setattr(access, "_read_secret_value", lambda: stored_hash)
    monkeypatch.setenv(ENV_NAME, other)
    assert access.get_configured_hash() == stored_hash
    monkeypatch.setattr(access, "_read_secret_value", lambda: None)
    assert access.get_configured_hash() == other


def test_delay_schedule_grows_and_is_capped():
    assert [delay_for_failures(n) for n in (0, 1, 2)] == [0, 0, 0]
    assert [delay_for_failures(n) for n in (3, 4, 5)] == [5, 10, 20]
    assert delay_for_failures(50) == access.MAX_DELAY_SECONDS


def test_record_failure_blocks_only_after_threshold():
    state = {"failures": 0, "blocked_until": 0.0}
    state = record_failure(state, now=100.0)
    state = record_failure(state, now=100.0)
    assert seconds_blocked(state, now=100.0) == 0
    state = record_failure(state, now=100.0)
    assert seconds_blocked(state, now=101.0) == pytest.approx(4.0)
    assert seconds_blocked(state, now=106.0) == 0


# --- comportamento a schermo ----------------------------------------------

def test_fail_closed_without_secret_shows_warning_and_no_login(no_secrets_file):
    at = AppTest.from_string(GATE_SCRIPT).run()
    assert not at.exception
    assert _written(at)[-1] == "DENIED"
    assert any("non e' configurata" in w.value for w in at.warning)
    assert not [t for t in at.text_input if t.key == "write-password-test"]


def test_wrong_password_gets_generic_error(no_secrets_file, monkeypatch, stored_hash):
    monkeypatch.setattr(access, "_read_secret_value", lambda: stored_hash)
    at = AppTest.from_string(GATE_SCRIPT).run()
    at.text_input(key="write-password-test").input("wrong-test-pw")
    _button(at, "Sblocca modifiche").click().run()
    assert _written(at)[-1] == "DENIED"
    assert [e.value for e in at.error] == ["Password non valida."]


def test_correct_password_grants_access_and_logout_revokes(no_secrets_file, monkeypatch, stored_hash):
    monkeypatch.setattr(access, "_read_secret_value", lambda: stored_hash)
    at = AppTest.from_string(GATE_SCRIPT).run()
    at.text_input(key="write-password-test").input(CORRECT)
    _button(at, "Sblocca modifiche").click().run()
    assert _written(at)[-1] == "ALLOWED"
    _button(at, "Esci dalla modalità modifica").click().run()
    assert _written(at)[-1] == "DENIED"


def test_three_failures_block_even_correct_password(no_secrets_file, monkeypatch, stored_hash):
    monkeypatch.setattr(access, "_read_secret_value", lambda: stored_hash)
    at = AppTest.from_string(GATE_SCRIPT).run()
    for _ in range(3):
        at.text_input(key="write-password-test").input("wrong-test-pw")
        _button(at, "Sblocca modifiche").click().run()
    at.text_input(key="write-password-test").input(CORRECT)
    _button(at, "Sblocca modifiche").click().run()
    assert _written(at)[-1] == "DENIED"
    assert [e.value for e in at.error][-1] == "Troppi tentativi. Riprova più tardi."


# --- lettura protetta (require_read_access) -------------------------------

READ_SCRIPT = """
import streamlit as st
from dashboard.access import require_read_access
require_read_access("t")
st.write("CONTENT")
"""


def test_read_gate_fail_closed_without_secret(no_secrets_file):
    at = AppTest.from_string(READ_SCRIPT).run()
    assert not at.exception
    assert not [m for m in at.markdown if m.value == "CONTENT"]
    assert any("non e' configurata" in w.value for w in at.warning)
    assert not at.button


def test_read_gate_hides_content_until_correct_password(no_secrets_file, monkeypatch, stored_hash):
    monkeypatch.setattr(access, "_read_secret_value", lambda: stored_hash)
    at = AppTest.from_string(READ_SCRIPT).run()
    assert not [m for m in at.markdown if m.value == "CONTENT"]
    assert [t for t in at.text_input if t.key == "read-password-t"]
    at.text_input(key="read-password-t").input("wrong-test-pw")
    _button(at, "Sblocca pagina").click().run()
    assert not [m for m in at.markdown if m.value == "CONTENT"]
    assert [e.value for e in at.error] == ["Password non valida."]
    at.text_input(key="read-password-t").input(CORRECT)
    _button(at, "Sblocca pagina").click().run()
    assert [m for m in at.markdown if m.value == "CONTENT"]
    _button(at, "Esci").click().run()
    assert not [m for m in at.markdown if m.value == "CONTENT"]


def test_read_gate_shares_session_flag_with_write_gate(no_secrets_file, monkeypatch, stored_hash):
    monkeypatch.setattr(access, "_read_secret_value", lambda: stored_hash)
    at = AppTest.from_string(READ_SCRIPT)
    at.session_state[GRANTED_KEY] = True
    at.run()
    assert [m for m in at.markdown if m.value == "CONTENT"]
