"""Configurazione di lega centralizzata (TASK-019/A4): un solo posto per i
parametri che definiscono le regole della lega — budget, slot per ruolo,
formazione titolare di default, numero di squadre, stagione corrente.
Prima duplicati o hardcoded in più file (ROLE_SLOTS ridefinito identico in
ranking/budget.py, ranking/lp_optimizer.py e scripts/simulate_auctions.py;
500 ripetuto come default in almeno 5 firme di funzione): cambiare una
regola della lega richiedeva trovare e aggiornare ognuna di quelle copie a
mano, con il rischio concreto di aggiornarne una e dimenticare le altre."""

# Crediti totali a disposizione di ogni squadra in asta.
TOTAL_CREDITS = 500

# Numero di squadre della lega. Non consumato da nessun modulo al momento
# (ranking/replacement.py, che calcolava il "replacement level" da questo
# valore, è stato rimosso in TASK-015: alimentava solo il vecchio Price
# Engine) — resta qui come dato di lega, riusabile se servisse di nuovo.
LEAGUE_TEAMS = 8

# Slot per ruolo di una rosa completa (25 giocatori: 3+8+8+6).
ROLE_SLOTS = {"P": 3, "D": 8, "C": 8, "A": 6}

# Formazione titolare di default (11 giocatori: 1+3+4+3) per la Rosa Ideale
# e per il confronto Rosa Ideale vs LP — vedi ranking.ideal_squad.FORMATIONS
# per l'elenco completo delle formazioni supportate.
DEFAULT_FORMATION = "3-4-3"

# Stagione corrente — usata dal filtro stagione/campionato sulle statistiche
# (TASK-008) e dalla tabella `teams` (db/schema.sql, TASK-003/P0-006).
CURRENT_SEASON = "2026/27"

# Bonus/malus del regolamento di lega, usati da ranking/fantamedia.py per
# ricavare una fantamedia dalle componenti di player_season_stats quando
# nessuna fonte la pubblica (BACKLOG-2026-08-31 §3). Sono i valori del
# Fantacalcio classico di Serie A: cambiali qui se la tua lega ne usa altri
# — è l'unico posto in cui sono scritti.
#
# Mancano di proposito le voci che player_season_stats non registra
# (rigore parato/sbagliato, autogol, portiere imbattuto): non sono state
# messe a zero, semplicemente non sono calcolabili, ed è per questo che la
# fantamedia derivata è un'approssimazione dichiarata e non un valore reale.
BONUS_GOAL = 3.0
BONUS_ASSIST = 1.0
MALUS_YELLOW_CARD = -0.5
MALUS_RED_CARD = -1.0
MALUS_GOAL_CONCEDED = -1.0
