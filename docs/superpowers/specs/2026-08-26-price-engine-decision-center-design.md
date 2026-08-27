# Price Engine, Scarcity, Replacement Level, Marginal Squad Value, Decision Center (Gruppo A) + scraper fantanalisi/squadre (Gruppo B)

Data: 2026-08-26

## 0. Contesto

`impossibile-analisi-avanzata.md` bollava come "impossibile" un intero blocco di
funzionalità (sez. 3-9, 16, 19), ma la motivazione data ("richiede xG/xA/event/
tracking data, storico multi-stagione, architettura a microservizi") vale solo per
una parte di quel blocco (Heatmap reale, Trend Detection/Player Archetypes
multi-stagione, Fixture Difficulty a calendario). Price Engine, Scarcity,
Replacement Level, Marginal Squad Value e Decision Center sono calcolabili oggi
con score/prezzo/budget già in database — erano finiti nello stesso bucket solo
perché il documento originale li presentava insieme.

`https://www.fantanalisi.it/squadre` (non ancora scrappata: esiste solo
`scrapers/fantanalisi.py` per `/giocatori`) espone dati Understat reali per
squadra (xG, xGA, PPDA) e un confronto prezzo asta vs "equo" — sblocca un
secondo gruppo di funzionalità, circoscritto (niente calendario partite, quindi
niente vera Fixture Difficulty).

Restano fuori scope, confermati impossibili: MLOps/backtesting/model registry,
nomination/pressure in tempo reale, Fixture Difficulty a calendario, heatmap
reale, trend detection/archetipi multi-stagione.

## 1. Price Engine — `ranking/price_engine.py` (nuovo)

```
fair_price = score / mediana_value_for_money_del_ruolo * 10
```

Interpretazione: il prezzo a cui questo giocatore renderebbe quanto un
giocatore "medio" del ruolo per credito speso (la mediana di
`value_for_money` tra i giocatori disponibili del ruolo, già calcolata da
`ranking/scorer.py`).

```
max_price = fair_price * (1 + SCARCITY_PREMIUM_MAX * scarcity/100
                             + REPLACEMENT_PREMIUM_MAX * replacement_advantage_norm)
```

- `SCARCITY_PREMIUM_MAX = 0.25`: scarsità massima (100) → fino a +25% sopra il fair price.
- `REPLACEMENT_PREMIUM_MAX = 0.15`: `replacement_advantage_norm` = `replacement_advantage`
  normalizzato (clamp 0-1, scala /20 punti score — un vantaggio di 20+ punti sul
  miglior alternativo è già "molto meglio delle alternative").
- Recommended range: `[fair_price * 0.95, max_price]`.
- Status: `BUY` se `price_current <= max_price`, `PASS` se
  `price_current > max_price * 1.05`, altrimenti `BORDERLINE`.

Questi coefficienti sono scelte esplicite e documentate nel codice (non
derivate da un fit sui dati, che richiederebbe uno storico che non abbiamo) —
punto di partenza ragionevole, regolabile in futuro.

## 2. Scarcity Score — `ranking/scarcity.py` (nuovo)

```
comparabili = [alt for alt in disponibili_ruolo
               if alt.decision_score >= player.decision_score * 0.9]  # esclude se stesso
scarcity = round(100 * exp(-len(comparabili) / 4), 1)
```

0 alternative comparabili → 100. 4 alternative → ~37. 8 → ~14. Decadimento
esponenziale invece di una soglia lineare arbitraria: ogni alternativa in più
pesa via via meno (la differenza tra 0 e 1 alternativa conta molto di più
della differenza tra 10 e 11).

## 3. Replacement Level / Advantage — `ranking/replacement.py` (nuovo)

```
replacement_level = max(score dei disponibili del ruolo, esclso il giocatore)
replacement_advantage = player.score - replacement_level
```

Semplificazione dichiarata: "migliore alternativa" = il più alto Fantasy
Value tra gli altri disponibili nel ruolo, senza filtrare per prezzo/budget
(la spec originale parlava di "realisticamente acquistabile" — versione più
sofisticata rimandabile a un secondo giro se il segnale si rivela troppo
grezzo).

## 4. Marginal Squad Value — estende `ranking/purchase_advisor.py`

```python
def compute_marginal_squad_value(player, slot, roster_role_scores) -> float:
    fantasy_value = player.get("score") or 0.0
    if slot["remaining"] > 0 or not roster_role_scores:
        return round(fantasy_value, 1)
    weakest_owned = min(roster_role_scores)
    return round(max(0.0, fantasy_value - weakest_owned), 1)
```

Stesso confronto già usato dentro `evaluate_purchase` (righe ~50-65) per il
verdetto "inutile_hai_di_meglio", ma esposto come numero riusabile altrove
(Decision Center), non solo dentro il flusso di valutazione prezzo-ipotetico.

## 5. Decision Center — `dashboard/data_access.get_decision_center` + `dashboard/components.render_decision_center`

Per ogni ruolo, tra i candidati **disponibili e affrontabili col budget
residuo** (stessa base di `get_squad_suggestions`), calcola fair/max
price, scarcity, replacement_advantage, marginal_value e li assegna a un
bucket, il migliore per bucket (fino a `limit` per bucket, default 3):

- **EVITA**: già in tier `DA_EVITARE` (`ranking/tiers.classify_role`).
- **BUY**: `price_current <= max_price` e `marginal_squad_value > 0`.
- **DIFFERENZIALE**: `value_for_money_percentile >= 80` e `price_current` sotto
  la mediana prezzi del ruolo, escludendo chi è già in tier `TOP` (altrimenti
  non sarebbe una scoperta, sarebbe ovvio). **Approssimazione dichiarata**: la
  spec originale definisce un differenziale anche per "bassa popolarità", dato
  che non abbiamo (nessuna fonte ci dà tassi di acquisto nella lega/community) —
  usiamo solo qualità/prezzo, non popolarità.
- **ATTENDI**: `max_price < price_current <= max_price * 1.15` (vicino al
  limite, potenzialmente comprabile se il prezzo scende o cambia la situazione).

Ordinati per `decision_score` dentro ogni bucket. Sezione visualizzata come
expander in cima a "La Mia Rosa", con motivazione breve per ogni voce
(riusa lo stile già presente in `evaluate_purchase.reasons`).

## 6. Scraper `scrapers/fantanalisi_squadre.py` (nuovo) + tabella `team_strength`

Stesso pattern di `scrapers/fantanalisi.py` (Playwright sync,
`BaseScraper`-style). Da `https://www.fantanalisi.it/squadre`: per ogni
squadra (20, matching per nome — molto più semplice del matching giocatori
già risolto altrove nel progetto) estrae `xg`, `xga`, `ppda` (valori
aggregati per squadra mostrati sulla pagina, non serie temporali).

Nuova tabella:

```sql
CREATE TABLE IF NOT EXISTS team_strength (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    xg REAL,
    xga REAL,
    ppda REAL,
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    UNIQUE(team, source, scrape_date)
);
```

Storicizzata come le quotazioni (una riga per scrape, non overwrite), coerente
col principio "nessun dato importante va sovrascritto" del progetto.

**Uso**: esposta come fattore informativo nella scheda squadra/giocatore
("Attacco Understat: xG 1.8/partita, 3° in Serie A" / "Difesa concede 1.4 xGA/
partita, 15° in Serie A") — **non** entra nel calcolo di `score`/Fantasy Value
esistente in questa iterazione: cambiare una formula già in produzione e
validata (1000 aste simulate, calibrazione confermata) sulla base di un solo
numero aggregato per squadra è un rischio che non ha senso correre senza
prima vedere il dato reale una volta scrappato.

**Fuori scope esplicito** (rimandato): titolarità tattica per-giocatore,
rigoristi/punizioni/corner da fantanalisi, cross-check prezzo "equo" vs aste
live — richiedono di scrappare anche le sotto-sezioni per giocatore della
pagina squadra e fare matching nome-giocatore su una terza fonte; valutabile
in un secondo giro una volta verificato che lo scraper base (solo dati
squadra) sia stabile.

## 7. Ordine di esecuzione

1. Gruppo A: `price_engine.py`, `scarcity.py`, `replacement.py`, estensione
   `purchase_advisor.py`, `get_decision_center` + UI, test unitari, verifica
   nel browser.
2. Gruppo B: schema `team_strength`, scraper, verifica contro il sito reale,
   integrazione minimale in UI (sola visualizzazione), test.
