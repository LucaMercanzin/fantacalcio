"""Cancello di accesso per le azioni che scrivono nel database.

Le pagine con dati personali o di terze persone (rosa, acquisti, avversari,
note, foto) passano da `require_read_access()`: senza accesso il contenuto non
viene mostrato. Le azioni che modificano dati (rosa, avversari, pesi delle fonti,
conferma dei match) passano da `require_write_access()`:

- la password non sta nel codice: l'hash arriva da `st.secrets`
  (chiave `WRITE_PASSWORD_HASH`) oppure dalla variabile d'ambiente
  `FANTACALCIO_WRITE_PASSWORD_HASH`. Contiene solo un hash PBKDF2-SHA256
  con sale, mai la password in chiaro;
- se l'hash manca o non e' valido le scritture restano disabilitate (fail-closed);
- il confronto usa `hmac.compare_digest`;
- i tentativi falliti sono limitati per sessione Streamlit, con attesa crescente;
- il messaggio d'errore e' sempre generico.

Limite noto: il contatore dei tentativi vive nella sessione Streamlit, quindi
aprendo una nuova sessione il contatore riparte da zero.

Generare l'hash: `python -m dashboard.access` (chiede la password senza mostrarla).
"""

import hashlib
import hmac
import logging
import math
import os
import secrets
import sqlite3
import time
from typing import Callable

import streamlit as st

logger = logging.getLogger(__name__)

SECRET_NAME = "WRITE_PASSWORD_HASH"
ENV_NAME = "FANTACALCIO_WRITE_PASSWORD_HASH"
PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
MIN_ITERATIONS = 100_000
MAX_CANDIDATE_LENGTH = 256
FREE_ATTEMPTS = 3
BASE_DELAY_SECONDS = 5
MAX_DELAY_SECONDS = 300

GRANTED_KEY = "_write_access_granted"
ATTEMPTS_KEY = "_write_access_attempts"


def hash_password(password: str, salt: bytes | None = None,
                  iterations: int = PBKDF2_ITERATIONS) -> str:
    """Restituisce la stringa da mettere in secrets: pbkdf2_sha256$iter$sale$hash."""
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{PBKDF2_ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def _parse_hash(stored: str):
    parts = stored.strip().split("$")
    if len(parts) != 4 or parts[0] != PBKDF2_ALGORITHM:
        return None
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except ValueError:
        return None
    if iterations < MIN_ITERATIONS or not salt or not expected:
        return None
    return iterations, salt, expected


def verify_password(candidate, stored_hash) -> bool:
    """True solo se `candidate` produce lo stesso hash di `stored_hash`."""
    if not isinstance(candidate, str) or not isinstance(stored_hash, str):
        return False
    if not candidate or len(candidate) > MAX_CANDIDATE_LENGTH:
        return False
    parsed = _parse_hash(stored_hash)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    digest = hashlib.pbkdf2_hmac("sha256", candidate.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def _read_secret_value():
    """Valore grezzo da st.secrets; None se il file manca o la chiave non c'e'."""
    try:
        return st.secrets.get(SECRET_NAME)
    except Exception:  # noqa: BLE001 - nessun file secrets: si passa all'ambiente
        return None


def get_configured_hash():
    """Hash valido da st.secrets o dalla variabile d'ambiente, altrimenti None."""
    value = _read_secret_value()
    if not value:
        value = os.environ.get(ENV_NAME)
    if not value or not isinstance(value, str):
        return None
    if _parse_hash(value) is None:
        logger.warning("Hash della password di scrittura non valido: scritture disabilitate")
        return None
    return value.strip()


def delay_for_failures(failures: int) -> int:
    """Secondi di attesa dopo il numero di tentativi falliti (0 sotto la soglia)."""
    if failures < FREE_ATTEMPTS:
        return 0
    return min(BASE_DELAY_SECONDS * 2 ** (failures - FREE_ATTEMPTS), MAX_DELAY_SECONDS)


def seconds_blocked(state: dict, now: float) -> float:
    return max(0.0, state.get("blocked_until", 0.0) - now)


def record_failure(state: dict, now: float) -> dict:
    failures = state.get("failures", 0) + 1
    delay = delay_for_failures(failures)
    return {"failures": failures, "blocked_until": now + delay if delay else 0.0}


def run_db_write(description: str, action: Callable, *args) -> bool:
    """Esegue una scrittura; in caso di errore SQLite mostra un messaggio generico.

    Nessuno stack trace verso l'utente. Nel log solo il tipo di errore, non i valori.
    """
    try:
        action(*args)
    except sqlite3.Error as exc:
        logger.error("Scrittura non riuscita (%s): %s", description, type(exc).__name__)
        st.error("Operazione non riuscita. Riprova; se il problema continua controlla i log.")
        return False
    return True


def _attempts_state() -> dict:
    return st.session_state.get(ATTEMPTS_KEY) or {"failures": 0, "blocked_until": 0.0}


def _logout(scope: str) -> None:
    st.session_state[GRANTED_KEY] = False
    st.rerun()


WRITE_CAPTION = (
    "Per registrare o modificare dati serve la password. "
    "La consultazione resta pubblica."
)
READ_CAPTION = (
    "Questa pagina mostra acquisti, avversari, note e foto. "
    "Per consultarla serve la password."
)
WRITE_UNCONFIGURED = (
    "Modifiche disabilitate: la password di scrittura non e' configurata "
    "su questo ambiente. Vedi README, sezione «Accesso in scrittura»."
)
READ_UNCONFIGURED = (
    "Pagina protetta: la password non e' configurata su questo ambiente, "
    "quindi il contenuto non e' disponibile. Vedi README, sezione «Accesso in scrittura»."
)


def _gate(scope: str, mode: str, *, caption: str, unconfigured: str,
          logout_label: str, show_logout: bool) -> bool:
    """Cancello condiviso da lettura e scrittura: stessa password, stesso flag di sessione."""
    stored = get_configured_hash()
    if stored is None:
        st.warning(unconfigured)
        return False

    if st.session_state.get(GRANTED_KEY):
        if show_logout and st.button(logout_label, key=f"{mode}-logout-{scope}"):
            _logout(scope)
        return True

    state = _attempts_state()
    wait = seconds_blocked(state, time.time())
    if wait > 0:
        st.caption(f"Tentativi sospesi: riprova tra {math.ceil(wait)} secondi.")

    with st.form(f"{mode}-login-{scope}"):
        st.markdown("**Modifiche protette**" if mode == "write" else "**Pagina protetta**")
        st.caption(caption)
        password = st.text_input(
            "Password", type="password", max_chars=MAX_CANDIDATE_LENGTH,
            key=f"{mode}-password-{scope}",
        )
        submitted = st.form_submit_button("Sblocca modifiche" if mode == "write" else "Sblocca pagina")

    if submitted:
        now = time.time()
        if seconds_blocked(state, now) > 0:
            st.error("Troppi tentativi. Riprova più tardi.")
        elif verify_password(password, stored):
            st.session_state[ATTEMPTS_KEY] = {"failures": 0, "blocked_until": 0.0}
            st.session_state[GRANTED_KEY] = True
            st.rerun()
        else:
            st.session_state[ATTEMPTS_KEY] = record_failure(state, now)
            logger.warning("Accesso negato (%s)", mode)
            st.error("Password non valida.")
    return False


def require_write_access(scope: str, show_logout: bool = True) -> bool:
    """Mostra il cancello di accesso e restituisce True se le scritture sono permesse.

    `scope` identifica la pagina/sezione e deve essere unico per run (chiave del form).
    `show_logout=False` se la pagina ha gia' un pulsante di uscita (vedi require_read_access).
    """
    return _gate(
        scope, "write", caption=WRITE_CAPTION, unconfigured=WRITE_UNCONFIGURED,
        logout_label="Esci dalla modalità modifica", show_logout=show_logout,
    )


def require_read_access(scope: str) -> bool:
    """Protegge il contenuto di una pagina: senza accesso lo script si ferma (st.stop).

    Fail-closed: anche senza hash configurato il contenuto non viene mostrato.
    Usa la stessa password e lo stesso flag di sessione di require_write_access:
    sbloccata la pagina, le scritture della sessione sono permesse.
    Chiamarla prima di qualunque lettura dal database.
    """
    allowed = _gate(
        scope, "read", caption=READ_CAPTION, unconfigured=READ_UNCONFIGURED,
        logout_label="Esci", show_logout=True,
    )
    if not allowed:
        st.stop()
    return True


if __name__ == "__main__":
    import getpass

    print(hash_password(getpass.getpass("Nuova password di scrittura: ")))
