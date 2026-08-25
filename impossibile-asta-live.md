# Impossibile — Auction Intelligence Engine in tempo reale

> Spostato da `imperfezioni.md` (ora `visione-progetto.md`) durante la
> riorganizzazione del 2026-08-25. Contenuto della visione originale
> **non realisticamente raggiungibile** con le fonti dati e l'architettura
> attuali del progetto.
>
> **Perché è impossibile (per ora):** presuppone un feed live dei rilanci e del budget degli avversari durante l'asta (Opponent Budget Modeling, Rival Threat Score, Nomination Strategy, Emotional Overbid Detection, Auction Cockpit in tempo reale). La nostra asta è in presenza/vocale: l'unico dato che abbiamo sugli avversari è quello inserito manualmente a posteriori ("Presi dagli avversari", già implementato).
>
> Resta qui come riferimento/ispirazione futura, non come roadmap attiva.

---

# AGGIORNAMENTO — AUCTION INTELLIGENCE ENGINE

L'applicazione è progettata esclusivamente per supportare il fantallenatore durante la preparazione e lo svolgimento dell'asta.

Non deve occuparsi della gestione della formazione settimanale, del matchday, del capitano o delle scelte di schieramento.

Il focus assoluto è:

PREPARAZIONE ASTA
        ↓
ANALISI MERCATO
        ↓
VALUTAZIONE GIOCATORI
        ↓
STRATEGIA
        ↓
ASTA LIVE
        ↓
AGGIORNAMENTO DINAMICO
        ↓
OTTIMIZZAZIONE ROSA

---

# 84. Auction Intelligence Engine

Deve essere presente un motore specificamente progettato per l'asta.

Per ogni giocatore deve calcolare dinamicamente:

- Consensus Price;
- Fair Price;
- Auction Value;
- Maximum Bid;
- Minimum Value;
- Expected Value;
- Risk;
- Scarcity;
- Replacement Level;
- Opportunity Cost;
- Expected Fantasy Production;
- Starting Probability;
- Bonus Potential;
- Malus Risk;
- Price Confidence;
- Decision Confidence.

Il sistema deve distinguere chiaramente:

MARKET PRICE
quanto viene effettivamente pagato;

FAIR PRICE
quanto il modello ritiene che valga;

MAXIMUM BID
quanto conviene realisticamente spendere;

AUCTION VALUE
quanto quel giocatore vale nella situazione specifica della propria asta.

---

# 85. Dynamic Maximum Bid

Il Maximum Bid non deve essere un valore fisso.

Deve cambiare in tempo reale in base a:

- budget residuo;
- giocatori ancora disponibili;
- giocatori già acquistati;
- ruoli ancora da coprire;
- scarsità;
- replacement level;
- prezzi medi dell'asta;
- prezzi già pagati;
- comportamento degli avversari;
- numero di giocatori rimasti;
- strategia della propria rosa;
- alternative disponibili.

Esempio:

Player A

Fair Price:
32

Maximum Bid iniziale:
38

Dopo alcuni acquisti:

Maximum Bid:
41

Dopo la perdita di un'alternativa:

Maximum Bid:
44

Il valore deve quindi essere contestuale.

---

# 86. Real-Time Auction State

Durante l'asta il sistema deve mantenere uno stato aggiornato della lega.

Deve conoscere:

TU
↓
Budget
Rosa
Ruoli mancanti

AVVERSARI
↓
Budget
Rosa
Ruoli mancanti

MERCATO
↓
Disponibili
Acquistati
Non ancora chiamati

Il sistema deve aggiornare automaticamente questi dati dopo ogni acquisto.

---

# 87. Auction Pressure

Il sistema deve calcolare la pressione competitiva dell'asta.

Esempio:

PLAYER A

Tu:
3 giocatori necessari in attacco

Avversario 1:
2 attaccanti necessari

Avversario 2:
1 attaccante necessario

Avversario 3:
4 attaccanti necessari

Auction Pressure:
HIGH

Questo permette di prevedere quando un giocatore rischia di essere pagato sopra il Fair Price.

---

# 88. Price Inflation / Deflation

Il sistema deve monitorare l'inflazione dell'asta.

Esempio:

Fair Price medio:
30

Prezzo medio effettivo:
35

Inflation:
+16.7%

Oppure:

Fair Price medio:
30

Prezzo medio effettivo:
25

Deflation:
-16.7%

Il modello deve adattare progressivamente le proprie valutazioni.

---

# 89. Live Market Value

Il valore di un giocatore deve poter cambiare durante l'asta.

Esempio:

Prima dell'asta:

Player A
Fair Price:
30

Dopo 50 giocatori acquistati:

Fair Price:
34

Dopo la scomparsa di tre alternative:

Fair Price:
38

Questo perché il valore di un giocatore dipende anche dalla scarsità residua.

---

# 90. Auction Timing

Il sistema deve stimare il momento migliore per acquistare un determinato giocatore.

Deve considerare:

- numero di giocatori rimasti;
- budget medio degli avversari;
- ruoli già coperti;
- alternative disponibili;
- inflazione;
- fase dell'asta;
- probabilità che il giocatore venga richiamato;
- rischio di rimanere senza alternative.

Output:

BUY NOW

WAIT

PASS

SAVE BUDGET

---

# 91. Auction Strategy

Il sistema deve poter suggerire una strategia generale.

Esempio:

STRATEGIA ATTUALE

🟢 Hai vantaggio economico
🟡 Attacco ancora scoperto
🔴 Pochi attaccanti top rimasti

Strategia consigliata:

Conservare 25% del budget
fino ai prossimi 3 attaccanti.

---

# 92. Nomination Strategy

Se il formato dell'asta permette di scegliere il giocatore da chiamare, il sistema deve suggerire anche le nomination.

Esempio:

CALL PLAYER A

Motivo:

- non è un tuo target;
- può consumare il budget degli avversari;
- crea pressione;
- riduce il budget disponibile dei competitor.

Oppure:

DO NOT CALL PLAYER B

Motivo:

- è un tuo target;
- rischi di aumentarne il prezzo;
- è meglio aspettare una fase più favorevole.

---

# 93. Opponent Budget Modeling

Il budget degli avversari deve essere analizzato dinamicamente.

Per ogni avversario:

Budget:
142

Spesa residua stimata:
118

Giocatori mancanti:
7

Attaccanti mancanti:
2

Massimo teorico per un attaccante:
61

Massimo realistico:
48

Il sistema deve quindi stimare quanto ogni avversario può realisticamente spendere.

---

# 94. Rival Threat Score

Ogni avversario deve avere un Threat Score.

Esempio:

TEAM A
Threat Score:
91/100

TEAM B
Threat Score:
74/100

TEAM C
Threat Score:
42/100

Il punteggio deve considerare:

- budget;
- giocatori posseduti;
- ruoli mancanti;
- forza della rosa;
- necessità;
- strategia osservata;
- capacità di competere per determinati giocatori.

---

# 95. Player Competition Score

Per ogni giocatore deve essere stimata la probabilità che venga conteso.

Esempio:

Player A

Competition Score:
87/100

Motivi:

- 4 avversari hanno bisogno del ruolo;
- 2 hanno budget elevato;
- poche alternative rimaste;
- giocatore molto desiderato.

Questo deve contribuire alla stima del prezzo finale.

---

# 96. Expected Auction Price

Oltre al Fair Price deve essere stimato:

Expected Auction Price.

Esempio:

Fair Price:
32

Expected Auction Price:
37

Maximum Bid:
40

Interpretazione:

Il giocatore probabilmente verrà pagato 37.

Fino a 40 è ancora conveniente.

Oltre 40 il rapporto rischio/rendimento peggiora.

---

# 97. Auction Price Distribution

Quando i dati sono sufficienti, il sistema deve produrre una distribuzione dei prezzi.

Esempio:

Expected Price:
37

Range:
32–43

P25:
34

Median:
37

P75:
40

P90:
43

Questo permette di capire il rischio di sovrapprezzo.

---

# 98. Stop-Loss

Durante l'asta deve essere possibile impostare un limite massimo.

Esempio:

Player A

Fair Price:
32

Maximum Bid:
39

STOP:
40

Quando il prezzo raggiunge 40:

🔴 STOP

Il sistema deve impedire che l'utente superi il limite per effetto dell'emotività.

---

# 99. Emotional Overbid Detection

Il sistema deve poter identificare situazioni in cui il prezzo sta diventando irrazionale.

Esempio:

Fair Price:
30

Current Bid:
43

Expected Auction Price:
34

Overbid:
+43%

Alert:

🔴 OVERBID

Il giocatore sta costando significativamente più del valore stimato.

---

# 100. Portfolio Construction

L'optimizer deve ragionare sulla rosa come un portafoglio.

Non deve scegliere semplicemente i migliori giocatori.

Deve massimizzare:

TOTAL SQUAD VALUE

considerando:

- budget;
- rischio;
- upside;
- stabilità;
- scarsità;
- replacement level;
- correlazione tra giocatori;
- alternative;
- ruoli;
- strategia.

---

# 101. Portfolio Risk

La rosa deve avere un Risk Score.

Esempio:

Squad Risk:
32/100

Componenti:

Injury Risk:
12

Rotation Risk:
8

Starting Risk:
5

Discipline Risk:
4

Price Risk:
3

Il sistema deve identificare anche la concentrazione del rischio.

Esempio:

🔴 46% del valore della rosa dipende da soli 2 giocatori.

---

# 102. Portfolio Diversification

Quando possibile, il sistema deve evitare una rosa eccessivamente dipendente da un singolo profilo.

Deve analizzare:

- concentrazione di budget;
- concentrazione di squadra;
- concentrazione di ruolo;
- dipendenza da rigoristi;
- dipendenza da pochi giocatori;
- rischio complessivo.

Questo non significa evitare automaticamente giocatori della stessa squadra.

La correlazione deve essere valutata in base alla strategia.

---

# 103. Auction Cockpit

Durante l'asta deve esistere una modalità completamente diversa dalla dashboard normale.

La UI deve essere progettata come un cockpit.

Esempio:

text
┌──────────────────────────────────────────────┐
│ BUDGET: 147          GIOCATORI: 17/25       │
├──────────────────────────────────────────────┤
│                                              │
│ PLAYER CURRENTLY AUCTIONED                   │
│                                              │
│ LAUTARO MARTINEZ                             │
│                                              │
│ Fair Price       38                          │
│ Expected Price   41                          │
│ Maximum Bid      44                          │
│ Current Bid      39                          │
│                                              │
│ 🟢 BUY                                       │
│                                              │
├──────────────────────────────────────────────┤
│ ALTERNATIVE                                  │
│ Player B       31                            │
│ Player C       28                            │
│ Player D       24                            │
├──────────────────────────────────────────────┤
│ AVVERSARI                                    │
│ Team A Budget: 132                           │
│ Team B Budget: 104                           │
│ Team C Budget: 88                            │
└──────────────────────────────────────────────┘

La modalità asta deve privilegiare:

velocità;
leggibilità;
decisione immediata;
informazioni essenziali;
aggiornamento real-time.

Non deve diventare una pagina piena di grafici inutili.

---

# 104. Auction Decision Output

Il risultato principale del sistema durante l'asta deve essere estremamente semplice:

🟢 COMPRA

🟡 VALUTA

🔴 LASCIA

e, quando necessario:

🔥 AGGRESSIVO

💰 RISPARMIA

⏳ ASPETTA

🚨 OVERBID

Il sistema deve comunque permettere di aprire il dettaglio e vedere il ragionamento completo.
---

# 105. Principio definitivo dell'app

L'app deve essere esclusivamente un:

FANTASY FOOTBALL AUCTION INTELLIGENCE ENGINE

Il suo obiettivo non è dirti semplicemente quali sono i giocatori migliori.

Deve dirti:

"QUANTO VALE QUESTO GIOCATORE PER LA TUA ASTA, QUANTO PUOI PAGARLO, QUANTO PROBABILMENTE VERRÀ PAGATO, QUALI ALTERNATIVE HAI, CHI PUÒ FARE CONCORRENZA, QUANTO È SCARSO IL RUOLO E COME CAMBIA LA TUA STRATEGIA SE LO COMPRI O LO PERDI."

La pipeline definitiva diventa quindi:

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
HISTORICAL DATABASE
↓
PLAYER MODEL
↓
FANTASY MODEL
↓
MARKET MODEL
↓
RISK MODEL
↓
CONSENSUS ENGINE
↓
FAIR VALUE
↓
REPLACEMENT LEVEL
↓
SCARCITY
↓
AUCTION PRICE MODEL
↓
OPPONENT MODEL
↓
PORTFOLIO MODEL
↓
AUCTION OPTIMIZER
↓
LIVE AUCTION
↓
DYNAMIC RECALCULATION
↓
DECISION

Il sistema deve essere costruito per massimizzare il valore della rosa ottenuta con il budget disponibile, non per massimizzare il numero di giocatori "forti".

La metrica finale non è quindi:

"quanto è forte il giocatore?"

ma:

"quanto valore aggiunge questo acquisto alla mia rosa rispetto a tutte le alternative disponibili in questo preciso momento dell'asta?"

