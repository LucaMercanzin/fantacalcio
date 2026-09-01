"""Riconosce a quale stagione appartengono le statistiche di una quotazione.

Il problema (BACKLOG-2026-08-31 §6). Quattro fonti su sei pubblicano
presenze/media voto/fantamedia **senza dire di quale stagione parlano**, e a
fine agosto le fonti cambiano stagione sotto i piedi: lo scrape del 31/08 ha
reso i dati peggiori di quelli del 26/08 perché fantacalciopedia era passata
alla 2026/27 senza cambiare nulla nella pagina. La difesa messa in piedi il
31/08 (`consensus.engine._stats_eligible_rows`) funziona ma è un'euristica
sulle presenze: `<= 2 partite` contro `>= 10 partite` non possono essere la
stessa stagione. **Verso ottobre quella distanza sparisce** — la stagione in
corso supera le 10 giornate e la guardia smette di distinguere.

La soluzione qui è non inferire, ma *riconoscere*. `player_season_stats`
contiene, per 540 giocatori, presenze e media voto **etichettate con la
stagione** (fantacalciopedia le pubblica sulla pagina di dettaglio, dove il
grafico porta l'anno esplicito). Se la riga senza etichetta dice 35 presenze
e 6,39 di media, e l'unica stagione etichettata di quel giocatore con quei
due numeri è la 2025/26, allora quella riga *è* la 2025/26: non è una stima,
è un riconoscimento fatto sui dati della fonte stessa.

Tre esiti possibili, e sono tenuti distinti apposta in `stats_season_basis`:

- `matched:2` — presenze **e** media voto combaciano con una sola stagione.
  È il caso forte e quello di gran lunga più frequente.
- `matched:1` — combaciano le sole presenze (la fonte non pubblica la media,
  o l'ancora non ce l'ha) e una sola stagione le ha. Più debole ma ancora
  un riconoscimento, non un'ipotesi.
- `inferred:rollover` — nessuna stagione etichettata combacia, il giocatore
  ha almeno una stagione conclusa a referto e la riga ne dichiara pochissime:
  la pagina è appena rotolata sulla stagione nuova, che nelle ancore non c'è
  ancora. Questa è l'unica vera inferenza e si vede dal nome.

Ambiguo resta ambiguo: se due stagioni hanno gli stessi numeri, o se non c'è
nessuna ancora, la riga resta `NULL`. Un "non lo so" onesto vale più di
un'etichetta plausibile, perché a valle `stats_season` viene creduto.
"""

import logging

from config import CURRENT_SEASON

logger = logging.getLogger(__name__)

# Una stagione con meno partite di così, per un giocatore che ne ha almeno
# una conclusa alle spalle, è la stagione appena cominciata — non un'annata
# vera vista male. Stessa soglia di consensus.engine, e per lo stesso motivo:
# nessun giocatore ha 28 presenze e 1 presenza nella stessa stagione.
ROLLOVER_APPEARANCES_MAX = 2
COMPLETED_SEASON_APPEARANCES_MIN = 10

# Le presenze devono combaciare esatte; la media voto no. Le fonti la
# arrotondano a decimali diversi (6,39 contro 6,4) e confrontarla per
# uguaglianza stretta scarterebbe ancore corrette. Mezzo decimo è più largo
# di qualsiasi arrotondamento e più stretto della differenza fra due stagioni
# reali dello stesso giocatore.
AVG_RATING_TOLERANCE = 0.05


def _anchors_by_player(conn) -> dict:
    """player_id -> [(season, appearances, avg_rating)], solo stagioni con
    almeno le presenze note: un'ancora senza presenze non può ancorare
    niente. Caricate in blocco una volta sola perché il chiamante gira su
    migliaia di righe di `quotations` e una query per riga renderebbe questo
    passo più lento dello scraping che lo precede."""
    anchors = {}
    cursor = conn.execute(
        """
        SELECT player_id, season, appearances, avg_rating
        FROM player_season_stats
        WHERE appearances IS NOT NULL
          AND (competition IS NULL OR competition = 'serie_a')
        """
    )
    for row in cursor.fetchall():
        anchors.setdefault(row["player_id"], []).append(
            (row["season"], row["appearances"], row["avg_rating"])
        )
    return anchors


def resolve_row(appearances, avg_rating, anchors: list) -> tuple:
    """(season, basis) per una singola riga, o (None, None) se resta ignota.

    Pura di proposito: tutta la logica decidibile sta qui, senza database,
    così i casi limite (ambiguità, assenza di ancore, rollover) sono
    testabili senza montare uno schema."""
    if appearances is None:
        return (None, None)

    same_appearances = [a for a in anchors if a[1] == appearances]

    if avg_rating is not None:
        both = [
            a for a in same_appearances
            if a[2] is not None and abs(a[2] - avg_rating) <= AVG_RATING_TOLERANCE
        ]
        if len(both) == 1:
            return (both[0][0], "matched:2")
        if len(both) > 1:
            # Due stagioni identiche su presenze *e* media: non c'è modo di
            # sceglierne una, e sceglierla a caso sarebbe peggio del NULL.
            return (None, None)

    if len(same_appearances) == 1:
        return (same_appearances[0][0], "matched:1")
    if len(same_appearances) > 1:
        return (None, None)

    completed = [a for a in anchors if a[1] >= COMPLETED_SEASON_APPEARANCES_MIN]
    if completed and appearances <= ROLLOVER_APPEARANCES_MAX:
        return (CURRENT_SEASON, "inferred:rollover")

    return (None, None)


def resolve_stats_seasons(conn, scrape_date: str | None = None) -> dict:
    """Riempie `quotations.stats_season` dove è NULL, per uno scrape_date o
    per tutto lo storico se non passato.

    Non tocca mai una riga che ha già una stagione: quella di
    `fantacalcio_online` è dichiarata dalla fonte (`stats_season_basis =
    'declared'`) e vale più di qualsiasi riconoscimento fatto qui."""
    anchors = _anchors_by_player(conn)

    query = """
        SELECT id, player_id, source, appearances, avg_rating
        FROM quotations
        WHERE stats_season IS NULL AND appearances IS NOT NULL
    """
    params = ()
    if scrape_date:
        query += " AND scrape_date = ?"
        params = (scrape_date,)

    updates = []
    counts = {"matched:2": 0, "matched:1": 0, "inferred:rollover": 0, "unresolved": 0}
    for row in conn.execute(query, params).fetchall():
        season, basis = resolve_row(
            row["appearances"], row["avg_rating"], anchors.get(row["player_id"], []),
        )
        if season is None:
            counts["unresolved"] += 1
            continue
        counts[basis] += 1
        updates.append((season, basis, row["id"]))

    conn.executemany(
        "UPDATE quotations SET stats_season = ?, stats_season_basis = ? WHERE id = ?",
        updates,
    )
    conn.commit()
    logger.info("Stagioni risolte: %s", counts)
    return {"resolved": len(updates), **counts}
