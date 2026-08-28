# AI RULES — Regole operative

## SCOPO

Questo file definisce le regole operative che ogni AI agent deve seguire quando lavora sul progetto.

Le regole valgono indipendentemente dal modello utilizzato.

L'obiettivo è ottenere:

* ragionamento corretto;
* modifiche minime e precise;
* consumo efficiente dei token;
* rispetto dell'architettura esistente;
* nessuna modifica fatta "a tentativi";
* nessuna invenzione;
* nessuna perdita di tempo su problemi non pertinenti.

---

# 1. PRIMA PENSA, POI AGISCI

Non iniziare immediatamente a modificare file.

Prima di qualsiasi modifica:

1. capire cosa viene richiesto;
2. individuare i file coinvolti;
3. ricostruire il flusso del codice;
4. identificare la causa del problema;
5. valutare le dipendenze;
6. definire una strategia;
7. solo dopo modificare il codice.

NON fare:

```text
vedo il problema
↓
apro un file
↓
modifico
↓
errore
↓
modifico altro
↓
altro errore
↓
provo un'altra cosa
```

Questo comportamento spreca token, tempo e introduce regressioni.

Preferire:

```text
problema
↓
raccolta contesto
↓
analisi
↓
ipotesi
↓
verifica
↓
piano
↓
implementazione
↓
test
↓
verifica finale
```

---

# 2. NON BRUCIARE TOKEN

I token sono una risorsa.

Non utilizzare grandi quantità di output per dire cose che non servono.

Evitare:

* spiegazioni ripetitive;
* riassunti inutili;
* riletture dello stesso codice;
* output di file interi quando basta una parte;
* ripetizione della richiesta dell'utente;
* descrizioni ovvie;
* supposizioni non verificate;
* esplorazione indiscriminata dell'intero repository.

Prima di leggere un file chiedersi:

> Mi serve davvero questo file per risolvere il problema?

Prima di leggere 500 righe chiedersi:

> Mi servono tutte e 500?

Prima di eseguire un comando chiedersi:

> Quale informazione mi darà?

Ogni operazione deve avere uno scopo.

---

# 3. NON FARE FINTA DI AVER CAPITO

Se il codice non è ancora chiaro, non comportarsi come se lo fosse.

Distinguere sempre:

```text
FATTO
→ verificato direttamente nel codice

IPOTESI
→ possibile spiegazione ancora da verificare

CONCLUSIONE
→ verificata dopo l'analisi
```

Non inventare:

* funzioni;
* variabili;
* tabelle;
* colonne;
* API;
* comportamenti;
* dipendenze;
* configurazioni.

Se un'informazione manca, cercarla nel progetto prima di inventarla.

---

# 4. NON MODIFICARE IL CODICE PER TENTATIVI

Evitare modifiche speculative.

Esempio sbagliato:

```text
Forse il problema è qui.
Modifico.
```

Se la causa non è stata verificata:

```text
1. individuare il comportamento
2. seguire il flusso
3. verificare l'origine
4. trovare la causa
5. modificare
```

Una modifica deve avere una motivazione tecnica precisa.

---

# 5. PRIMA DI MODIFICARE, CERCA LA CAUSA REALE

Quando viene segnalato un bug:

Non correggere semplicemente il punto in cui il bug appare.

Chiedersi:

> Perché questo valore/comportamento arriva qui in questo stato?

Analizzare il flusso:

```text
INPUT
 ↓
VALIDAZIONE
 ↓
NORMALIZZAZIONE
 ↓
LOGICA
 ↓
DATABASE
 ↓
OUTPUT
```

La soluzione deve essere applicata nel punto corretto dell'architettura.

---

# 6. RISPETTA IL CODICE ESISTENTE

Questo è un progetto esistente.

Non riscrivere automaticamente ciò che già funziona.

Prima capire:

* convenzioni;
* naming;
* struttura;
* pattern;
* classi;
* funzioni;
* dipendenze;
* compatibilità legacy.

Se una modifica può essere fatta con 10 righe, non trasformarla in un refactoring da 300 righe.

---

# 7. MODIFICA IL MINIMO NECESSARIO

Principio:

> Minimum necessary change.

Se il problema riguarda:

```text
function A()
```

non modificare automaticamente:

```text
A()
B()
C()
D()
E()
```

a meno che l'analisi dimostri che sono coinvolte.

Ogni modifica aggiuntiva aumenta il rischio di regressione.

---

# 8. NON FARE REFACTORING NON RICHIESTO

Non usare un bug come pretesto per riscrivere il progetto.

NON fare automaticamente:

* refactoring globale;
* rinominazioni;
* cambio framework;
* cambio database;
* cambio architettura;
* conversione completa;
* eliminazione di codice legacy;
* sostituzione di librerie.

Se viene individuato un miglioramento interessante ma non necessario:

```text
MIGLIORAMENTO SEPARATO
```

e non inserirlo nella modifica corrente.

---

# 9. QUANDO IL TASK È COMPLESSO

Per task complessi creare mentalmente un piano prima di agire.

Formato:

```text
OBIETTIVO
↓

FILE COINVOLTI
↓

DIPENDENZE
↓

CAUSA / ARCHITETTURA
↓

SOLUZIONE
↓

IMPLEMENTAZIONE
↓

TEST
```

Non iniziare a modificare file finché il piano non è sufficientemente chiaro.

---

# 10. NON ESPLORARE TUTTO IL REPOSITORY SENZA MOTIVO

Usare un'esplorazione progressiva.

### Livello 1

Identificare:

* file principale;
* funzione;
* classe;
* endpoint;
* componente.

### Livello 2

Leggere le dipendenze direttamente coinvolte.

### Livello 3

Espandere la ricerca solamente se necessario.

Non effettuare:

```text
scan completo repository
```

come prima operazione se il problema può essere risolto analizzando 3-5 file.

---

# 11. USA GLI STRUMENTI CON INTELLIGENZA

Ogni comando deve rispondere a una domanda.

Esempio:

```text
grep/search
→ dove viene definita questa funzione?

read
→ come funziona questa funzione?

search
→ chi la utilizza?

test
→ la modifica funziona?

git diff
→ cosa ho effettivamente cambiato?
```

Non eseguire comandi casuali.

---

# 12. PRIMA DI SCRIVERE CODICE, DEFINISCI IL RISULTATO

Deve essere chiaro:

```text
INPUT
↓
COMPORTAMENTO ATTESO
↓
OUTPUT
```

Confrontarlo con:

```text
COMPORTAMENTO ATTUALE
```

Solo la differenza necessaria deve essere modificata.

---

# 13. VERIFICA SEMPRE IL DIFF

Dopo una modifica:

```text
git diff
```

oppure equivalente.

Controllare:

* file modificati;
* righe modificate;
* codice aggiunto;
* codice rimosso;
* modifiche accidentali;
* debug lasciato nel codice;
* logging inutile;
* formattazioni massive;
* file modificati senza motivo.

Se sono stati modificati 15 file per un problema che sembrava riguardare una funzione, fermarsi e verificare perché.

---

# 14. TEST

Dopo ogni modifica significativa:

1. eseguire il test più piccolo utile;
2. verificare il comportamento;
3. controllare eventuali regressioni;
4. solo dopo considerare il task concluso.

Non dichiarare:

```text
"Risolto"
```

se la modifica non è stata verificata.

Usare invece:

```text
IMPLEMENTATO
```

quando è stata scritta ma non ancora verificata.

Usare:

```text
VERIFICATO
```

quando il comportamento è stato effettivamente testato.

---

# 15. ERRORI DURANTE IL LAVORO

Se una modifica produce un errore:

NON iniziare una catena di tentativi casuali.

Fare:

```text
errore
↓
leggi errore
↓
individua causa
↓
verifica causa
↓
correggi
↓
test
```

Non accumulare patch sopra patch senza capire il motivo.

---

# 16. NON NASCONDERE I PROBLEMI

Se una soluzione introduce:

* workaround;
* limitazioni;
* comportamento non ideale;
* incompatibilità;
* dati mancanti;

dichiararlo.

Non mascherare un problema con:

```text
if (...)
    return;
```

solo per far sparire l'errore.

---

# 17. CODICE LEGACY

Questo progetto contiene codice legacy.

Non assumere che:

```text
vecchio = sbagliato
nuovo = migliore
```

Il codice esistente può dipendere da:

* PHP legacy;
* convenzioni WI400;
* Meridian;
* database;
* chiamate esterne;
* comportamenti impliciti;
* compatibilità con altri moduli.

Prima di cambiare qualcosa, verificare chi lo utilizza.

---

# 18. COMPATIBILITÀ

Prima di introdurre una soluzione moderna verificare:

* versione PHP;
* librerie disponibili;
* struttura del progetto;
* compatibilità server;
* compatibilità database;
* compatibilità browser;
* convenzioni esistenti.

Non introdurre tecnologie nuove solamente perché sono più moderne.

---

# 19. QUANDO USARE INTERNET / DOCUMENTAZIONE

Utilizzare fonti esterne quando servono informazioni che non possono essere determinate dal repository.

Esempi:

* documentazione API;
* comportamento di una libreria;
* sintassi di una versione specifica;
* documentazione ufficiale;
* endpoint pubblici;
* aggiornamenti tecnologici.

Non fare ricerche web se la risposta è già chiaramente presente nel progetto.

---

# 20. SCRAPING E DATI ESTERNI

Quando si lavora con una fonte esterna:

1. verificare la struttura reale;
2. identificare HTML/API pubbliche;
3. verificare quali dati sono effettivamente disponibili;
4. normalizzare i dati;
5. gestire errori;
6. rispettare robots.txt e termini d'uso;
7. non bypassare sistemi di autenticazione o anti-bot.

Non assumere che un dato esista solamente perché sembra utile.

---

# 21. QUANDO ESISTONO PIÙ SOLUZIONI

Confrontare:

```text
SOLUZIONE A
vantaggi
svantaggi

SOLUZIONE B
vantaggi
svantaggi
```

Scegliere quella che:

1. risolve il problema;
2. modifica meno codice;
3. mantiene compatibilità;
4. è più semplice da mantenere;
5. introduce meno rischio.

Non scegliere automaticamente la soluzione più sofisticata.

---

# 22. NON CONFONDERE COMPLESSITÀ CON QUALITÀ

Una soluzione con:

```text
500 righe
```

non è automaticamente migliore di una con:

```text
30 righe
```

La soluzione migliore è quella sufficientemente robusta per il problema.

---

# 23. PRIORITÀ ASSOLUTE

Quando devi scegliere tra:

```text
velocità
quantità di codice
eleganza
```

e:

```text
correttezza
```

la correttezza viene prima.

Ordine:

```text
1. CORRETTEZZA
2. COMPRENSIONE
3. COMPATIBILITÀ
4. SEMPLICITÀ
5. EFFICIENZA
6. ELEGANZA
```

---

# 24. NON DIMENTICARE L'OBIETTIVO DELL'UTENTE

Non ottimizzare il codice perdendo di vista ciò che è stato richiesto.

Prima domanda:

> Qual è esattamente il risultato che l'utente vuole ottenere?

Poi:

> Qual è la modifica minima necessaria per ottenerlo?

---

# 25. REGOLA FINALE

Prima di ogni modifica significativa chiedersi:

```text
HO CAPITO IL PROBLEMA?
        ↓
SO PERCHÉ SUCCEDE?
        ↓
SO QUALI FILE SONO COINVOLTI?
        ↓
SO QUAL È LA SOLUZIONE?
        ↓
POSSO FARLO CON MENO MODIFICHE?
        ↓
POSSO VERIFICARE IL RISULTATO?
```

Se una risposta è NO:

**non procedere alla modifica finché non hai raccolto le informazioni necessarie.**

L'obiettivo non è produrre più codice.

L'obiettivo è produrre **la modifica corretta, nel posto corretto, con il minor numero di cambiamenti e il minor consumo inutile di risorse.**
