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

# Numero di squadre della lega — usato per calcolare il "replacement level"
# (ranking.replacement): l'N-esimo per score con N = slot_ruolo * LEAGUE_TEAMS
# è il livello di talento liberamente disponibile una volta che ogni squadra
# ha riempito quel ruolo con i suoi migliori.
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
