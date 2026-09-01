# Visione del progetto — Fantasy Football Intelligence Dashboard

> Rinominato da `imperfezioni.md`. Questo file contiene la visione fondativa del
> progetto e le parti che sono realistiche con le fonti dati e l'architettura
> attuali (alcune già implementate, altre no ma raggiungibili con scraping
> pubblico e dati che già trattiamo).
>
> Le parti della visione originale che richiedono dati o infrastrutture che
> **non abbiamo e difficilmente avremo** (provider a pagamento, tracking/event
> data, integrazione live con l'asta, un vero motore MLOps) sono state spostate
> in file separati, così restano documentate ma non si confondono con la
> roadmap realistica:
>
> - [`impossibile-analisi-avanzata.md`](impossibile-analisi-avanzata.md) — Price Engine su dati storici che non abbiamo, Heatmap con tracking reale, Trend Detection/Player Archetypes multi-stagione, Fixture Difficulty basata su xG avversario, motore standalone separato da Streamlit.
> - [`impossibile-mlops-governance.md`](impossibile-mlops-governance.md) — Data Quality Layer, Model Versioning/Registry, Backtesting senza data leakage, Calibration, A/B Testing dei modelli: infrastruttura da vera data science team, sproporzionata per un progetto hobby.
> - [`impossibile-asta-live.md`](impossibile-asta-live.md) — Auction Intelligence Engine in tempo reale (Opponent Budget Modeling, Rival Threat Score, Nomination Strategy, Emotional Overbid Detection, Auction Cockpit): presuppone un feed live dei rilanci avversari che l'asta vera (in presenza/vocale) non ci dà, oltre a quanto già registriamo manualmente con "Presi dagli avversari".

---

# Fantasy Football Intelligence Dashboard

## 1. Visione del progetto

L'obiettivo è trasformare l'attuale applicazione di fantacalcio da una semplice dashboard di quotazioni in una vera piattaforma di **Fantasy Football Intelligence**.

L'app deve diventare una guida completa per prendere decisioni al fantacalcio utilizzando:

* dati storici;
* statistiche individuali;
* prestazioni stagionali;
* statistiche avanzate;
* bonus e malus;
* ruolo e posizione;
* titolarità;
* gerarchie sui calci piazzati;
* rigoristi;
* forma recente;
* stato fisico;
* valore di mercato;
* quotazioni provenienti da più fonti;
* consenso ponderato delle fonti;
* rapporto qualità/prezzo;
* rischio;
* disponibilità dei giocatori nella propria lega;
* composizione attuale della propria rosa;
* composizione delle rose degli avversari;
* calendario e difficoltà delle prossime partite;
* probabili formazioni;
* trend recente;
* affidabilità e qualità dei dati.

L'app non deve essere solamente un database.

Deve diventare uno **strumento decisionale**.

L'obiettivo finale è rispondere non soltanto alla domanda:

> "Quanto vale questo giocatore?"

ma soprattutto:

> "Conviene comprarlo, a quale prezzo, rispetto a quali alternative e considerando la situazione reale della mia lega?"

---

# 2. Principio fondamentale: niente scraping nella dashboard

Lo scraping non deve essere il cuore dell'applicazione.

La dashboard Streamlit non deve interrogare direttamente siti esterni ogni volta che l'utente apre una pagina.

L'architettura deve essere separata:

```text
                  DATA SOURCES
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
       Dataset        API         Import
          │            │            │
          └────────────┼────────────┘
                       ↓
                RAW DATA / DATA LAKE
                       ↓
                NORMALIZZAZIONE
                       ↓
                ENTITY MATCHING
             "chi è questo giocatore?"
                       ↓
                VALIDAZIONE DATI
                       ↓
                DATA PROCESSING
                       ↓
                 WEIGHTED ENGINE
                       ↓
                CONSENSUS ENGINE
                       ↓
                     MySQL
                       ↓
                  Repository
                       ↓
                   Streamlit
```

Lo scraping può esistere come uno degli importer, ma non deve essere una dipendenza critica della dashboard.

### Vantaggi

* maggiore stabilità;
* meno problemi causati da modifiche HTML;
* meno rischio di rate limit;
* meno rischio di blocchi;
* caricamento più veloce;
* possibilità di conservare lo storico;
* possibilità di aggiungere nuove fonti;
* possibilità di ricalcolare i dati;
* separazione tra acquisizione e visualizzazione;
* possibilità di eseguire gli aggiornamenti tramite job schedulati;
* possibilità di verificare e correggere i dati senza modificare la UI.

---

# 3. Dataset iniziale

Il progetto deve partire da un grande dataset di giocatori.

Il dataset iniziale deve essere il più ampio possibile e deve essere successivamente arricchito da ulteriori fonti.

## Dati anagrafici

Per ogni giocatore, quando disponibili:

* ID interno;
* ID delle fonti esterne;
* nome;
* cognome;
* nome completo;
* data di nascita;
* età;
* nazionalità;
* squadra;
* campionato;
* ruolo principale;
* ruoli secondari;
* piede preferito;
* altezza;
* peso.

## Dati economici

* valore di mercato;
* quotazione fantasy;
* quotazioni provenienti dalle diverse fonti;
* prezzo storico;
* variazioni di prezzo;
* data dell'ultimo aggiornamento;
* prezzo minimo;
* prezzo massimo;
* variazione percentuale;
* trend del prezzo;
* differenza tra prezzo fantasy e valore di mercato.

## Dati sportivi

* presenze;
* titolarità;
* minuti;
* gol;
* assist;
* xG;
* xA;
* tiri;
* tiri in porta;
* occasioni create;
* passaggi chiave;
* passaggi;
* precisione passaggi;
* dribbling;
* contrasti;
* intercetti;
* recuperi;
* progressive carries;
* progressive passes;
* clean sheet;
* ammonizioni;
* espulsioni;
* autogol;
* rigori segnati;
* rigori sbagliati.

---

# 4. Dati temporali e storico

Tutti i dati importanti devono essere storicizzati.

Non bisogna semplicemente sovrascrivere il valore precedente.

Per esempio, se un giocatore passa da 32 a 35 crediti:

```text
player_id
old_value = 32
new_value = 35
changed_at = timestamp
source = fonte
```

Lo stesso principio deve essere applicato a:

* quotazioni;
* valore di mercato;
* ruolo;
* squadra;
* gerarchie;
* stato fisico;
* titolarità;
* rigorista;
* punizioni;
* corner;
* rating;
* consensus;
* Fantasy Rating.

L'app deve quindi poter rispondere anche a:

> "Come è cambiato questo giocatore negli ultimi 30 giorni?"

e:

> "Perché il suo Fantasy Rating è aumentato?"

---

# 5. Entity Matching

Il sistema deve identificare correttamente lo stesso giocatore anche quando le fonti utilizzano nomi diversi.

Esempio:

```text
Lautaro Martinez
Lautaro Martínez
L. Martinez
Martinez Lautaro
```

devono essere ricondotti allo stesso `player_id`.

Il sistema deve utilizzare, quando disponibili:

* ID esterni;
* nome;
* cognome;
* data di nascita;
* squadra;
* nazionalità;
* ruolo;
* altri identificativi.

Il `player_id` interno deve essere stabile e indipendente dalla singola fonte.

## Matching confidence

Il sistema dovrebbe inoltre assegnare una percentuale di affidabilità al match.

Esempio:

```text
MATCH

Lautaro Martínez
        ↓
Player ID: 1042

Confidence: 99.8%
```

Un match incerto non deve essere inserito automaticamente nel database definitivo.

Può essere inserito in una coda:

```text
MATCH DA VALIDARE
```

per una successiva verifica.

---

# 6. Sistema di consenso tra fonti

La quotazione finale non deve dipendere da una sola fonte.

Il sistema deve calcolare un **consensus score** utilizzando una media ponderata.

Esempio:

```text
Fonte A → 28 → peso 40%
Fonte B → 31 → peso 30%
Fonte C → 26 → peso 20%
Fonte D → 35 → peso 10%
```

Formula:

```text
consensus =
    valore_A × peso_A
  + valore_B × peso_B
  + valore_C × peso_C
  + valore_D × peso_D
```

I pesi devono essere normalizzati.

Il consensus deve inoltre conservare:

* valore originale;
* fonte;
* peso applicato;
* timestamp;
* recency;
* eventuale penalizzazione outlier;
* confidence finale.

---

# 7. Affidabilità delle fonti

Ogni fonte deve avere un proprio livello di affidabilità.

Esempio iniziale:

```text
Fonte ufficiale        1.00
Fonte specializzata    0.85
Fonte statistica       0.80
Fonte community        0.60
Dataset generico       0.40
```

Questi valori devono essere configurabili nel database e non hard-coded nella dashboard.

La struttura può essere:

```text
sources
source_weights
source_data_quality
```

La qualità di una fonte potrebbe inoltre essere valutata dinamicamente sulla base dello storico degli errori.

---

# 8. Recenza del dato

Un dato recente deve avere maggiore influenza rispetto a un dato vecchio.

Il sistema può utilizzare un decadimento temporale.

Esempio:

```text
peso_recenza = e^(-giorni / 30)
```

Il parametro deve essere configurabile.

Questo permette di evitare che dati vecchi continuino a influenzare eccessivamente il consenso.

La recency deve essere applicata in maniera differenziata quando necessario.

Per esempio:

* infortunio → altissima recenza;
* probabile formazione → altissima recenza;
* valore di mercato → recenza media;
* statistiche storiche → recenza più bassa;
* caratteristiche fisiche → recenza molto bassa.

---

# 9. Rilevamento degli outlier

Se una fonte si discosta fortemente dal resto delle fonti, non deve necessariamente determinare il risultato finale.

Il sistema deve poter:

* calcolare la distanza dal consenso;
* individuare valori anomali;
* ridurre il peso di un valore anomalo;
* mantenere comunque il dato originale;
* mantenere la fonte;
* mantenere lo storico.

L'obiettivo non è eliminare automaticamente i dati diversi, ma evitare che un singolo dato distorca il risultato.

Per esempio:

```text
Fonte A → 30
Fonte B → 31
Fonte C → 29
Fonte D → 48  ← OUTLIER
```

Il sistema deve segnalare:

```text
OUTLIER DETECTED
Fonte D
Deviazione: +54%
```

senza cancellare il dato.

---

# 10. Data Quality e validazione

Ogni dato dovrebbe avere un livello di qualità.

Possibili stati:

```text
VALID
WARNING
SUSPICIOUS
INVALID
MISSING
```

Il sistema deve controllare automaticamente:

* valori impossibili;
* duplicati;
* date errate;
* giocatori senza squadra;
* statistiche incoerenti;
* minuti superiori al possibile;
* gol negativi;
* prezzi fuori scala;
* ruoli incompatibili;
* eventi duplicati;
* conflitti tra fonti.

Esempio:

```text
Data Quality Score: 94/100
```

Questo score deve essere distinto dal Fantasy Rating.

---

# 11. Database

Il database deve essere strutturato in modo modulare.

## Tabelle principali

```text
players
teams
competitions
seasons
sources
source_weights
```

## Statistiche

```text
player_season_stats
player_match_stats
player_events
player_positions
```

## Valutazioni

```text
player_valuations
player_market_values
player_consensus
player_ratings
player_fantasy_scores
```

## Ruoli e gerarchie

```text
player_roles
player_roles_history
player_set_pieces
player_set_pieces_history
```

## Stato fisico

```text
player_injuries
player_suspensions
player_availability
```

## Calendario

```text
fixtures
team_strength
fixture_difficulty
```

## Fantacalcio

```text
leagues
league_rules
league_teams
fantasy_rosters
fantasy_roster_players
fantasy_transactions
fantasy_bids
fantasy_budget
```

## Sistema decisionale

```text
player_recommendations
player_alternatives
player_risk_scores
player_confidence_scores
optimizer_runs
```

---

# 12. Snapshot del database

Il sistema deve poter creare snapshot della situazione.

Esempio:

```text
2026-08-24 18:00
```

Lo snapshot deve permettere di ricostruire:

* quotazioni;
* disponibilità;
* rose;
* rating;
* consensus;
* gerarchie;
* stato fisico.

Questo è particolarmente importante durante un'asta.

---

# 13. Scheda giocatore

La pagina di dettaglio deve essere il centro dell'applicazione.

Deve mostrare:

* nome;
* squadra;
* ruolo;
* ruoli secondari;
* età;
* altezza;
* peso;
* piede;
* valore di mercato;
* quotazione consensus;
* forma;
* titolarità stimata;
* affidabilità;
* stato fisico;
* infortunio;
* squalifica;
* rigorista;
* punizioni;
* corner;
* gerarchie della squadra;
* Fantasy Rating;
* rapporto qualità/prezzo;
* livello di rischio;
* confidence score.

---

# 14. Storico delle prestazioni

La scheda deve permettere di analizzare il giocatore stagione per stagione.

## Statistiche base

* presenze;
* partite da titolare;
* minuti;
* gol;
* assist;
* gol su rigore;
* rigori sbagliati;
* ammonizioni;
* espulsioni;
* autogol;
* clean sheet.

## Statistiche fantasy

* bonus;
* malus;
* media voto;
* fantamedia;
* bonus medi;
* malus medi.

## Statistiche avanzate

* xG;
* xA;
* tiri;
* tiri in porta;
* occasioni create;
* passaggi chiave;
* dribbling;
* contrasti;
* intercetti;
* recuperi;
* progressive carries;
* progressive passes.

---

# 15. Grafici storici

La pagina giocatore deve mostrare graficamente l'evoluzione del giocatore.

Possibili grafici:

* gol per stagione;
* assist per stagione;
* fantamedia;
* media voto;
* xG;
* xA;
* minuti;
* presenze;
* bonus;
* malus;
* andamento della quotazione;
* andamento del valore di mercato;
* Fantasy Rating;
* titolarità;
* disponibilità;
* trend recente.

L'utente deve poter cambiare:

```text
Periodo
[ Ultime 5 partite ▼ ]

Stagione
[ 2025/26 ▼ ]

Competizione
[ Serie A ▼ ]
```

---

# 16. Analisi forma recente

Oltre allo storico stagionale deve esistere una sezione dedicata alla forma recente.

Possibili finestre:

```text
Ultime 3
Ultime 5
Ultime 10
Ultime 15
Intera stagione
```

Metriche:

* gol;
* assist;
* xG;
* xA;
* minuti;
* tiri;
* occasioni create;
* media voto;
* fantamedia;
* bonus;
* malus.

La forma recente deve avere un peso separato rispetto alla performance storica.

---

# 17. Heatmap

La scheda giocatore deve includere una heatmap del campo.

La heatmap deve essere basata su dati reali di posizione/evento quando disponibili.

Non deve essere una semplice immagine decorativa.

## Metriche possibili

* tocchi;
* zona media di ricezione;
* passaggi;
* tiri;
* assist;
* recuperi;
* progressive carries;
* progressive passes.

L'utente deve poter cambiare metrica e periodo.

Esempio:

```text
HEATMAP

Metrica:
[ Tocchi ▼ ]

Stagione:
[ 2025/26 ▼ ]

Partite:
[ Tutte ▼ ]
```

Se non sono disponibili dati di tracking/posizione sufficientemente affidabili, l'app deve mostrare chiaramente:

```text
Heatmap non disponibile per questa fonte/dataset.
```

Non deve inventare una heatmap.

---

# 18. Radar / esagono del giocatore

Ogni giocatore deve avere un radar/esagono con un profilo sintetico.

Il radar non deve essere basato su numeri inventati.

Deve essere calcolato a partire dalle statistiche reali.

I valori devono essere normalizzati rispetto ai giocatori dello stesso ruolo.

## Fisico

Quando i dati sono disponibili:

* velocità;
* accelerazione;
* forza;
* resistenza.

## Tecnica

* passaggio;
* controllo;
* dribbling;
* cross.

## Attacco

* finalizzazione;
* xG;
* tiri;
* posizionamento.

## Creazione

* xA;
* occasioni create;
* passaggi chiave;
* assist.

## Difesa

* intercetti;
* contrasti;
* recuperi.

## Mentalità / affidabilità

* continuità;
* minuti giocati;
* disciplina;
* affidabilità.

Un difensore non deve essere penalizzato perché segna meno di un attaccante.

I rating devono essere contestualizzati al ruolo.

---

# 19. Normalizzazione dei rating

I rating devono essere normalizzati rispetto a gruppi comparabili.

Possibili gruppi:

```text
Portieri
Difensori centrali
Terzini
Esterni
Centrocampisti
Trequartisti
Ali
Attaccanti
```

Quando necessario deve essere utilizzata una normalizzazione percentile.

Esempio:

```text
xG percentile tra gli attaccanti: 91
xA percentile tra gli attaccanti: 73
Minuti percentile tra gli attaccanti: 88
```

Questo rende il rating più interpretabile.

---

# 20. Fantasy Rating

Il progetto deve creare un rating proprietario orientato al fantacalcio.

Il Fantasy Rating deve considerare:

```text
potenziale
+
bonus attesi
+
titolarità
+
rigori
+
continuità
+
rapporto qualità/prezzo
-
rischio
```

Possibili componenti:

* produzione offensiva;
* produzione difensiva;
* probabilità di titolarità;
* probabilità di bonus;
* frequenza di malus;
* probabilità di essere rigorista;
* stato fisico;
* continuità;
* prezzo;
* trend recente;
* qualità della squadra;
* calendario;
* consenso delle fonti.

Il risultato deve essere interpretabile.

Non deve essere una black box.

---

# 21. Expected Fantasy Value

Oltre al Fantasy Rating deve essere calcolato un valore atteso.

Esempio concettuale:

```text
Expected Fantasy Value =
    expected_minutes
  × expected_fantasy_points_per_90
  × availability_factor
  × fixture_factor
```

Il modello deve distinguere:

```text
QUALITÀ DEL GIOCATORE
```

da:

```text
UTILITÀ FANTASY ATTUALE
```

Un giocatore molto forte ma sempre in panchina non deve necessariamente avere lo stesso valore fantasy di un titolare meno forte ma estremamente affidabile.

---

# 22. Rigoristi e calci piazzati

La scheda giocatore deve indicare chiaramente:

* rigorista principale;
* rigorista secondario;
* tiratore delle punizioni;
* tiratore dei corner;
* gerarchia attuale;
* storico della gerarchia;
* variazioni recenti.

Esempio:

```text
RIGORI
🟢 Principale

PUNIZIONI
🟡 Secondario

CORNER
🟢 Principale
```

Il sistema deve poter registrare anche il cambio di gerarchia nel tempo.

Deve inoltre indicare la confidence della gerarchia:

```text
Rigorista principale
Confidence: 92%
```

---

# 23. Bonus e malus

La piattaforma deve avere uno storico completo degli eventi fantasy.

## Bonus

* gol;
* assist;
* gol decisivo;
* gol su rigore;
* clean sheet;
* eventuali bonus specifici del regolamento.

## Malus

* ammonizione;
* espulsione;
* autogol;
* rigore sbagliato;
* gol subito dal portiere;
* eventuali altri malus del regolamento.

Il sistema deve permettere di configurare il regolamento fantasy utilizzato.

---

# 24. Sistema regolamento fantasy

Il sistema non deve assumere un unico regolamento.

Ogni lega deve poter definire:

```text
Gol
Assist
Ammonizione
Espulsione
Rigore sbagliato
Rigore parato
Gol subito
Clean sheet
Gol decisivo
Gol vittoria
Bonus portiere
Malus portiere
```

In questo modo il Fantasy Rating può essere ricalcolato in funzione della lega.

Esempio:

```text
Lega A
Gol attaccante = +3

Lega B
Gol attaccante = +4
```

Lo stesso giocatore potrebbe quindi avere un valore fantasy differente nelle due leghe.

---

# 25. Rosa ideale

La dashboard deve avere una sezione dedicata alla **Rosa Ideale**.

La Rosa Ideale rappresenta la combinazione di giocatori che massimizza il potenziale fantasy secondo il modello.

Possibili criteri:

```text
potenziale
+
bonus attesi
+
titolarità
+
rigoristi
+
continuità
+
rapporto qualità/prezzo
```

Questa modalità può concentrarsi sulla qualità teorica dei giocatori senza essere vincolata esclusivamente dalla disponibilità effettiva nella lega.

---

# 26. Rosa ideale realistica

La seconda sezione deve mostrare una **Rosa Ideale Realistica**.

Questa deve considerare lo stato reale della lega.

Deve tenere conto di:

* budget disponibile;
* giocatori già acquistati;
* giocatori acquistati dagli avversari;
* giocatori ancora disponibili;
* ruoli mancanti;
* vincoli della rosa;
* composizione della propria rosa;
* strategia della propria squadra;
* prezzo dei giocatori;
* valore atteso;
* rischio.

La rosa deve aggiornarsi automaticamente.

---

# 27. Aggiornamento dinamico delle rose

Se l'utente acquista un giocatore:

```text
Lautaro Martinez
```

il sistema deve aggiornare automaticamente la Rosa Ideale Realistica.

Se un avversario acquista Lautaro:

```text
AVVERSARIO
↓
Lautaro Martinez
```

Lautaro deve essere rimosso dai giocatori disponibili per l'utente.

Il sistema deve quindi conoscere:

```text
TU
↓
Rosa attuale

AVVERSARIO 1
↓
Rosa attuale

AVVERSARIO 2
↓
Rosa attuale

...

DATABASE
↓
Giocatori disponibili
```

e ricalcolare le opportunità.

---

# 28. Optimizer della rosa

Il sistema deve avere un motore di ottimizzazione.

Schema:

```text
                  TU
                   │
            ROSA ATTUALE
                   │
                   ↓
             OPTIMIZER
                   │
          ┌────────┴────────┐
          ↓                 ↓
     ROSA IDEALE      ROSA REALISTICA
```

L'optimizer deve considerare:

* budget;
* ruoli;
* giocatori disponibili;
* giocatori già acquistati;
* giocatori degli avversari;
* Fantasy Rating;
* valore atteso;
* rischio;
* rapporto qualità/prezzo;
* equilibrio della rosa;
* regolamento della lega.

Per la prima implementazione può essere utilizzato un modello di ottimizzazione lineare/intera.

Successivamente può essere introdotta una funzione obiettivo più sofisticata.

---

# 29. Simulazione dell'asta

Il sistema dovrebbe poter simulare scenari.

Esempio:

```text
Budget iniziale: 500
Budget rimanente: 287

Scenario:
Acquisto Lautaro a 42

→ budget rimanente: 245
→ modifica priorità attaccanti
→ modifica alternative
→ modifica budget per centrocampo
```

L'utente dovrebbe poter simulare un acquisto senza modificare realmente la rosa.

```text
SIMULA ACQUISTO
```

e confrontare:

```text
Scenario A
Lautaro 42

Scenario B
Attaccante A 25
Attaccante B 17
```

---

# 30. Sistema "Perché comprarlo?"

Ogni giocatore deve avere una spiegazione sintetica e comprensibile.

Esempio:

```text
Lautaro Martinez — 42 crediti

🟢 Rigorista
🟢 Alta probabilità di titolarità
🟢 Alta produzione offensiva
🟢 Fantamedia elevata
🟡 Prezzo elevato
🔴 Costo opportunità alto
```

Il sistema deve spiegare i fattori positivi e negativi.

La spiegazione deve essere generata dai dati del modello, non inventata manualmente.

---

# 31. Sistema "Perché NON comprarlo?"

Ogni giocatore deve poter mostrare anche i principali rischi:

* prezzo troppo alto;
* concorrenza nel ruolo;
* bassa titolarità;
* rischio infortunio;
* calendario sfavorevole;
* bassa produzione;
* molti malus;
* scarso rapporto qualità/prezzo;
* alternative migliori;
* costo opportunità.

Esempio:

```text
RISCHI

🔴 Prezzo 22% superiore al valore stimato
🟡 Titolare non garantito
🟡 Calendario difficile
🟢 Nessun problema fisico rilevante
```

---

# 32. Alternative

Per ogni giocatore deve essere possibile mostrare alternative comparabili.

Esempio:

```text
GIOCATORE TARGET

Lautaro Martinez
42 crediti

ALTERNATIVE

Giocatore A
28 crediti

Giocatore B
25 crediti

Giocatore C
21 crediti
```

Le alternative devono essere selezionate in base a:

* ruolo;
* Fantasy Rating;
* prezzo;
* disponibilità;
* rendimento;
* rischio;
* rapporto qualità/prezzo;
* titolarità.

L'algoritmo deve evitare di proporre alternative semplicemente perché appartengono allo stesso ruolo.

Deve cercare giocatori con un profilo fantasy comparabile.

---

# 33. Calendario e fixture difficulty

Il calendario deve entrare nel modello decisionale.

Per ogni squadra devono essere calcolati:

* difficoltà prossime partite;
* gol attesi;
* clean sheet atteso;
* forza avversario;
* casa/trasferta;
* sequenza delle partite;
* periodi particolarmente favorevoli;
* periodi particolarmente difficili.

Esempio:

```text
PROSSIME 5 PARTITE

Milan     ███████░░░
Roma      ████░░░░░░
Napoli    █████░░░░░
```

Il calendario non deve determinare da solo il Fantasy Rating, ma essere un fattore correttivo.

---

# 34. Probabile formazione e titolarità

La titolarità deve essere modellata come probabilità.

Esempio:

```text
TITOLARITÀ STIMATA

90%  ██████████████████
```

Possibili fattori:

* minuti recenti;
* ultime formazioni;
* concorrenza;
* infortuni;
* squalifiche;
* rotazioni;
* calendario;
* modulo;
* gerarchie.

Il modello deve distinguere:

```text
probabilità convocazione
probabilità titolarità
probabilità ingresso
minuti attesi
```

---

# 35. Injury Risk e Availability

Lo stato fisico deve essere integrato nel modello.

Possibili stati:

```text
FIT
DOUBTFUL
INJURED
SUSPENDED
RETURNING
```

Devono essere mantenuti:

* tipo di infortunio;
* data inizio;
* data stimata rientro;
* data effettiva rientro;
* partite saltate;
* storico infortuni;
* giorni di indisponibilità.

Il modello deve distinguere:

```text
Rischio infortunio
```

da:

```text
Infortunio attuale
```

---

# 36. Player Comparison

Deve essere presente una modalità di confronto.

Esempio:

```text
COMPARA

Lautaro Martinez
vs
Marcus Thuram
vs
Vlahovic
```

Confronto su:

* prezzo;
* Fantasy Rating;
* titolarità;
* gol;
* assist;
* xG;
* xA;
* fantamedia;
* media voto;
* minuti;
* rigorista;
* rischio;
* calendario;
* qualità/prezzo;
* trend.

---

# 37. Market Scanner

Deve essere presente una sezione che analizzi automaticamente il mercato.

Categorie:

```text
MIGLIORI ACQUISTI
SOTTO-VALUTATI
SOPRA-VALUTATI
MIGLIOR RAPPORTO QUALITÀ/PREZZO
ALTI POTENZIALI
BASSO RISCHIO
DIFFERENZIALI
SORPRESE
```

Esempio:

```text
TOP VALUE

1. Player A
Value Score: 94

2. Player B
Value Score: 91

3. Player C
Value Score: 88
```

---

# 38. Differenziali

Il sistema deve identificare giocatori sottovalutati o poco considerati.

Un differenziale può essere definito da:

```text
Fantasy Rating alto
+
Prezzo basso
+
Bassa popolarità
+
Titolarità elevata
```

Il sistema deve distinguere:

```text
Differenziale di valore
```

da:

```text
Scommessa ad alto rischio
```

---

# 39. Data Warehouse

Il progetto deve essere trattato come un piccolo data warehouse sportivo.

La pipeline ideale è:

```text
FONTI
  ↓
IMPORTER
  ↓
RAW DATA
  ↓
NORMALIZZAZIONE
  ↓
ENTITY MATCHING
  ↓
VALIDAZIONE
  ↓
STORICO
  ↓
CALCOLI
  ↓
CONSENSUS
  ↓
FANTASY RATING
  ↓
OPTIMIZER
  ↓
DATABASE
  ↓
STREAMLIT
```

La UI non deve essere responsabile dell'acquisizione dei dati.

---

# 40. Separazione dei livelli

Il progetto deve essere organizzato almeno in questi livelli:

```text
Data Sources
    ↓
Importers
    ↓
Normalization
    ↓
Entity Matching
    ↓
Validation
    ↓
Database
    ↓
Repository / Data Access
    ↓
Business Logic
    ↓
Fantasy Engine
    ↓
Optimizer
    ↓
Streamlit UI
```

Questo permette di sostituire una fonte senza dover riscrivere la dashboard.

---

# 41. Repository Pattern

La UI non deve eseguire SQL direttamente.

La struttura dovrebbe essere:

```text
Streamlit
    ↓
Services
    ↓
Repositories
    ↓
MySQL
```

Esempio:

```text
PlayerRepository
LeagueRepository
StatsRepository
MarketRepository
FantasyRepository
```

Questo rende il progetto più facilmente testabile e manutenibile.

---

# 42. Cache

Streamlit deve utilizzare caching dove appropriato.

La dashboard non deve ricaricare continuamente dati invariati.

Distinguere:

```text
STATIC DATA
```

da:

```text
DYNAMIC DATA
```

Esempio:

```text
Anagrafica giocatore
→ cache lunga

Statistiche storiche
→ cache media

Probabili formazioni
→ cache breve

Stato asta
→ praticamente real-time
```

---

# 43. Aggiornamenti automatici

Gli importer devono poter essere eseguiti tramite job.

Esempio:

```text
Scheduler
    ↓
Importer
    ↓
Validation
    ↓
Normalization
    ↓
Database
    ↓
Recalculation
```

Possibili frequenze:

```text
Quotazioni       → giornaliero
Statistiche      → giornaliero
Infortuni        → frequente
Probabili formazioni → frequente
Mercato          → giornaliero
Storico          → una volta
```

La frequenza deve essere configurabile per fonte.

---

# 44. Audit e tracciabilità

Ogni dato importante deve poter essere ricondotto alla sua origine.

Per ogni valore:

```text
VALUE
SOURCE
SOURCE_ID
TIMESTAMP
IMPORT_RUN
CONFIDENCE
```

L'utente deve poter vedere:

```text
Consensus: 31.2

Fonti:
Fonte A → 30
Fonte B → 32
Fonte C → 31
Fonte D → 35
```

Questo rende il sistema trasparente.

---

# 45. Versionamento dei modelli

I calcoli non devono essere irreversibili.

Ogni Fantasy Rating dovrebbe sapere con quale versione del modello è stato calcolato.

Esempio:

```text
Fantasy Rating: 87.4
Model Version: v1.4
Calculated: 2026-08-24 17:55
```

Quando il modello cambia:

```text
v1.4
↓
v1.5
```

deve essere possibile ricalcolare i dati storici.

---

# 46. Confidence Score

Ogni previsione dovrebbe avere una confidence.

Esempio:

```text
Fantasy Rating
87

Confidence
92%
```

La confidence può dipendere da:

* quantità di dati;
* qualità delle fonti;
* accordo tra fonti;
* recenza;
* completezza;
* stabilità del giocatore;
* disponibilità delle statistiche.

Un rating 90 con confidence 98% deve essere considerato diversamente da un rating 90 con confidence 42%.

---

# 47. Explainability

Ogni decisione del sistema deve poter essere spiegata.

Per esempio:

```text
Fantasy Rating: 87

Contributi principali:

+12 Produzione offensiva
+10 Titolarità
+8 Rigori
+7 Forma recente
+5 Calendario
+4 Qualità squadra

-5 Prezzo
-3 Rischio fisico
-2 Malus
```

Questo è fondamentale per evitare una vera e propria black box.

---

# 48. Dashboard principale

La dashboard principale dovrebbe mostrare una panoramica immediata.

Possibili sezioni:

```text
┌─────────────────────────────────────────────┐
│ FANTASY FOOTBALL INTELLIGENCE               │
├─────────────────────────────────────────────┤
│ Budget │ Rosa │ Disponibili │ Rating Medio  │
├─────────────────────────────────────────────┤
│ TOP ACQUISTI                                │
├─────────────────────────────────────────────┤
│ SOTTO-VALUTATI                              │
├─────────────────────────────────────────────┤
│ DIFFERENZIALI                               │
├─────────────────────────────────────────────┤
│ MIGLIORI ALTERNATIVE                        │
├─────────────────────────────────────────────┤
│ RISCHI / ALERT                              │
└─────────────────────────────────────────────┘
```

---

# 49. Alert system

Il sistema deve generare alert automatici.

Esempi:

```text
🟢 Rigorista appena nominato
🟢 Prezzo in forte crescita
🟢 Titolarità aumentata
🟡 Possibile turnover
🟡 Infortunio da monitorare
🔴 Squalifica
🔴 Perdita del posto da titolare
🔴 Prezzo molto superiore al valore stimato
```

Gli alert devono avere timestamp e storico.

---

# 50. Sistema di notifiche

In futuro gli alert possono essere inviati tramite:

* dashboard;
* email;
* Telegram;
* webhook;
* notifiche push.

La logica degli alert deve però rimanere indipendente dal canale di notifica.

---

# 51. Ottimizzazione in tempo reale durante l'asta

La modalità asta dovrebbe essere una modalità separata dell'app.

Durante l'asta deve essere possibile registrare:

```text
PLAYER
PRICE
TEAM
OWNER
TIMESTAMP
```

Dopo ogni acquisto:

```text
DATABASE
   ↓
ROSE AGGIORNATE
   ↓
GIOCATORI DISPONIBILI
   ↓
BUDGET
   ↓
OPTIMIZER
   ↓
NUOVA STRATEGIA
```

La dashboard dovrebbe mostrare:

```text
CHI COMPRARE ORA
```

e:

```text
CHI EVITARE
```

in funzione della situazione attuale.

---

# 52. Strategia adattiva

La strategia deve cambiare in funzione della situazione.

Esempio:

```text
Budget alto
+
Molti giocatori disponibili
=
Strategia aggressiva
```

oppure:

```text
Budget basso
+
Pochi giocatori disponibili
=
Strategia conservativa
```

Il sistema dovrebbe suggerire:

```text
TARGET
TARGET ALTERNATIVO
PREZZO MASSIMO
PREZZO CONSIGLIATO
PREZZO OLTRE IL QUALE PASSARE
```

---

# 53. Prezzo massimo consigliato

Per ogni giocatore deve essere possibile calcolare:

```text
Prezzo stimato
Prezzo massimo
Prezzo opportunità
```

Esempio:

```text
Lautaro

Valore stimato:       38
Prezzo consigliato:   40
Prezzo massimo:       44
Prezzo attuale:       42

STATUS:
🟢 Acquistabile
```

Se il prezzo supera il valore massimo:

```text
🔴 PASSARE
```

---

# 54. Costo opportunità

Il sistema deve considerare che spendere 50 crediti per un giocatore impedisce di spenderli altrove.

Per questo deve confrontare:

```text
Acquisto A
```

contro:

```text
Combinazione B + C
```

Esempio:

```text
Lautaro → 45

oppure

Attaccante B → 25
Centrocampista C → 20
```

Il modello deve valutare entrambe le configurazioni.

---

# 55. Obiettivo finale

Il risultato finale deve essere una piattaforma in grado di rispondere a domande come:

## Sul singolo giocatore

* Quanto vale?
* Quanto è affidabile?
* Quanto gioca?
* Quanti gol produce?
* Quanti assist produce?
* Come è andato nelle ultime stagioni?
* Quanto prende di voto?
* Quanto produce come fantamedia?
* È rigorista?
* È titolare?
* Come gioca in campo?
* Dove si posiziona?
* Quali sono i suoi punti di forza?
* Quali sono i suoi punti deboli?
* Qual è il suo rapporto qualità/prezzo?
* Quanto è rischioso?
* Qual è la confidence del modello?

## Sul mercato

* Chi è il miglior acquisto?
* Chi è sottovalutato?
* Chi è sopravvalutato?
* Quali sono le migliori alternative?
* Chi conviene comprare con un determinato budget?
* Quali giocatori sono ancora disponibili?
* Qual è il prezzo massimo consigliato?

## Sulla propria rosa

* Quali ruoli devo ancora coprire?
* Quali giocatori mi mancano?
* Qual è la mia rosa ideale?
* Qual è la miglior rosa realistica?
* Chi devo cercare all'asta?
* Quali sono le alternative se perdo un giocatore?
* Come devo distribuire il budget?

## Sulla lega

* Chi è già stato acquistato?
* Quali giocatori sono ancora disponibili?
* Quali giocatori sono stati presi dagli avversari?
* Come cambia la mia strategia dopo ogni acquisto?
* Qual è la migliore rosa possibile con ciò che rimane?
* Quali sono i giocatori più importanti ancora disponibili?

---

# 56. Principio finale

L'app non deve essere costruita come:

```text
SCRAPING
    ↓
STREAMLIT
```

ma come:

```text
                ┌───────────────┐
                │  DATA SOURCES │
                └───────┬───────┘
                        ↓
                ┌───────────────┐
                │   DATA LAKE   │
                └───────┬───────┘
                        ↓
                ┌───────────────┐
                │ NORMALIZATION │
                └───────┬───────┘
                        ↓
                ┌───────────────┐
                │ ENTITY MATCH  │
                └───────┬───────┘
                        ↓
                ┌───────────────┐
                │  VALIDATION   │
                └───────┬───────┘
                        ↓
                ┌───────────────┐
                │    MYSQL      │
                └───────┬───────┘
                        ↓
             ┌──────────┴──────────┐
             ↓                     ↓
      CONSENSUS ENGINE       FANTASY ENGINE
             │                     │
             └──────────┬──────────┘
                        ↓
                  OPTIMIZER
                        ↓
                   STREAMLIT
                        ↓
             FANTASY INTELLIGENCE
```

---

# 57. Priorità di sviluppo

La priorità di sviluppo deve essere:

1. costruire il database;
2. definire il modello dati;
3. raccogliere un grande dataset iniziale;
4. costruire gli importer;
5. creare il layer RAW DATA;
6. normalizzare i dati;
7. implementare l'entity matching;
8. implementare la validazione;
9. creare lo storico;
10. implementare il consensus engine;
11. implementare il sistema di confidence;
12. implementare il Fantasy Rating;
13. implementare l'Expected Fantasy Value;
14. implementare statistiche e grafici;
15. implementare analisi della forma;
16. implementare heatmap;
17. implementare radar/esagono;
18. implementare rigoristi e gerarchie;
19. implementare calendario e fixture difficulty;
20. implementare titolarità e probabili formazioni;
21. implementare injury/availability tracking;
22. implementare il sistema di leghe e rose;
23. implementare il market scanner;
24. implementare il sistema di alternative;
25. implementare il price recommendation engine;
26. implementare l'optimizer;
27. implementare la simulazione dell'asta;
28. implementare gli alert;
29. costruire la dashboard Streamlit definitiva;
30. implementare caching e performance optimization;
31. implementare test automatici;
32. implementare logging e monitoring;
33. introdurre versionamento dei modelli;
34. introdurre notifiche e integrazioni esterne.

---

# 58. MVP consigliato

Per evitare di costruire subito un sistema enorme, il progetto dovrebbe partire da un MVP.

## MVP — Fase 1

```text
Players
Teams
Seasons
Sources

Player Season Stats
Player Match Stats

Market Values
Fantasy Quotations

Entity Matching

Consensus Engine

Fantasy Rating

Player Detail

Historical Charts
```

## Fase 2

```text
Set Pieces
Injuries
Availability
Fixture Difficulty
Probable Lineups

Heatmap
Radar
Player Comparison
```

## Fase 3

```text
Leagues
Rosters
Transactions
Bids
Available Players

Realistic Squad Optimizer
Market Scanner
Alternatives
Price Recommendation
```

## Fase 4

```text
Auction Mode
Auction Simulation
Adaptive Strategy
Alerts
Notifications
Advanced Prediction
```

In questo modo ogni fase produce un'applicazione già utilizzabile senza aspettare la realizzazione dell'intero sistema.

---

# 59. Struttura software consigliata

Una possibile struttura iniziale:

```text
fantasy-football/
│
├── app/
│   ├── streamlit_app.py
│   │
│   ├── pages/
│   │   ├── dashboard.py
│   │   ├── players.py
│   │   ├── player_detail.py
│   │   ├── market.py
│   │   ├── comparison.py
│   │   ├── squad.py
│   │   ├── league.py
│   │   └── auction.py
│   │
│   └── components/
│       ├── player_card.py
│       ├── charts.py
│       ├── radar.py
│       ├── heatmap.py
│       ├── alerts.py
│       └── tables.py
│
├── core/
│   ├── fantasy_engine/
│   ├── consensus_engine/
│   ├── optimizer/
│   ├── scoring/
│   ├── predictions/
│   └── recommendations/
│
├── data/
│   ├── importers/
│   ├── normalization/
│   ├── entity_matching/
│   ├── validation/
│   └── pipelines/
│
├── database/
│   ├── models/
│   ├── repositories/
│   ├── migrations/
│   └── connection.py
│
├── config/
│   ├── settings.py
│   ├── sources.py
│   └── fantasy_rules.py
│
├── jobs/
│   ├── update_players.py
│   ├── update_stats.py
│   ├── update_market.py
│   ├── update_injuries.py
│   └── recalculate_ratings.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── scripts/
│
├── requirements.txt
├── .env
└── README.md
```

---

# 60. Principio architetturale definitivo

Il progetto deve rispettare una regola fondamentale:

> **La UI visualizza e permette di interagire con i dati. Non deve essere responsabile della loro acquisizione, normalizzazione o interpretazione primaria.**

La responsabilità deve essere distribuita:

```text
IMPORTER
    ↓
acquisisce

NORMALIZER
    ↓
uniforma

ENTITY MATCHER
    ↓
identifica

VALIDATOR
    ↓
controlla

DATABASE
    ↓
conserva

CONSENSUS ENGINE
    ↓
combina

FANTASY ENGINE
    ↓
interpreta

OPTIMIZER
    ↓
decide

STREAMLIT
    ↓
visualizza
```

Questo rende il progetto scalabile.

Una nuova fonte non deve richiedere la riscrittura della dashboard.

Un nuovo regolamento non deve richiedere la riscrittura del database.

Un nuovo algoritmo di Fantasy Rating non deve richiedere la modifica degli importer.

Un nuovo frontend non deve richiedere la modifica della pipeline dati.

---

# 61. Visione finale

L'obiettivo non è avere semplicemente una pagina con la quotazione di un giocatore.

L'obiettivo è creare una **guida completa e dinamica al fantacalcio**, alimentata da dati storici e da più fonti, capace di analizzare i giocatori e di suggerire concretamente le migliori decisioni per la propria rosa.

Il prodotto finale deve comportarsi più come un **Fantasy Football Decision Engine** che come un semplice database.

La piattaforma deve trasformare:

```text
DATI
```

in:

```text
INFORMAZIONI
```

poi:

```text
INFORMAZIONI
        ↓
ANALISI
```

poi:

```text
ANALISI
        ↓
VALUTAZIONE
```

e infine:

```text
VALUTAZIONE
        ↓
DECISIONE
```

La vera funzione dell'applicazione è quindi:

```text
DATA
 ↓
KNOWLEDGE
 ↓
INSIGHT
 ↓
DECISION
```

Il risultato deve essere una piattaforma capace di dire non soltanto:

> "Questo giocatore ha un Fantasy Rating di 87."

ma:

> "Questo giocatore ha un Fantasy Rating di 87, una confidence del 93%, è rigorista principale, ha una probabilità di titolarità del 91%, un valore stimato di 38 crediti e un prezzo attuale di 34. È quindi un acquisto conveniente fino a circa 40 crediti. L'alternativa migliore è il giocatore X a 27 crediti. Se però viene acquistato dall'avversario Y, la strategia ottimale cambia verso il giocatore Z."

Questa è la direzione definitiva del progetto:

**non una dashboard di fantacalcio, ma un sistema di Fantasy Football Intelligence capace di trasformare dati, statistiche, mercato e situazione della lega in decisioni operative.**

# Parte II — Evoluzione: da dashboard a Decision Engine

> Questa parte è stata scritta dopo la Parte I e a lungo è rimasta
> appesa in coda con una numerazione tutta sua che ripartiva da §1,
> mentre la Parte I era già arrivata a §61 — e poi saltava a §106
> senza che §62-§105 esistessero da nessuna parte
> (BACKLOG-2026-08-31 §11). Le sezioni sono state rinumerate per
> continuare la sequenza, §62 in poi, **senza spostare né riscrivere
> una riga di contenuto**: cambiano solo i numeri nei titoli.
>
> I riferimenti "spec NN" che compaiono nei log di sessione in fondo
> al file NON usano questa numerazione: vengono dall'`imperfezioni.md`
> originale, prima che venisse diviso nei tre `impossibile-*.md`, ed
> erano già scollegati da questo documento prima della rinumerazione.

Le seguenti modifiche devono essere integrate nella specifica principale del progetto.

L'obiettivo è rendere il sistema non soltanto una dashboard statistica, ma un vero **Fantasy Football Decision Engine**, capace di trasformare dati grezzi in analisi, valutazioni, previsioni e decisioni operative.

---

# 62. Separazione tra dati osservati, metriche, previsioni e decisioni

Il sistema deve distinguere chiaramente quattro livelli:

```text
RAW DATA
    ↓
OBSERVED DATA
    ↓
DERIVED METRICS
    ↓
PREDICTIONS
    ↓
RECOMMENDATIONS
```

Esempio:

```text
Gol = dato osservato

xG/90 = metrica derivata

Probabilità di segnare = previsione

"Compralo fino a 38 crediti" = raccomandazione
```

Ogni valore deve quindi essere classificato in base alla propria natura.

Questo permette di sapere sempre:

* da dove proviene un dato;
* se è stato osservato direttamente;
* se è stato calcolato;
* se è una previsione;
* se deriva da una decisione del modello.

---

# 63. Separazione dei principali Score

Il sistema non deve concentrare tutto in un singolo Fantasy Rating.

Devono essere presenti almeno:

```text
PLAYER QUALITY
```

Quanto è forte il giocatore dal punto di vista calcistico.

```text
FANTASY VALUE
```

Quanto è utile al fantacalcio.

```text
VALUE FOR MONEY
```

Quanto rendimento offre rispetto al prezzo.

```text
RISK
```

Quanto è rischioso acquistarlo.

```text
CONFIDENCE
```

Quanto sono affidabili i dati e il modello che producono il risultato.

Infine:

```text
FANTASY DECISION SCORE
```

che combina le metriche precedenti.

Esempio:

```text
Player Quality       91
Fantasy Value        88
Value for Money      94
Risk                 22
Confidence            96%

Decision Score        89
```

Il sistema deve evitare di confondere la qualità assoluta del giocatore con la sua convenienza fantasy.

---


# 64. Contextual Help & Explainability UI

L'applicazione deve includere un sistema di spiegazioni contestuali accessibile direttamente dall'interfaccia.

Ogni metrica, indicatore, punteggio, abbreviazione e decisione del modello deve poter essere spiegato passando il mouse sopra l'elemento oppure cliccando su un'icona informativa.

L'obiettivo è evitare che l'utente debba ricordare il significato di tutte le metriche proprietarie del sistema.

---

# 65. Tooltip contestuali

Ogni elemento complesso deve avere un tooltip.

Esempio:

```text
SCARCITY 84/100  [?]

SCARCITY

Misura quanto è difficile trovare alternative
di valore simile ancora disponibili nell'asta.

84/100 = elevata scarsità.

Più il valore è alto, maggiore è il rischio
di perdere il giocatore senza avere alternative
equivalenti.

La metrica considera:
• giocatori disponibili
• qualità delle alternative
• ruolo
• replacement level
• budget residuo
• numero di giocatori ancora necessari

# 66. Glossario integrato

Deve essere presente un glossario consultabile direttamente dall'app.

Il glossario deve contenere almeno:

Fair Price;
Expected Auction Price;
Maximum Bid;
Auction Value;
Scarcity;
Replacement Level;
Opportunity Cost;
Competition Score;
Auction Pressure;
Inflation;
Deflation;
Risk Score;
Value Score;
Fantasy Rating;
Expected Fantasy Production;
Starting Probability;
Bonus Potential;
Malus Risk;
Price Confidence;
Decision Confidence;
Threat Score;
Market Momentum;
Portfolio Risk;
Portfolio Value;
Player Competition;
Price Distribution.
# 67. Spiegazione delle metriche

Ogni metrica deve avere tre livelli di spiegazione:

Livello 1 — Tooltip rapido

Una spiegazione di una o due frasi.

Esempio:

Fair Price

Il prezzo che il modello considera equo
per questo giocatore nella situazione attuale.
Livello 2 — Spiegazione dettagliata

Apertura del tooltip o click:

FAIR PRICE

Il Fair Price rappresenta il valore economico
stimato del giocatore.

Viene calcolato considerando:

• produzione fantasy prevista
• titolarità
• bonus attesi
• rischio
• ruolo
• scarsità
• replacement level
• mercato
• qualità delle fonti
• situazione della tua rosa
Livello 3 — Breakdown

L'utente deve poter vedere come è stato ottenuto il valore.

Esempio:

FAIR PRICE: 36

Produzione fantasy       +12
Titolarità               +6
Rigorista                +5
Scarcity                 +4
Forma                     +2
Rischio                   -2
Prezzo di mercato         +3
Alternative disponibili  -1
────────────────────────────
VALORE FINALE             36
# 68. Help per ogni decisione

Anche le decisioni del sistema devono essere spiegabili.

Esempio:

🟢 COMPRA FINO A 42

Tooltip:

PERCHÉ?

Il modello considera 42 crediti il limite
massimo consigliato.

A 42 il rapporto rischio/rendimento
rimane positivo.

Oltre 42 esistono alternative con un
rapporto qualità/prezzo migliore.
# 69. Explainability della decisione

Per ogni raccomandazione deve essere possibile aprire:

PERCHÉ QUESTA DECISIONE?

e visualizzare:

Fattori positivi

🟢 Rigorista principale
🟢 Alta titolarità
🟢 Produzione offensiva elevata
🟢 Poche alternative disponibili

Fattori negativi

🔴 Prezzo elevato
🟡 Rischio infortunio
🟡 Competizione elevata

Confronto

Fair Price:
36

Prezzo attuale:
38

Maximum Bid:
42

Expected Auction Price:
39

Decision:
COMPRA

# 70. Tooltips sulle metriche dell'asta

Durante l'asta le metriche principali devono essere sempre accompagnate da un sistema di help.

Esempio:

Fair Price [?]
Expected Price [?]
Maximum Bid [?]
Scarcity [?]
Risk [?]
Competition [?]
Opportunity Cost [?]

L'utente deve poter capire immediatamente ogni termine.

# 71. Esempio — Scarcity
SCARCITY 84/100 [?]

Tooltip:

SCARCITY

Indica quanto è difficile sostituire questo
giocatore con un'alternativa di valore simile.

84/100 = molto difficile da sostituire.

La scarsità aumenta quando:

• rimangono pochi giocatori forti nel ruolo;
• le alternative hanno un Fantasy Rating molto inferiore;
• molti avversari hanno ancora bisogno del ruolo;
• il replacement level è basso;
• il budget disponibile rende difficile acquistare alternative.

Una Scarcity elevata può giustificare un Maximum Bid
superiore al Fair Price standard.
# 72. Esempio — Replacement Level
REPLACEMENT LEVEL 72 [?]

Tooltip:

REPLACEMENT LEVEL

Rappresenta il livello del miglior giocatore
che puoi realisticamente acquistare come alternativa
se perdi questo giocatore.

Se il Replacement Level è basso,
perdere il giocatore è più grave.

Se il Replacement Level è alto,
hai molte alternative disponibili.
# 73. Esempio — Opportunity Cost
OPPORTUNITY COST -4.2 [?]

Tooltip:

OPPORTUNITY COST

Misura il valore delle alternative che rinunci
ad acquistare spendendo il budget su questo giocatore.

Esempio:

Player A:
40 crediti

Alternative:
Player B:
28

Player C:
22

Se spendere 40 su Player A impedisce di ottenere
combinazioni più efficienti, il costo opportunità
aumenta.

Più è alto il costo opportunità,
più bisogna essere cauti nell'acquisto.
# 74. Esempio — Maximum Bid
MAXIMUM BID 42 [?]

Tooltip:

MAXIMUM BID

È il prezzo massimo che il modello consiglia
di pagare in questa specifica situazione d'asta.

Non è necessariamente uguale al Fair Price.

Può aumentare o diminuire in base a:

• budget residuo;
• scarsità;
• alternative;
• giocatori rimasti;
• esigenze della rosa;
• budget degli avversari;
• replacement level;
• strategia d'asta;
• costo opportunità.

Il Maximum Bid viene aggiornato dinamicamente.
# 75. Esempio — Competition Score
COMPETITION 76/100 [?]

Tooltip:

COMPETITION SCORE

Stima quanto è probabile che altri partecipanti
competano aggressivamente per questo giocatore.

Il punteggio considera:

• budget degli avversari;
• ruoli ancora scoperti;
• giocatori già acquistati;
• alternative disponibili;
• necessità delle altre rose;
• comportamento osservato durante l'asta.

Un Competition Score elevato indica un maggiore
rischio di prezzo superiore al Fair Price.
# 76. Esempio — Risk Score
RISK 18/100 [?]

Tooltip:

RISK SCORE

Misura l'incertezza associata al giocatore.

Può includere:

• rischio infortunio;
• rischio rotazione;
• rischio titolarità;
• rischio disciplinare;
• volatilità delle prestazioni;
• incertezza del ruolo;
• rischio prezzo.

0 = rischio minimo
100 = rischio massimo
# 77. Esempio — Expected Auction Price
EXPECTED PRICE 39 [?]

Tooltip:

EXPECTED AUCTION PRICE

È il prezzo che il modello stima possa essere
raggiunto durante l'asta.

È diverso dal Fair Price.

FAIR PRICE:
quanto vale secondo il modello.

EXPECTED PRICE:
quanto probabilmente verrà pagato.

MAXIMUM BID:
quanto puoi arrivare a pagare senza compromettere
l'efficienza della tua rosa.
# 78. Esempio — Auction Pressure
AUCTION PRESSURE HIGH [?]

Tooltip:

AUCTION PRESSURE

Misura la pressione competitiva presente
in questo momento dell'asta.

Aumenta quando:

• molti partecipanti hanno bisogno dello stesso ruolo;
• rimangono pochi giocatori di livello elevato;
• gli avversari hanno molto budget;
• ci sono poche alternative;
• il giocatore è particolarmente desiderato.

Una pressione elevata tende ad aumentare
il prezzo finale.
# 79. Colori e livelli

I tooltip devono essere coerenti con i colori utilizzati dall'interfaccia.

Esempio:

🟢 favorevole
🟡 attenzione
🔴 sfavorevole

Per i punteggi:

0–30:
basso

31–60:
medio

61–80:
alto

81–100:
molto alto

Le soglie devono essere configurabili e non hard-coded.

# 80. "Come viene calcolato?"

Per ogni metrica derivata deve essere presente una funzione:

ⓘ Come viene calcolato?

che mostra:

formula;
variabili utilizzate;
pesi;
periodo temporale;
fonti utilizzate;
data dell'ultimo aggiornamento;
versione del modello.

Esempio:

SCARCITY

Model:
Scarcity Engine v1.4

Updated:
24/08/2026 17:32

Inputs:
• 17 players available
• 4 competitors needing ST
• Replacement Level: 68
• Top-tier alternatives: 3

Confidence:
87%
# 81. Source Transparency

Quando una metrica utilizza dati provenienti da più fonti, l'utente deve poter vedere quali.

Esempio:

FANTASY RATING 87 [?]

Sources:

Source A     40%
Source B     30%
Source C     20%
Source D     10%

Data freshness:
94%

Confidence:
91%

L'utente deve poter distinguere:

VALORE DEL MODELLO

da

QUALITÀ DEL DATO.

# 82. Data Freshness Indicator

Ogni informazione sensibile al tempo deve mostrare la propria recenza.

Esempio:

Rigorista:
🟢 Principale

Aggiornato:
2 ore fa [?]

Tooltip:

DATA FRESHNESS

Indica quanto recentemente questa informazione
è stata verificata.

Più il dato è recente, maggiore è la sua affidabilità
per decisioni relative all'asta.
# 83. Help persistente

L'utente deve poter attivare una modalità:

HELP MODE

che evidenzia tutti gli elementi dell'interfaccia che dispongono di una spiegazione.

In questo modo un nuovo utente può imparare progressivamente il funzionamento dell'app senza dover consultare documentazione esterna.

# 84. Glossario accessibile dall'asta

Nella modalità Auction Cockpit deve essere sempre disponibile:

[ ? GLOSSARIO ]

Il glossario deve poter essere cercato.

Esempio:

Cerca:
scarcity

↓

SCARCITY
Definizione
Formula
Interpretazione
Esempio
Impatto sul Maximum Bid
# 85. Principio UX

L'app deve essere estremamente potente dal punto di vista analitico, ma non deve richiedere all'utente di ricordare il funzionamento interno del modello.

La regola deve essere:

SE NON È IMMEDIATAMENTE COMPRENSIBILE
↓
DEVE ESSERE SPIEGABILE

Ogni numero importante deve poter rispondere a:

"Cosa significa?"

"Come viene calcolato?"

"Da quali dati deriva?"

"Quanto è affidabile?"

"Come influenza la mia decisione?"

Questo sistema di Contextual Help deve essere considerato parte integrante dell'architettura della dashboard e non una funzionalità secondaria.

# 86. Fonti dati ufficiali del progetto

L'applicazione deve utilizzare un numero limitato di fonti affidabili.

L'obiettivo non è raccogliere il maggior numero possibile di siti, ma ottenere il miglior rapporto tra:

- qualità dei dati;
- copertura;
- affidabilità;
- aggiornamento;
- stabilità;
- facilità di normalizzazione;
- rischio di blocco;
- carico sul sistema.

La dashboard NON deve interrogare tutte le fonti quando viene aperta.

Le fonti devono essere utilizzate dagli importer e i dati devono essere salvati nel database.

Architettura:

FONTI
 ↓
IMPORTER
 ↓
RAW DATA
 ↓
NORMALIZZAZIONE
 ↓
DATABASE
 ↓
CONSENSUS / FANTASY ENGINE
 ↓
STREAMLIT

---

# 87. Set iniziale di fonti

Il progetto deve partire con un numero limitato di fonti principali.

## 1. Fantacalcio.it

Utilizzo principale:

- quotazioni;
- FVM;
- ruoli;
- statistiche fantasy;
- media voto;
- fantamedia;
- gol;
- assist;
- ammonizioni;
- espulsioni;
- rigori;
- storico stagionale;
- dati specifici per il fantacalcio.

È la fonte di riferimento per la componente fantasy italiana.

I dati devono essere salvati localmente e non richiesti direttamente dalla dashboard.

---

## 2. FBref

Utilizzo principale:

- statistiche individuali;
- presenze;
- minuti;
- gol;
- assist;
- tiri;
- passaggi;
- creazione;
- difesa;
- statistiche avanzate;
- dati stagionali;
- confronto tra giocatori.

FBref deve essere utilizzato principalmente come fonte statistica indipendente dalla componente fantasy.

---

## 3. Understat

Utilizzo principale:

- xG;
- xA;
- shot data;
- produzione offensiva;
- expected goals;
- expected assists;
- dati avanzati offensivi.

Understat deve essere utilizzato per arricchire il modello con metriche expected.

I dati devono essere importati nel database e associati al player_id interno.

---

## 4. SofaScore

Utilizzo principale:

- statistiche partita;
- statistiche stagionali;
- rating;
- minuti;
- eventi;
- forma recente;
- informazioni sulla disponibilità;
- dati di partita;
- posizione/zone di gioco quando disponibili.

SofaScore deve essere considerato una fonte complementare e non necessariamente la fonte primaria per ogni metrica.

---

## 5. Transfermarkt

Utilizzo principale:

- valore di mercato;
- storico del valore di mercato;
- trasferimenti;
- squadra;
- data di nascita;
- nazionalità;
- altezza;
- piede;
- informazioni anagrafiche;
- storico trasferimenti.

Il valore di mercato Transfermarkt deve essere distinto dalla quotazione fantasy.

NON devono essere trattati come la stessa metrica.

---

# 88. Gerarchia delle fonti

Le fonti non devono avere tutte lo stesso peso.

Il sistema deve assegnare un peso configurabile per ogni categoria.

Esempio:

```text
FANTASY DATA
Fantacalcio.it       → peso alto

STATISTICHE
FBref                → peso alto
SofaScore            → peso alto

EXPECTED DATA
Understat             → peso alto

MARKET VALUE
Transfermarkt         → peso alto

I pesi effettivi devono essere configurabili nel database.

NON devono essere hard-coded nella dashboard.

# 89. Principio Multi-Source

Una singola metrica non deve necessariamente provenire da una sola fonte.

Esempio:

PLAYER

Gol:
Fantacalcio.it
FBref
SofaScore

xG:
Understat
eventuale altra fonte futura

Market Value:
Transfermarkt

Quotazione Fantasy:
Fantacalcio.it
eventuali future fonti fantasy

Il sistema deve conservare separatamente:

valore originale;
fonte;
timestamp;
stagione;
player_id;
qualità;
confidence.
# 90. Nessuna richiesta diretta dalla dashboard

Streamlit non deve fare:

USER
↓
STREAMLIT
↓
SITO ESTERNO
↓
SCRAPING
↓
STREAMLIT

Deve fare:

USER
↓
STREAMLIT
↓
MYSQL
↓
DATI GIÀ IMPORTATI

Questo permette di mantenere la dashboard veloce anche quando sono presenti migliaia di giocatori, statistiche e record storici.

# 91. Sistema di aggiornamento manuale

La dashboard deve avere un pulsante dedicato:

🔄 AGGIORNA STATISTICHE

Il pulsante NON deve necessariamente fare scraping direttamente all'interno della pagina Streamlit.

Deve avviare un processo di aggiornamento controllato.

Flusso:

CLICK
  ↓
AVVIO UPDATE JOB
  ↓
IMPORTER
  ↓
DOWNLOAD / SCRAPING
  ↓
RAW DATA
  ↓
VALIDAZIONE
  ↓
NORMALIZZAZIONE
  ↓
ENTITY MATCHING
  ↓
DATABASE
  ↓
RICALCOLO METRICHE
  ↓
CONSENSUS
  ↓
FANTASY RATING
  ↓
AUCTION ENGINE
  ↓
COMPLETATO
# 92. Stato dell'aggiornamento

Quando l'utente preme:

🔄 AGGIORNA STATISTICHE

la dashboard deve mostrare lo stato del processo.

Esempio:

AGGIORNAMENTO DATI

✓ Fantacalcio.it
✓ FBref
✓ Understat
⟳ SofaScore
○ Transfermarkt

Progress:
68%

Ultimo aggiornamento:
24/08/2026 17:42

Al termine:

✓ AGGIORNAMENTO COMPLETATO

Giocatori aggiornati:
523

Nuovi record:
1.842

Statistiche aggiornate:
14.238

Metriche ricalcolate:
523

Consensus aggiornati:
523

Fantasy Rating aggiornati:
523

Auction Values aggiornati:
523

Durata:
01:42
# 93. Aggiornamento selettivo

Il pulsante deve permettere, quando possibile, di scegliere il tipo di aggiornamento.

Esempio:

🔄 AGGIORNA DATI

[ Aggiornamento completo ]

[ Solo quotazioni ]

[ Solo statistiche ]

[ Solo infortuni ]

[ Solo valori di mercato ]

[ Ricalcola modelli ]

L'aggiornamento completo deve essere utilizzato quando necessario.

Gli aggiornamenti parziali devono evitare di scaricare nuovamente dati che non sono cambiati.

# 94. Aggiornamento incrementale

Gli importer devono preferire un aggiornamento incrementale.

Esempio:

Ultimo aggiornamento:
10:00

Nuovo aggiornamento:
17:00

Il sistema deve cercare principalmente i dati modificati dopo le 10:00 quando la fonte lo permette.

Questo riduce:

traffico;
tempo;
carico;
rischio di rate limit;
numero di richieste;
tempo necessario per aggiornare il database.
# 95. Cache

I dati importati devono essere memorizzati localmente.

La dashboard non deve ripetere la stessa richiesta a una fonte esterna.

Ogni record deve avere almeno:

source
source_player_id
player_id
value
collected_at
updated_at
season_id
# 96. Rate Limiting

Gli importer devono implementare:

rate limiting;
retry controllati;
timeout;
backoff;
caching;
gestione degli errori;
logging.

Il sistema non deve effettuare centinaia di richieste contemporaneamente senza controllo.

# 97. Fallimento di una fonte

Se una fonte non è disponibile:

FBref
❌ Temporaneamente non disponibile

l'applicazione deve continuare a funzionare utilizzando i dati già presenti nel database.

NON deve diventare inutilizzabile perché una singola fonte è offline.

La dashboard deve mostrare:

⚠ Dati FBref non aggiornati

Ultimo aggiornamento:
24/08/2026 12:30

Le altre fonti sono aggiornate.
# 98. Data Freshness

Ogni fonte deve avere il proprio timestamp.

Esempio:

Fantacalcio.it
✓ aggiornato 5 min fa

FBref
✓ aggiornato 2 ore fa

Understat
✓ aggiornato 3 ore fa

SofaScore
✓ aggiornato 25 min fa

Transfermarkt
✓ aggiornato ieri

Questo dato deve essere visibile nella sezione Data Quality.

# 99. Fonti future

L'architettura deve permettere di aggiungere successivamente nuove fonti senza modificare:

Streamlit;
Fantasy Engine;
Auction Engine;
database principale;
player_id interno.

Una nuova fonte deve richiedere principalmente:

NUOVO IMPORTER
      ↓
NORMALIZER
      ↓
ENTITY MATCHING
      ↓
DATABASE
# 100. Principio fondamentale sulle fonti

Il progetto NON deve cercare di utilizzare 20-30 siti contemporaneamente.

Un numero ridotto di fonti di qualità è preferibile a una quantità enorme di fonti duplicate.

Il sistema deve privilegiare:

QUALITÀ
+
STABILITÀ
+
STORICO
+
AGGIORNAMENTO
+
INDIPENDENZA TRA FONTI

rispetto alla semplice quantità.

# 101. Aggiornamento delle metriche dell'asta

Dopo ogni aggiornamento dei dati, devono essere ricalcolati automaticamente tutti i valori dipendenti.

Esempio:

Nuovo dato:

Player A
xG aumentato

↓

Fantasy Model

↓

Fantasy Rating aggiornato

↓

Fair Price aggiornato

↓

Scarcity ricalcolata

↓

Expected Auction Price aggiornato

↓

Maximum Bid aggiornato

↓

Alternative aggiornate

↓

Auction Strategy aggiornata

L'utente non deve dover ricalcolare manualmente ogni metrica.

# 102. Ultimo aggiornamento globale

La dashboard deve mostrare sempre:

DATI

Ultimo aggiornamento:
24/08/2026 17:45

Stato:
🟢 Tutte le fonti aggiornate

Modelli:
Auction Engine v1.0

Ultimo ricalcolo:
24/08/2026 17:47

In questo modo l'utente sa immediatamente se sta lavorando con dati aggiornati.

# 103. Regola finale

Il pulsante:

🔄 AGGIORNA STATISTICHE

deve aggiornare i dati nel database e successivamente ricalcolare tutte le metriche necessarie.

La dashboard deve leggere esclusivamente dal database.

NON deve essere necessario aggiornare manualmente la pagina per ogni singola fonte.

NON deve essere necessario eseguire manualmente ogni importer.

L'utente deve poter premere un singolo pulsante e ottenere:

DATI AGGIORNATI
↓
MODELLI AGGIORNATI
↓
FAIR PRICE AGGIORNATI
↓
MAXIMUM BID AGGIORNATI
↓
SCARCITY AGGIORNATA
↓
ALTERNATIVE AGGIORNATE
↓
AUCTION STRATEGY AGGIORNATA


**Queste 5 fonti sono un buon punto di partenza**: abbastanza diverse da creare un vero consensus, ma non così tante da trasformare l'aggiornamento in una macchina ingestibile. Fantacalcio.it è particolarmente importante perché fornisce direttamente dati fantasy e quotazioni/FVM, mentre le altre servono soprattutto a costruire il livello statistico, expected e di mercato. :contentReference[oaicite:2]{index=2}

Una precisazione importante: **prima di implementare gli scraper va verificato per ogni sito cosa è consentito dai relativi termini/robots e se esiste un'API o un dataset utilizzabile**. Non farei partire il progetto assumendo automaticamente che ogni pagina sia liberamente scrappabile.

# 104. Mappa completa delle fonti dati

Il sistema deve utilizzare fonti diverse a seconda del tipo di informazione richiesta.

NON è necessario interrogare tutte le fonti.

Per ogni categoria deve essere definita:

- fonte primaria;
- fonte secondaria;
- eventuale fonte di backup;
- peso della fonte;
- frequenza di aggiornamento;
- qualità del dato;
- disponibilità dello storico;
- modalità di acquisizione;
- eventuali limiti API;
- eventuali limitazioni legali/licenza.

L'architettura deve permettere di sostituire una fonte senza modificare il resto dell'applicazione.

---

# 105. Quotazioni e dati Fantasy

## Fonte primaria

Fantacalcio.it

Utilizzare per:

- quotazione;
- FVM;
- ruolo Classic;
- ruolo Mantra;
- media voto;
- fantamedia;
- gol;
- assist;
- ammonizioni;
- espulsioni;
- rigori;
- gol subiti;
- presenze;
- statistiche fantasy;
- storico stagionale.

## Fonti secondarie possibili

- Fantacalcio Online;
- Fantapazz;
- Fantamaster;
- Fantacalcio.it storico.

La fonte primaria deve avere il peso maggiore per le metriche specificamente legate al fantacalcio.

NON bisogna mischiare automaticamente quotazioni provenienti da sistemi fantasy con regole diverse.

---

# 106. Statistiche calcistiche generali

## Fonte primaria

FBref

Utilizzare per:

- presenze;
- minuti;
- titolarità;
- gol;
- assist;
- tiri;
- tiri in porta;
- passaggi;
- passaggi progressivi;
- carries;
- dribbling;
- contrasti;
- intercetti;
- recuperi;
- statistiche offensive;
- statistiche difensive;
- statistiche stagionali;
- confronti tra giocatori.

## Fonti secondarie

SofaScore

FotMob

WhoScored

Football-data.org

Queste fonti devono essere utilizzate soprattutto per verificare o completare i dati.

---

# 107. xG / xA / Expected Data

## Fonte primaria

Understat

Utilizzare per:

- xG;
- xA;
- shot data;
- produzione offensiva;
- qualità delle occasioni;
- expected goals;
- expected assists.

## Fonti alternative

FBref

Opta

StatsBomb

SofaScore

Sportmonks

IMPORTANTE:

xG provenienti da provider diversi NON devono essere trattati automaticamente come lo stesso valore.

Esempio:

Understat xG:
12.4

Opta xG:
11.8

StatsBomb xG:
12.1

Il database deve conservare separatamente:

```text
xg_understat
xg_opta
xg_statsbomb

e successivamente può essere creato:

xg_consensus
# 108. Eventi partita

Per gli eventi dettagliati:

gol;
assist;
rigori;
rigori sbagliati;
ammonizioni;
espulsioni;
sostituzioni;
tiri;
falli;
recuperi;
contrasti;
eventi minuto per minuto.

Fonti possibili:

Primarie / professionali

Opta / Stats Perform

StatsBomb

Wyscout

Fonti accessibili

SofaScore

FotMob

FBref

Il progetto deve preferire una fonte strutturata/API quando disponibile.

# 109. Heatmap e posizione in campo

Per la heatmap la priorità deve essere data a fonti che possiedono coordinate/event data.

Fonti possibili:

Opta;
StatsBomb;
Wyscout;
SkillCorner;
SofaScore;
FotMob.

La fonte deve fornire dati sufficientemente granulari per costruire una vera heatmap.

NON deve essere utilizzata una semplice immagine presa da un sito.

La heatmap deve essere generata dall'applicazione a partire dai dati.

Esempio:

eventi
 ↓
coordinate X/Y
 ↓
normalizzazione campo
 ↓
aggregazione
 ↓
heatmap
# 110. Valore di mercato
Fonte primaria

Transfermarkt

Utilizzare per:

valore di mercato;
storico del valore;
trasferimenti;
data trasferimento;
squadra;
nazionalità;
data di nascita;
altezza;
piede;
informazioni anagrafiche.
Fonti alternative

CIES Football Observatory

Capology / fonti economiche compatibili

altri provider professionali di market valuation.

IMPORTANTE:

Market Value NON equivale a Fantasy Value.

Esempio:

Market Value:
€55M

Fantasy Fair Price:
42 crediti

Sono due metriche completamente diverse.

# 111. Anagrafica giocatori

Per:

nome;
cognome;
nome completo;
data di nascita;
nazionalità;
altezza;
piede;
posizione;
squadra;
numero di maglia;
ID esterno.

Fonti possibili:

Transfermarkt;
FBref;
SofaScore;
FotMob;
football-data.org;
API-Football;
Sportmonks.

Il sistema deve preferire fonti con identificativi stabili.

# 112. Entity Matching

Per identificare lo stesso giocatore:

Fonti utili:

Transfermarkt ID;
FBref ID;
SofaScore ID;
FotMob ID;
API-Football ID;
football-data.org ID.

Il sistema deve costruire una tabella:

player_source_ids

Esempio:

internal_player_id: 153

Fantacalcio ID: 1234
FBref ID: 9876
SofaScore ID: 54321
Transfermarkt ID: 111222
FotMob ID: 333444

L'ID interno rimane stabile anche se una fonte cambia struttura.

# 113. Infortuni

Per:

infortunio;
tipo;
data;
durata;
rientro previsto;
stato;
partite saltate.

Fonti possibili:

Primarie

Siti ufficiali dei club

Siti ufficiali delle competizioni

Secondarie

Transfermarkt

SofaScore

FotMob

Sky Sport

La Gazzetta dello Sport

Tuttosport

Il sistema deve distinguere:

INJURED
DOUBTFUL
RETURNING
AVAILABLE

e non trasformare automaticamente una notizia in un dato certo.

# 114. Squalifiche

Per:

squalifica;
numero giornate;
motivo;
data;
partite da saltare;
rientro.

Fonti prioritarie:

Lega Serie A;
FIGC;
comunicati ufficiali;
fonti ufficiali delle competizioni.

Fonti secondarie:

Fantacalcio.it;
SofaScore;
Transfermarkt.

Le fonti ufficiali devono avere priorità sulle fonti giornalistiche.

# 115. Probabili formazioni e titolarità

Per stimare:

probabilità di titolarità;
possibile XI;
concorrenza;
rotazione;
indisponibili;
posizione prevista.

Fonti possibili:

Fantacalcio.it;
Sky Sport;
La Gazzetta dello Sport;
Tuttosport;
SofaScore;
FotMob;
siti ufficiali delle squadre.

IMPORTANTE:

La probabile formazione NON deve essere trattata come certezza.

Deve diventare una variabile probabilistica:

Starting Probability:
82%

non:

Titolarità:
SI
# 116. Rigoristi

Per identificare:

rigorista principale;
secondo rigorista;
terzo rigorista;
rigori calciati;
rigori segnati;
rigori sbagliati;
storico della gerarchia.

Fonti:

statistiche ufficiali;
Fantacalcio.it;
Transfermarkt;
SofaScore;
FBref;
siti ufficiali delle squadre;
comunicazioni/news ufficiali.

Il sistema deve combinare:

STORICO
+
GERARCHIA ATTUALE
+
MINUTAGGIO
+
PRESENZA IN CAMPO
# 117. Punizioni e corner

Per:

punizioni dirette;
punizioni indirette;
corner;
tiratore principale;
secondo tiratore;
quantità di calci piazzati;
assist da palla inattiva.

Fonti possibili:

Opta;
StatsBomb;
Wyscout;
SofaScore;
FotMob;
FBref;
fonti ufficiali.

Questa categoria deve avere particolare importanza perché i calci piazzati possono influenzare direttamente:

assist;
xA;
gol;
bonus;
Fantasy Rating.
# 118. Forma recente

Per la forma recente utilizzare principalmente:

SofaScore;
FotMob;
FBref;
Fantacalcio.it.

Il sistema deve poter calcolare finestre diverse:

Ultime 3 partite
Ultime 5
Ultime 10
Stagione
Ultimi 30 giorni

NON utilizzare solamente la media stagionale.

# 119. Calendario

Per:

partite future;
casa/trasferta;
sequenza avversari;
difficoltà calendario;
partite ravvicinate;
congestione del calendario.

Fonti:

Lega Serie A;
football-data.org;
SofaScore;
FotMob;
API-Football;
Sportmonks.

Il calendario deve essere salvato nel database.

# 120. Forza della squadra

Per valutare il contesto del giocatore:

posizione in classifica;
gol segnati;
gol subiti;
xG squadra;
xGA;
possesso;
produzione offensiva;
produzione difensiva.

Fonti:

FBref;
SofaScore;
Opta;
StatsBomb;
football-data.org.

Questi dati devono contribuire al modello del giocatore ma non sostituire le statistiche individuali.

# 121. Dati economici e stipendi

Se utili per analisi aggiuntive:

stipendio;
contratto;
scadenza;
costo trasferimento;
valore di mercato.

Fonti:

Transfermarkt;
Capology;
fonti ufficiali.

Questi dati sono secondari per l'asta fantasy.

Non devono avere un peso eccessivo nel Fantasy Rating.

# 122. Fonte ufficiale Serie A

Quando disponibile, la fonte ufficiale della Lega Serie A deve avere priorità per:

calendario;
risultati;
squadre;
competizione;
comunicazioni ufficiali;
dati ufficiali della competizione.

Le informazioni ufficiali devono avere priorità rispetto alle fonti giornalistiche quando si verifica un conflitto.

# 123. API / Provider professionali

Se in futuro il progetto dispone di budget per dati professionali, possono essere integrate:

Opta / Stats Perform;
StatsBomb;
Wyscout;
Sportradar;
SkillCorner;
Sportmonks;
API-Football.

Questi provider NON devono essere aggiunti tutti contemporaneamente.

Prima deve essere verificato:

costo;
licenza;
copertura Serie A;
profondità dello storico;
frequenza aggiornamento;
API;
rate limits;
possibilità di archiviare i dati;
diritti di utilizzo;
possibilità di redistribuire/elaborare i dati.
# 124. Pool consigliato per la prima versione

Per la V1 NON utilizzare 20 fonti.

Il set iniziale consigliato è:

1. Fantacalcio.it
   → Fantasy / quotazioni / MV / FM / bonus / malus

2. FBref
   → statistiche individuali / storico

3. Understat
   → xG / xA / shot data

4. SofaScore
   → forma / match data / rating / eventi complementari

5. Transfermarkt
   → market value / anagrafica / trasferimenti

6. Lega Serie A
   → calendario / informazioni ufficiali

7. FIGC
   → squalifiche / comunicazioni ufficiali

Queste sono le fonti di base.

# 125. Fonti secondarie opzionali

Solo se una metrica non è sufficientemente coperta:

FotMob
WhoScored
API-Football
Sportmonks
Football-data.org
CIES
Capology
Wyscout
StatsBomb
Opta

Non devono essere attivate tutte.

Devono essere utilizzate solamente quando aggiungono informazione realmente utile.

# 126. Regola di ridondanza

Il sistema deve evitare di avere:

10 fonti
↓
stessa statistica
↓
10 valori quasi identici

È inutile aumentare artificialmente il numero delle fonti.

Meglio:

1 fonte fantasy
+
2 fonti statistiche
+
1 fonte expected
+
1 fonte mercato
+
fonti ufficiali

rispetto a 20 fonti ridondanti.

# 127. Fonte primaria per ogni metrica

Nel database deve essere definita una matrice:

METRICA              PRIMARY             SECONDARY

Fantasy Price        Fantacalcio.it      Fantapazz
MV                   Fantacalcio.it      —
FM                   Fantacalcio.it      —
Gol                  FBref               SofaScore
Assist               FBref               SofaScore
xG                   Understat            FBref
xA                   Understat            FBref
Minutes              FBref               SofaScore
Starting XI          SofaScore            Fantacalcio.it
Market Value         Transfermarkt        CIES
Injury               Club ufficiale       Transfermarkt
Suspension           FIGC/Lega           Fantacalcio.it
Rigoristi            Fantacalcio.it      SofaScore
Set Pieces           SofaScore            Opta
Calendar             Lega Serie A        SofaScore

La matrice deve essere configurabile.

# 128. Source Confidence

Ogni dato importato deve avere:

source
source_priority
source_confidence
collected_at
updated_at

Esempio:

xG

Understat:
12.4
confidence 0.90

FBref:
12.1
confidence 0.85

SofaScore:
12.6
confidence 0.80

Il Fantasy Engine può successivamente calcolare:

xG Consensus:
12.36
# 129. Data Conflict Resolution

Quando due fonti sono in conflitto:

Fonte A:
rigorista principale

Fonte B:
rigorista secondario

il sistema NON deve semplicemente scegliere casualmente.

Deve:

confrontare timestamp;
confrontare affidabilità;
verificare eventuale fonte ufficiale;
mantenere entrambi i dati;
calcolare confidence;
registrare il conflitto;
scegliere il dato utilizzato dal modello.

Esempio:

Rigorista:
Lautaro Martinez

Confidence:
93%

Fonti:
3 concordano
1 discordante
# 130. Source Health Monitoring

La dashboard amministrativa deve mostrare lo stato delle fonti:

SOURCE HEALTH

Fantacalcio.it     🟢
FBref               🟢
Understat           🟢
SofaScore           🟢
Transfermarkt       🟡
Lega Serie A        🟢
FIGC                🟢

Per ogni fonte:

ultimo aggiornamento;
ultimo successo;
ultimo errore;
numero record importati;
tempo medio import;
error rate;
stato API/scraper.
# 131. Principio definitivo

La piattaforma non deve essere costruita attorno ai siti.

Deve essere costruita attorno alle METRICHE.

Il sistema deve poter dire:

MI SERVE:
xG
↓
cerco la fonte primaria configurata

MI SERVE:
Fantasy Price
↓
cerco la fonte fantasy configurata

MI SERVE:
Market Value
↓
cerco la fonte market value configurata

MI SERVE:
Suspension
↓
cerco prima la fonte ufficiale

In questo modo se una fonte smette di funzionare:

SOURCE DOWN
     ↓
FALLBACK SOURCE
     ↓
DATABASE
     ↓
ENGINE

e l'applicazione continua a funzionare.

# 132. Regola di performance

Il numero di fonti non deve influenzare direttamente il tempo di caricamento della dashboard.

La dashboard deve leggere:

MYSQL

e NON:

MYSQL
+
SITO 1
+
SITO 2
+
SITO 3
+
SITO 4
+
SITO 5

Gli aggiornamenti devono essere eseguiti tramite importer separati.

Il pulsante:

🔄 AGGIORNA STATISTICHE

avvia il processo di aggiornamento e successivamente ricalcola:

Consensus;
Fantasy Rating;
Fair Price;
Expected Auction Price;
Maximum Bid;
Scarcity;
Replacement Level;
Opportunity Cost;
Competition Score;
Risk Score;
Auction Strategy.

La dashboard rimane quindi veloce anche con uno storico molto grande.


Una cosa importante: **non userei Opta/StatsBomb/Wyscout come scraper nella V1**. Sono ottimi provider professionali, ma sono prodotti commerciali/API con licenze e costi; per un progetto personale partirei dalle fonti accessibili e strutturerei l'architettura in modo da poterli aggiungere successivamente. I provider professionali differiscono anche nella definizione delle metriche, quindi non bisogna trattare automaticamente, per esempio, uno xG Opta e uno xG StatsBomb come identici. :contentReference[oaicite:2]{index=2}

Inoltre, **football-data.org lo terrei come fonte di supporto**, soprattutto per competizioni, calendario, squadre, giocatori e risultati: la sua API espone proprio queste risorse e applica rate limiting, quindi è più sensato usarla come complemento che come motore statistico principale. :contentReference[oaicite:3]{index=3}

# 133. Player Image System

Le immagini dei giocatori NON devono essere recuperate tramite una ricerca Google casuale.

L'attuale comportamento:

Google Images
    ↓
prima immagine trovata
    ↓
URL salvato
    ↓
dashboard

NON è accettabile per la versione definitiva.

Il sistema deve utilizzare un catalogo strutturato di immagini sportive.

---

# 134. Player Image Provider

Ogni giocatore deve avere una o più immagini associate al proprio `player_id`.

Esempio:

```text
player_id:
153

name:
Lautaro Martinez

image:
https://...

source:
Sportmonks

image_type:
headshot

updated_at:
2026-08-24

La relazione deve essere:

player
   ↓
player_id
   ↓
player_image
   ↓
image_provider

L'immagine non deve essere identificata solamente dal nome del giocatore.

# 135. Fonti immagini

Le immagini devono provenire preferibilmente da:

Fonte primaria

Sportmonks Football API

Il provider restituisce direttamente un image_path associato al giocatore e al relativo ID. Questo è preferibile a una ricerca generica sul web.

Fonti alternative / future

Possono essere valutati provider professionali come:

Sportradar;
Stats Perform / Opta;
Wyscout;
API-Football;
Sportmonks;
altri provider con licenza esplicita per l'utilizzo delle immagini.

La scelta definitiva deve dipendere da:

qualità delle immagini;
copertura Serie A;
aggiornamento;
disponibilità API;
costo;
licenza;
possibilità di utilizzo nell'applicazione.
# 136. Image Matching

Il sistema deve collegare l'immagine al giocatore tramite gli ID delle fonti.

Esempio:

internal_player_id:
153

Fantacalcio ID:
1234

SofaScore ID:
98765

Sportmonks ID:
54321

Transfermarkt ID:
111222

L'immagine viene quindi associata al:

internal_player_id = 153

e non al testo:

"Lautaro Martinez"

Questo evita problemi con:

omonimi;
nomi abbreviati;
accenti;
ordine nome/cognome;
cambi di squadra;
variazioni del nome.
# 137. Image Quality

Il sistema deve verificare automaticamente la qualità dell'immagine.

Controlli:

URL valido;
HTTP status;
immagine realmente disponibile;
dimensioni minime;
formato;
aspect ratio;
presenza di placeholder;
immagine duplicata;
immagine corrotta.

Un'immagine non valida deve essere sostituita dalla fonte secondaria.

# 138. Image Fallback

Il sistema deve utilizzare una gerarchia:

PRIMARY IMAGE
      ↓
SECONDARY IMAGE
      ↓
TEAM / LEAGUE FALLBACK
      ↓
DEFAULT PLAYER PLACEHOLDER

Mai:

Google Images
    ↓
prima immagine disponibile
# 139. Placeholder professionale

Se non esiste una fotografia valida, deve essere mostrato un placeholder coerente con il design dell'app.

Esempio:

┌─────────────────────┐
│                     │
│       PLAYER        │
│        ICON         │
│                     │
└─────────────────────┘

Il placeholder deve essere preferibile a una fotografia casuale o non verificata.

# 140. Tipologia di immagini

La dashboard deve preferire:

Headshot

Fotografia frontale o busto del giocatore.

Utilizzata per:

player card;
classifiche;
risultati ricerca;
Auction Cockpit;
confronti.
Action Photo

Fotografia durante una partita.

Utilizzata eventualmente nella pagina dettaglio.

Team Photo

Utilizzata per:

squadra;
club;
contesto del giocatore.

La player card principale deve utilizzare preferibilmente l'HEADSHOT.

# 141. Standard grafico

Tutte le immagini devono essere normalizzate.

Il sistema deve applicare:

stesso aspect ratio;
stesso contenitore;
stesso crop;
stesso background quando necessario;
stesso border radius;
stessa dimensione.

Esempio:

PLAYER CARD

┌───────────────┐
│               │
│   HEADSHOT    │
│               │
├───────────────┤
│ Lautaro       │
│ Inter         │
│ ATT           │
└───────────────┘

In questo modo anche immagini provenienti da provider diversi avranno un aspetto coerente.

# 142. Image Cache

Le immagini non devono essere scaricate ad ogni caricamento della dashboard.

Pipeline:

IMAGE PROVIDER
      ↓
IMAGE DOWNLOAD
      ↓
VALIDATION
      ↓
CACHE / STORAGE
      ↓
DATABASE REFERENCE
      ↓
STREAMLIT

La dashboard deve leggere l'immagine dalla cache/CDN/storage configurato.

# 143. Image Metadata

Il database deve mantenere:

player_images

id
player_id
source
source_player_id
image_url
local_path
image_type
width
height
hash
is_primary
is_valid
created_at
updated_at

Questo permette di cambiare provider senza perdere lo storico.

# 144. Image Deduplication

Il sistema deve evitare di scaricare più volte la stessa immagine.

Può utilizzare:

URL;
hash del file;
source ID;
timestamp.

Esempio:

SHA256(image)

Se due URL restituiscono la stessa immagine, il sistema può evitare duplicati.

# 145. Aggiornamento immagini

Il pulsante:

🔄 AGGIORNA STATISTICHE

deve poter aggiornare anche le immagini quando necessario.

Tuttavia le immagini NON devono essere riscaricate ogni volta.

Il sistema deve controllare:

immagine esistente?
    ↓
SI
    ↓
ancora valida?
    ↓
SI → non scaricare

NO
    ↓
aggiorna

Questo riduce traffico e tempi di aggiornamento.

# 146. Image Source Indicator

Nella sezione amministrativa deve essere possibile vedere la fonte dell'immagine.

Esempio:

LAUTARO MARTINEZ

Image:
✓ Valid

Provider:
Sportmonks

Last checked:
24/08/2026

Type:
Headshot
# 147. Copyright / Licensing

Il sistema NON deve assumere che un'immagine trovata online sia liberamente utilizzabile.

Prima di utilizzare un provider di immagini devono essere verificati:

termini d'uso;
licenza;
diritti di utilizzo;
possibilità di caching;
possibilità di mostrare l'immagine nella propria applicazione;
eventuali obblighi di attribuzione;
eventuali limiti commerciali;
eventuali limiti sulla redistribuzione.

La fonte dell'immagine deve essere memorizzata nel database.

# 148. Image Provider Abstraction

L'applicazione deve avere un'interfaccia astratta:

ImageProvider
    │
    ├── SportmonksImageProvider
    ├── SofaScoreImageProvider
    ├── ApiFootballImageProvider
    └── FutureImageProvider

La UI non deve sapere da dove proviene l'immagine.

Deve semplicemente chiedere:

get_player_image(player_id)

e ricevere l'immagine corretta.

# 149. Obiettivo finale

La scheda giocatore deve apparire come una vera player card professionale.

Esempio:

┌──────────────────────────────────────────┐
│                                          │
│            [ PLAYER HEADSHOT ]           │
│                                          │
│          LAUTARO MARTINEZ                │
│          INTER                           │
│          ATTACCANTE                      │
│                                          │
├──────────────────────────────────────────┤
│ Fantasy Rating              91            │
│ Fair Price                   36           │
│ Maximum Bid                  42           │
│ Scarcity                     84           │
│ Risk                         18           │
└──────────────────────────────────────────┘

L'immagine deve sembrare parte integrante della piattaforma e non una fotografia casuale recuperata da Google.

La priorità deve essere:

immagine corretta;
giocatore corretto;
fonte identificabile;
qualità uniforme;
licenza verificata;
caching;
fallback automatico.

Il sistema deve quindi trattare le immagini come un vero dataset strutturato, esattamente come tratta statistiche, quotazioni e informazioni anagrafiche.


**Questa modifica la farei sicuramente.** E, anzi, la collegherei direttamente al sistema di **Entity Matching** che abbiamo già progettato: una volta che hai `player_id` + ID delle varie fonti, ottenere la foto corretta diventa molto più affidabile. Sportmonks, per esempio, restituisce esplicitamente `image_path` insieme all'ID del giocatore, quindi è esattamente il tipo di struttura che cerchiamo. :contentReference[oaicite:2]{index=2}

---

# Log sessione 2026-08-25 — integrazione repo esterni (fantacalcio-py, ScraperFantacalcio, fantacalcio-optimization, fantabeto, fantaSimulatore, FantacalcioPython)

Sessione partita dalla richiesta di valutare 6 repo GitHub esterni e integrare le idee utili nel progetto. Riepilogo di cosa è stato deciso, fatto e imparato — utile come riferimento futuro, non da rileggere come spec (quella resta sopra).

## Decomposizione e scope

I 6 repo sono stati raggruppati in 4 sotto-progetti indipendenti:

- **A — Metriche extra Fantacalciopedia** (da ScraperFantacalcio + fantacalcio-py): fatto.
- **B — Solver LP per la rosa ottimale** (da fantacalcio-optimization): fatto.
- **C — Predizione ML del punteggio** (da fantabeto, Bayesian NN): **annullato su richiesta esplicita dell'utente**, non implementato.
- **D — Simulatore calendario/classifica Monte Carlo** (da fantaSimulatore + FantacalcioPython): **annullato su richiesta esplicita dell'utente**, non implementato. Avrebbe richiesto import di un export Excel calendario lega, mai definito.

## A — Metriche extra da Fantacalciopedia (fatto)

Fantacalciopedia espone sulle pagine **dettaglio** del singolo giocatore (non sulla pagina elenco, che è l'unica scrappata finora) dati aggiuntivi verificati dal vivo: `Algoritmo Fantacalciopedia` (ALG FCP, 0-100), `Punteggio FCP`, `Solidità fantainvestimento %`, `Resistenza infortuni %`, presenze/gol/assist previsti, tag skill (Titolare, Rigorista, Goleador, Outsider...). La sorgente più pulita per i 4 valori numerici è `ul.skills li[data-percent]` (non il testo duplicato "3 su 5" altrove nella pagina).

Implementato:
- `scrapers/fantacalciopedia.py`: `parse_html` ora cattura anche `detail_url`; nuove `parse_detail`/`fetch_detail`.
- `db/schema.sql`: tabella `fcp_metrics` (player_id, scrape_date, alg_fcp, punteggio_fcp, investment_stability_pct, injury_resistance_pct, predicted_appearances/goals/assists, skills).
- `db/repository.py`: `save_fcp_metrics`, `get_latest_fcp_metrics`, `get_all_latest_fcp_metrics`.
- `pipeline/run_fcp_metrics.py`: script standalone, matching giocatore via `matching.player_matcher.match_name_to_player` (già esistente in progetto, riusato senza inventare nulla di nuovo), throttling **5s/richiesta** su richiesta esplicita dell'utente (~673 giocatori ⇒ circa 1 ora).
- `ranking/scorer.py`: `compute_risk` pesa (peso ridotto 0.2) `investment_stability_pct`/`injury_resistance_pct` se presenti, nessuna regressione se assenti; `alg_fcp` esposto come segnale informativo separato in `enrich_scores` (non mescolato in Fantasy Value/Player Quality).
- `dashboard/data_access.py` + `components.py`: merge e visualizzazione (ALG FCP + tag skill nella scheda giocatore).

**Nota operativa importante**: `pipeline/run_fcp_metrics.py` va lanciato con `python -m pipeline.run_fcp_metrics` dalla root del progetto, **non** `python pipeline/run_fcp_metrics.py` — altrimenti `ModuleNotFoundError: No module named 'db'` perché la root non è sul path. Vale probabilmente per gli altri script in `pipeline/` in contesti simili.

Spec completo: `docs/superpowers/specs/2026-08-25-fcp-metrics-design.md`.

## B — Solver LP per la rosa ottimale (fatto)

Nuovo modulo `ranking/lp_optimizer.py`, libreria **PuLP** (aggiunta a `requirements.txt`), due modalità:
- `constrained`: rosa attuale (`my_roster`) fissa, ottimizza solo gli slot rimanenti col budget residuo.
- `from_scratch`: ignora la rosa attuale, ottimizza tutti i 25 slot (3-8-8-6) con budget pieno — riferimento teorico.

Massimizza la somma di Fantasy Value (`score`) rispettando slot per ruolo e budget; candidati senza `price_current` vengono esclusi (un LP non può ottimizzare un costo ignoto). Esposto in `dashboard/data_access.py` (`get_optimal_squad_lp`) e in UI su `dashboard/pages/5_La_Mia_Rosa.py`, sezione "Rosa Ottimale (LP)", accanto alla Rosa Ideale euristica già esistente (non l'ha sostituita: sono due strategie diverse, una greedy e una ottima matematicamente).

## Stile "Apple-like" applicato alla dashboard

Su richiesta diretta (non tramite il tool `/design`, applicato direttamente al codice):
- `.streamlit/config.toml`: tema con blu di sistema `#0071e3`, superfici `#ffffff`/`#f5f5f7`, testo `#1d1d1f`.
- `dashboard/components.py`: nuova `inject_global_css()` — font stack `-apple-system`/SF Pro, sidebar grigio chiaro, bottoni pill blu, metriche in card arrotondate (18px), header con blur, expander/tabelle/alert con bordi arrotondati.
- Card giocatore (`fc-card`) ammorbidita: bordo più sottile, raggio maggiore, ombra leggera invece che dura.
- Collegata a tutte le pagine (`app.py`, le pagine per ruolo via `render_role_page`, le altre via `get_db_connection()`).
- **Verificata visivamente** con Streamlit avviato in locale e navigazione browser reale (non solo lettura codice) — approccio da ripetere per modifiche UI future, come da istruzioni di progetto.

## Idee per grafici (non ancora implementate), proposte a fine sessione

Ispirate ai repo esaminati e ai dati già disponibili in DB dopo il sotto-progetto A:

1. Scatter "Sottovalutati": ALG FCP (Y) vs Prezzo (X) per ruolo.
2. Radar per giocatore: Player Quality, Fantasy Value, Value for Money, Risk, ALG FCP normalizzati (collegabile alla sezione 18 "Radar/esagono" già presente in questa spec, ora con un dato esterno reale da includerci).
3. Bar chart Solidità/Resistenza infortuni per i giocatori in rosa.
4. Confronto Rosa Ideale (euristica) vs Rosa Ottimale (LP): Fantasy Value totale delle due strategie a confronto.
5. Istogramma prezzi per ruolo (inflazione asta).
6. Andamento storico Fantasy Value/quotazione per singolo giocatore (dati multi-`scrape_date` già in `quotations`, manca solo il grafico).

## Cose imparate / da ricordare

- Il progetto ha già un meccanismo di fuzzy-matching robusto (`matching/player_matcher.py`, `match_name_to_player`) pensato apposta per fonti che non espongono un `player_id` interno: va sempre riusato per nuove fonti, mai reinventato.
- `match_name_to_player` usa `fuzz.ratio`/`fuzz.partial_ratio`, **sensibili all'ordine delle parole**: "Martinez Lautaro" vs "Lautaro Martinez" può non matchare sopra soglia (85) se l'ordine è invertito tra fonti — attenzione nei test e in eventuali nuove fonti che invertono nome/cognome.
- Gli script in `pipeline/` vanno eseguiti come modulo (`python -m pipeline.xxx`) dalla root, non come file diretto.
- Fantacalciopedia tiene i segnali "di qualità" (ALG FCP, solidità, resistenza infortuni) solo nelle pagine dettaglio giocatore, non nell'elenco — qualunque arricchimento futuro da questa fonte richiede uno scrape per-giocatore aggiuntivo (costoso in richieste, va throttlato).


---

# Auction Intelligence Engine (implementato) — 2026-08-26

> I "(spec NN)" qui sotto rimandano alla numerazione dell'`imperfezioni.md`
> originale, non alle sezioni di questo file: vedi la nota della Parte II.

> Spostato da `impossibile-asta-live.md`: si è rivelato raggiungibile senza
> un feed live degli avversari, lavorando solo sui dati che l'app ha già
> (acquisti miei + "presi dagli avversari" registrati a mano) e assumendo
> che tutte le squadre della lega seguano le stesse regole (stesso budget,
> stessi slot per ruolo) di `ranking/budget.py`. Motore in
> `ranking/auction_intelligence.py`, aggregato da
> `dashboard/data_access.get_auction_intelligence`, mostrato nella scheda
> giocatore (`render_auction_intelligence`) sotto "Valuta acquisto".

## Dynamic Maximum Bid (spec 85)

Il Maximum Bid non è un valore fisso: parte dal fair price (quotazione
consensus) e sale con l'inflazione d'asta osservata e con la scarsità di
alternative nel ruolo, ma non supera mai quanto è realmente disponibile
(budget residuo meno una riserva di 1 credito per ogni altro slot ancora da
riempire — "massimo teorico" — scalato a un "massimo realistico" all'78%).

## Price Inflation / Deflation (spec 88) e Live Market Value (spec 89)

Confronta il prezzo medio pagato (miei acquisti + avversari) con il fair
price medio degli stessi giocatori al momento dell'acquisto: il segnale di
inflazione/deflazione risultante alza o abbassa progressivamente Expected
Auction Price e Maximum Bid per ogni valutazione successiva. Richiede almeno
3 acquisti registrati per essere considerato affidabile.

## Auction Timing (spec 90) e Auction Decision Output (spec 104)

Output semplice — 🟢 BUY NOW / ⏳ WAIT / 🔴 PASS / 💰 SAVE BUDGET — con il
motivo principale sempre visibile sotto, mai una black box.

## Opponent Budget Modeling (spec 93) e Rival Threat Score (spec 94)

Per ogni avversario osservato (dai "Presi dagli avversari"): speso, budget
residuo stimato, slot e ruoli mancanti, "massimo teorico"/"realistico" per
ogni ruolo, e un Threat Score 0-100 che combina budget residuo relativo e
aggressività di spesa osservata rispetto alla media della lega.

## Expected Auction Price (spec 96) e Auction Price Distribution (spec 97)

Oltre al fair price, quanto probabilmente costerà (Expected Auction Price) e
— quando ci sono almeno 5 acquisti storici — un range P25/mediana/P75/P90
proiettato sul fair price di questo giocatore specifico, invece di un
singolo numero.

## Stop-Loss (spec 98) ed Emotional Overbid Detection (spec 99)

Il Maximum Bid *è* lo stop-loss: il prezzo inserito nel campo "Prezzo da
valutare" viene confrontato con l'Expected Auction Price e, se supera del
15% o più, scatta un alert 🚨 OVERBID visibile subito.

## Cosa resta fuori (vedi `impossibile-asta-live.md`)

Nomination Strategy (92), Auction Pressure per-singola-nomina in tempo
reale (87), aggiornamento realmente automatico dello stato lega senza
input manuale (86), Portfolio Construction/Risk/Diversification (100-102),
e l'Auction Cockpit come vista full-screen dedicata invece che una sezione
nella scheda giocatore (103).
