# Design: metriche extra da Fantacalciopedia (pagine dettaglio giocatore)

Data: 2026-08-25
Sotto-progetto A di 4 (integrazione idee da repository esterni: fantacalcio-py,
ScraperFantacalcio, fantacalcio-optimization, fantabeto, fantaSimulatore,
FantacalcioPython). Gli altri tre restano fuori scope per questo spec.

## Obiettivo

Oggi `scrapers/fantacalciopedia.py` legge solo la pagina elenco per ruolo
(presenze, fantamedia). Le pagine dettaglio del singolo giocatore espongono
segnali aggiuntivi non ancora sfruttati:

- `alg_fcp` — Algoritmo Fantacalciopedia, 0-100
- `punteggio_fcp` — Punteggio FCP
- `investment_stability_pct` — Solidità fantainvestimento, %
- `injury_resistance_pct` — Resistenza infortuni, %
- `predicted_appearances`, `predicted_goals`, `predicted_assists`
- `skills` — tag testuali (es. Rigorista, Titolare, Goleador, Outsider)

Verificato dal vivo sulla pagina di Hojlund Rasmus
(fantacalciopedia.com/.../hojlund-rasmus.html).

## Allineamento player_id (matching)

Le pagine dettaglio non espongono un ID interno al nostro DB: il join va
fatto per (nome, squadra), esattamente come già avviene per altre fonti che
non portano un player_id (es. pagina rigoristi/voti).

- Si riusa **`matching.player_matcher.match_name_to_player(name, team,
  players, threshold=80)`**, già presente nel progetto — nessun nuovo
  sistema di matching da introdurre.
- `players` è la lista `{"id", "canonical_name", "team"}` letta da
  `db/repository.py` (stessa lista usata dagli altri call site di
  `match_name_to_player`).
- Il `name`/`team` passati sono quelli letti dalla pagina elenco FCP (stesso
  testo già usato oggi per costruire i `PlayerRecord` di
  `fantacalciopedia.py`), non un parsing separato dalla pagina dettaglio —
  così il matching riusa lo stesso testo normalizzato che già alimenta
  `match_records` per questa fonte.
- Se `match_name_to_player` ritorna `None` (nessun match sopra soglia o
  match ambiguo), il giocatore viene **scartato con log warning**: niente
  righe orfane in `fcp_metrics`, coerente con l'integrità della foreign key
  `player_id NOT NULL REFERENCES players(id)`.
- Ordine di esecuzione: `run_fcp_metrics.py` deve girare **dopo** che
  `players` è già popolato dallo scraping principale (stesso vincolo
  implicito già esistente per le altre pipeline che fanno matching contro
  `players`), altrimenti non c'è nulla contro cui matchare.

## Architettura

1. `scrapers/fantacalciopedia.py`
   - `parse_html` cattura anche l'`detail_url` di ogni giocatore dalla
     pagina elenco (oggi l'href non viene letto).
   - Nuova funzione `fetch_detail(url: str) -> FcpDetail` (dataclass) che fa
     il parsing della pagina dettaglio con BeautifulSoup ed estrae i campi
     elencati sopra. Selettori dedicati, separati da `parse_html`.

2. `pipeline/run_fcp_metrics.py` (nuovo script, separato dallo scraping
   principale)
   - Legge i player attualmente in `players` (per costruire la lista per il
     matching) e gli URL dettaglio ottenuti dall'ultimo scrape della pagina
     elenco.
   - Itera sulle pagine dettaglio con un piccolo delay tra le richieste
     (throttling, stesso stile già in uso negli altri scraper del progetto)
     — ~600 richieste HTTP, non deve bloccare la pipeline principale né
     girare alla stessa frequenza.
   - Per ogni dettaglio: matcha via `match_name_to_player`, poi scrive su
     `fcp_metrics` con `scrape_date` odierno.

3. `db/schema.sql` — nuova tabella:
   ```sql
   CREATE TABLE IF NOT EXISTS fcp_metrics (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       player_id INTEGER NOT NULL REFERENCES players(id),
       scrape_date TEXT NOT NULL,
       alg_fcp REAL,
       punteggio_fcp REAL,
       investment_stability_pct REAL,
       injury_resistance_pct REAL,
       predicted_appearances INTEGER,
       predicted_goals INTEGER,
       predicted_assists INTEGER,
       skills TEXT
   );
   ```
   Tabella separata da `quotations`: fonte e cadenza di scraping diverse,
   collegata via `player_id`. Nessun vincolo UNIQUE su (player_id,
   scrape_date): si tiene lo storico, come `quotations`.

4. `db/repository.py` — nuovi metodi:
   - `save_fcp_metrics(player_id, scrape_date, **fields)`
   - `get_latest_fcp_metrics(player_id)` — ultima riga per `scrape_date`.

5. `ranking/scorer.py`
   - `compute_risk` accetta in input opzionale `injury_resistance_pct` /
     `investment_stability_pct`; se assenti (giocatore non ancora scrappato
     in dettaglio, o scartato per matching ambiguo) il comportamento resta
     identico a oggi — nessuna regressione.
   - `alg_fcp` esposto come segnale informativo separato (non mescolato
     silenziosamente in `compute_risk`/`compute_player_quality`), coerente
     con la separazione degli score già presente nel codice.

6. `dashboard/data_access.py` + `components.py`
   - Merge dei metrics FCP (via `get_latest_fcp_metrics`) nella riga
     giocatore.
   - Nuova colonna/badge per `alg_fcp` e per i tag `skills`.

## Gestione errori

- Pagina dettaglio non raggiungibile o struttura HTML cambiata → log
  warning, skip del singolo giocatore, la pipeline continua (stesso stile
  già visto in `scrapers/base.py` e altri scraper).
- Match nome/squadra sotto soglia o ambiguo → skip con log warning (vedi
  sezione matching sopra).
- Campi singoli mancanti sulla pagina dettaglio (es. giocatore senza
  "Resistenza infortuni") → `None`, gestito come opzionale ovunque, nessun
  crash.

## Testing

- Unit test per `fetch_detail`/parsing HTML della pagina dettaglio, con
  fixture HTML salvata (stesso pattern dei test esistenti per gli altri
  scraper in `tests/`).
- Unit test per il matching: caso match trovato, caso sotto soglia, caso
  ambiguo (due giocatori stesso nome/squadra) → nessuna riga scritta.
- Unit test per `compute_risk` con e senza i nuovi input (nessuna
  regressione quando i dati FCP mancano).
- Unit test repository per `save_fcp_metrics` / `get_latest_fcp_metrics`.

## Fuori scope (rimandato ai prossimi sotto-progetti)

- B: solver LP per la rosa ottimale (fantacalcio-optimization).
- C: predizione ML del punteggio (fantabeto).
- D: simulatore calendario/classifica post-asta (fantaSimulatore,
  FantacalcioPython).
