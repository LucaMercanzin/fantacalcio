# Specifiche scraping — Portieri Fantacalcio

## 1. Obiettivo

Lo scraping dei portieri deve produrre **esattamente 20 giocatori**, prendendo per ciascuna delle 20 squadre di Serie A:

1. il portiere titolare / prima scelta;
2. il portiere di riserva / seconda scelta.

Totale:

**20 squadre × 2 portieri = 40 giocatori**

> **Nota:** se l'obiettivo reale è avere 20 giocatori totali, allora bisogna prendere **un solo portiere per squadra**. Se invece si vuole "primo + sostituto per ogni squadra", il risultato matematico è 40. La specifica deve quindi usare come parametro `2 portieri per squadra` oppure `1 portiere per squadra` per evitare ambiguità.

Per il comportamento richiesto in questa fase, assumere:

**1° + 2° portiere per ciascuna squadra = 40 giocatori.**

---

# 2. Data di esecuzione

Lo scraping definitivo deve essere eseguito:

**1 settembre 2026, a mercato chiuso.**

Lo scraping deve quindi rappresentare la rosa delle squadre **successiva alla chiusura del calciomercato**, non la situazione precedente.

Non utilizzare una lista statica preparata settimane prima.

---

# 3. Regola fondamentale: rosa reale alla data dello scraping

La lista dei portieri deve essere costruita dinamicamente in base alla rosa aggiornata.

Lo scraper deve:

* aggiungere i giocatori acquistati;
* rimuovere i giocatori ceduti;
* aggiornare la squadra del giocatore;
* aggiornare il ruolo;
* aggiornare l'ordine gerarchico dei portieri;
* eliminare giocatori che non appartengono più alla Serie A;
* evitare duplicati.

Esempio concettuale:

```text
PRIMA DEL MERCATO

Napoli
1. Portiere A
2. Portiere B


DOPO IL MERCATO

Napoli
1. Meret
2. Portiere C
```

Il risultato finale deve contenere:

```text
Meret → Napoli → 1° portiere
Portiere C → Napoli → 2° portiere
```

e **non** il vecchio portiere ceduto.

---

# 4. Nessuna lista hardcoded dei giocatori

Non creare una struttura del tipo:

```php
$portieri = [
    'Meret',
    'Di Gregorio',
    ...
];
```

perché diventerebbe immediatamente obsoleta.

La lista deve essere il risultato dello scraping.

È invece consentito mantenere una configurazione delle **20 squadre partecipanti alla Serie A**, purché anche questa venga verificata/aggiornata per la stagione corrente.

---

# 5. Individuazione delle 20 squadre

Lo scraper deve prima determinare le 20 squadre di Serie A della stagione.

Ordine richiesto:

1. squadre già presenti in Serie A;
2. squadre neopromosse;
3. le neopromosse devono essere collocate **in fondo all'ordinamento**.

Esempio concettuale:

```text
1. Squadra A
2. Squadra B
3. Squadra C
...
17. Squadra Q
18. Neopromossa 1
19. Neopromossa 2
20. Neopromossa 3
```

L'ordinamento delle squadre non deve influenzare la scelta del titolare e della riserva.

---

# 6. Identificazione dei portieri

Per ogni squadra devono essere individuati i portieri appartenenti alla rosa aggiornata.

Lo scraper deve cercare tutti i giocatori con ruolo:

```text
POR / GK / Goalkeeper / Portiere
```

a seconda del formato utilizzato dalla fonte.

Successivamente deve stabilire:

```text
1° → prima scelta
2° → seconda scelta
```

---

# 7. Determinazione del titolare

Non utilizzare semplicemente il primo portiere trovato dalla pagina.

La priorità per determinare il titolare deve essere:

### Priorità 1 — gerarchia esplicita della fonte

Se la fonte indica:

```text
Portieri
1. Meret
2. Milinkovic-Savic
3. ...
```

utilizzare quell'ordine.

### Priorità 2 — informazioni sulla formazione

Se disponibile:

* formazione probabile;
* undici titolare;
* depth chart;
* numero di presenze;
* indicazione "starter".

### Priorità 3 — informazioni più recenti

In caso di parità, privilegiare l'informazione più recente.

---

# 8. Determinazione della riserva

Il secondo giocatore nella gerarchia dei portieri deve essere considerato:

```text
2° portiere / backup
```

Non deve essere scelto semplicemente in base al rating fantacalcio.

La gerarchia della squadra viene prima del rating.

Esempio:

```text
NAPOLI

1. Meret       → TITOLARE
2. Portiere B  → RISERVA
3. Portiere C  → TERZO
```

Output:

```text
Meret
Portiere B
```

Il terzo portiere viene escluso dalla lista principale.

---

# 9. Caso di trasferimento durante il mercato

Questo è un punto fondamentale.

Se un portiere presente nella vecchia lista viene ceduto:

```text
Napoli
Meret
Portiere B
```

e il mercato produce:

```text
Meret
Portiere C
```

la nuova lista deve diventare:

```text
Meret
Portiere C
```

Il vecchio:

```text
Portiere B
```

deve essere rimosso se non appartiene più alla rosa.

---

# 10. Caso di acquisto

Se una squadra acquista un nuovo portiere:

```text
Juventus

Di Gregorio
Portiere B
```

e durante il mercato arriva:

```text
Portiere C
```

lo scraper deve rivalutare la gerarchia:

```text
1. Di Gregorio
2. Portiere C
3. Portiere B
```

e mantenere:

```text
Di Gregorio
Portiere C
```

se questa è la gerarchia risultante dalle fonti.

Non basta quindi:

```text
aggiungi Portiere C
```

ma bisogna **ricalcolare l'ordine dei portieri della squadra**.

---

# 11. Giocatore venduto

Ogni giocatore deve essere associato alla squadra corrente.

Se lo scraper trova:

```text
Giocatore X
vecchia squadra = Napoli
nuova squadra = Torino
```

non deve più comparire tra i portieri del Napoli.

Deve essere eventualmente considerato per il Torino se:

* è effettivamente portiere;
* appartiene alla rosa;
* rientra nei primi due della gerarchia.

---

# 12. Cambio squadra durante il mercato

Il controllo deve quindi essere effettuato sul dato:

```text
current_team
```

e non sul dato storico.

Esempio:

```text
PLAYER
    ↓
TRANSFER
    ↓
CURRENT TEAM
    ↓
CURRENT SQUAD
    ↓
GOALKEEPER HIERARCHY
```

---

# 13. Controllo anti-errore

Prima di generare l'output finale effettuare questi controlli:

```text
20 squadre presenti
        ↓
ogni squadra ha almeno 1 portiere
        ↓
ogni squadra ha almeno 2 portieri
        ↓
seleziona primi 2
        ↓
40 giocatori totali
        ↓
controllo duplicati
        ↓
controllo squadra corrente
        ↓
output finale
```

Se una squadra non ha due portieri identificabili, **non inventare il secondo giocatore**.

Segnalare:

```text
WARNING:
Juventus → trovato solamente 1 portiere verificabile
```

---

# 14. Controllo dei trasferimenti

Prima del salvataggio definitivo confrontare:

```text
DATABASE/LISTA PRECEDENTE
            VS
ROSA SCRAPATA 1 SETTEMBRE
```

Classificare i cambiamenti:

```text
ADDED
REMOVED
TRANSFERRED
UNCHANGED
```

Esempio:

```text
ADDED
+ Portiere C → Napoli

REMOVED
- Portiere B → Napoli

TRANSFERRED
→ Portiere D → Torino
```

Questo rende molto più semplice verificare che lo scraping abbia realmente recepito il mercato.

---

# 15. Aggiornamento dei giocatori già presenti

Se il giocatore esiste già nel database, non creare un nuovo record se l'identificativo è lo stesso.

Aggiornare invece:

```text
team
ranking
status
rating
quotazione
FM
eventuali altri dati
```

La chiave dovrebbe essere preferibilmente un:

```text
player_id
```

stabile fornito dalla fonte.

In assenza di ID affidabile, utilizzare una procedura di matching basata su:

```text
nome + cognome + data/identificativo giocatore
```

evitando di usare esclusivamente il nome.

---

# 16. Output

Per ogni squadra salvare almeno:

```text
team
player
player_id
role
goalkeeper_rank
status
source
scraped_at
```

Esempio:

```text
Napoli
Meret
12345
POR
1
starter
[source]
2026-09-01
```

e:

```text
Napoli
Portiere B
67890
POR
2
backup
[source]
2026-09-01
```

---

# 17. Ordinamento finale

Le squadre devono essere visualizzate nell'ordine stabilito dal progetto.

Le **neopromosse devono comparire per ultime**.

All'interno di ogni squadra:

```text
1° portiere
2° portiere
```

Quindi:

```text
SQUADRA 1
├── Portiere 1
└── Portiere 2

SQUADRA 2
├── Portiere 1
└── Portiere 2

...

NEOPROMOSSA 1
├── Portiere 1
└── Portiere 2

NEOPROMOSSA 2
├── Portiere 1
└── Portiere 2

NEOPROMOSSA 3
├── Portiere 1
└── Portiere 2
```

---

# 18. Importante: Meret, Di Gregorio e casi analoghi

Non assumere che i dati attualmente presenti siano corretti.

La presenza di giocatori come:

```text
Di Gregorio
Meret
Milinkovic-Savic
...
```

deve essere determinata **dalla situazione reale del 1 settembre**, non dalla lista attualmente visualizzata.

Se oggi la card mostra Di Gregorio ma la situazione di mercato successiva al 1 settembre determina una gerarchia diversa, lo scraper deve aggiornare automaticamente il risultato.

Allo stesso modo, se Meret deve essere presente, deve comparire automaticamente senza doverlo aggiungere manualmente.

---

# 19. Regola finale

Il processo corretto è:

```text
              1 SETTEMBRE
                   │
                   ▼
          SCRAPING SERIE A
                   │
                   ▼
        20 SQUADRE AGGIORNATE
                   │
                   ▼
       ROSA ATTUALE DI OGNI CLUB
                   │
                   ▼
        FILTRO SOLO PORTIERI
                   │
                   ▼
        GERARCHIA DEI PORTIERI
                   │
             ┌─────┴─────┐
             ▼           ▼
          1° POR       2° POR
             │           │
             └─────┬─────┘
                   ▼
             OUTPUT FINALE
```

**Nessun giocatore deve essere mantenuto perché era presente nella vecchia lista.**

La lista finale deve rappresentare esclusivamente la **rosa reale dopo la chiusura del mercato**, con i giocatori ceduti rimossi e i nuovi acquisti inseriti.

---

# 20. Nota sul numero totale

Prestare particolare attenzione a questo requisito:

> **"primo e sostituto per ogni squadra" = 40 giocatori, non 20.**

Se l'interfaccia deve invece mostrare **20 giocatori totali**, allora la regola deve essere:

```text
20 squadre
×
1 portiere principale
=
20 giocatori
```

Se vuoi mostrare la coppia **titolare + sostituto**, il dataset corretto è:

```text
20 squadre
×
2 portieri
=
40 giocatori
```

La distinzione deve essere definita prima di implementare lo scraper per evitare che il frontend e il backend lavorino con numeri diversi.
