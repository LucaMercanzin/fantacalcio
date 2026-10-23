"""Validazione lato server degli input dei form (dashboard/validation.py)."""

import pytest

from config import TOTAL_CREDITS
from dashboard.validation import (
    MAX_OPPONENT_NAME_LENGTH,
    InputError,
    validate_opponent_name,
    validate_price,
    validate_weight,
)


@pytest.mark.parametrize("value", [1, TOTAL_CREDITS, 42.0])
def test_price_accepts_integers_in_range(value):
    assert validate_price(value) == int(value)


@pytest.mark.parametrize("value", [0, -1, TOTAL_CREDITS + 1, 1e308])
def test_price_rejects_out_of_range(value):
    with pytest.raises(InputError):
        validate_price(value)


@pytest.mark.parametrize("value", [2.5, float("nan"), float("inf"), "10", None, True])
def test_price_rejects_non_integer_or_non_numeric(value):
    with pytest.raises(InputError):
        validate_price(value)


def test_opponent_name_is_stripped():
    assert validate_opponent_name("  Mario Rossi  ") == "Mario Rossi"


@pytest.mark.parametrize("value", ["", "   ", None, 123])
def test_opponent_name_rejects_empty_or_non_text(value):
    with pytest.raises(InputError):
        validate_opponent_name(value)


def test_opponent_name_length_limit():
    assert validate_opponent_name("a" * MAX_OPPONENT_NAME_LENGTH)
    with pytest.raises(InputError):
        validate_opponent_name("a" * (MAX_OPPONENT_NAME_LENGTH + 1))


@pytest.mark.parametrize("value", ["Mario\x00Rossi", "Mario\nRossi", "Mario‮Rossi"])
def test_opponent_name_rejects_control_characters(value):
    with pytest.raises(InputError):
        validate_opponent_name(value)


def test_opponent_name_keeps_sql_metacharacters_as_plain_text():
    # Non e' una regola SQL (la query e' parametrizzata): verifica solo che il valore
    # passi come testo, senza essere alterato o scartato.
    raw = "O'Brien'); DROP TABLE players;--"
    assert validate_opponent_name(raw) == raw


@pytest.mark.parametrize("value", [0, 0.5, 10, 10.0])
def test_weight_accepts_range(value):
    assert validate_weight(value) == float(value)


@pytest.mark.parametrize("value", [-0.5, 10.5, float("nan"), float("inf"), "1", None])
def test_weight_rejects_out_of_range_or_invalid(value):
    with pytest.raises(InputError):
        validate_weight(value)
