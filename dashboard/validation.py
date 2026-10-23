"""Validazione lato server degli input dei form prima di ogni scrittura.

I messaggi di `InputError` sono in italiano e possono essere mostrati all'utente
cosi' come sono. Nessun valore digitato viene riportato nei log.
"""

import math
import unicodedata

from config import TOTAL_CREDITS

MAX_OPPONENT_NAME_LENGTH = 60
MAX_WEIGHT = 10.0


class InputError(ValueError):
    """Input non valido: il messaggio e' pensato per l'utente."""


def validate_price(value, max_price: int = TOTAL_CREDITS) -> int:
    """Prezzo in crediti: numero intero tra 1 e `max_price` (budget totale)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError("Il prezzo deve essere un numero.")
    if isinstance(value, float) and (not math.isfinite(value) or value != int(value)):
        raise InputError("Il prezzo deve essere un numero intero di crediti.")
    price = int(value)
    if not 1 <= price <= max_price:
        raise InputError(f"Il prezzo deve essere tra 1 e {max_price} crediti.")
    return price


def validate_opponent_name(raw) -> str:
    """Nome dell'avversario: testo non vuoto, senza caratteri di controllo, max 60."""
    if not isinstance(raw, str):
        raise InputError("Indica il nome dell'avversario.")
    name = raw.strip()
    if not name:
        raise InputError("Indica il nome dell'avversario.")
    if len(name) > MAX_OPPONENT_NAME_LENGTH:
        raise InputError(
            f"Il nome dell'avversario è troppo lungo (massimo {MAX_OPPONENT_NAME_LENGTH} caratteri)."
        )
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise InputError("Il nome contiene caratteri non validi.")
    return name


def validate_weight(value) -> float:
    """Peso di una fonte: numero finito tra 0 e MAX_WEIGHT."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InputError("Il peso deve essere un numero.")
    if not 0 <= value <= MAX_WEIGHT:
        raise InputError(f"Il peso deve essere tra 0 e {MAX_WEIGHT:g}.")
    return float(value)
