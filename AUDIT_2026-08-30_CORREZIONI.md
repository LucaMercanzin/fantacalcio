# Correzioni all'audit + implementazione — 30/08/2026 (sera)

Questo documento fa due cose: **corregge** parti sbagliate di
`AUDIT_DATI_2026-08-30.md` (scritte leggendo tabelle SQL grezze invece della
pipeline applicativa vera) e riporta **cosa è stato effettivamente
implementato**, verificato con la test suite reale (450/450 passati).

Convenzione `claude.md`: FATTO (verificato nel codice/DB), IPOTESI, CONCLUSIONE.

---

## 1. Perché l'audit precedente andava corretto

`claude.md` §5/§17 impone di verificare la causa reale nel codice che gira
davvero prima di modificarlo. L'audit di stamattina non l'ha fatto fino in
fondo: ha interrogato `player_consensus` e `quotations` con SQL scritto ad
hoc, non le funzioni che l'app usa davvero (`dashboard/data_access.py`,
`consensus/engine.py`, `ranking/scorer.py`). Eseguendo quelle funzioni sul
DB reale sono emerse differenze sostanziali.

## 2. "57% giocatori senza fantamedia" — FALSO, corretto

**Claim originale (sbagliato):** 458/802 giocatori (57%) hanno
`player_consensus.fantamedia` NULL o 0, quindi non classificabili.

**FATTO, verificato ora sulla pipeline live** (`get_ranked_role` +
`get_insufficient_data_players` per ruolo):

| ruolo | ranked | di cui `estimated` | insufficient_data |
|---|---:|---:|---:|
| P | 32 | 17 (53%) | 0 |
| D | 144 | 50 (35%) | 1 |
| C | 155 | 56 (36%) | 0 |
| A | 74 | 30 (41%) | 1 |

**CONCLUSIONE:** esiste già un meccanismo di fallback prezzo→fantamedia
stimata (`ranking/scorer.py: estimate_fantamedia`, TASK-011b — mappa il
prezzo di un giocatore sul percentile di prezzo del ruolo e gli assegna la
fantamedia di un giocatore reale allo stesso percentile), che copre già la
stragrande maggioranza dei casi. L'"insufficiente" reale è ~0-1 giocatore su
ruolo, non 458. L'audit originale confondeva "colonna vuota nella tabella
grezza" con "il giocatore non è classificabile nell'app" — sono cose
diverse, perché `player_consensus` è uno snapshot materializzato di un run
precedente (TASK-013), non l'input dello scoring in tempo reale.

**Cosa NON è cambiato:** questa parte era già a posto. Non ho toccato
`estimate_fantamedia`/`enrich_scores`.

## 3. Il caso Lazio — causa vera diversa da quella scritta stamattina

**Causa scritta stamattina (parzialmente sbagliata):**
"`ranking/goalkeepers.py:38` scarta chi ha `score is None`, e lo score è
`None` per mancanza di fantamedia."

**Causa vera, verificata eseguendo `build_goalkeeper_depth_chart` sul DB
reale:** Mandas e Motta non arrivano nemmeno alla fase di scoring. Vengono
scartati prima, dal filtro in `dashboard/data_access.py:_compute_ranked_role`
(righe 194-200 prima della modifica):

```python
and (
    (r.get("appearances") is not None and r["appearances"] >= RELIABLE_APPEARANCES_MIN)  # >=15
    or (
        r.get("appearances") is None
        and (r.get("fantamedia") is not None or r.get("avg_rating") is not None)
    )
)
```

`RELIABLE_APPEARANCES_MIN = 15`. Questo filtro accetta **o** presenze note
≥15 **o** presenze del tutto sconosciute con un segnale — ma scarta chi ha
presenze note ma basse. Mandas ha 0 presenze 2025/26 (era in prestito),
Motta ne ha 14 (una sotto soglia). Nessuno dei due passa il filtro, quindi
**nessuno dei due arriva a `rank_players`**, e la Lazio sparisce del tutto
dalla depth chart — non "un solo portiere identificabile", proprio zero,
come confermato riproducendo il bug:

```
warnings: ['Cagliari','Fiorentina','Inter','Milan','Monza','Napoli','Roma','Sassuolo']
missing: []   # Lazio non appare nemmeno come "missing" perché build_goalkeeper_depth_chart
              # veniva chiamato in questo test senza expected_teams
```

Con `expected_teams` (come nella vera pagina Streamlit, `dashboard/
components.py:render_goalkeeper_depth_chart`), Lazio finiva in `missing`,
esattamente il messaggio segnalato dall'utente.

**Verificato anche:** una volta che un portiere supera questo filtro, lo
`score = None` gate di `compute_goalkeeper_score` (mancanza fantamedia) è
già coperto dallo stesso `estimate_fantamedia` della sez. 2 — **nessuna
modifica allo scoring necessaria**. Il problema era solo il filtro di
esclusione a monte.

Perché quel filtro esiste ed è giusto altrove: su una pagina ruolo con
centinaia di alternative (D/C/A), nascondere le chiare riserve (bassa
presenza nota) evita di intasare la lista. Su portieri, dove una squadra ne
ha 2-5 in tutto, non c'è "affollamento" da evitare — e il filtro cancella
esattamente il portiere che una depth chart deve mostrare di più: chi è
appena stato promosso titolare o rientra da un prestito, il cui conteggio
presenze dell'anno scorso non dice nulla sul ruolo di quest'anno.

## 4. Fix implementato — VERIFICATO

**File modificati:**

- `dashboard/data_access.py`
  - `_compute_ranked_role`: nuovo parametro `require_reliable_appearances: bool = True`
    (default invariato per ogni altro chiamante — nessuna regressione sulle pagine ruolo generiche).
  - Nuova funzione `get_goalkeeper_pool(conn)`: stessa pipeline di
    `get_ranked_role(conn, "P")` ma con `require_reliable_appearances=False`,
    usata **solo** dalla depth chart portieri.
- `dashboard/components.py`: `render_goalkeeper_depth_chart` ora chiama
  `get_goalkeeper_pool(conn)` invece di `get_ranked_role(conn, "P")`.
- `ranking/goalkeepers.py`: docstring aggiornate (descrivevano la vecchia fonte dati).
- `tests/test_data_access.py`: nuovo test
  `test_get_goalkeeper_pool_includes_keepers_get_ranked_role_excludes`,
  replica lo scenario Lazio reale (portiere a 0 presenze + portiere a 14
  presenze, entrambi senza fantamedia) e verifica che `get_goalkeeper_pool`
  li includa mentre `get_ranked_role` continua a escluderli.

**VERIFICATO** (non solo "implementato" — eseguito):

```
python -m pytest tests/ -q
450 passed, 5 deselected
```

Riproduzione end-to-end sul DB reale, prima/dopo:

| | prima | dopo |
|---|---|---|
| squadre con 0 portieri identificabili | Lazio | **0** |
| squadre con solo 1 portiere identificabile | 8 (Cagliari, Fiorentina, Inter, Milan, Monza, Napoli, Roma, Sassuolo) | **0** |
| squadre totali con titolare+riserva | 19/20 | **20/20** |

**Limite residuo, dichiarato non nascosto (claude.md §16):** l'ordine
titolare/riserva dentro ogni squadra resta quello documentato in
`giocatori/portieri.md` §7 (presenze come priorità, punteggio come
tie-break). All'inizio di una nuova stagione, per una squadra la cui
gerarchia portieri è appena cambiata, questo produce un ordine sbagliato:
per la Lazio il risultato attuale è **Motta titolare, Furlanetto riserva**
(entrambi ora almeno visibili — prima nessuno dei due lo era), mentre il
titolare reale è Mandas. La causa: nessuno scraper di questo progetto
cattura una gerarchia esplicita da fonte (`portieri.md` Priorità 1) né un
indicatore "titolare/ballottaggio" (verificato: `quotations.status` è NULL
su tutte le 3.509 righe) — `ranking/goalkeepers.py` lo dichiarava già
onestamente nel proprio docstring prima di questa modifica. Non ho inventato
un euristica sostitutiva (es. usare il prezzo come proxy) perché non è
prevista dalla spec (`portieri.md` §7) e altererebbe un comportamento già
deliberato altrove senza una fonte dati reale a supporto — serve un nuovo
scraper di gerarchia esplicita (I3 dell'audit originale, sforzo M, non
implementato oggi).

## 5. Price engine (M1/M4 dell'audit originale) — non toccato, per scelta

Ho verificato **dal vivo** (non sulla tabella statica) che il problema è
reale: `get_ranked_role(conn, "A")` restituisce `price_current=500.00`
(il tetto esatto, `AUCTION_CANONICAL_CEILING = TOTAL_CREDITS`) per **4
attaccanti diversi** (Hojlund, Malen, Lautaro, Ramos Gonçalo). La causa non è
quella scritta stamattina ("fattore di conversione naive 12.5") — quel
problema (TASK-019/TASK-022) risulta già affrontato nel codice. La causa
verificata ora è più sottile: `compute_source_scale_factors`
(`consensus/engine.py`) ancora ogni fonte al proprio **99° percentile**,
assumendo che quel percentile debba mappare sul tetto (500). Ma con ~500+
giocatori per fonte, il 99° percentile corrisponde a ~5 giocatori, non al
più caro in assoluto — quindi ogni fonte ha per costruzione un pugno di
nomi (i veri top player) il cui prezzo, dopo il riscalamento, sfora il
tetto e viene tagliato a 500 dal clamp già esistente (commento in
`consensus/engine.py:42-77`, che documenta il clamp come intenzionale e
riferisce un caso precedente simile, TASK-022).

Il risultato pratico: i 4-5 giocatori più costosi del gioco diventano
**indistinguibili tra loro** (tutti "500"), proprio dove differenziare
conta di più. Non è un valore assurdo isolato come i "696 crediti" che
TASK-022 aveva corretto — è un problema più fine, di perdita di
informazione nella coda della distribuzione.

**Perché non l'ho corretto oggi:** a differenza del bug portieri (causa
univoca, fix a basso rischio, isolato a una pagina), qui esistono più
soluzioni valide con trade-off reali (percentile più alto vs rank-transform
vs preservare l'ordine pre-clamp per il solo display) e il clamp attuale è
una scelta deliberata e già testata (TASK-022), non una svista. Toccarlo
senza una decisione esplicita rischierebbe di contraddire un compromesso
già scelto consapevolmente da chi ha costruito il motore prezzi.
`claude.md` §21 chiede di confrontare le soluzioni prima di sceglierne una,
non di riscrivere un motore di pricing condiviso da otto pagine
dell'app sulla base di un'assunzione non verificata con l'utente.

**Se vuoi che lo risolva**, le opzioni concrete sono:
- **A (minima):** alzare l'ancora da p99 a un percentile più alto (es. p99.7)
  calibrato sul DB reale — riduce quanti giocatori saturano, non elimina il
  fenomeno.
- **B (strutturale):** sostituire il riscalamento lineare per-fonte con un
  rank-transform sull'intera popolazione del ruolo (converte il percentile
  di prezzo in credito, non il valore grezzo) — elimina il fenomeno alla
  radice, ma è una riscrittura di `consensus/engine.py` che tocca 8+ punti
  di consumo (`price_engine.py`, `auction_intelligence.py`,
  `lp_optimizer.py`, `ideal_squad.py`...) e richiede nuovi test di
  regressione mirati prima di essere considerata sicura.

## 6. Normalizzazione squadre (C1 dell'audit originale) — già gestita, non serve intervento

**FATTO, verificato leggendo il codice (non ipotizzato):** `players.team`
contiene davvero varianti come `ATALANTA`/`Atalanta`/`CAG`/`Cagliari`, ma
`matching/player_matcher.normalize_team()` (troncamento a 3 lettere +
alias map da `team_aliases`) e `dashboard/data_access.normalize_team_name()`
+ `TEAM_CODE_TO_FULL` già collassano tutte le varianti sullo stesso codice/
nome canonico ovunque l'app le consuma (`_enrich_role_rows`,
`is_current_serie_a_team`, la depth chart portieri stessa). La riga C1
dell'audit originale ("ogni club è spaccato in due bucket") era dedotta
dalla tabella grezza e non si verifica nell'output reale dell'app —
**ritirata**. `team_aliases` con 11 righe basta perché copre solo i casi in
cui il troncamento a 3 lettere sbaglia (prefissi come "AC"/"AS"/"ACF"), non
ogni possibile variante di casing (quelle le gestisce già la normalizzazione
lowercase+regex a monte).

## 7. Riepilogo onesto

| Voce audit originale | Esito |
|---|---|
| Lazio senza portieri | **Corretto e verificato** (causa reale diversa da quella scritta stamattina) |
| 8 squadre con un solo portiere | **Corretto dallo stesso fix** |
| Ordine titolare/riserva Lazio | **Non corretto** — limite dichiarato, serve nuovo scraper di gerarchia |
| "57% dati insufficienti" | **Ritrattato** — errore di misurazione, la realtà è ~0-1 per ruolo |
| Prezzi d'asta saturi a 500 | **Confermato dal vivo**, non corretto — richiede una decisione di design (sez. 5) |
| Normalizzazione squadre (C1) | **Ritrattato** — già gestita dal codice esistente |
| Tabelle vuote (xG, piazzati, infortuni) | Invariato, confermato: restano vuote, nessuna azione oggi |
