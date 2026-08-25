# Impossibile — MLOps, Backtesting e Model Governance

> Spostato da `imperfezioni.md` (ora `visione-progetto.md`) durante la
> riorganizzazione del 2026-08-25. Contenuto della visione originale
> **non realisticamente raggiungibile** con le fonti dati e l'architettura
> attuali del progetto.
>
> **Perché è impossibile (per ora):** è infrastruttura da vero team di data science (model registry, versionamento, backtesting senza data leakage, calibration, A/B testing dei modelli): richiede anni di dati storici granulari e una pipeline di training/valutazione che non esiste e non è giustificata per un tool di preparazione asta per una singola lega.
>
> Resta qui come riferimento/ispirazione futura, non come roadmap attiva.

---

# AGGIORNAMENTO — DATA GOVERNANCE, BACKTESTING E MODEL GOVERNANCE

Aggiungere alla specifica principale del progetto le seguenti componenti. Queste funzionalità completano l'architettura trasformando il sistema in un motore misurabile, spiegabile, versionabile, verificabile e continuamente migliorabile.

---

# 25. Data Quality Layer

Il sistema deve introdurre un livello specifico per la qualità dei dati.

La pipeline deve diventare:

DATA SOURCES
    ↓
RAW DATA
    ↓
NORMALIZATION
    ↓
ENTITY MATCHING
    ↓
DATA QUALITY
    ↓
VALIDATION
    ↓
CORE DATABASE

Il Data Quality Layer deve controllare:

- dati mancanti;
- dati duplicati;
- dati incoerenti;
- valori impossibili;
- valori fuori range;
- conflitti tra fonti;
- dati troppo vecchi;
- identificativi non validi;
- giocatori non correttamente associati;
- statistiche incomplete;
- variazioni anomale;
- fonti temporaneamente inattive.

Il sistema non deve eliminare automaticamente i dati problematici.

Deve conservarli, segnalarli e ridurne eventualmente l'influenza.

---

# 26. Data Quality Score

Ogni fonte, dataset e record importante deve poter avere un Data Quality Score.

Esempio:

Data Quality Score: 94/100

Completezza        98
Recenza             95
Consistenza         93
Affidabilità fonte  90
Entity Match       100

Il Data Quality Score deve poter influenzare la Confidence delle analisi successive.

Esempio:

Dato:
xG = 8.42

Data Quality = 97
Confidence = alta

oppure:

Dato:
xG = 8.42

Data Quality = 51
Confidence = bassa

---

# 27. Data Lineage

Ogni metrica importante deve essere riconducibile alla propria origine.

Il sistema deve poter rispondere alla domanda:

"Da dove arriva questo valore?"

Esempio:

Fantasy Rating: 88
        ↓
Feature Engine v1.4.2
        ↓
xG
xA
Minutes
Starting Probability
Set Pieces
Form
Price
Risk
        ↓
Source A
Source B
Source C

Devono essere conservati, quando disponibili:

- fonte;
- ID della fonte;
- timestamp;
- stagione;
- competizione;
- importer utilizzato;
- versione dell'importer;
- trasformazioni applicate;
- versione del modello.

---

# 28. Model Versioning

Tutti i modelli e gli algoritmi che producono risultati devono essere versionati.

Esempio:

Fantasy Rating: 88

Model Version:
1.4.2

Calculated At:
2026-08-24 17:30

Quando il modello cambia:

v1.4.2
   ↓
v1.5.0

i vecchi risultati non devono essere sovrascritti senza storico.

Il database deve poter conservare:

player_id
metric
value
model_version
calculated_at

Questo permette di confrontare:

Fantasy Rating v1.3
Fantasy Rating v1.4
Fantasy Rating v1.5

e capire come e perché il valore è cambiato.

---

# 29. Model Registry

Deve essere presente un registro dei modelli.

Struttura indicativa:

models

model_id
model_name
model_version
description
created_at
active
parameters

Possibili modelli:

- Player Quality Model;
- Fantasy Value Model;
- Risk Model;
- Price Model;
- Starting Probability Model;
- Expected Fantasy Points Model;
- Scarcity Model;
- Decision Model.

Ogni risultato deve essere associato alla versione del modello che lo ha prodotto.

---

# 30. Explainability Engine

Ogni decisione prodotta dal sistema deve essere spiegabile.

Non deve essere sufficiente:

BUY

Il sistema deve poter mostrare:

BUY

+18% Expected Value
+11 Replacement Advantage
+9 Set-Piece Value
+7 Starting Probability

-4 Injury Risk
-3 Price Premium

Oppure:

Perché comprarlo?

🟢 Rigorista principale
🟢 91% probabilità di titolarità
🟢 xG/90 sopra la media del ruolo
🟢 Alta produzione offensiva
🟢 Prezzo inferiore al Fair Price

Perché non comprarlo?

🔴 Prezzo in rapido aumento
🟡 Calendario difficile
🟡 Rischio rotazione

L'utente deve poter capire quali fattori hanno prodotto la raccomandazione.

---

# 31. Decision Audit

Ogni raccomandazione importante deve poter essere registrata.

Esempio:

24/08/2026

Player:
Lautaro Martinez

Decision:
BUY

Fair Price:
38

Maximum Price:
43

Fantasy Value:
88

Risk:
18

Confidence:
94%

Replacement Advantage:
+11

Scarcity:
94

Successivamente il sistema deve poter verificare cosa è realmente successo.

---

# 32. Backtesting

Il sistema deve includere un vero modulo di Backtesting.

Obiettivo:

verificare se il modello sarebbe stato efficace utilizzando solamente le informazioni disponibili nel momento in cui la previsione sarebbe stata effettuata.

Schema:

PAST DATA
    ↓
MODEL
    ↓
PREDICTION
    ↓
ACTUAL RESULT
    ↓
COMPARISON
    ↓
MODEL PERFORMANCE

Esempio:

Prediction:

Expected Goals:
0.72

Expected Fantasy Points:
7.1

Starting Probability:
91%

Dopo la partita:

Actual:

Goals:
1

Fantasy Points:
8

Started:
YES

Il sistema deve registrare la differenza tra previsione e risultato.

---

# 33. Backtesting senza Data Leakage

Il backtesting deve impedire qualsiasi forma di data leakage.

Quando viene simulata una previsione storica, il modello deve utilizzare esclusivamente informazioni che sarebbero state disponibili in quel momento.

Non deve utilizzare:

- risultati futuri;
- statistiche future;
- cambi di ruolo avvenuti successivamente;
- prezzi futuri;
- informazioni pubblicate dopo la previsione;
- dati aggiornati retroattivamente che non erano disponibili al momento della previsione.

Schema corretto:

Dati disponibili fino al 10/09
        ↓
MODEL
        ↓
PREVISIONE 11/09
        ↓
RISULTATO REALE

Mai:

Dati 2025/26 completi
        ↓
Previsione retroattiva

---

# 34. Model Performance

Il sistema deve misurare quantitativamente le performance dei propri modelli.

Per le probabilità:

- Brier Score;
- Log Loss;
- Calibration.

Per le previsioni numeriche:

- MAE;
- RMSE;
- MAPE.

Per le classificazioni:

- Precision;
- Recall;
- F1;
- Accuracy.

Per le raccomandazioni:

- ROI;
- Profitability;
- Hit Rate;
- Opportunity Cost.

Esempio:

BUY recommendations

Hit Rate:        72%
Average ROI:    +14%
Average Error:    8%

---

# 35. Calibration

Le probabilità prodotte dal sistema devono essere calibrate.

Se il modello indica:

Titolarità = 80%

su un grande numero di casi simili dovrebbe verificarsi una titolarità reale vicina all'80%.

Il sistema deve quindi monitorare:

Predicted Probability
vs
Observed Frequency

Questo deve essere applicabile a:

- probabilità di titolarità;
- probabilità di gol;
- probabilità di assist;
- probabilità clean sheet;
- probabilità di rigore;
- probabilità di bonus;
- probabilità di malus.

---

# 36. Historical Snapshot

Il sistema deve poter ricostruire lo stato del database in un determinato momento.

Esempio:

League State
24/08/2026 18:00

deve poter mostrare:

- giocatori disponibili;
- prezzi;
- rose;
- budget;
- ranking;
- Fantasy Rating;
- recommendations.

Esattamente come erano in quel momento.

Questo è fondamentale per:

- backtesting;
- audit;
- simulazioni;
- analisi storiche;
- debugging.

---

# 37. Model Comparison

Deve essere possibile confrontare due versioni del modello.

Esempio:

PLAYER

Model v1.4
Fantasy Value: 82

Model v1.5
Fantasy Value: 88

Difference:
+6

Il sistema deve poter spiegare perché il valore è cambiato.

Esempio:

Reason:

New model gives greater weight to:
+ xG/90
+ Starting Probability
+ Set Pieces
- Injury Risk

---

# 38. A/B Testing dei modelli

Quando possibile, il sistema deve poter confrontare modelli differenti.

Esempio:

MODEL A
Fantasy Rating v1.4

MODEL B
Fantasy Rating v1.5

Il sistema deve verificare quale modello produce migliori risultati reali.

L'evoluzione del modello deve quindi essere basata sui risultati misurati e non esclusivamente su valutazioni soggettive.

---

# 39. Alert System

Il sistema deve poter generare alert quando cambia significativamente una variabile.

Esempi:

🚨 TITOLARITÀ IN CALO

Player A
91% → 63%

🚨 RIGORISTA CAMBIATO

Player B
Secondo rigorista → Primo rigorista

📈 BREAKOUT SIGNAL

Player C

xG ↑
Minutes ↑
Shots ↑
Role ↑

💰 PRICE OPPORTUNITY

Player D

Fair Price: 32
Current Price: 25

⚠️ RISK ALERT

Player E

Injury Risk ↑
Starting Probability ↓

Gli alert devono essere basati sui dati e avere una propria Confidence.

---

# 40. Audit Log

Le operazioni importanti devono essere registrate.

Struttura indicativa:

timestamp
user_id
action
entity
old_value
new_value
source

Esempio:

24/08/2026 18:42

Action:
Roster Update

Player:
Lautaro Martinez

Old Status:
Available

New Status:
Owned by Team 1

Questo permette di ricostruire l'evoluzione della lega.

---

# 41. Regolamento Fantasy come configurazione

Il regolamento fantasy deve essere completamente configurabile.

Esempio:

GOAL              +3
ASSIST            +1
PENALTY_GOAL      +3
YELLOW            -0.5
RED               -1
OWN_GOAL          -2
PENALTY_MISS      -3
GOAL_CONCEDED     -1
CLEAN_SHEET       +1

Il sistema non deve avere valori fantasy hard-coded.

Il regolamento deve poter essere associato alla singola lega.

---

# 42. Fantasy Rules Engine

Il regolamento deve essere gestito da un vero Fantasy Rules Engine.

Schema:

MATCH EVENTS
      ↓
RULE ENGINE
      ↓
FANTASY EVENTS
      ↓
FANTASY SCORE

Gli eventi reali:

- Goal;
- Assist;
- Yellow Card;
- Penalty Miss;
- Clean Sheet;
- Goal Conceded;
- Red Card;
- Own Goal;
- altri eventi previsti dal regolamento;

devono essere trasformati secondo le regole specifiche della lega.

Il sistema deve poter supportare:

- leghe differenti;
- bonus personalizzati;
- malus personalizzati;
- regole speciali;
- sistemi di punteggio differenti.

---

# 43. Data Quality vs Model Confidence vs Decision Confidence

Il sistema deve distinguere chiaramente tre concetti.

DATA QUALITY

Quanto sono affidabili i dati utilizzati.

MODEL CONFIDENCE

Quanto il modello è sicuro della propria previsione.

DECISION CONFIDENCE

Quanto è forte la raccomandazione finale considerando dati, modello, mercato e situazione della rosa.

Esempio:

Data Quality:        96%
Model Confidence:    89%
Decision Confidence: 91%

Questi tre valori non devono essere considerati sinonimi.

---

# 44. Pipeline completa definitiva

L'architettura complessiva viene quindi aggiornata a:

                         DATA SOURCES
                              ↓
                         RAW DATA
                              ↓
                       NORMALIZATION
                              ↓
                       ENTITY MATCHING
                              ↓
                        DATA QUALITY
                              ↓
                         VALIDATION
                              ↓
                       CORE DATABASE
                              ↓
                 ┌────────────┴────────────┐
                 ↓                         ↓
           OBSERVED DATA             HISTORICAL DATA
                 │                         │
                 └────────────┬────────────┘
                              ↓
                       FEATURE ENGINE
                              ↓
                 ┌────────────┼────────────┐
                 ↓            ↓            ↓
             PLAYER        FANTASY        MARKET
             MODEL          MODEL         MODEL
                 │            │            │
                 └────────────┼────────────┘
                              ↓
                     PREDICTION ENGINE
                              ↓
                 ┌────────────┴────────────┐
                 ↓                         ↓
             VALUE MODEL                RISK MODEL
                 │                         │
                 └────────────┬────────────┘
                              ↓
                       DECISION ENGINE
                              ↓
                          OPTIMIZER
                              ↓
                       RECOMMENDATIONS
                              ↓
                           STREAMLIT
                              ↓
                    USER DECISION / ASTA
                              ↓
                       ACTUAL RESULTS
                              ↓
                         BACKTESTING
                              ↓
                     MODEL EVALUATION
                              ↓
                       MODEL ITERATION

---

# 45. Governance trasversale

Sopra tutta l'architettura devono essere presenti:

- MODEL VERSIONING;
- DATA LINEAGE;
- EXPLAINABILITY;
- AUDIT LOG;
- HISTORICAL SNAPSHOTS;
- MODEL REGISTRY;
- DATA QUALITY MONITORING.

Questi sistemi devono essere indipendenti dalla UI.

---

# 46. Principio definitivo del progetto

Il sistema non deve limitarsi a rispondere:

"Quanto è forte questo giocatore?"

Deve arrivare a rispondere:

"Quanto vale questo giocatore, quanto è probabile che produca valore, quanto è rischioso, quanto è sostituibile, quanto dovrei pagarlo, quanto migliora la mia rosa e qual è la decisione ottimale considerando la situazione attuale della mia lega?"

La trasformazione definitiva deve quindi essere:

DATA
 ↓
OBSERVATION
 ↓
VALIDATION
 ↓
FEATURES
 ↓
ANALYSIS
 ↓
PREDICTION
 ↓
VALUATION
 ↓
RISK
 ↓
SCARCITY
 ↓
REPLACEMENT LEVEL
 ↓
SQUAD VALUE
 ↓
OPTIMIZATION
 ↓
DECISION
 ↓
ACTUAL RESULT
 ↓
BACKTEST
 ↓
MODEL IMPROVEMENT

L'obiettivo finale è costruire un sistema misurabile, spiegabile, versionabile, verificabile e continuamente migliorabile, non una semplice raccolta di statistiche.

Il prodotto finale deve essere quindi un vero:

# FANTASY FOOTBALL INTELLIGENCE & DECISION ENGINE

capace di trasformare dati provenienti da più fonti in informazioni, previsioni, valutazioni economiche e decisioni operative specifiche per ogni giocatore, rosa e lega.

FASE 1
Database + schema

        ↓

FASE 2
Dataset iniziale + importer

        ↓

FASE 3
Normalization + Entity Matching

        ↓

FASE 4
Data Quality + Data Lineage

        ↓

FASE 5
Storico giocatori + statistiche

        ↓

FASE 6
Consensus Engine

        ↓

FASE 7
Fantasy Rating + Risk + Value

        ↓

FASE 8
Player Detail
Grafici
Radar
Heatmap
Set Pieces

        ↓

FASE 9
Leghe + Rose + Mercato

        ↓

FASE 10
Optimizer

        ↓

FASE 11
Explainability + Recommendations

        ↓

FASE 12
Backtesting + Calibration

        ↓

FASE 13
Alert + Model Registry + Audit

        ↓

FASE 14
Dashboard Streamlit definitiva

