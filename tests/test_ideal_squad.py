"""Le formazioni supportate dalla Rosa Ideale.

L'euristica greedy che questo modulo conteneva è stata rimossa
(docs/superpowers/specs/2026-09-01-rosa-ideale-indice-qualita-design.md); il
comportamento della Rosa Ideale è ora coperto dai test di
dashboard.data_access.get_ideal_squad in tests/test_data_access.py.
"""

from ranking.ideal_squad import FORMATIONS


def test_every_formation_fields_eleven_players():
    for name, formation in FORMATIONS.items():
        assert sum(formation.values()) == 11, name


def test_every_formation_has_exactly_one_goalkeeper():
    for name, formation in FORMATIONS.items():
        assert formation["P"] == 1, name
