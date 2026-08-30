> **AGGIORNAMENTO 30/08/2026 (sera) — vedi `AUDIT_2026-08-30_CORREZIONI.md`.**
> Parte della sez. 3 di questo documento (copertura `player_consensus`, "57%
> insufficienti") è stata scritta leggendo le tabelle SQL grezze, non la
> pipeline applicativa reale (`_compute_ranked_role`, `estimate_fantamedia`).
> Verificato girando il codice vero: quella cifra è sbagliata, la copertura
> live è ~99%. La sez. 1.1 (portieri) restava corretta nel sintomo ma
> sbagliata nella causa attribuita — la causa vera, verificata ed **ora
> corretta nel codice**, è nel documento di correzione. Non fidarti dei
> numeri sotto senza leggere prima quello.

# Audit dati e pipeline — 30/08/2026

Audit nato da due sintomi segnalati in uso reale ("la rosa ideale è completamente errata",
"nessun portiere identificabile per la Lazio"). Entrambi risalgono a **tre cause a monte**,
non a bug nei moduli che mostrano l'errore.

Convenzione `claude.md` §3: ogni affermazione è marcata **FATTO** (verificato su
`data/fantacalcio.db` o sul codice), **IPOTESI** (da verificare), **CONCLUSIONE** (dedotta
da fatti verificati).

Contesto lega (`config.py`): 8 squadre × 500 crediti, rose da 25 (3P/8D/8C/6A), 3-4-3,
stagione 2026/27. **Budget totale in circolo nella lega: 4.000 crediti.**

---

## Verdetto in una riga

Il motore di prezzo d'asta è inutilizzabile (produce 4,7× il denaro che esiste nella lega) e
il 57% dei giocatori non è classificabile perché il modello pretende una `fantamedia` di
stagione corrente che a fine agosto **non esiste per nessuno**. Tutto il resto è conseguenza.

---

## 1. I due problemi segnalati — causa verificata

### 1.1 "Nessun portiere identificabile per la Lazio"

**FATTO.** La Lazio ha 4 portieri in `players`, incluso il titolare corretto:

| id | nome | fantamedia | appearances | source_count |
|---|---|---|---|---|
| 99 | Mandas Christos | **NULL** | 0 | 6 |
| 479 | Motta Edoardo | **NULL** | 14 | 6 |
| 480 | RENZETTI Davide | **NULL** | NULL | 4 |
| 543 | Furlanetto Alessio | 4.83 | 2 | 4 |

**FATTO.** `ranking/goalkeepers.py:38` scarta chi ha `score is None`, e lo `score` è `None`
quando manca la `fantamedia` (P0-002/TASK-002). Restano 0-1 portieri per squadra.

**FATTO.** Mandas ha `fantamedia = NULL` da **tutte e 6 le fonti** (`quotations`). Non è un
bug di scraping: al 26/08 la stagione 2026/27 non ha ancora prodotto fantamedie.

**FATTO.** Il dato però *esiste già in casa*, in `player_season_stats`:

| stagione | presenze | avg_rating |
|---|---|---|
| 2025/26 | 0 | NULL ← prestito all'estero |
| 2024/25 | 9 | 6.28 |
| 2023/24 | 8 | 6.25 |

**CONCLUSIONE.** Il modello richiede una metrica che al momento dell'asta non può esistere,
e non ricade sullo storico che ha già in database. Non è un problema della Lazio: è
strutturale, e colpisce ogni giocatore rientrato da un prestito, ogni neoacquisto e ogni
promosso. Il paradosso è che l'unico portiere Lazio "classificabile" è il quarto
(Furlanetto, 2 presenze), mentre il titolare vero viene scartato.

Stesso schema del finding già noto "Audero non è più il portiere #1"
(`OPUS_PROJECT_REVIEW.md`): non era stato risolto alla radice.

### 1.2 "La rosa ideale è completamente errata" / "certi prezzi sono sballati"

Avevi ragione, ma il problema è più grande di qualche prezzo storto.

**FATTO.** Somma di **tutti** i `price_auction`: **18.733 crediti** su 205 giocatori.
Il denaro che esiste nella lega è **4.000** (8 × 500). Il modello stampa **4,7× la moneta
circolante**.

**FATTO.** Quattro attaccanti sono quotati **esattamente 500.00** — cioè
`AUCTION_CANONICAL_CEILING`, che `consensus/engine.py:47` definisce come `TOTAL_CREDITS`.
Non sono prezzi: sono valori che hanno sfondato il tetto e sono stati troncati al budget
intero di una squadra.

| giocatore | listino | asta |
|---|---:|---:|
| Hojlund | 41.59 | **500.00** ← clamp |
| Malen | 48.41 | **500.00** ← clamp |
| Martinez Lautaro | 45.74 | **500.00** ← clamp |
| Ramos Goncalo | 45.96 | **500.00** ← clamp |
| Thuram | 41.19 | 477.67 |

**FATTO.** Una rosa da 25 costruita coi più cari per ruolo costa **6.434 crediti** su 500
disponibili (12,9×). Qualsiasi ottimizzatore su questi numeri restituisce `infeasible` o
sceglie a caso fra i pochi giocatori sotto soglia — da qui la "rosa ideale errata".

**FATTO — causa radice.** Le 5 fonti hanno scale di prezzo **incompatibili**, e vengono
mediate insieme:

| fonte | n | mediana | max |
|---|---:|---:|---:|
| fantacalcio_it | 540 | 5.00 | 36.00 |
| fantanalisi | 491 | **2.00** | **382.00** |
| fantapazz | 648 | 11.00 | 83.00 |
| fantacalcio_online | 228 | 15.41 | 141.74 |
| pianetafanta | 582 | 16.20 | 93.10 |

Una mediana che va da 2.00 a 16.20 (8×) e un massimo che va da 36 a 382 (10,6×) significa
che queste colonne **non misurano la stessa cosa**. Mandas, sei fonti: 10.0 / 12.13 / 27.0 /
17.0 / 28.4 / NULL. Mediarle non produce un prezzo, produce un numero senza unità.

`ranking/price_engine.py` documenta già il problema ("P0-001's mixed price scales") e
`consensus/engine.py:54` ammette che il fattore `DEFAULT_LISTINO_TO_AUCTION_FACTOR = 12.5`
è "naive". **CONCLUSIONE:** la correzione applicata non ha funzionato — i numeri sopra sono
la prova empirica.

**FATTO.** `price_listino`, al contrario, **è sano**. Confrontato coi listoni pubblici
2026/27 sta nella stessa scala (Paz 32.27 vs ~30 reale, McTominay 33.75 vs ~28,
Calhanoglu 33.82 vs ~27). È l'unica colonna prezzo usabile oggi.

---

## 2. La lista che avevi chiesto, fatta sui dati sani

Il tuo "metti almeno il giocatore col credito più alto per ogni ruolo", calcolato su
`price_listino` (non su `price_auction`, che è rotto), filtrato a Serie A e `active=1`:

**Portieri (3) — 57,5 cr**
Svilar (Roma, 20.44) · Carnesecchi (Atalanta, 18.53) · Maignan (Milan, 18.53)

**Difensori (8) — 154,1 cr**
Dimarco (Inter, 23.18) · Wesley (Roma, 21.27) · Bremer (Juve, 20.75) · Bastoni (Inter, 19.07)
Pavlovic (Milan, 18.51) · Di Lorenzo (Napoli, 17.59) · Akanji (Inter, 17.03) · Kalulu (Juve, 16.67)

**Centrocampisti (8) — 242,5 cr**
Calhanoglu (Inter, 33.82) · McTominay (Napoli, 33.75) · Paz (Como, 32.27) · Pulisic (Milan, 30.99)
Orsolini (Bologna, 30.19) · Rabiot (Milan, 28.55) · De Bruyne (Napoli, 27.24) · Baturina (Como, 25.68)

**Attaccanti (6) — 264,4 cr**
Malen (Roma, 48.41) · Ramos (Milan, 45.96) · Lautaro (Inter, 45.74)
Hojlund (Napoli, 41.59) · Kolo Muani (Juve, 41.55) · Thuram (Inter, 41.19)

**Totale 718,5 cr su 500** — corretto che non ci stia: è la lista dei più cari per ruolo, non
una rosa acquistabile. Serve da riferimento di scala, non da piano d'asta.

⚠️ Due valori da non fidarsi: **Ramos e Kolo Muani hanno `fantamedia = 0.00`** ma entrano nei
top-6 solo per prezzo. E **Malen ha `fantamedia = 8.84`**, fuori dalla finestra plausibile di
Serie A (~2.0–9.5) — è il finding P0-004, ancora aperto.

---

## 3. Stato reale dei dati

**FATTO — 11 tabelle su 24 sono vuote:**

| tabella | righe | conseguenza |
|---|---:|---|
| `player_advanced_stats` | 0 | niente xG/xA — pesano 25-35% nel modello di `rosa-ideale.md` §24 |
| `player_set_pieces` | 0 | niente rigoristi/piazzati — "Errore 8 e 9" del metodo |
| `player_injuries` | 0 | niente rischio infortuni |
| `player_match_ratings` | 0 | niente forma recente (usata da `ideal_squad.compute_ideal_score`) |
| `player_anagrafica` | 0 | niente età/minutaggio |
| `player_transfers` | 0 | vuota nonostante TASK-004c |
| `team_fixture_difficulty` | 0 | niente calendario |
| `scraping_runs` | 0 | vuota nonostante TASK-006 |
| `player_fantanalisi_valuations` | 0 | fonte non materializzata |
| `my_roster`, `opponent_picks` | 0 | atteso pre-asta |

**CONCLUSIONE.** Il modello di scoring documentato in `giocatori/rosa-ideale.md` §24 pesa
xG 25-35%, rigori, piazzati e minutaggio previsto. **Nessuno di questi input esiste.** Lo
scorer gira su fantamedia + avg_rating + presenze, cioè su una frazione del modello che il
documento descrive. Non è un bug: è uno scostamento fra progetto e implementazione che non
è dichiarato da nessuna parte nella UI.

**FATTO — copertura `player_consensus` (802 righe):**
- `fantamedia` NULL o 0 → **458 (57%)**
- `appearances` NULL o 0 → 232 (29%)
- `price_listino` NULL → 117 (15%)
- una sola fonte → 179 (22%)

**FATTO — `quotations.stats_season` e `stats_competition` sono NULL su tutte e 3.509 le
righe.** TASK-008 ha aggiunto le colonne, ma nessuno scraper le popola: il filtro
stagione/campionato che quel task doveva abilitare è **inerte**.

**FATTO — nomi squadra non normalizzati.** `players.team` è TEXT libero e contiene doppioni:

```
ATALANTA / Atalanta      CAG / Cagliari       COMO / Como
FIORENTINA / Fiorentina  FROSINONE/Frosinone  GENOA / Genoa
JUVENTUS / Juventus      LEC / Lecce          MILAN / Milan
MONZA / Monza            PAR / Parma          SAS / Sassuolo
+ "Estero", "Serie Minori"
```

`team_aliases` ha **11 righe per 20 squadre**. **CONCLUSIONE:** ogni club è spaccato in due
bucket e la depth chart portieri legge solo quello che capita — causa indipendente e
concorrente del sintomo 1.1.

**FATTO — encoding e casing su `canonical_name`:** `WESLEY Fran?a Lima` (mojibake),
`RAMOS Goncalo Matias`, `PEDRAZA Alfonso Sag`, `RENZETTI Davide` in maiuscolo contro
`Bastoni Alessandro` in Title Case.

---

## 4. PULIZIA

| # | Intervento | Perché | Sforzo |
|---|---|---|---|
| C1 | Normalizzare `players.team` su FK a `teams.id`, completare `team_aliases` (11→20+ con sigle e maiuscole) | Elimina i bucket doppi; sblocca depth chart e ogni group-by squadra | M |
| C2 | Escludere `Estero` / `Serie Minori` / squadre non in Serie A 2026/27 dai pool rankati | Oggi entrano nei conteggi e nelle liste | S |
| C3 | Fissare encoding a UTF-8 in ingresso scraper + normalizzare casing dei nomi | `Fran?a` è un dato corrotto salvato, non un problema di display | S |
| C4 | Rimuovere o popolare le 11 tabelle vuote | Schema che promette dati inesistenti; ogni join ci passa a vuoto | S |
| C5 | Validare `fantamedia` nella finestra ~2.0–9.5 in ingresso, `None` + warning fuori range | P0-004 ancora aperto (Malen 8.84) | S |
| C6 | Committare `data/*.db-wal`/`-shm` in `.gitignore` | Untracked in `git status` | XS |

## 5. INTEGRAZIONI

| # | Intervento | Perché | Sforzo |
|---|---|---|---|
| I1 | **Fallback storico per `fantamedia`**: se manca la stagione corrente, usare `player_season_stats` dell'ultima stagione con presenze > soglia, marcando il dato come `stimato` | **Sblocca il 57% dei giocatori non classificabili.** È il singolo intervento a maggior impatto | M |
| I2 | Popolare `stats_season`/`stats_competition` negli scraper | Rende operativo TASK-008, oggi inerte | M |
| I3 | Gerarchia portieri esplicita da fonte (1°/2°/3°) | `goalkeepers.py` lo documenta come non disponibile e ripiega su score; è la ragione per cui un quarto portiere può risultare titolare | M |
| I4 | `player_set_pieces` (rigoristi, punizioni, corner) | Il metodo lo tratta come discriminante; oggi pesa 0 | M |
| I5 | `player_advanced_stats` (xG/xA) | Senza, il modello §24 non è implementabile | L |
| I6 | `player_injuries` + `player_anagrafica` | Rischio disponibilità e minutaggio previsto | M |

## 6. MIGLIORAMENTI

| # | Intervento | Perché | Sforzo |
|---|---|---|---|
| M1 | **Riscrivere la derivazione di `price_auction`**: normalizzare ogni fonte sulla propria scala (percentile o z-score) *prima* di mediare, mai valori grezzi | Causa radice di 18.733 vs 4.000. Il fattore fisso 12.5 non può funzionare su scale che differiscono di 10× | **L** |
| M2 | **Vincolo di conservazione del budget**: la somma dei prezzi dei top `LEAGUE_TEAMS × 25` giocatori deve tendere a `LEAGUE_TEAMS × TOTAL_CREDITS` (4.000) | Trasforma "il prezzo è plausibile?" in un test automatico, non in un giudizio a occhio | M |
| M3 | Test di regressione sulle invarianti: nessun prezzo pari al clamp; somma prezzi ≈ 4.000; ogni squadra Serie A ha ≥1 portiere rankabile | Tutti e tre i sintomi di questo audit sarebbero stati intercettati prima dell'uso | M |
| M4 | Fino a M1, **usare `price_listino` come prezzo di riferimento** in UI e ottimizzatore, e nascondere `price_auction` | Rimedio immediato: il listino è già in scala corretta | **S** |
| M5 | Badge esplicito `misurato` / `stimato` / `assente` su ogni cella derivata | TASK-029 esiste ma non copre il fallback di I1 | S |
| M6 | Dichiarare in UI quali fattori del modello §24 sono attivi | Oggi la dashboard lascia intendere un modello xG-based che non gira | S |
| M7 | Tarare `ROLE_BUDGET_PCT` (6/16/32/46) su 8 squadre | A 8 squadre solo 200 giocatori su 802 vengono acquistati: il livello di sostituzione è molto più alto che a 10-12 squadre, quindi pagare i top conviene *di più* e la panchina costa *meno*. La ripartizione attuale non tiene conto della dimensione lega — `LEAGUE_TEAMS` è dichiarato "non consumato da nessun modulo" in `config.py` | M |

---

## 7. Ordine di esecuzione consigliato

L'asta è imminente: la priorità non è la correttezza teorica, è **avere numeri usabili**.

**Subito (rimedio, ore)**
1. **M4** — passare a `price_listino` ovunque. Da solo rende la Rosa Ideale sensata.
2. **C2** — togliere Estero/Serie Minori dai pool.

**Prima dell'asta (giorni)**
3. **I1** — fallback storico fantamedia. Sblocca 57% dei giocatori e risolve il caso Mandas.
4. **C1** — normalizzazione squadre. Risolve la seconda causa della depth chart portieri.
5. **C5** — validazione range fantamedia.

**Dopo l'asta (settimane)**
6. **M1 + M2 + M3** — ricostruzione del motore prezzi con invarianti testate.
7. **I2 → I4 → I5 → I6** — colmare le tabelle vuote, in quest'ordine di rapporto valore/sforzo.
8. **M7** — taratura sulla lega a 8.

---

## 8. Nota di metodo

Questo audit è partito con ricerche web sui listoni pubblici e con domande all'utente sulle
regole di lega. Entrambe le cose erano sbagliate:

- le regole erano già in `config.py` (`TOTAL_CREDITS`, `LEAGUE_TEAMS`, `ROLE_SLOTS`);
- i dati erano già in `data/fantacalcio.db`, più affidabili di qualunque estrazione web;
- le quotazioni raccolte via web erano internamente incoerenti (scale diverse fra fetch,
  liste "top 10" non ordinate, nomi storpiati) e non andavano riportate come fatti.

`claude.md` §3 e §19 lo prescrivono già: *"Se un'informazione manca, cercarla nel progetto
prima di inventarla"*, *"Non fare ricerche web se la risposta è già chiaramente presente nel
progetto"*. Vale la pena rileggerle prima del prossimo intervento.
