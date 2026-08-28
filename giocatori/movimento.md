# Specifiche scraping — Selezione giocatori Fantacalcio per profilo tattico

## 1. Obiettivo

Lo scraper non deve limitarsi a leggere il ruolo ufficiale del giocatore.

Per la selezione dei giocatori da inserire nel dataset fantacalcio bisogna considerare anche il **profilo tattico e offensivo reale**.

L'obiettivo è privilegiare giocatori che abbiano:

* minutaggio rilevante;
* titolarità o forte possibilità di titolarità;
* coinvolgimento offensivo;
* gol;
* assist;
* occasioni create;
* posizione avanzata;
* calci piazzati;
* capacità di portare bonus;
* ruolo tattico favorevole al fantacalcio.

La classificazione deve quindi essere:

```text
RUOLO UFFICIALE
      +
POSIZIONE IN CAMPO
      +
COMPITI TATTICI
      +
PRODUZIONE OFFENSIVA
      +
TITOLARITÀ
      =
PROFILO FANTACALCISTICO
```

---

# 2. Principio generale

Non bisogna chiedersi solamente:

> "È difensore, centrocampista o attaccante?"

Bisogna chiedersi:

> **"Dove gioca realmente e quanto è coinvolto nella fase offensiva?"**

Questo è fondamentale perché due giocatori con lo stesso ruolo ufficiale possono avere un valore fantacalcistico completamente diverso.

Esempio:

```text
DIFENSORE
centrale puro
→ profilo difensivo

DIFENSORE
terzino molto offensivo
→ profilo interessante

DIFENSORE
quinto di centrocampo
→ profilo molto interessante
```

Analogamente:

```text
CENTROCAMPISTA
mediano
→ poco interessante

CENTROCAMPISTA
box-to-box
→ medio

CENTROCAMPISTA
trequartista / mezzala offensiva
→ molto interessante

CENTROCAMPISTA
quasi seconda punta
→ estremamente interessante
```

E per gli attaccanti:

```text
PUNTA
→ gol

ESTERNO OFFENSIVO
→ assist + gol

SECONDA PUNTA
→ gol + assist

ESTERNO MOLTO DIFENSIVO
→ profilo da penalizzare
```

---

# 3. Difensori

## Obiettivo

Tra i difensori bisogna dare **particolare priorità a terzini e quinti di centrocampo offensivi**.

Ordine di preferenza indicativo:

```text
QUINTO OFFENSIVO
        ↓
TERZINO OFFENSIVO
        ↓
TERZINO
        ↓
BRACCETTO OFFENSIVO
        ↓
DIFENSORE CENTRALE CON BONUS
        ↓
CENTRALE
        ↓
CENTRALE DIFENSIVO PURO
```

---

# 4. Terzini

Un terzino deve ricevere un punteggio maggiore quando:

* sale frequentemente;
* arriva sul fondo;
* crossa;
* crea occasioni;
* fornisce assist;
* entra nell'ultimo terzo;
* calcia corner;
* calcia punizioni;
* effettua molti passaggi chiave;
* conclude frequentemente;
* viene utilizzato come terzino molto alto.

Esempio concettuale:

```text
TERZINO A

cross          █████████
assist         ████████
passaggi chiave ███████
tiro           █████
```

→ **profilo fantacalcistico alto**

---

# 5. Quinti di centrocampo

I quinti devono ricevere **un bonus specifico**.

Un quinto che gioca stabilmente:

```text
LWB / RWB
```

o:

```text
esterno di centrocampo
```

deve essere considerato particolarmente interessante anche se la fonte lo classifica come difensore.

Motivo:

il ruolo reale può essere molto più vicino a quello di un esterno offensivo che a quello di un difensore.

### Esempio

```text
3-5-2

       ATT
       ATT

  QUINTO       QUINTO

     CC   CC   CC

    DC  DC  DC
```

I quinti devono quindi avere un peso superiore rispetto ai centrali.

---

# 6. Difensori centrali

I centrali non devono essere esclusi.

Devono però essere valutati soprattutto per:

* gol;
* assist;
* colpi di testa;
* presenza sui corner;
* calci piazzati;
* rigori;
* capacità di portare bonus;
* titolarità.

Un centrale che segna frequentemente deve poter superare un terzino poco offensivo.

Quindi:

```text
CENTRALE NORMALE
→ punteggio medio

CENTRALE DA 4–5 GOL
→ punteggio alto

CENTRALE CHE BATTE RIGORI
→ punteggio molto alto
```

---

# 7. Penalizzazione dei difensori

Applicare una penalizzazione ai difensori che:

* giocano esclusivamente centrali;
* hanno pochissima partecipazione offensiva;
* tirano raramente;
* non creano occasioni;
* non hanno bonus storici;
* non partecipano ai piazzati.

Non eliminarli necessariamente dal database.

La penalizzazione serve a **farli scendere nella graduatoria**.

---

# 8. Centrocampisti

Per i centrocampisti bisogna fare un filtro molto più aggressivo.

Non interessa particolarmente avere semplicemente:

```text
"un centrocampista titolare"
```

Interessa avere:

> **un centrocampista che gioca vicino alla porta o che partecipa concretamente alla produzione offensiva.**

---

# 9. Gerarchia centrocampisti

Ordine indicativo:

```text
TREQUARTISTA
        ↓
MEZZALA OFFENSIVA
        ↓
CENTROCAMPISTA OFFENSIVO
        ↓
BOX-TO-BOX CON BONUS
        ↓
ESTERNO / ALA CLASSIFICATO CC
        ↓
CENTROCAMPISTA CENTRALE
        ↓
MEDIANO
        ↓
REGISTA BASSO
```

I primi profili devono avere una forte priorità.

---

# 10. Centrocampisti quasi attaccanti

Questo è un criterio fondamentale.

Se un centrocampista:

* gioca stabilmente sulla trequarti;
* arriva spesso in area;
* effettua inserimenti;
* tira frequentemente;
* segna;
* fornisce assist;
* gioca dietro una o due punte;
* viene utilizzato come seconda punta in alcune situazioni;

deve essere considerato **molto interessante**.

Esempio:

```text
RUOLO DATABASE:
CENTROCAMPISTA

POSIZIONE REALE:
TREQUARTISTA

GOL:
8

ASSIST:
7

→ PROFILO OFFENSIVO MOLTO ALTO
```

Il ruolo nominale non deve penalizzarlo.

---

# 11. Centrocampisti da evitare / penalizzare

Penalizzare fortemente:

* mediani;
* incontristi;
* registi bassi;
* giocatori utilizzati prevalentemente davanti alla difesa;
* centrocampisti con pochissimi tiri;
* giocatori con produzione offensiva molto bassa.

Esempio:

```text
CDM
       ↓
poche conclusioni
poche occasioni
pochi gol
pochi assist
       ↓
PROFILO FANTACALCISTICO BASSO
```

---

# 12. Attaccanti

Per gli attaccanti bisogna privilegiare **due archetipi principali**:

### A. Punte da gol

Profilo:

* centravanti;
* prima punta;
* finalizzatore;
* alto volume di tiri;
* presenza in area;
* rigori;
* xG elevato;
* gol.

### B. Esterni da assist + gol

Profilo:

* ala;
* esterno offensivo;
* seconda punta;
* giocatore che parte largo ma entra dentro;
* alto numero di occasioni create;
* assist;
* gol.

Questi sono i due principali profili da ricercare.

---

# 13. Penalizzazione degli esterni difensivi

Non considerare automaticamente un esterno come ottimo attaccante.

Questo è un punto importante.

Un giocatore può essere classificato:

```text
ATTACCANTE
```

ma giocare realmente:

```text
5-4-1 / 3-5-2
esterno molto basso
```

con compiti principalmente difensivi.

In quel caso deve essere penalizzato.

---

# 14. Caso Politano

Il caso di Politano è esattamente il tipo di situazione che il sistema deve riconoscere.

Non basta:

```text
Politano
RUOLO = ATTACCANTE
```

per considerarlo automaticamente un profilo offensivo ideale.

Bisogna valutare:

```text
POSIZIONE MEDIA
+
COMPITI TATTICI
+
CONTRIBUTO DIFENSIVO
+
TIRI
+
XG
+
ASSIST
+
PASSAGGI CHIAVE
+
TOCCHI IN AREA
```

Se il giocatore viene utilizzato frequentemente con compiti di ripiegamento e forte partecipazione alla fase difensiva, il suo **profilo fantacalcistico offensivo deve essere ridimensionato**.

Non necessariamente deve essere eliminato.

Deve semplicemente perdere posizioni rispetto a un esterno più offensivo.

---

# 15. Profilo offensivo

Creare un valore interno:

```text
offensive_profile_score
```

da utilizzare per classificare i giocatori.

Il punteggio può essere costruito indicativamente da:

```text
GOL
+
ASSIST
+
xG
+
xA
+
TIRI
+
TIRI IN PORTA
+
PASSAGGI CHIAVE
+
TOCCHI IN AREA
+
CREAZIONE OCCASIONI
+
POSIZIONE MEDIA
+
PIAZZATI
+
RIGORI
```

e sottrarre:

```text
COMPITI DIFENSIVI
+
POSIZIONE BASSA
+
BASSO COINVOLGIMENTO OFFENSIVO
```

---

# 16. Non usare solamente statistiche offensive

Le statistiche devono essere combinate con il ruolo tattico.

Esempio:

```text
Giocatore A

8 gol
2 assist
ma gioca punta

→ ottimo
```

contro:

```text
Giocatore B

8 gol
2 assist
ma gioca mediano

→ dato anomalo da verificare
```

Il sistema deve quindi utilizzare le statistiche per **capire il profilo**, non semplicemente per ordinare i giocatori.

---

# 17. Profilazione tattica

Per ogni giocatore sarebbe utile produrre una classificazione interna:

```text
GK
CB
OFFENSIVE_CB
FB
OFFENSIVE_FB
WINGBACK
DM
CM
BOX_TO_BOX
AM
WINGER
SECOND_STRIKER
ST
```

Esempio:

```text
Giocatore
Ruolo ufficiale: DIF

Profilo tattico:
OFFENSIVE_FB
```

oppure:

```text
Giocatore
Ruolo ufficiale: CEN

Profilo tattico:
AM
```

oppure:

```text
Giocatore
Ruolo ufficiale: ATT

Profilo tattico:
WINGER
```

Questo permette di fare una selezione molto più intelligente.

---

# 18. Sistema di scoring consigliato

Creare un punteggio separato dal rating fantacalcio:

```text
fantasy_profile_score
```

Indicativamente:

### DIFENSORI

```text
QUINTO OFFENSIVO       +++++
TERZINO OFFENSIVO      ++++
TERZINO                +++
BRACCETTO OFFENSIVO    +++
CENTRALE DA BONUS      ++
CENTRALE NORMALE       +
CENTRALE DIFENSIVO     -
```

### CENTROCAMPISTI

```text
TREQUARTISTA            +++++
MEZZALA OFFENSIVA      ++++
CENTROCAMPISTA OFF.    ++++
SECONDA PUNTA           +++++
BOX-TO-BOX              +++
ESTERNO OFFENSIVO       ++++
CENTRALE                +
MEDIANO                 -
REGISTA BASSO           -
```

### ATTACCANTI

```text
PRIMA PUNTA FINALIZZATORE   +++++
SECONDA PUNTA               +++++
ALA OFFENSIVA               ++++
ESTERNO GOAL + ASSIST       ++++
ESTERNO DIFENSIVO           ++
ATTACCANTE POCO PRODUTTIVO  +
```

---

# 19. Bonus specifici

Aggiungere bonus quando il giocatore:

```text
+ rigori
+ punizioni
+ corner
+ vice-rigori
+ vice-punizioni
+ vice-corner
+ titolarità consolidata
+ 90 minuti frequenti
+ alto coinvolgimento offensivo
```

Questi elementi possono modificare significativamente il ranking.

---

# 20. Penalizzazioni

Applicare penalizzazioni quando:

```text
- ruolo prevalentemente difensivo
- posizione molto bassa
- alto volume di compiti difensivi
- basso numero di tiri
- basso xG
- basso xA
- pochi tocchi in area
- basso numero di occasioni create
- minutaggio insufficiente
- riserva
```

La penalizzazione deve essere **graduata**, non binaria.

---

# 21. Titolarità

Il profilo offensivo da solo non basta.

Un giocatore estremamente offensivo ma destinato alla panchina non deve automaticamente superare un titolare.

Quindi:

```text
PROFILO OFFENSIVO
×
PROBABILITÀ TITOLARITÀ
×
MINUTAGGIO PREVISTO
```

deve determinare il valore finale.

---

# 22. Giovani e nuovi acquisti

Per i giocatori appena arrivati in Serie A o appena trasferiti, può mancare lo storico statistico.

In questo caso utilizzare:

1. ruolo tattico nella nuova squadra;
2. statistiche della stagione precedente;
3. ruolo giocato nella precedente squadra;
4. minutaggio precedente;
5. costo/valutazione se disponibile;
6. informazioni sulla probabile titolarità;
7. caratteristiche tattiche.

Non assegnare automaticamente un punteggio basso solamente perché non esiste uno storico Serie A.

---

# 23. Trasferimenti

Come per i portieri, il dataset definitivo deve essere aggiornato il:

**1 settembre 2026, a mercato chiuso.**

Procedura:

```text
ROSA PRECEDENTE
       ↓
SCRAPING NUOVA ROSA
       ↓
NUOVI ACQUISTI
       ↓
CESSIONI
       ↓
CAMBIO SQUADRA
       ↓
NUOVO RUOLO TATTICO
       ↓
NUOVO PROFILO
       ↓
NUOVO SCORE
```

Un giocatore ceduto deve essere rimosso dalla squadra precedente.

Un giocatore acquistato deve essere inserito nella nuova squadra.

Il suo profilo deve essere ricalcolato sulla **nuova situazione tattica**.

---

# 24. Importante: il profilo deve essere dinamico

Non salvare solamente:

```text
role = ATT
```

ma preferibilmente:

```text
role = ATT
tactical_profile = WINGER
offensive_profile_score = 87
defensive_involvement_score = 62
goal_threat_score = 82
assist_potential_score = 79
starter_probability = 91
```

In questo modo il sistema può successivamente decidere come utilizzare il giocatore.

---

# 25. Obiettivo finale

Il sistema deve cercare:

## PORTIERI

```text
1° portiere
2° portiere
```

## DIFENSORI

```text
TERZINI OFFENSIVI
QUINTI
BRACCETTI OFFENSIVI
CENTRALI DA BONUS
```

## CENTROCAMPISTI

```text
TREQUARTISTI
MEZZALI OFFENSIVE
CENTROCAMPISTI QUASI ATTACCANTI
ESTERNI OFFENSIVI
```

## ATTACCANTI

```text
PUNTE DA GOL
SECONDE PUNTE
ESTERNI DA GOL + ASSIST
ALI OFFENSIVE
```

e deve penalizzare:

```text
DIFENSORI PURI
MEDIANI
REGISTI BASSI
CENTROCAMPISTI DIFENSIVI
ESTERNI MOLTO DIFENSIVI
ATTACCANTI CON COMPITI PREVALENTEMENTE DIFENSIVI
```

---

# 26. Filosofia del sistema

La domanda che deve guidare l'algoritmo non è:

> **"Che ruolo ha questo giocatore?"**

ma:

> **"Quanto è probabile che questo giocatore produca bonus fantacalcistici in base a dove gioca, cosa gli viene chiesto di fare e quanto gioca?"**

Quindi:

```text
RUOLO UFFICIALE
        ↓
RUOLO TATTICO REALE
        ↓
POSIZIONE
        ↓
COMPITI
        ↓
TITOLARITÀ
        ↓
PRODUZIONE OFFENSIVA
        ↓
BONUS POTENZIALI
        ↓
FANTASY PROFILE SCORE
```

Questa logica deve essere applicata **a tutti i giocatori**, non solamente agli attaccanti.

L'obiettivo è evitare risultati formalmente corretti ma fantacalcisticamente stupidi: ad esempio un mediano molto titolare davanti a un trequartista, oppure un esterno classificato attaccante ma con compiti prevalentemente difensivi davanti a una punta da 15 gol.
