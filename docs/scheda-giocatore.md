# Scheda Giocatore — Specifiche tecniche e UI

## 1. Obiettivo

Implementare nel progetto una **scheda giocatore completa per il Fantacalcio**, ispirata per quantità e profondità dei dati alle schede presenti su Fantanalisi, ma con:

* grafica proprietaria;
* componenti UI coerenti con il resto dell'applicazione;
* struttura moderna e responsive;
* dati normalizzati e utilizzabili anche dal motore di analisi;
* nessuna copia del layout, CSS o identità visiva di Fantanalisi.

La scheda deve diventare il punto centrale per analizzare un singolo giocatore prima e durante l'asta.

L'obiettivo non è semplicemente mostrare statistiche, ma permettere all'utente di capire:

1. quanto è forte il giocatore;
2. quanto dovrebbe essere pagato;
3. quanto viene realmente pagato;
4. quanto è affidabile;
5. quanto gioca;
6. quanti bonus può produrre;
7. quali sono i suoi rischi;
8. come si colloca rispetto agli altri giocatori dello stesso ruolo.

---

# 2. URL e identificazione

Ogni giocatore deve avere un identificativo univoco.

Formato indicativo:

```text
/giocatori/{id}-{slug}
```

Esempio:

```text
/giocatori/1-martinez-l
```

Il sistema non deve dipendere dallo slug per identificare il giocatore.

Il campo principale deve essere:

```text
player_id
```

Lo slug deve essere utilizzato solamente per la URL.

---

# 3. Struttura generale della pagina

La pagina deve essere organizzata in sezioni/card.

Struttura consigliata:

```text
┌─────────────────────────────────────────────────────┐
│                 PLAYER HEADER                       │
│                                                     │
│  FOTO   L. Martinez                                 │
│         Inter                                       │
│         ATTACCANTE                                  │
│                                                     │
│         Tier 1        FVM 237       Max 261         │
└─────────────────────────────────────────────────────┘

┌─────────────────────┐ ┌─────────────────────────────┐
│ VALORE FANTACALCIO  │ │ ASTA                        │
│                     │ │                             │
│ FVM                 │ │ Prezzo mediano              │
│ Max Bid             │ │ Prezzo tipico               │
│ Ranking             │ │ P75                         │
└─────────────────────┘ └─────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ PERFORMANCE                                         │
│                                                     │
│ FM   MV   Gol   Assist   Presenze   Bonus           │
└─────────────────────────────────────────────────────┘

┌─────────────────────┐ ┌─────────────────────────────┐
│ TITOLARITÀ          │ │ RISCHIO                     │
│                     │ │                             │
│ Starter probability │ │ Infortuni                   │
│ Presenze attese     │ │ Rotazioni                   │
│ Coppe               │ │ Squalifiche                 │
└─────────────────────┘ └─────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ STORICO                                             │
│                                                     │
│ 2018/19 ─────────────────────────────── 2025/26     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ UNDERSTAT / ADVANCED DATA                           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ CALENDARIO                                          │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ANALISI AUTOMATICA                                  │
│                                                     │
│ Punti forti                                         │
│ Punti deboli                                        │
│ Perché comprarlo                                    │
│ Quando evitarlo                                     │
└─────────────────────────────────────────────────────┘
```

---

# 4. Header giocatore

L'header deve essere immediatamente leggibile.

### Dati

* foto giocatore;
* nome;
* cognome;
* nome abbreviato;
* squadra;
* ruolo;
* ruolo Fantacalcio;
* numero maglia;
* piede;
* età;
* altezza;
* eventuale status.

Esempio:

```text
Lautaro Martínez
Inter
ATTACCANTE

21 anni
Argentino
Destro
```

---

# 5. Valore Fantacalcio

Questa è una delle sezioni più importanti.

Visualizzare:

* FVM / prezzo equo;
* Max Bid;
* quotazione;
* ranking assoluto;
* ranking ruolo;
* tier;
* fascia di valore;
* differenza rispetto alla quotazione;
* differenza rispetto al prezzo d'asta;
* valore percentuale.

Esempio:

```text
FVM             237
MAX BID         261
QUOTAZIONE      32

RANKING         #3
RANKING RUOLO   #2
TIER            1
```

---

# 6. Sistema di valutazione

Il sistema deve distinguere chiaramente:

### FVM

Valore teorico del giocatore.

### Max Bid

Prezzo massimo consigliato.

### Prezzo di mercato

Prezzo realmente osservato nelle aste.

### Quotazione

Valore ufficiale/listone.

Questi valori non devono essere confusi.

Visualizzare anche:

```text
Prezzo asta mediano
Prezzo asta tipico
25° percentile
75° percentile
Minimo
Massimo
Numero aste
```

---

# 7. Dati delle aste

Raccogliere, quando disponibili:

* prezzo minimo;
* prezzo massimo;
* prezzo medio;
* mediana;
* moda/prezzo tipico;
* P25;
* P50;
* P75;
* numero di aste;
* numero di acquisti;
* andamento temporale;
* distribuzione dei prezzi.

La UI dovrebbe permettere di visualizzare una distribuzione:

```text
Prezzo

        █
        █ █
      █ █ █
    █ █ █ █ █
  █ █ █ █ █ █ █
────────────────────
  100 150 200 250 300
```

Il dato più importante deve essere la **mediana**, non la media.

---

# 8. Performance

Visualizzare almeno:

* presenze;
* presenze da titolare;
* minuti;
* media voto;
* fantamedia;
* gol;
* assist;
* rigori segnati;
* rigori sbagliati;
* ammonizioni;
* espulsioni;
* autogol;
* bonus;
* malus.

Separare chiaramente:

```text
Media voto
Fantamedia
```

Non considerarli equivalenti.

---

# 9. Statistiche avanzate

Quando disponibili, raccogliere:

* xG;
* xA;
* xG/90;
* xA/90;
* tiri;
* tiri/90;
* tiri in porta;
* occasioni create;
* passaggi chiave;
* tocchi in area;
* big chances;
* conversion rate;
* gol attesi;
* assist attesi;
* xGChain;
* xGBuildup.

Le statistiche avanzate devono essere mostrate separatamente dalle statistiche Fantacalcio.

---

# 10. Titolarità

Creare un indice di titolarità.

Dati:

* probabilità di titolarità;
* presenze attese;
* minuti attesi;
* presenze da titolare;
* sostituzioni;
* rotazioni;
* concorrenza nel ruolo;
* gerarchia della squadra;
* impatto delle coppe.

Esempio UI:

```text
TITOLARITÀ

██████████████████░░  88%

Presenze attese       31
Titolare atteso       Sì
Rischio rotazione     Basso
```

---

# 11. Bonus potential

Creare un'area dedicata al potenziale bonus.

Indicatori:

* probabilità gol;
* probabilità assist;
* gol attesi;
* assist attesi;
* rigori;
* punizioni;
* corner;
* coinvolgimento offensivo.

Per gli attaccanti:

```text
Gol attesi
Assist attesi
Tiri
Tiri/90
Tocchi area
Rigori
```

Per centrocampisti:

```text
Gol
Assist
xG
xA
Calci piazzati
Corner
Rigori
```

Per difensori:

```text
Gol
Assist
Cross
Calci piazzati
Bonus difensivi
```

---

# 12. Ruolo tattico

Non limitarsi al ruolo Fantacalcio.

Distinguere:

```text
Ruolo Fantacalcio:
C

Ruolo tattico:
Esterno offensivo

Posizione:
Ala destra

Funzione:
Creatore
```

Per i difensori distinguere soprattutto:

* centrale;
* terzino;
* quinto;
* braccetto.

Questo è fondamentale per il calcolo del valore Fantacalcio.

Un quinto di centrocampo deve essere valutato diversamente da un difensore centrale.

---

# 13. Profilo offensivo

Calcolare un indice offensivo.

Esempio:

```text
OFFENSIVITÀ

████████████████░░░░  82/100
```

Componenti:

* xG;
* xA;
* tiri;
* tocchi in area;
* gol;
* assist;
* rigori;
* posizione media;
* ruolo tattico.

---

# 14. Profilo difensivo

Per difensori e centrocampisti:

* contrasti;
* intercetti;
* duelli;
* recuperi;
* blocchi;
* palloni recuperati;
* falli;
* ammonizioni.

Il profilo difensivo non deve però pesare automaticamente quanto quello offensivo nel ranking Fantacalcio.

---

# 15. Affidabilità

Creare un indice di affidabilità.

Componenti:

* continuità delle prestazioni;
* continuità di presenze;
* infortuni;
* rotazioni;
* rendimento;
* volatilità della fantamedia;
* dipendenza dai bonus.

Esempio:

```text
AFFIDABILITÀ

█████████████████░░░  85/100
```

---

# 16. Volatilità

Misurare quanto il rendimento varia da partita a partita.

Visualizzare:

```text
Fantamedia
8.5 ┤       ●
8.0 ┤   ●       ●
7.5 ┤ ●   ● ●
7.0 ┤       ●
6.5 ┤ ●
    └────────────────
```

Indicatori:

* deviazione standard;
* media;
* mediana;
* percentuale di giornate sopra 8;
* percentuale sotto 6;
* percentuale con bonus;
* percentuale con malus.

---

# 17. Storico

Mostrare lo storico stagione per stagione.

Colonne:

```text
Stagione
Squadra
Presenze
Titolare
MV
FM
Gol
Assist
Amm.
Esp.
```

Possibilità di visualizzare grafici temporali.

---

# 18. Calendario

Mostrare il calendario futuro della squadra.

Per ogni giornata:

```text
Giornata
Avversario
Casa/Trasferta
Difficoltà
```

Calcolare un indice di calendario.

Esempio:

```text
CALENDARIO PROSSIME 8

G1  ████░  Facile
G2  ██░░░  Difficile
G3  █████  Molto facile
...
```

Il calendario deve contribuire al valore previsto del giocatore.

---

# 19. Infortuni

Quando disponibili:

* stato attuale;
* tipo di infortunio;
* data;
* rientro previsto;
* partite saltate;
* storico infortuni.

Non mostrare informazioni non confermate come certe.

Distinguere:

```text
Disponibile
In dubbio
Infortunato
Squalificato
```

---

# 20. Squalifiche

Visualizzare:

* stato disciplinare;
* giornate di squalifica;
* cartellini;
* storico squalifiche.

---

# 21. Squadra

Analizzare il contesto della squadra:

* allenatore;
* modulo;
* forza offensiva;
* forza difensiva;
* gol segnati;
* gol subiti;
* possesso;
* produzione offensiva;
* rigori conquistati;
* piazzati.

Il rendimento del giocatore deve essere contestualizzato alla squadra.

---

# 22. Allenatore

Quando disponibile:

* allenatore attuale;
* modulo preferito;
* moduli utilizzati;
* frequenza utilizzo giocatore;
* storico con allenatore;
* compatibilità tattica.

---

# 23. Analisi automatica

La pagina deve produrre un'analisi sintetica.

Esempio:

```text
VERDETTO

★★★★★

Top player offensivo.

PUNTI FORTI
+ Grande potenziale gol
+ Titolare quasi certo
+ Rigorista
+ Alta continuità

RISCHI
- Prezzo d'asta elevato
- Possibile turnover in coppa

ASTA

Prezzo ideale: 220-240
Prezzo massimo: 261
Oltre 270 → sconsigliato
```

Questa sezione deve essere generata dai dati, non scritta manualmente per ogni giocatore.

---

# 24. Confronto con il ruolo

Permettere di confrontare il giocatore con la media del ruolo.

Esempio:

```text
                 Giocatore    Media ruolo

Fantamedia          8.1          7.0
Gol                 18            9
Assist               7            4
Presenze             32           27
xG                  16.2         9.1
xA                   5.8         4.2
```

Aggiungere percentile:

```text
Gol             ██████████████████  94°
Assist          ███████████████     82°
Presenze        █████████████████   91°
```

---

# 25. Ranking

Mostrare:

* ranking generale;
* ranking per ruolo;
* ranking per bonus;
* ranking per fantamedia;
* ranking per rapporto qualità/prezzo;
* ranking per affidabilità;
* ranking per potenziale.

---

# 26. Value for Money

Creare un indice:

```text
VALUE FOR MONEY

████████████████░░░░  81/100
```

Basato su:

```text
Valore previsto
/
Prezzo d'asta previsto
```

Il sistema deve evidenziare:

```text
🟢 Sottovalutato
🟡 Prezzo corretto
🔴 Sopravvalutato
```

---

# 27. Analisi asta

La scheda deve fornire un intervallo operativo:

```text
PREZZO IDEALE
220-240

PREZZO BUONO
240-255

PREZZO MASSIMO
261

SOPRA 261
❌ Non conveniente
```

Questi valori devono essere calcolati dal motore, non hardcoded.

---

# 28. Scoring

Creare uno score complessivo.

Esempio:

```text
SCORE FANTACALCIO

91/100
```

Sottoscore:

```text
Bonus          94
Titolarità     91
Rendimento     89
Affidabilità   85
Calendario     78
Prezzo         82
Rischio        76
```

I pesi devono poter essere modificati dal motore di analisi.

---

# 29. Design system

IMPORTANTE:

La UI deve essere **proprietaria**.

Non copiare:

* CSS;
* colori;
* layout;
* card;
* tipografia;
* componenti;
* icone;
* struttura visuale;
* naming delle sezioni

di Fantanalisi.

Fantanalisi deve essere utilizzato esclusivamente come riferimento per la **quantità e tipologia dei dati**.

La nostra applicazione deve mantenere il proprio design system.

---

# 30. Principi grafici

La pagina deve essere:

* moderna;
* pulita;
* leggibile;
* densa di informazioni ma non caotica;
* responsive;
* desktop-first per la dashboard;
* mobile-friendly;
* coerente con il resto dell'app.

Usare:

* card;
* badge;
* progress bar;
* grafici;
* tabelle;
* tooltip;
* indicatori di stato;
* percentile;
* ranking.

Evitare:

* muri di testo;
* tabelle enormi senza gerarchia;
* colori eccessivi;
* grafici decorativi senza valore informativo.

---

# 31. Colori semantici

I colori devono avere significato.

```text
VERDE
positivo / conveniente / titolare

GIALLO
attenzione / rischio medio

ROSSO
rischio / prezzo eccessivo / indisponibile

BLU
informazioni / statistiche

GRIGIO
informazioni secondarie
```

Non utilizzare il colore come unico metodo per comunicare un'informazione.

---

# 32. Responsive

Desktop:

```text
Header
2-4 colonne di KPI
griglia statistiche
grafici
tabelle
```

Tablet:

```text
2 colonne
```

Mobile:

```text
1 colonna
```

L'ordine delle sezioni deve mantenere priorità:

1. giocatore;
2. valore;
3. asta;
4. rendimento;
5. titolarità;
6. rischi;
7. statistiche;
8. storico;
9. calendario;
10. dati avanzati.

---

# 33. Raccolta dati

Il sistema di scraping deve essere separato dalla UI.

Architettura:

```text
SCRAPER
   ↓
RAW DATA
   ↓
NORMALIZER
   ↓
DATABASE
   ↓
ANALYSIS ENGINE
   ↓
API
   ↓
PLAYER PAGE
```

Non fare scraping direttamente dal frontend.

---

# 34. Dati raw

Conservare sempre i dati originali quando possibile.

Struttura indicativa:

```text
player_raw_data
```

con:

```text
source
source_url
scraped_at
raw_payload
```

Questo permette di effettuare nuovamente il parsing senza dover riscrapare il sito.

---

# 35. Normalizzazione

Creare un modello interno indipendente dalla fonte.

Esempio:

```json
{
  "player_id": 1,
  "name": "Lautaro Martinez",
  "team": "Inter",
  "role": "A",
  "fair_value": 237,
  "max_bid": 261,
  "auction_median": 336,
  "expected_appearances": 32,
  "expected_fantamedia": 7.75
}
```

La UI deve utilizzare esclusivamente il modello interno.

---

# 36. Multi-source

Il sistema deve essere progettato per poter aggiungere successivamente altre fonti.

Esempio:

```text
Fantanalisi
     │
Fantacalcio.it
     │
Fantacalcio Online
     │
Fantapazz
     │
altre fonti
     │
     ▼
SOURCE NORMALIZER
     │
     ▼
UNIFIED PLAYER DATA
```

Non creare codice fortemente dipendente da Fantanalisi.

---

# 37. Aggiornamento dati

Salvare sempre:

```text
scraped_at
updated_at
source
```

I dati dinamici devono poter essere aggiornati senza modificare la struttura della pagina.

---

# 38. Caching

Non effettuare richieste ripetute inutilmente.

Utilizzare:

```text
cache
rate limiting
retry
timeout
logging
```

Rispettare sempre robots.txt, termini d'uso e eventuali limitazioni della fonte.

Non bypassare:

* CAPTCHA;
* login;
* paywall;
* sistemi anti-bot;
* controlli di accesso.

---

# 39. Logging scraper

Ogni scraping deve registrare:

```text
URL
timestamp
status code
tempo risposta
success/failure
errore
numero dati estratti
```

Esempio:

```text
[OK] 1-martinez-l
[OK] 2-...
[ERROR] 3-...
```

---

# 40. Gestione errori

Se una fonte cambia struttura HTML:

```text
SCRAPER ERROR
     ↓
LOG
     ↓
DATA NON AGGIORNATA
     ↓
UI MOSTRA ULTIMO DATO VALIDO
```

Non sostituire automaticamente dati validi con `null`.

---

# 41. Priorità implementazione

## Fase 1 — MVP

Implementare:

* player header;
* squadra;
* ruolo;
* FVM;
* Max Bid;
* ranking;
* tier;
* prezzo asta;
* presenze;
* MV;
* FM;
* gol;
* assist;
* titolarità;
* storico;
* calendario.

## Fase 2

Aggiungere:

* advanced stats;
* xG;
* xA;
* volatilità;
* affidabilità;
* bonus potential;
* value for money;
* confronto ruolo.

## Fase 3

Aggiungere:

* analisi automatica;
* distribuzione aste;
* scoring avanzato;
* contesto tattico;
* analisi allenatore;
* infortuni;
* squalifiche.

## Fase 4

Aggiungere:

* multi-source;
* confronto giocatori;
* simulazione prezzo;
* suggerimento automatico di acquisto;
* integrazione con la rosa dell'utente.

---

# 42. Regola fondamentale

Non costruire una semplice "copia di Fantanalisi".

Costruire una **scheda giocatore proprietaria**, utilizzando Fantanalisi come una delle fonti di dati e come riferimento per capire quali informazioni sono utili.

Il valore del progetto deve essere nel:

```text
DATI
+
NORMALIZZAZIONE
+
ANALISI
+
SCORING
+
ASTA
+
UX
```

e non semplicemente nello scraping.

---

# 43. Risultato finale

L'utente deve poter aprire un giocatore e capire in meno di 30 secondi:

```text
CHI È?
        ↓
QUANTO È FORTE?
        ↓
QUANTO GIOCA?
        ↓
QUANTI BONUS PORTA?
        ↓
QUAL È IL SUO RISCHIO?
        ↓
QUANTO VALE?
        ↓
QUANTO LO PAGHERANNO?
        ↓
FINO A QUANTO DEVO SPENDERCI?
```

La scheda deve quindi funzionare contemporaneamente come:

* pagina statistica;
* scouting report;
* valutazione economica;
* analisi asta;
* confronto ruolo;
* strumento decisionale.

FONTE SCRAPING
→ https://www.fantanalisi.it/giocatori/1-martinez-l

OBIETTIVO
→ estrarre TUTTI i dati pubblicamente disponibili nella pagina

REGOLE
→ non replicare UI Fantanalisi
→ non replicare CSS
→ non replicare layout
→ non limitarsi ai dati elencati manualmente
→ se esistono altri dati nell'HTML/API pubblica, recuperarli
→ normalizzare tutto nel nostro modello
→ presentare tutto con il design system del progetto