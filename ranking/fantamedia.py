"""Fantamedia ricavata dalle componenti, invece che stimata dal prezzo.

Il problema (BACKLOG-2026-08-31 §3). Solo 275 giocatori su 838 hanno una
fantamedia pubblicata da una fonte. Per gli altri 563 il Fantasy Value usa
`ranking.scorer.estimate_fantamedia`, che mappa il percentile di prezzo del
giocatore sulla curva prezzo/fantamedia del suo ruolo. È una proxy onesta ma
resta una proxy, e ha un limite strutturale: **due giocatori con lo stesso
prezzo ricevono la stessa fantamedia stimata anche se rendono in modo
completamente diverso**. Un difensore che segna 5 gol e uno che non ne segna
nessuno, quotati uguale, escono identici.

`player_season_stats` però contiene già, per 540 giocatori e con la stagione
etichettata, tutto ciò che serve a *calcolarla* invece di stimarla: media
voto, presenze, gol, assist, ammonizioni, espulsioni, gol subiti. La
fantamedia del Fantacalcio è esattamente la media voto più i bonus/malus per
partita, quindi:

    fantamedia = media_voto + (bonus_totali + malus_totali) / presenze

Questo non è modellare: è applicare il regolamento (i valori stanno in
config.py) a numeri già in tabella. Il risultato distingue i due difensori
dell'esempio, cosa che la stima da prezzo non può fare per costruzione.

**Cosa NON è.** Un'approssimazione dichiarata, non un valore reale, per due
ragioni che vanno tenute in vista invece che nascoste:

1. `player_season_stats` non registra rigori parati/sbagliati, autogol e
   porta inviolata. Per un portiere pesano parecchio; per un giocatore di
   movimento sono marginali.
2. È la stagione **scorsa**. Vale come base di partenza, non come forma
   attuale — esattamente come la fantamedia pubblicata dalle fonti a
   inizio stagione.

Per questo il valore viene marcato (`fantamedia_basis = "derived"`) e non si
sostituisce mai a una fantamedia vera: si inserisce **fra** quella e la
stima da prezzo, come secondo miglior ripiego.
"""

from config import (
    BONUS_ASSIST,
    BONUS_GOAL,
    MALUS_GOAL_CONCEDED,
    MALUS_RED_CARD,
    MALUS_YELLOW_CARD,
)

# Sotto questo numero di presenze i bonus/malus per partita sono dominati dal
# caso: un gol in 2 partite vale +1,5 di fantamedia e descrive l'episodio, non
# il giocatore. Sotto soglia si preferisce la stima da prezzo, che almeno
# parla della valutazione complessiva di un giocatore invece che di due
# domeniche. 5 è la stessa soglia oltre la quale ranking.scorer considera
# affidabile il record presenze.
MIN_APPEARANCES = 5

# Un valore fuori da questa banda non è una fantamedia: è un errore di
# scraping o un giocatore con 20 gol in 6 partite. La Serie A reale sta
# ampiamente dentro (i migliori attaccanti viaggiano sui 9, i peggiori
# difensori sui 4), quindi un risultato fuori banda viene scartato invece
# che troncato — troncare fabbricherebbe un numero plausibile da un dato
# che plausibile non è.
PLAUSIBLE_RANGE = (3.0, 12.0)


def derive_fantamedia(season_stats: dict | None) -> float | None:
    """Fantamedia dalla riga di `player_season_stats`, o None se non è
    calcolabile o non è credibile.

    Serve la media voto e le presenze: senza la prima non c'è base su cui
    sommare i bonus, senza le seconde non c'è modo di ridurli a "per
    partita". Gol/assist/cartellini mancanti valgono zero — lì l'assenza
    del dato e lo zero coincidono davvero (nessun gol registrato = nessun
    bonus gol), a differenza della media voto, dove non coincidono affatto.
    """
    if not season_stats:
        return None

    avg_rating = season_stats.get("avg_rating")
    appearances = season_stats.get("appearances")
    if avg_rating is None or not appearances or appearances < MIN_APPEARANCES:
        return None

    total = (
        BONUS_GOAL * (season_stats.get("goals_scored") or 0)
        + BONUS_ASSIST * (season_stats.get("assists") or 0)
        + MALUS_YELLOW_CARD * (season_stats.get("yellow_cards") or 0)
        + MALUS_RED_CARD * (season_stats.get("red_cards") or 0)
        + MALUS_GOAL_CONCEDED * (season_stats.get("goals_conceded") or 0)
    )
    value = avg_rating + total / appearances

    low, high = PLAUSIBLE_RANGE
    if not low <= value <= high:
        return None
    return round(value, 2)
