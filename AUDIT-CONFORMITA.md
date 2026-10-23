# Audit di conformità e sicurezza: fantacalcio

Data: 17/10/2026. Ambito: repository locale `fantacalcio/` (Python, Streamlit, SQLite).
Nessun deploy, commit, push, modifica dell'indice Git o operazione su database o servizi reali.
Tutte le verifiche sono locali. Questo documento non è un parere legale: i punti marcati
«da verificare» richiedono revisione di un professionista prima della pubblicazione.

Riferimenti normativi: GDPR (Reg. UE 2016/679), D.Lgs. 196/2003, linee guida cookie del
Garante (10/06/2021), WCAG 2.2 AA.

## 1. Ambito

- Pagine Streamlit: `dashboard/pages/1_Portieri.py` ... `8_Privacy.py`, `dashboard/components.py`
  (barra di acquisto), `dashboard/player_detail.py`.
- Accesso dati e scritture: `db/repository.py`, `db/connection.py`, `dashboard/data_access.py`.
- Configurazione: `.streamlit/config.toml`, `.gitignore`, `README.md`.
- Dati: `data/fantacalcio.db` (sola lettura per l'ispezione dello schema), `data/photos/`.
- Dipendenze: `requirements.txt`, `requirements-dev.txt`.

Non ispezionato: il contenuto dei campi `player_notes.notes` e dei dati storici di `data/fantacalcio.db`.
La verifica nel browser non è stata eseguita (vedi sezione 6).

## 2. Stato dei test

| Momento | Comando | Esito |
|---|---|---|
| Prima | `python -m pytest -q` | 537 passed, 6 deselected (70 s) |
| Dopo | `python -m pytest -q` | 591 passed, 6 deselected (85 s) |
| 17/10/2026, dopo lettura protetta | `python -m pytest -q` | 612 passed, 6 deselected (114 s) |

Le 54 nuove prove sono in `tests/test_access_gate.py` (12 prove sul cancello, di cui alcune con AppTest),
`tests/test_input_validation.py`, `tests/test_sql_parameterization.py` e
`tests/test_write_pages_gate.py` (5 prove sulle pagine, su una copia del DB in `tmp_path`:
il file tracciato non viene toccato). Nessun test esistente è stato modificato o disattivato.

Lint: `python -m ruff check` sui file toccati e nuovi: un solo errore E402 in
`dashboard/components.py:1078` (import a fine modulo), già presente nel commit HEAD.

## 3. Rilievi

Severità: Critico, Alto, Medio, Basso. Stato: CORRETTO = corretto con prova; APERTO = richiede decisione o intervento.

| ID | Sev. | Rilievo | File:riga (origine) | Stato |
|---|---|---|---|---|
| R1 | Critico | Le azioni di scrittura non avevano autenticazione: chiunque avesse l'URL poteva registrare/rimuovere acquisti, modificare i pesi delle fonti e confermare i match. | `dashboard/pages/5_La_Mia_Rosa.py` (form ~52-98, rimozioni ~124, ~157); `dashboard/components.py` barra acquisto (~578-670); `dashboard/pages/7_Monitoraggio.py` (pesi ~95-112, match ~225-231) | CORRETTO (sez. 4.1) |
| R2 | Alto | Letture pubbliche di dati di acquisto, nomi di avversari (terze persone), note e foto: rosa, prezzi e «presi dagli avversari» erano visibili a chiunque. | `dashboard/pages/1_Portieri.py` ... `4_Attaccanti.py`, `5_La_Mia_Rosa.py`, `6_Dettaglio_Giocatore.py`; `dashboard/components.py` (barra di acquisto) | IMPLEMENTATO e testato con AppTest (sez. 4.8); verifica nel browser non eseguita. Chiusura approvata da Luca il 17/10/2026 |
| R3 | Alto | Dati personali e dati di gioco nel repository tracciato: `data/fantacalcio.db` e i file `data/photos/*.jpg` sono versionati in Git, anche se `.gitignore` li esclude. | `.gitignore` righe 6-7 e 11; indice Git (784 file tracciati in `data/`) | APERTO, BLOCCATO: rimuoverli dall'indice rompe il deploy su Streamlit Cloud (sez. 4.7). Serve decisione di Luca (D7) |
| R4 | Alto | Mancava un'informativa privacy: nessuna pagina sul titolare, sulle fonti, sul fornitore di hosting e sulla conservazione. | `dashboard/pages/8_Privacy.py` | PARZIALE: pagina creata, campi `[DA FORNIRE]` aperti |
| R5 | Medio | Errori non gestiti: Streamlit mostra per default i dettagli dell'errore (stack trace) all'utente; le scritture SQLite non avevano gestione. | `.streamlit/config.toml` (sezione `[client]` assente, ora presente); scritture in pagine e componenti | CORRETTO (sez. 4.3) |
| R6 | Medio | Input dei form non validati lato server: prezzo senza tetto, nome avversario senza limite di lunghezza né controllo di caratteri di controllo, pesi senza limite superiore. | `dashboard/pages/5_La_Mia_Rosa.py:75` (prezzo), `:74` (avversario); `dashboard/components.py` barra acquisto (~630-640); `dashboard/pages/7_Monitoraggio.py` (pesi) | CORRETTO (sez. 4.2) |
| R7 | Medio | Il file `.streamlit/secrets.toml` non era escluso da Git: un hash o un segreto locale poteva finire nel repository. | `.gitignore` | CORRETTO: regola aggiunta (riga 53) |
| R8 | Basso | SQL costruito con f-string nel codice: nessun valore utente nel testo SQL (verificato), ma il pattern è fragile. | `db/connection.py:38,120,130,206-223`; `db/repository.py:322,344,365,406,467,511-515,531` | CORRETTO come guardia: test statico con elenco revisionato (sez. 4.5) |
| R9 | Basso | Limite dei tentativi solo per sessione Streamlit: aprendo una nuova sessione il contatore riparte da zero. | `dashboard/access.py` (`ATTEMPTS_KEY`) | APERTO: limite di progetto, vedi sez. 6 |
| R10 | Basso | Versione Streamlit diversa: `requirements.txt` fissa `streamlit==1.65.0`, l'ambiente locale ha 1.62.0. Il comportamento di `showErrorDetails` è stato verificato sulla 1.62. | `requirements.txt` | APERTO: allineare e riverificare |
| R11 | Basso | Log: nessun dato personale o segreto nei log trovati (`dashboard/components.py:171`, `db/connection.py:225`: registrano solo eccezione o id). Il nuovo codice registra solo il tipo di errore e l'evento di accesso negato, mai la password. | `dashboard/components.py:171`, `db/connection.py:225`, `dashboard/access.py` | VERIFICATO nel codice; nessuna modifica |
| R12 | Basso | Dipendenze: `pip-audit` non è installato. Non è stato installato perché non è una dipendenza del progetto. | — | NON VERIFICATO (sez. 6) |

Nessuna chiamata di rete dal codice della dashboard, verificata con ricerca (`requests`, `urllib`,
`httpx`, `playwright`, URL, CDN, font esterni): l'unico collegamento esterno è il profilo
Transfermarkt, aperto solo su clic. Nessuno script di analytics o pixel nel codice dell'app.

## 4. Correzioni con evidenza

### 4.1 Cancello di accesso (R1)

- Nuovo modulo `dashboard/access.py`:
  - l'hash arriva da `st.secrets["WRITE_PASSWORD_HASH"]` o dalla variabile d'ambiente
    `FANTACALCIO_WRITE_PASSWORD_HASH`; nel codice non c'è alcun hash reale;
  - formato PBKDF2-HMAC-SHA256 con sale, 600000 iterazioni di default, minimo 100000 in verifica;
  - confronto con `hmac.compare_digest` (verificato da test con spy);
  - fail-closed: hash mancante o malformato → scritture disabilitate con avviso;
  - attesa crescente dopo 3 tentativi: 5 s, 10 s, 20 s, fino a 300 s;
  - messaggio d'errore generico: «Password non valida.» / «Troppi tentativi. Riprova più tardi.»;
  - pulsante «Esci dalla modalità modifica».
- Le scritture sono disabilitate in tutte le sezioni individuate in R1 (`disabled=not writes_allowed`).
  La disabilitazione è solo lato interfaccia; le funzioni `db/repository.py` non controllano la sessione.
- Letture pubbliche invariate.

Evidenza: `python -m pytest -q tests/test_access_gate.py tests/test_write_pages_gate.py` → 16 passed
(test: senza segreto nessun form e scritture disabilitate; password errata; accesso e logout;
blocco dopo tre errori anche con password giusta; pagine Rosa e Monitoraggio con scritture disabilitate
e, con sessione sbloccata, abilitate). Questa prova copre le pagine Rosa e Monitoraggio.
La barra di acquisto in `components.py` è coperta solo da compilazione e revisione del codice:
nessun test a schermo la esercita.

### 4.2 Validazione lato server (R6)

- `dashboard/validation.py`: `validate_price` (intero 1..500, il budget `TOTAL_CREDITS`),
  `validate_opponent_name` (1..60 caratteri dopo `strip`, nessun carattere di controllo Unicode),
  `validate_weight` (numero finito tra 0 e 10).
- Chiamate nei tre punti di scrittura prima del DB.

Evidenza: `python -m pytest -q tests/test_input_validation.py` → passed (prove di confine,
NaN, infinito, booleani, stringhe, caratteri di controllo).

### 4.3 Errori (R5)

- `.streamlit/config.toml`: `[client] showErrorDetails = "none"`.
- `dashboard/access.py:run_db_write`: intercetta `sqlite3.Error`, mostra un messaggio generico e
  registra nel log solo il tipo di errore.

Evidenza: configurazione letta; opzione `none` presente nell'enum di Streamlit 1.62
(`streamlit/config.py`). Verifica nel browser non eseguita (sez. 6).

### 4.4 Log (R11)

Ricerca di `print`, `logging`, `logger` in `dashboard/` e `db/`: due occorrenze, entrambe senza dati personali.
Nessuna modifica necessaria.

### 4.5 Query parametrizzate (R8)

- Ogni valore utente passa come parametro `?` (verificato per opponent_name, nome giocatore,
  prezzo, pesi, stato match). Ricerca testuale dei giocatori (`search_and_sort`) avviene in memoria.
- Le f-string SQL interpolano solo nomi di tabelle, colonne e costanti del codice
  (`_EXCLUDE_*`, `HISTORICAL_SOURCE_SUFFIX`, `TABLE_HEALTH_SPECS`, `_PLAYER_CHILD_TABLES`).
- `tests/test_sql_parameterization.py`: guardia AST con elenco revisionato, più prove di comportamento
  con stringhe tipo SQL-injection (salvate come testo, nessuna tabella eliminata).

Evidenza: `python -m pytest -q tests/test_sql_parameterization.py` → passed.

### 4.6 Privacy (R4)

- `dashboard/pages/8_Privacy.py`: pagina informativa con sezioni su titolare, cosa fa l'app, dati trattati,
  fonti dei dati (domini ricavati dal codice in `scrapers/`), hosting, cookie, conservazione, diritti,
  aggiornamento. Ciò che non è verificato è marcato «[DA VERIFICARE]», ciò che manca è «[DA FORNIRE]».
- Test: `tests/test_write_pages_gate.py::test_privacy_page_renders_without_exception` → passed.

Fonti dei dati elencate nella pagina (da `scrapers/` e `scrapers/photo_downloader.py`):
fantacalcio.it, fantanalisi.it, fantapazz.com, pianetafanta.it, fantacalciopedia.com,
api.fantacalcio-online.com, transfermarkt.it, it.wikipedia.org.

### 4.7 Dati tracciati in Git (R3): nessuna modifica, solo rilievo

Schema di `data/fantacalcio.db` (solo nomi di tabelle e colonne, letto in sola lettura, nessun valore):
- Dati di gioco pubblici sui giocatori: `players`, `quotations`, `player_consensus`, `player_season_stats`,
  `player_match_ratings`, `player_injuries` (infortuni dei giocatori), `player_set_pieces`,
  `player_advanced_stats`, `player_fantanalisi_valuations`, `fcp_metrics`, `team_*`, `teams`, `sources`.
- Dati anagrafici di atleti pubblici: `player_anagrafica` (data di nascita, altezza, piede, nazionalità, numero di maglia).
- Dati del gestore: `my_roster` (giocatori acquistati, prezzo, data), `player_notes` (note in testo libero: contenuto non ispezionato).
- Dati di terze persone: `opponent_picks` (nome dell'avversario, prezzo, data).
- Log tecnici: `scraping_runs`, `pipeline_job_runs`.
- Abbinamento nomi: `player_source_matches`, `player_transfermarkt_ids`.
- Foto: 846 file `.jpg` in `data/photos/` (immagini di giocatori da fonti pubbliche).

Verifica del 17/10/2026 (lavoro dell'agente haiku-fantacalcio): il comando `git rm --cached` NON è stato eseguito.
Motivo: DB e foto sono usati a runtime dal codice (`dashboard/common.py` `DB_PATH` su `data/fantacalcio.db`;
`dashboard/components.py` `PHOTOS_DIR` su `data/photos/`), e il README (sez. Deploy) dice che Streamlit Community Cloud
si aggiorna da solo a ogni push su `main`. Senza quei file nel repository la dashboard pubblicata partirebbe con un DB
vuoto e senza foto. Il `.gitignore` contiene già le regole (righe 6, 7 e 11): non è stato aggiunto nulla.
Il comando, da eseguire solo dopo la decisione D7, resta:

```
git rm --cached -r data/fantacalcio.db data/photos
```

I file restano nel disco. La storia Git continua a contenerli: per rimuoverli dalla storia serve una riscrittura, che
richiede autorizzazione esplicita (non fatta). Per togliere i dati dal repository senza rompere il deploy serve una
sorgente esterna (storage o database dedicato): è un cambio di architettura, non incluso in questo task.

### 4.8 Lettura protetta (R2)

- `dashboard/access.py`: nuova funzione `require_read_access(scope)`. Usa lo stesso meccanismo di `require_write_access`
  (hash PBKDF2 in `st.secrets` chiave `WRITE_PASSWORD_HASH` o variabile `FANTACALCIO_WRITE_PASSWORD_HASH`, confronto
  `hmac.compare_digest`, attesa crescente, messaggi generici). Il cancello è stato estratto in `_gate()` condiviso.
- Fail-closed: senza hash la pagina mostra un avviso e si ferma (`st.stop()`). Nessun dato viene letto né mostrato.
- Pagine protette: `1_Portieri`, `2_Difensori`, `3_Centrocampisti`, `4_Attaccanti`, `5_La_Mia_Rosa`, `6_Dettaglio_Giocatore`.
  Il cancello è chiamato prima di `get_db_connection()`, perché quella funzione disegna la barra crediti e il menu laterale.
- Non protette, invariate: `7_Monitoraggio` (letture pubbliche, scritture già protette), `8_Privacy`.
- Sessione: la stessa password e lo stesso flag di sessione sbloccano lettura e scrittura. La barra di acquisto
  (`components.py`, `require_write_access("purchase", show_logout=False)`) non ripete il pulsante di uscita.
- Test: `tests/test_access_gate.py` (3 prove sul cancello di lettura) e `tests/test_write_pages_gate.py`
  (test per ciascuna pagina protetta: senza hash, senza accesso, con accesso). Esito: 38 passed sui due file; suite completa 612 passed.
- Non verificato nel browser: aspetto del cancello, tastiera, messaggi a schermo. Verificato solo con AppTest.

Limiti nuovi o confermati:
- Il cancello è lato interfaccia. Chi legge il database o il codice vede comunque i dati.
- Su Streamlit Cloud le pagine di ruolo restano bloccate finché `WRITE_PASSWORD_HASH` non è configurato nei Secrets (vedi D5).
- `app.py` non elenca `8_Privacy.py` nel menu di navigazione: la pagina privacy è raggiungibile solo per URL diretto (vedi sez. 6).

## 5. Dati e decisioni da fornire (Luca)

| # | Richiesta | Motivo |
|---|---|---|
| D1 | `[DA FORNIRE]` titolare del trattamento: nome o ragione sociale | Pagina privacy |
| D2 | `[DA FORNIRE]` contatto privacy dedicato | Art. 13 e 15-22 GDPR |
| D3 | `[DA FORNIRE]` tempi di conservazione di acquisti, avversari e log | Art. 13 GDPR |
| D4 | `[DA FORNIRE]` data di pubblicazione della pagina | Trasparenza |
| D5 | Generare l'hash con `python -m dashboard.access` in un terminale interattivo e inserirlo in Secrets (Cloud) e in `.streamlit/secrets.toml` (locale). La password non va mai scritta nel repository o in chat | R1 |
| D6 | Chiusa il 17/10/2026 da Luca: le pagine con rosa, avversari, note e foto richiedono la password (sez. 4.8). Confermare o correggere, in particolare se le pagine di ruolo devono restare pubbliche con i soli dati di gioco | R2 |
| D7 | Decidere come togliere DB e foto dal repository senza rompere il deploy (storage esterno, o lasciarli tracciati e accettare il rischio), e se riscrivere la storia | R3, sez. 4.7 |
| D8 | Confermare i limiti scelti: prezzo 1..500, peso 0..10 | R6: limiti scelti dall'audit, non dal requisito |
| D9 | Verificare con un professionista: basi giuridiche, eventuale necessità di informativa estesa, ruolo di Streamlit Community Cloud | Parere legale |
| D10 | Allineare `streamlit` tra `requirements.txt` (1.65.0) e l'ambiente (1.62.0) | R10 |

## 6. Rischi residui e controlli non eseguiti

- Il cancello è lato interfaccia: chi ha accesso al codice o al server può modificare il database direttamente.
- Il limite dei tentativi è per sessione (R9): un attaccante che apre sessioni nuove non è rallentato. Un limite globale richiederebbe uno storage condiviso fuori dalla sessione.
- Password e hash: la sicurezza dipende dalla forza della password scelta da Luca.
- Non verificato nel browser: form, messaggi, disabilitazioni visive, logout, accessibilità WCAG 2.2 AA (contrasto, focus, tastiera) della pagina privacy e del cancello. Eseguire una prova manuale o Playwright prima del lancio.
- Non verificato: intestazioni HTTP, HTTPS e cookie del servizio Streamlit Community Cloud; informativa del fornitore; ubicazione dei dati.
- Non verificato: `pip-audit` (non installato) e vulnerabilità note delle dipendenze.
- Non verificato: comando `python -m dashboard.access` in terminale interattivo. In questa sessione `getpass` su Windows ha atteso la console e il comando è stato interrotto; la funzione di hash è verificata dai test.
- Non verificato: il rollback su Streamlit Community Cloud (nel README è marcato come tale).
- Il pulsante di accesso non è stato testato con password reale: nei test è usata una password di prova (`correct-test-pw`) solo dentro i test, non è un segreto.
- Il banner dei cookie non è stato deciso: l'app non imposta cookie propri nel codice, ma i cookie del servizio di hosting non sono verificati (vedi pagina privacy).

## 7. Checklist pre-lancio

| Voce | Esito | Evidenza |
|---|---|---|
| Scritture protette da password | PASSA | sez. 4.1, test del cancello |
| Fail-closed senza segreto | PASSA | `test_rosa_page_without_secret_is_fail_closed` |
| Nessun hash o segreto nel repository | PASSA | ricerca in `*.py`, `*.toml`, `*.md`, `*.example`: solo il placeholder |
| `secrets.toml` ignorato da Git | PASSA | `.gitignore` riga 53 (`git check-ignore`) |
| Messaggi d'errore generici, nessuno stack trace | PASSA (configurazione) | `showErrorDetails = "none"`; verifica browser non eseguita |
| Validazione input lato server | PASSA | `tests/test_input_validation.py` |
| Query parametrizzate | PASSA | `tests/test_sql_parameterization.py` |
| Test suite | PASSA | 591 passed, 6 deselected |
| Lint dei file toccati | PASSA (eccetto errore preesistente E402) | ruff |
| Informativa privacy | PARZIALE | campi `[DA FORNIRE]` (D1-D4) |
| Consenso cookie | NON VERIFICATO | cookie del servizio di hosting |
| Dati personali nel repository tracciato | NON PASSA | R3, bloccato da decisione D7 (sez. 4.7) |
| Letture pubbliche di dati di terzi | PASSA (test AppTest) | R2, sez. 4.8; browser non verificato |
| Dipendenze vulnerabili | NON VERIFICATO | R12, pip-audit assente |
| Accessibilità WCAG 2.2 AA | NON VERIFICATO | nessuna prova nel browser |
| Intestazioni HTTP e HTTPS del servizio | NON VERIFICATO | Streamlit Community Cloud |
| Rollback documentato | PARZIALE | README, marcato come non verificato |
| Limite tentativi condiviso | NON PASSA (limite noto) | R9 |
