from scrapers.fantanalisi import parse_rows

# Formato reale delle righe estratte via eval_on_selector_all: una lista di
# celle testo per riga, nell'ordine Mio, R, Nome, Status, Squadra, Qt, FVM,
# Fm att., Mv att., G+A, Pres, Prezzo, Aste live, Fasce affare, Max, Tier,
# Risk, Note (18 colonne).
MALEN_ROW = [
    "⭐🚫", "A", "Malen", "Titolare", "Roma", "36", "207", "7.72", "6.41",
    "25+4", "32", "240", "382", "≤168 · ≤216", "264", "1", "●", "🎯 Rig.",
]
STIMATO_ROW = [
    "⭐🚫", "P", "Riserva P.", "Riserva", "Como", "5", "8", "6.00", "6.00",
    "0+0", "5", "3", "~4", "≤2 · ≤3", "4", "5", "●●●", "",
]


def test_parse_rows_extracts_aste_live_as_price():
    records = parse_rows([MALEN_ROW])

    assert len(records) == 1
    malen = records[0]
    assert malen.name == "Malen"
    assert malen.team == "Roma"
    assert malen.role_classic == "A"
    assert malen.price_current == 382
    assert malen.source == "fantanalisi"


def test_parse_rows_treats_estimated_price_as_missing():
    records = parse_rows([STIMATO_ROW])

    assert records[0].price_current is None


def test_parse_rows_skips_incomplete_rows():
    assert parse_rows([["A", "Malen"]]) == []
