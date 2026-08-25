# Impossibile — Analisi avanzata e modello predittivo

> Spostato da `imperfezioni.md` (ora `visione-progetto.md`) durante la
> riorganizzazione del 2026-08-25. Contenuto della visione originale
> **non realisticamente raggiungibile** con le fonti dati e l'architettura
> attuali del progetto.
>
> **Perché è impossibile (per ora):** richiede xG/xA/event/tracking data (Understat, Opta, StatsBomb...) che non scrappiamo, storico multi-stagione granulare per Trend Detection e Player Archetypes, e un'architettura a microservizi ("motore senza Streamlit") sproporzionata per un progetto singolo.
>
> Resta qui come riferimento/ispirazione futura, non come roadmap attiva.

---

# 3. Price Engine

Deve essere introdotto un vero **Price Engine**.

Per ogni giocatore il sistema deve calcolare:

```text
Valore teorico
Prezzo consigliato
Range di acquisto
Prezzo massimo
Prezzo oltre il quale passare
Prezzo attuale
```

Esempio:

```text
Lautaro Martinez

Valore stimato:       38
Prezzo consigliato:   35-39
Prezzo massimo:       43
Prezzo attuale:       34

STATUS:
🟢 BUY
```

Se il prezzo supera il valore massimo:

```text
🔴 PASS
```

Il prezzo massimo deve essere calcolato in funzione di:

* Fantasy Value;
* Expected Fantasy Value;
* budget;
* scarcity;
* replacement level;
* alternative disponibili;
* costo opportunità;
* situazione della rosa;
* situazione della lega.

---

# 4. Valore globale vs valore nella propria rosa

Il sistema deve distinguere:

```text
GLOBAL FANTASY VALUE
```

da:

```text
MARGINAL SQUAD VALUE
```

Il primo misura quanto è forte il giocatore in assoluto.

Il secondo misura quanto quel giocatore migliora concretamente la rosa dell'utente.

Esempio:

```text
Lautaro

Global Fantasy Value: 92

Ma:
- attacco già completo;
- budget limitato;
- alternative disponibili;

Marginal Squad Value: 71
```

Questo valore deve essere utilizzato dall'optimizer.

Lo stesso giocatore può quindi essere:

```text
Ottimo giocatore
```

ma:

```text
Cattivo acquisto per la mia rosa
```

---

# 5. Optimizer multi-obiettivo

L'optimizer non deve limitarsi a massimizzare il Fantasy Rating.

La funzione obiettivo deve considerare:

```text
Expected Fantasy Points
+
Value
+
Starting Probability
+
Squad Balance
+
Scarcity
+
Replacement Advantage

-
Risk
-
Cost
-
Opportunity Cost
```

con vincoli relativi a:

* budget;
* ruoli;
* numero di giocatori;
* giocatori disponibili;
* giocatori già acquistati;
* regolamento della lega;
* composizione della rosa.

L'optimizer deve poter produrre soluzioni alternative.

Esempio:

```text
SCENARIO A
Lautaro → 45 crediti

SCENARIO B
Attaccante B → 25
Centrocampista C → 20
```

Il sistema deve confrontare le due configurazioni e determinare quale massimizza il valore complessivo della rosa.

---

# 6. Scarcity Score

Deve essere introdotto lo **Scarcity Score**.

Il sistema deve valutare quanto sia difficile sostituire un giocatore.

Esempio:

```text
Attaccanti top disponibili: 3
Centrocampisti top disponibili: 12
```

Un giocatore può quindi avere:

```text
Scarcity Score: 94
```

anche se il suo Fantasy Rating non è il più alto.

La scarcity deve tenere conto di:

* numero di giocatori comparabili disponibili;
* qualità delle alternative;
* prezzo delle alternative;
* differenza di rendimento;
* situazione della lega;
* numero di squadre concorrenti.

---

# 7. Replacement Level

Deve essere introdotto il concetto di **Replacement Level**.

Il sistema deve chiedersi:

> Quanto è migliore questo giocatore rispetto alla migliore alternativa che posso realisticamente acquistare?

Esempio:

```text
Lautaro                 92
Migliore alternativa    81

Replacement Advantage   +11
```

Altro esempio:

```text
Centrocampista A         87
Migliore alternativa     85

Replacement Advantage    +2
```

Il primo giocatore ha quindi un'importanza strategica maggiore.

Il Replacement Advantage deve entrare nel calcolo del valore e dell'optimizer.

---

# 8. Decision Center

La dashboard deve avere una sezione centrale denominata:

```text
DECISION CENTER
```

Questa deve trasformare le analisi in decisioni operative.

Esempio:

```text
┌──────────────────────────────────────┐
│         DECISION CENTER              │
├──────────────────────────────────────┤
│                                      │
│ 🟢 COMPRA                            │
│ Player A                             │
│ Max Price: 38                        │
│                                      │
│ 🟢 DIFFERENZIALE                     │
│ Player B                             │
│                                      │
│ 🟡 ATTENDI                           │
│ Player C                             │
│                                      │
│ 🔴 EVITA                             │
│ Player D                             │
│                                      │
└──────────────────────────────────────┘
```

Ogni decisione deve essere accompagnata da una spiegazione.

---

# 9. Confidence Score

Ogni previsione deve avere una propria confidence.

Esempio:

```text
Titolarità:             89%   Confidence 94%
Rigorista principale:   YES   Confidence 98%
Fair Price:              38   Confidence 81%
Expected Points:        6.4   Confidence 72%
```

La confidence deve dipendere da:

* quantità dei dati;
* qualità delle fonti;
* accordo tra le fonti;
* recenza;
* completezza;
* stabilità del giocatore;
* disponibilità dei dati;
* consistenza storica.

Il sistema deve distinguere:

```text
Prediction
```

da:

```text
Prediction Confidence
```

---

# 10. Heatmap: solo dati reali

La heatmap deve essere generata esclusivamente quando esistono dati sufficienti.

Gerarchia:

```text
Tracking / Position Data
        ↓
Real Heatmap
```

oppure:

```text
Event Data
        ↓
Event Map
```

Se non sono disponibili dati sufficienti:

```text
Heatmap non disponibile per questo giocatore/fonte.
```

Il sistema non deve mai generare una heatmap fittizia o puramente decorativa.

---

# 11. Fantasy Role vs Tactical Role

Il database deve distinguere il ruolo fantasy dal ruolo tattico.

Esempio:

```text
Fantasy Role:
C

Tactical Roles:
LCM
CAM
RW
```

Devono quindi esistere:

```text
Fantasy Role
Tactical Role
Position History
```

Questo permette di analizzare l'evoluzione tattica senza modificare artificialmente il ruolo fantasy.

---

# 12. Role Evolution

Il sistema deve registrare l'evoluzione del ruolo.

Esempio:

```text
2023/24 → CM
2024/25 → RW
2025/26 → CAM
2026/27 → AM
```

Devono essere rilevati anche i cambiamenti statistici associati.

Esempio:

```text
Tiri ↑
xG ↑
Touch in box ↑
Occasioni create ↑
Set Pieces ↑
```

Questo può generare:

```text
BREAKOUT SIGNAL
```

oppure:

```text
DECLINE SIGNAL
```

Il sistema deve quindi individuare cambiamenti strutturali, non soltanto variazioni della forma.

---

# 13. Trend Detection

Deve essere introdotto un sistema di rilevamento dei trend.

Possibili segnali positivi:

```text
Minuti ↑
Tiri ↑
xG ↑
xA ↑
Touch area ↑
Titolarità ↑
Set pieces ↑
```

Possibili segnali negativi:

```text
Minuti ↓
xG ↓
Titolarità ↓
Concorrenza ↑
Tiri ↓
Ruolo arretrato
```

Il sistema deve produrre:

```text
BREAKOUT SIGNAL
STABLE
DECLINE SIGNAL
```

con relativa confidence.

---

# 14. Fixture Difficulty per ruolo

La difficoltà del calendario non deve essere unica.

Deve essere calcolata almeno per:

```text
Fixture Difficulty GK
Fixture Difficulty DEF
Fixture Difficulty MID
Fixture Difficulty ATT
```

Deve considerare:

* forza dell'avversario;
* casa/trasferta;
* expected goals;
* expected goals conceded;
* probabilità clean sheet;
* produzione offensiva avversaria;
* produzione difensiva avversaria;
* sequenza delle partite.

Questo permette di evitare valutazioni troppo generiche del calendario.

---

# 15. Player Archetypes

Il sistema deve poter assegnare archetipi ai giocatori.

Esempi:

```text
🔥 GOAL MACHINE
🎯 CREATOR
⚡ DIFFERENTIAL
🧱 DEFENSIVE ANCHOR
🎲 HIGH RISK / HIGH REWARD
💰 VALUE PICK
🧠 CONSISTENCY KING
🦶 SET-PIECE SPECIALIST
```

Gli archetipi devono essere generati automaticamente dai dati e non assegnati manualmente.

Un giocatore può appartenere a più archetipi.

---

# 16. Market Scanner

Il Market Scanner deve identificare automaticamente:

```text
MIGLIORI ACQUISTI
SOTTO-VALUTATI
SOPRA-VALUTATI
MIGLIOR VALUE FOR MONEY
DIFFERENZIALI
HIGH UPSIDE
LOW RISK
HIGH RISK / HIGH REWARD
```

Il sistema deve tenere conto anche della situazione reale della lega.

Un giocatore disponibile in generale ma già acquistato da un avversario non deve comparire tra i target acquistabili.

---

# 17. Auction Intelligence

La modalità asta deve diventare un modulo dedicato.

Dopo ogni acquisto:

```text
ACQUISTO
   ↓
AGGIORNAMENTO ROSE
   ↓
AGGIORNAMENTO BUDGET
   ↓
AGGIORNAMENTO DISPONIBILITÀ
   ↓
RECALCOLO SCARCITY
   ↓
RECALCOLO REPLACEMENT LEVEL
   ↓
RECALCOLO OPTIMIZER
   ↓
NUOVA STRATEGIA
```

La dashboard deve poter indicare:

```text
TARGET
ALTERNATIVE
MAX PRICE
CURRENT VALUE
PASS PRICE
```

---

# 18. Simulazione dell'asta

Deve essere possibile simulare un acquisto senza modificare la situazione reale.

Esempio:

```text
SIMULA:

Lautaro → 42
```

Il sistema deve mostrare:

```text
Budget rimanente
Nuova composizione ottimale
Nuove alternative
Giocatori da evitare
Nuovo valore marginale
Nuova strategia
```

L'utente può quindi confrontare:

```text
SCENARIO A
Lautaro 42

SCENARIO B
Attaccante B 25
Centrocampista C 17
```

prima di effettuare realmente l'acquisto.

---

# 19. Prezzo massimo e costo opportunità

Il sistema deve calcolare per ogni giocatore:

```text
Fair Price
Recommended Price
Maximum Price
Opportunity Cost
```

Il prezzo massimo deve dipendere dalla situazione specifica della rosa.

Un giocatore può quindi avere:

```text
Max Price globale: 43
```

ma:

```text
Max Price per la mia rosa: 37
```

perché esistono alternative più efficienti.

---

# 20. Architettura aggiornata

L'architettura definitiva deve essere:

```text
                    DATA SOURCES
                         ↓
                    RAW LAYER
                         ↓
                  NORMALIZATION
                         ↓
                  ENTITY MATCHING
                         ↓
                    VALIDATION
                         ↓
                   CORE DATABASE
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
        OBSERVED DATA          HISTORICAL DATA
              │                     │
              └──────────┬──────────┘
                         ↓
                  FEATURE ENGINE
                         ↓
              ┌──────────┼──────────┐
              ↓          ↓          ↓
          PLAYER      FANTASY      MARKET
          MODEL       MODEL        MODEL
              │          │          │
              └──────────┼──────────┘
                         ↓
                 PREDICTION ENGINE
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
        PLAYER VALUE           RISK MODEL
              │                     │
              └──────────┬──────────┘
                         ↓
                  DECISION ENGINE
                         ↓
                    OPTIMIZER
                         ↓
                 RECOMMENDATIONS
                         ↓
                    STREAMLIT
```

La UI deve essere considerata il **frontend del Decision Engine**, non il luogo in cui vengono eseguiti i calcoli fondamentali.

---

# 21. Il motore deve funzionare senza Streamlit

Prima di costruire la dashboard definitiva deve essere realizzato un motore Python indipendente.

Esempio concettuale:

```python
player = get_player(1042)

analysis = analyze_player(player)
```

Output:

```text
Player Quality:       91
Fantasy Value:        88
Value for Money:      94
Risk:                  18
Confidence:            96

Expected Points:      6.8

Fair Price:             38
Recommended Price:      35-39
Maximum Price:           43

Starting Probability:   91%
Penalty Taker:          YES

Best Alternative:
Player X

Recommendation:
BUY
```

Questo motore deve essere completamente indipendente da Streamlit.

Streamlit deve limitarsi a:

```text
INPUT
  ↓
SERVICE
  ↓
ENGINE
  ↓
OUTPUT
  ↓
UI
```

---

# 22. Nuova priorità di sviluppo

La roadmap viene aggiornata in questo modo:

1. definire il modello dati;
2. costruire il database;
3. raccogliere il dataset iniziale;
4. creare il RAW DATA layer;
5. creare gli importer;
6. implementare la normalizzazione;
7. implementare l'entity matching;
8. implementare la validazione;
9. creare lo storico;
10. implementare il Feature Engine;
11. implementare il Consensus Engine;
12. implementare Confidence Score;
13. implementare Player Quality;
14. implementare Fantasy Value;
15. implementare Value for Money;
16. implementare Risk Model;
17. implementare Expected Fantasy Value;
18. implementare Price Engine;
19. implementare Scarcity;
20. implementare Replacement Level;
21. implementare Marginal Squad Value;
22. implementare Fixture Difficulty;
23. implementare Titolarità e Probable Lineups;
24. implementare Injury/Availability;
25. implementare Set Pieces e gerarchie;
26. implementare Role Evolution;
27. implementare Trend Detection;
28. implementare Player Archetypes;
29. implementare Player Comparison;
30. implementare Market Scanner;
31. implementare Decision Center;
32. implementare League/Roster Engine;
33. implementare Optimizer multi-obiettivo;
34. implementare Auction Intelligence;
35. implementare Auction Simulation;
36. implementare Alert System;
37. costruire Streamlit UI;
38. implementare caching;
39. implementare test automatici;
40. implementare logging e monitoring;
41. implementare model versioning;
42. implementare notifiche.

---

# 23. Principio architetturale definitivo

Il progetto deve rispettare questa regola:

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

FEATURE ENGINE
    ↓
calcola metriche

CONSENSUS ENGINE
    ↓
combina fonti

FANTASY ENGINE
    ↓
valuta

PREDICTION ENGINE
    ↓
prevede

DECISION ENGINE
    ↓
raccomanda

OPTIMIZER
    ↓
costruisce la strategia

STREAMLIT
    ↓
visualizza
```

---

# 24. Visione finale aggiornata

L'obiettivo finale non è creare:

```text
DATABASE DI GIOCATORI
```

né semplicemente:

```text
DASHBOARD DI FANTACALCIO
```

Il prodotto deve diventare:

```text
FANTASY FOOTBALL DECISION ENGINE
```

capace di trasformare:

```text
DATA
 ↓
OBSERVATION
 ↓
FEATURES
 ↓
ANALYSIS
 ↓
PREDICTION
 ↓
VALUATION
 ↓
OPTIMIZATION
 ↓
DECISION
```

Il sistema deve poter dire:

> "Questo giocatore ha un Fantasy Value di 88, una confidence del 93%, è rigorista principale, ha una probabilità di titolarità del 91%, un fair price di 38 crediti e un prezzo massimo di 43. Nella tua rosa il suo Marginal Squad Value è 79. Il suo Replacement Advantage è +11 e la sua scarcity è 94. È quindi un target prioritario fino a 40 crediti. Oltre quella cifra il costo opportunità rende più conveniente la combinazione di Player X + Player Y."

Questo rappresenta il vero obiettivo del progetto:

**non limitarsi a descrivere i giocatori, ma determinare quale decisione produce il maggior valore possibile per la specifica rosa e situazione di lega dell'utente.**
