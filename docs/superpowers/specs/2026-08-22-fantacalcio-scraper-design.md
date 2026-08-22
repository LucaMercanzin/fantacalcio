# Fantacalcio Scraper & Dashboard — Design

## Obiettivo
Aggregare quotazioni e valutazioni giocatori di Fantacalcio da più siti, storicizzarle in un database locale, calcolare un ranking automatico per ruolo, e mostrare tutto in una dashboard web locale con 4 pagine (Portieri, Difensori, Centrocampisti, Attaccanti) più una pagina "La mia rosa" per gestire crediti e giocatori acquistati.

Uso: solo locale (nessun deploy cloud), esecuzione scraping automatica periodica (schedulata via Task Scheduler Windows), aggiornamento manuale a comando per le note/analisi testuali.

## Architettura

```
fantacalcio/
  scrapers/
    base.py            # interfaccia comune adapter
    fantacalcio_it.py
    gazzetta.py
    ... altri adapter (fino a ~20 fonti, aggiunti incrementalmente)
  matching/
    player_matcher.py  # riconciliazione nomi tra fonti
  ranking/
    scorer.py          # formula di ranking per ruolo
  db/
    schema.sql
    models.py
  scheduler/
    run_scraping.py    # job schedulato da Task Scheduler
  dashboard/
    app.py             # Streamlit multipage
    pages/
      1_Portieri.py
      2_Difensori.py
      3_Centrocampisti.py
      4_Attaccanti.py
      5_La_Mia_Rosa.py
  data/
    fantacalcio.db      # SQLite
```

## Componenti

### 1. Scraper modulare (plugin per sito)
Ogni sito ha un adapter Python isolato che implementa un'interfaccia comune (`fetch() -> list[PlayerRecord]`). Il record normalizzato include: nome, ruolo classic, ruolo mantra, squadra, quotazione attuale, quotazione iniziale, stato (infortunato/squalificato/disponibile), fantamedia storica, media voto, presenze.

Un adapter che fallisce (sito down, layout cambiato) non blocca gli altri: errori loggati, scraping continua con le fonti restanti.

Quando disponibile sulla fonte, l'adapter scarica anche l'URL della foto del giocatore e la salva localmente in `data/photos/<player_id>.jpg` (fallback ad avatar placeholder colorato per ruolo se la fonte non espone la foto).

Partiamo con 5-6 fonti solide e ben scrapabili, poi si aggiungono adapter incrementalmente fino a ~20, senza modificare il resto del sistema.

### 2. Matching giocatori tra fonti
Modulo che riconcilia lo stesso giocatore citato con nomi diversi tra siti (es. "Lautaro" vs "Lautaro Martinez"), usando normalizzazione stringhe + fuzzy matching, con squadra come ulteriore segnale di disambiguazione.

### 3. Database SQLite
Storicizza ogni esecuzione di scraping (non sovrascrive), permettendo di calcolare andamento prezzi nel tempo e fantamedia storica. Tabelle principali:
- `players` (anagrafica unificata)
- `quotations` (snapshot per fonte/data: prezzo, ruolo, stato)
- `my_roster` (giocatori acquistati dall'utente: player_id, prezzo pagato, data)
- `player_notes` (note/analisi testuali editabili per giocatore)

### 4. Motore di ranking
Formula automatica per ruolo, ricalcolata ad ogni scraping, basata su: fantamedia storica, affidabilità (presenze/partite giocate), quotazione, stato attuale (penalizza infortunati/squalificati). Produce l'ordinamento dal migliore al peggiore mostrato in dashboard.

### 5. Note/analisi editabili
Campo di testo libero per giocatore in `player_notes`, con contenuti come: alternative consigliate, "non prendere insieme a X", secondo/vice in rosa, alternativa low-cost da altra squadra. Non generato automaticamente da un'API — l'utente lo aggiorna a comando (chiede a Claude di analizzare i dati correnti e proporre/aggiornare i testi), poi resta fisso fino al prossimo aggiornamento manuale.

### 6. Gestione rosa e crediti
Sistema classico: 500 crediti totali, 25 giocatori (3 P, 8 D, 8 C, 6 A). Pagina "La mia rosa" permette di:
- Aggiungere giocatore acquistato + prezzo pagato
- Vedere crediti spesi/rimanenti totali e per ruolo
- Vedere slot ruolo ancora da completare

Effetti sulle 4 pagine ruolo:
- Giocatori già in rosa evidenziati visivamente
- Filtro "cosa posso permettermi" in base a crediti rimanenti per quel ruolo e slot mancanti
- Le note/consigli possono referenziare i crediti rimanenti (es. "con budget ridotto per la difesa, preferisci X a Y") quando l'utente aggiorna le analisi

### 7. Dashboard (Streamlit, multipage)
5 pagine da menu: Portieri, Difensori, Centrocampisti, Attaccanti, La Mia Rosa.

Ogni pagina ruolo mostra i giocatori come **"figurine"** (card stile Panini): foto (scaricata dal sito fonte durante lo scraping e salvata in `data/photos/`, fallback ad avatar placeholder colorato per ruolo se assente), nome, squadra, rating/ranking, quotazioni comparate tra fonti, fantamedia, stato, note/consigli, evidenziazione se già in rosa.

Controlli disponibili in pagina:
- **Barra di ricerca** per nome giocatore (filtro testuale live)
- **Ordinamento**: per ranking (default), per squadra, per quotazione
- Filtro "cosa posso permettermi" (da crediti rimanenti, vedi sezione 6)

### 8. Scheduling
Task Scheduler di Windows esegue `scheduler/run_scraping.py` periodicamente (default: giornaliero, configurabile) che lancia tutti gli adapter attivi, aggiorna il matching, salva nel DB e ricalcola il ranking. Le note testuali NON vengono toccate da questo job (restano manuali).

## Fuori scope (per ora)
- Deploy cloud / accesso remoto
- Generazione automatica delle note via API AI ad ogni scraping (costo + complessità non necessari ora)
- Copertura probabili formazioni e voti live in-partita (focus attuale: quotazioni/valutazioni)

## Prossimi passi
Decomposizione in piano di implementazione (writing-plans): schema DB → primi 2 adapter (Fantacalcio.it, Gazzetta) → matching → ranking → dashboard base 4 pagine → pagina rosa/crediti → scheduling → adapter aggiuntivi incrementali.
