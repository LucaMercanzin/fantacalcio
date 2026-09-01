"""Formazioni classiche supportate dalla Rosa Ideale.

Questo modulo conteneva anche un'euristica greedy (`build_ideal_squad`) che
costruiva la Rosa Ideale sotto vincolo di budget. È stata rimossa il
2026-09-01 (docs/superpowers/specs/2026-09-01-rosa-ideale-indice-qualita-
design.md): era dominata su ogni metrica dal solver LP che vive nella stessa
pagina, e nel frattempo la Rosa Ideale ha cambiato natura — è un indice di
qualità a budget illimitato, quindi non ha più un problema di ottimizzazione
da risolvere. Il calcolo vive ora in dashboard.data_access.get_ideal_squad.
"""

# Formazioni classiche supportate (P, D, C, A)
FORMATIONS = {
    "3-4-3": {"P": 1, "D": 3, "C": 4, "A": 3},
    "3-5-2": {"P": 1, "D": 3, "C": 5, "A": 2},
    "4-3-3": {"P": 1, "D": 4, "C": 3, "A": 3},
    "4-4-2": {"P": 1, "D": 4, "C": 4, "A": 2},
    "4-5-1": {"P": 1, "D": 4, "C": 5, "A": 1},
    "5-3-2": {"P": 1, "D": 5, "C": 3, "A": 2},
    "5-4-1": {"P": 1, "D": 5, "C": 4, "A": 1},
}
