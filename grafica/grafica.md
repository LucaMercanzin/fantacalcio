# Specifiche grafiche — Player Card Fantacalcio

## 1. Obiettivo

Ridisegnare completamente la card giocatore attuale mantenendo **tutte le informazioni e le funzionalità esistenti**, ma portando l'interfaccia verso un'estetica **Apple-like**:

* minimalista
* premium
* estremamente pulita
* molto spazio bianco
* gerarchia tipografica netta
* bordi sottili
* angoli morbidi
* ombre quasi impercettibili
* pochi colori
* animazioni discrete
* nessun elemento che sembri "gestionale vecchio stile"

Lo stile deve ricordare la filosofia visiva Apple, **non copiare componenti specifici di iOS/macOS**.

Il risultato deve sembrare una moderna applicazione web di fantacalcio premium.

---

# 2. Principi visivi

### Regola principale

> **La card deve sembrare quasi vuota, ma contenere tutte le informazioni necessarie.**

Evitare:

* bordi pesanti
* troppi colori
* grandi pulsanti blu
* gradienti vistosi
* ombre forti
* icone decorative inutili
* testo tutto della stessa dimensione
* informazioni ammassate
* elementi con allineamenti casuali

Usare:

* bianco
* grigio molto chiaro
* nero quasi assoluto
* un solo colore accent
* grandi raggi di curvatura
* spaziatura generosa
* tipografia pulita
* micro-interazioni

---

# 3. Layout generale della pagina

## Sfondo

La pagina non deve avere uno sfondo bianco puro.

```css
background: #f5f5f7;
```

Utilizzare quindi il classico approccio "pagina grigio chiarissimo + superfici bianche".

La card sarà bianca.

```css
background: #ffffff;
```

---

# 4. Griglia delle card

La schermata attuale mostra 5 card molto strette.

Questo va cambiato.

## Desktop

Container:

```css
max-width: 1440px;
margin: 0 auto;
padding: 32px 40px;
```

Grid:

```css
display: grid;
grid-template-columns: repeat(4, minmax(0, 1fr));
gap: 20px;
```

Con viewport molto ampia:

```css
grid-template-columns: repeat(5, minmax(0, 1fr));
```

ma solo se la larghezza disponibile permette card di almeno **250 px**.

### Larghezza minima card

```css
min-width: 240px;
```

Idealmente:

```text
250–280 px
```

Una card non deve mai diventare stretta al punto da troncare continuamente i nomi.

---

# 5. Card

Dimensioni indicative:

```css
border-radius: 18px;
background: #fff;
border: 1px solid #e5e5e7;
overflow: hidden;
```

Ombra iniziale:

```css
box-shadow: 0 2px 8px rgba(0,0,0,.04);
```

Non utilizzare una shadow evidente.

La card deve sembrare quasi appoggiata sulla pagina.

## Hover

Quando il mouse passa sopra:

```css
transform: translateY(-3px);
box-shadow: 0 8px 24px rgba(0,0,0,.08);
```

Transizione:

```css
transition:
    transform 180ms ease,
    box-shadow 180ms ease;
```

Niente animazioni aggressive.

---

# 6. Immagine giocatore

L'immagine deve essere il principale elemento visivo della card.

### Dimensioni

```css
width: 100%;
height: 190px;
object-fit: cover;
```

Su card più strette:

```css
height: 175px;
```

L'immagine deve occupare praticamente tutta la larghezza superiore della card.

Non creare un piccolo rettangolo fotografico sospeso dentro la card come nella versione attuale.

## Angoli

L'immagine eredita gli angoli superiori:

```css
border-radius: 17px 17px 0 0;
```

---

# 7. Badge posizione

Il ranking `#1`, `#2`, `#3` ecc. deve diventare un piccolo badge.

### Posizione

```text
top: 12px
left: 12px
```

### Dimensioni

Circa:

```css
width: 34px;
height: 34px;
border-radius: 50%;
```

Testo:

```css
font-size: 12px;
font-weight: 700;
```

Il badge non deve sembrare una medaglia gigante.

### Colore

Per i primi classificati può essere usato un accento dorato molto tenue.

```css
background: rgba(...);
```

Per il resto mantenere una soluzione neutra.

L'accento giallo deve essere **secondario**, non uno dei colori principali dell'interfaccia.

---

# 8. Area informazioni

Sotto la fotografia:

```text
┌──────────────────────────┐
│                          │
│ AUDERO EMIL              │
│ Como                     │
│                          │
│ Rating                   │
│ 66.5                     │
│                          │
│ ┌────────┬────────┬────┐ │
│ │ QUOT.  │ FM     │ IN │ │
│ │ 1.03   │ —      │1.1│ │
│ └────────┴────────┴────┘ │
│                          │
│ Vedi scheda →            │
│                          │
│          −  1  +         │
└──────────────────────────┘
```

Padding interno:

```css
padding: 20px;
```

---

# 9. Nome giocatore

Il nome è una delle informazioni più importanti.

### Stile

```css
font-size: 18px;
font-weight: 600;
line-height: 1.2;
letter-spacing: -0.3px;
color: #1d1d1f;
```

Il nome deve avere maggiore peso visivo rispetto alla squadra.

Esempio:

```text
AUDERO EMIL
```

non:

```text
AUDERO Emil
```

se il dato viene già restituito in maiuscolo.

---

# 10. Squadra

Sotto il nome:

```css
margin-top: 4px;
font-size: 13px;
font-weight: 500;
color: #86868b;
```

Esempio:

```text
AUDERO EMIL
Como
```

La squadra deve essere molto meno evidente del nome.

Non usare:

```text
COMO · Rating
```

perché mischia due informazioni diverse.

---

# 11. Rating

Il rating deve diventare una vera statistica.

### Layout

```text
RATING
66.5
```

Etichetta:

```css
font-size: 11px;
font-weight: 600;
text-transform: uppercase;
letter-spacing: .06em;
color: #86868b;
```

Valore:

```css
font-size: 30px;
font-weight: 600;
letter-spacing: -1px;
color: #1d1d1f;
```

Il rating deve essere visivamente dominante rispetto a quotazione e FM.

---

# 12. Statistiche secondarie

Quotazione, FM e ingresso devono essere contenuti in una piccola area statistica.

Esempio:

```text
┌────────────┬────────────┬────────────┐
│ QUOTAZIONE │     FM     │  INIZIALE  │
│            │            │            │
│   1.03     │    5.58    │    1.10    │
└────────────┴────────────┴────────────┘
```

Non utilizzare card dentro card con bordi pesanti.

Preferibile:

```css
background: #f5f5f7;
border-radius: 12px;
padding: 12px 8px;
```

Le tre colonne sono separate solamente dallo spazio.

Se necessario, utilizzare un separatore verticale molto tenue:

```css
border-left: 1px solid #e5e5e7;
```

---

# 13. Valori numerici

I valori devono avere font tabulare se disponibile:

```css
font-variant-numeric: tabular-nums;
```

Questo permette di allineare correttamente numeri come:

```text
1.03
14.27
54.53
66.00
```

Valore:

```css
font-size: 15px;
font-weight: 600;
color: #1d1d1f;
```

Etichetta:

```css
font-size: 10px;
font-weight: 600;
color: #86868b;
text-transform: uppercase;
```

---

# 14. Quotazione

La quotazione deve essere presentata chiaramente.

Non:

```text
Quot. 1.03 (in. 1.1)
```

Preferire:

```text
QUOTAZIONE
1.03
```

e l'eventuale quotazione iniziale:

```text
INIZIALE
1.10
```

come statistica separata.

Questo elimina il testo tra parentesi che attualmente rende la card visivamente disordinata.

---

# 15. FM

Stessa struttura:

```text
FM
5.58
```

Se il dato manca:

```text
FM
—
```

Il trattino deve avere lo stesso allineamento degli altri valori.

Non lasciare spazi vuoti che modifichino l'altezza della card.

---

# 16. Pulsante "Apri scheda"

Questo è uno degli elementi da eliminare completamente nella forma attuale.

### NON fare

```text
┌──────────────┐
│    Apri      │
│   scheda →   │
└──────────────┘
```

Il pulsante attuale occupa troppo spazio.

### Nuova soluzione

Un'azione testuale:

```text
Vedi scheda →
```

Posizionata sotto le statistiche.

Stile:

```css
font-size: 14px;
font-weight: 500;
color: #0071e3;
```

Nessun grande background blu.

---

# 17. Link scheda

Hover:

```text
Vedi scheda →
           ↗
```

La freccia può spostarsi di 2–3 px verso destra:

```css
transition: transform 160ms ease;
```

L'effetto deve essere quasi impercettibile.

---

# 18. Controllo quantità

I pulsanti `+` e `−` attuali sono troppo grandi e sembrano elementi indipendenti.

Devono diventare un unico controllo.

### Struttura

```text
┌──────────────────────┐
│      −    1    +     │
└──────────────────────┘
```

Altezza:

```css
height: 40px;
```

Border:

```css
1px solid #e5e5e7;
```

Radius:

```css
border-radius: 12px;
```

Background:

```css
#f5f5f7
```

### Pulsanti

```css
width: 40px;
height: 40px;
border-radius: 10px;
```

Il `+` e il `−` devono essere grigio scuro.

Non blu.

Il numero centrale:

```css
font-size: 15px;
font-weight: 600;
```

---

# 19. Gerarchia verticale

La card deve avere una spaziatura estremamente regolare.

Indicativamente:

```text
FOTO
190 px
│
20 px
│
NOME
22 px
│
4 px
│
SQUADRA
16 px
│
18 px
│
RATING LABEL
12 px
│
2 px
│
RATING VALUE
36 px
│
16 px
│
STATISTICHE
62 px
│
16 px
│
VEDI SCHEDA
20 px
│
14 px
│
QUANTITÀ
40 px
```

La spaziatura deve seguire una scala coerente:

```text
4
8
12
16
20
24
32
```

Evitare valori casuali come 13, 17, 23, 27 ecc. salvo necessità ottiche.

---

# 20. Tipografia

Utilizzare una font moderna sans-serif.

Se il progetto utilizza già Inter, può essere mantenuta.

Priorità:

```text
Inter
-apple-system
BlinkMacSystemFont
"SF Pro Display"
"SF Pro Text"
sans-serif
```

Non utilizzare font decorative.

## Pesi

```text
400 → informazioni secondarie
500 → elementi interattivi
600 → nomi e valori
700 → badge / elementi particolarmente importanti
```

Evitare di usare 700 ovunque.

---

# 21. Colori

Palette principale:

```text
Background:
#F5F5F7

Card:
#FFFFFF

Primary text:
#1D1D1F

Secondary text:
#6E6E73

Tertiary text:
#86868B

Border:
#E5E5E7

Subtle background:
#F5F5F7

Apple-like blue accent:
#0071E3
```

Il blu deve essere utilizzato principalmente per:

* link
* elementi interattivi
* stato attivo

Non per intere superfici enormi.

---

# 22. Stati dei giocatori

Se esistono diversi stati, evitare di colorare tutta la card.

Utilizzare piccoli indicatori.

Esempio:

```text
● Disponibile
● Acquistato
● In rosa
```

Il colore deve interessare solamente il punto/stato, non tutta la card.

---

# 23. Responsive

## Desktop ≥ 1200 px

```text
4–5 card per riga
gap: 20px
```

## Tablet 768–1199 px

```text
3 card per riga
gap: 16px
```

## Mobile 480–767 px

```text
2 card per riga
gap: 12px
```

Ridurre:

```text
padding card → 16px
immagine → 150–165px
nome → 16px
```

## Smartphone < 480 px

Possibile:

```text
1 card per riga
```

oppure 2 colonne se le card rimangono leggibili.

La priorità è **mai sacrificare leggibilità per mantenere due colonne**.

---

# 24. Header della pagina

Anche il testo:

```text
32 giocatori · pagina 1/2 · Clicca "Apri scheda" per i dettagli.
```

deve essere rifatto.

### Nuova gerarchia

```text
Giocatori

32 disponibili
Pagina 1 di 2
```

Eventualmente:

```text
32 giocatori
1 / 2
```

Il testo "Clicca Apri scheda per i dettagli" va eliminato.

È una spiegazione da interfaccia legacy.

L'interfaccia deve essere autoesplicativa.

---

# 25. Header consigliato

```text
Giocatori
32 giocatori                         1 / 2
```

Titolo:

```css
font-size: 32px;
font-weight: 700;
letter-spacing: -1px;
```

Meta:

```css
font-size: 14px;
color: #6e6e73;
```

---

# 26. Pagination

La paginazione non deve sembrare un elemento amministrativo.

Utilizzare:

```text
‹       1  2       ›
```

oppure:

```text
‹   1 / 2   ›
```

Pulsanti:

```css
width: 36px;
height: 36px;
border-radius: 50%;
```

Background molto leggero.

---

# 27. Mobile interaction

Su mobile:

* niente hover
* card completamente cliccabile
* pulsanti sufficientemente grandi
* minimo touch target ~44 px
* evitare testo minuscolo

---

# 28. Micro-interazioni

Le animazioni devono essere molto discrete.

### Card

```text
hover → translateY(-3px)
```

### Link

```text
freccia → translateX(3px)
```

### Plus/minus

Press:

```text
scale(0.96)
```

### Card apertura

Se viene aperta una scheda:

```text
opacity
transform
```

con durata:

```text
180–250 ms
```

Niente bounce.

Niente effetti "gaming".

---

# 29. Cosa eliminare dalla grafica attuale

Da rimuovere:

* ❌ enorme bottone blu "Apri scheda"
* ❌ `· Rating` accanto al nome della squadra
* ❌ testo `Quot. 1.03 (in. 1.1)`
* ❌ cerchi blu enormi per `+` e `−`
* ❌ bordo grigio troppo evidente
* ❌ card troppo strette
* ❌ spaziatura irregolare
* ❌ informazioni senza gerarchia
* ❌ testo "Clicca Apri scheda per i dettagli"
* ❌ valori numerici separati da righe di testo senza struttura

---

# 30. Obiettivo visivo finale

La card deve comunicare immediatamente:

```text
          FOTO
           ↓
      #1  AUDERO
          COMO

        RATING
          66.5

  QUOT.     FM      IN.
  1.03      —       1.10

      Vedi scheda →

       ┌───────────┐
       │  −  1  +  │
       └───────────┘
```

La sensazione finale deve essere:

**Apple / premium / sport-tech / minimal**

e non:

**gestionale / Bootstrap / admin panel / CRUD**.

---

# 31. Regola fondamentale

Non aggiungere elementi solamente perché "la card sembra vuota".

Lo spazio bianco è intenzionale.

Se un elemento non migliora:

1. comprensione
2. gerarchia
3. interazione
4. leggibilità

va eliminato.

La direzione estetica deve essere:

> **meno elementi, più gerarchia, più spazio, migliore tipografia.**

---

# 32. Priorità di implementazione

### P0 — indispensabile

* nuova struttura card
* immagine grande
* nome/squadra separati
* rating prominente
* statistiche strutturate
* eliminazione grande pulsante blu
* nuovo controllo quantità
* card più larga
* nuovo spacing
* palette Apple-like

### P1 — importante

* hover
* micro-interazioni
* responsive
* nuova pagination
* nuovo header pagina
* badge ranking ridisegnato

### P2 — rifinitura

* animazioni
* stati giocatore
* transizioni
* dettagli tipografici
* ottimizzazione pixel-perfect

---

# 33. Risultato atteso

Non bisogna semplicemente "abbellire" la card esistente.

Bisogna **ridisegnare la gerarchia visiva mantenendo invariata la logica applicativa**.

Il componente finale deve sembrare appartenere alla stessa famiglia di una moderna app Apple:

```text
background molto chiaro
        ↓
card bianca
        ↓
fotografia dominante
        ↓
nome forte
        ↓
informazioni secondarie discrete
        ↓
numeri grandi e leggibili
        ↓
azioni minimali
```

**Il riferimento estetico è Apple, ma il componente deve rimanere chiaramente un'interfaccia di fantacalcio.**
# 34. Riferimenti visivi allegati

Le immagini allegate a questa specifica devono essere utilizzate come **riferimento visivo diretto** per la progettazione della nuova interfaccia.

Non devono essere copiate letteralmente e non è necessario replicare esattamente i componenti presenti nelle immagini. Devono invece essere utilizzate per definire:

* proporzioni delle card
* quantità di spazio bianco
* rapporto tra immagine e contenuto
* dimensione e peso tipografico
* arrotondamento degli elementi
* trattamento delle superfici
* livello delle ombre
* gerarchia delle informazioni
* dimensione dei pulsanti
* comportamento degli elementi interattivi
* densità complessiva dell'interfaccia
* rapporto tra contenuto principale e informazioni secondarie

## Direzione estetica

Il riferimento generale deve essere quello delle immagini allegate: **premium, minimale, pulito e molto curato nei dettagli**.

Lo stile Apple dichiarato per il progetto deve essere interpretato soprattutto attraverso:

```text
spazio bianco
↓
tipografia
↓
gerarchia
↓
proporzioni
↓
superfici
↓
micro-interazioni
```

e non attraverso l'aggiunta di elementi che facciano semplicemente "Apple".

## Cosa osservare nelle immagini

### 1. Spazio

Prestare particolare attenzione alla quantità di spazio libero attorno agli elementi.

La UI non deve cercare di riempire ogni pixel disponibile.

Se le immagini di riferimento mostrano un elemento separato da 20–24 px dagli altri, mantenere una logica di spacing analoga invece di comprimere gli elementi per mostrare più informazioni.

### 2. Card

La card deve avere una presenza visiva molto simile a quella dei riferimenti:

* superficie pulita
* angoli morbidi
* bordo quasi impercettibile
* shadow molto leggera
* contenuto ben distanziato
* nessun effetto 3D evidente

La card deve risultare **solida ma leggera**.

### 3. Fotografia

La fotografia del giocatore deve essere trattata come un elemento editoriale importante, non come una semplice thumbnail.

Deve avere:

* dimensione generosa
* rapporto d'aspetto coerente tra tutti i giocatori
* crop consistente
* angoli arrotondati
* posizione stabile all'interno della card

Le immagini dei giocatori possono quindi diventare l'elemento più riconoscibile della card.

### 4. Tipografia

Utilizzare le immagini come riferimento soprattutto per la gerarchia:

```text
NOME GIOCATORE
        ↓
squadra
        ↓
dato principale
        ↓
dati secondari
        ↓
azioni
```

Il testo secondario non deve competere con il nome o con il rating.

### 5. Colore

Le immagini devono essere interpretate in modo coerente con una palette prevalentemente neutra.

Il colore deve essere utilizzato per attirare l'attenzione solamente dove serve.

In particolare:

* niente grandi superfici colorate senza necessità
* niente pulsanti saturi che dominano la card
* niente combinazioni di molti colori
* utilizzare l'accent color per le azioni e gli stati importanti

### 6. Dettagli

La qualità percepita deve derivare dai dettagli.

Prestare attenzione a:

* 1–2 px di differenza nei bordi
* allineamento perfetto
* baseline dei testi
* spaziature coerenti
* dimensioni dei touch target
* posizione delle icone
* comportamento hover/active
* transizioni
* uniformità delle immagini
* allineamento dei valori numerici

L'obiettivo non è aggiungere decorazioni, ma fare in modo che **ogni elemento sembri intenzionale**.

## Importante

Le immagini allegate costituiscono il **riferimento estetico**, mentre questa specifica costituisce il **riferimento funzionale e dimensionale**.

In caso di conflitto:

1. mantenere la funzionalità esistente;
2. mantenere leggibilità e accessibilità;
3. mantenere la gerarchia descritta in questa specifica;
4. utilizzare le immagini per determinare il look & feel.

Non trasformare quindi la card in una copia delle immagini di riferimento: **prendere la stessa qualità visiva e applicarla al contesto del fantacalcio**.
