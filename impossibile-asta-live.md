# Impossibile (residuo) — Auction Intelligence Engine in tempo reale

> Spostato da `imperfezioni.md` (ora `visione-progetto.md`) durante la
> riorganizzazione del 2026-08-25.
>
> **Aggiornamento 2026-08-26:** la maggior parte di questa visione (sezioni
> 84-85, 88-91, 93-99, 103-104) si è rivelata raggiungibile senza un feed
> live — vedi `visione-progetto.md` §"Auction Intelligence Engine
> (implementato)" per il motore reale (`ranking/auction_intelligence.py`,
> collegato alla scheda giocatore). Restano qui, davvero non raggiungibili
> con l'architettura attuale (asta vocale/in presenza, nessun feed esterno):
>
> - **Nomination Strategy (92)** e **Auction Pressure per-nomina (87)**: richiedono di sapere in tempo reale *quale giocatore sta per essere chiamato* e la reazione istantanea degli avversari — nessuna fonte dati ce lo dà;
> - **Real-Time Auction State (86)** nella sua forma "aggiornamento automatico dopo ogni acquisto senza intervento": oggi richiede che l'utente registri manualmente ogni "preso dagli avversari", non è automatico;
> - **Portfolio Construction/Risk/Diversification (100-102)**: ottimizzazione di portafoglio con correlazione tra giocatori — feature a sé, non ancora iniziata;
> - **Auction Cockpit come pagina/modalità separata (103)**: implementato come sezione nella scheda giocatore esistente, non come vista full-screen dedicata.
>
> Restano qui come riferimento/ispirazione futura, non come roadmap attiva.

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

> Parzialmente implementato: tutto questo stato è calcolabile e mostrato
> (budget/rosa/ruoli mancanti miei e degli avversari, disponibili) — ma solo
> dopo che l'utente registra manualmente ogni acquisto ("Presi dagli
> avversari"). Non c'è un aggiornamento "automatico" nel senso di un feed
> esterno: l'unico input è quello inserito a mano.

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

> La versione aggregata (quanti avversari mancano di quel ruolo, in totale)
> è implementata dentro l'Opponent Budget Model. La versione "per nomina in
> tempo reale" (chi sta rilanciando adesso su questo specifico giocatore)
> resta impossibile senza un feed live.

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

> 100-102 restano un blocco a sé (ottimizzazione di portafoglio con
> correlazione tra giocatori, non solo per singolo slot) — non ancora
> iniziato, non impossibile in senso stretto ma sostanzialmente più grande
> di quanto fatto finora per l'Auction Intelligence Engine.

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
