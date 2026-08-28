# Project Review

> Audit eseguito il 2026-08-28 su `main` @ `1e80aa8`, contro il codice reale e il database reale
> (`data/fantacalcio.db`, 803 giocatori, 9.327 quotazioni, scrape unico del 2026-08-26).
> Ogni finding marcato **CONFIRMED** è stato riprodotto eseguendo il codice del progetto: i comandi
> di riproduzione sono riportati nel finding. **LIKELY** = evidenza forte ma non eseguita.
> **POSSIBLE** = va verificato prima di agire.

---

## Executive Summary

### La domanda che conta

> **Posso fidarmi dei risultati prodotti da questo sistema?**

**No. Non allo stato attuale.** Il sistema è internamente coerente, ben testato (300 test verdi) e
ben documentato, ma **il dato su cui poggia tutto — `price_current` — è la media pesata di cinque
scale di prezzo diverse e incompatibili**. Da lì in poi ogni metrica derivata (Value for Money,
Decision Score, Price Engine, tier, Scarcity, Auction Intelligence, LP optimizer) è
matematicamente corretta e **semanticamente priva di significato**.

La prova più diretta: il solver LP, richiesto di costruire la rosa ottimale da 500 crediti,
restituisce questa (riprodotto, non ipotizzato):

```
P: Audero (1.03 cr), Di Gregorio, Milinkovic-Savic
D: Pavlovic, Spinazzola, Kempf, Obrador, Hermoso, Scalvini, Rensch, Zappacosta
C: Da Cunha, Mandragora, Rodriguez J., Ekkelenkamp, Modric, Perrone, Messias, Bernabé
A: Lauriente, Esposito S., Soulé, Leao, Bonny, Giovane
Costo 499.66 / 500 — status "optimal"
```

**Zero top player.** Niente Lautaro, Dimarco, Calhanoglu, Nico Paz, McTominay, Thuram. Nessun
fantallenatore firmerebbe questa rosa. Il solver non ha sbagliato i conti: ha risolto
correttamente **il problema sbagliato, su dati sbagliati**. Ed essendo etichettata "ottimo
matematico", è esattamente il tipo di risultato che sembra autorevole e non lo è.

### Cosa funziona davvero bene

Non è una lista di cortesia — questi sono punti di qualità reale e vanno **conservati**:

1. **La separazione dei layer è pulita e rispettata.** `scrapers/` → `matching/` → `pipeline/` →
   `db/repository.py` → `dashboard/data_access.py` → `dashboard/pages/`. Le pagine Streamlit sono
   di 6 righe l'una; nessuna query SQL nella UI; nessun `sqlite3` importato fuori da `db/`. È
   un'architettura migliore della media dei progetti di questa dimensione.
2. **Le funzioni di ranking sono pure e testabili.** `ranking/*.py` non tocca il DB: prende dict,
   restituisce numeri. Questo è ciò che rende *possibile* correggere i bug qui sotto senza
   riscrivere il progetto.
3. **La guardia di ambiguità nel matcher (`AMBIGUITY_MARGIN` + `_initials_conflict`) è una
   soluzione corretta a un problema reale** (Martinez L. vs Martinez Jo.), ed è la ragione per cui
   il DB **non ha duplicati di identità** (verificato: 0 collisioni su 803 giocatori). Va estesa,
   non rifatta.
4. **La cache invalidata da fingerprint del dato (`get_data_version`) invece che da TTL cieco** è
   la scelta giusta, e i commenti spiegano *perché*. Manca solo di coprire tre tabelle.
5. **La distinzione fra fonti "listino" e fonti "aste reali" (`REAL_PRICE_SOURCES`) è
   concettualmente corretta.** Il problema non è l'idea: è che una volta separate, le due famiglie
   vengono comunque mediate insieme sulla stessa colonna.
6. **La documentazione dei limiti (`impossibile-*.md`) è onesta e matura.** Molti progetti fingono
   di poter fare backtesting; questo dichiara che non può.

### Cosa è fragile

- **L'identità del giocatore è una stringa derivata**, non un ID stabile. Se una fonte cade, il
  nome canonico può cambiare e il giocatore diventa una riga nuova, orfana del proprio storico.
- **Il pipeline non è idempotente**: nel DB attuale **ogni quotazione esiste 3 volte** (verificato).
- **Non c'è transazione di run**: un crash a metà scraping lascia un dataset parziale che il
  sistema tratta come "l'ultimo dato buono".
- **I test testano l'implementazione, non il dominio.** 300 test verdi mentre il portiere di
  riserva del Como è il portiere #1 del gioco.

### I problemi che falsano i risultati (in ordine di gravità)

| # | Problema | Effetto osservato |
|---|---|---|
| 1 | 5 scale di prezzo mediate in un campo solo | Audero costa 1.03, Dimarco 94.88. Rapporto 92× puramente artificiale |
| 2 | `fantamedia` → fallback `avg_rating` | Audero (riserva, senza fantamedia) è il portiere #1 davanti a Svilar e Carnesecchi |
| 3 | `fantamedia = 0.0` come sentinella di "dato mancante" | 202 giocatori, fra cui Kolo Muani, Gonçalo Ramos, Mancini, Molina, marcati "🚫 Da evitare" |
| 4 | Presenze/fantamedia senza chiave stagione né campionato | Le presenze di Vicario al Tottenham entrano nel ranking Serie A |
| 5 | Universo squadre hardcoded e sbagliato | 3 club di Serie B dentro (Frosinone, Monza, Venezia), 3 di Serie A fuori |
| 6 | `confidence` bassa **riduce** la penalità di rischio | Un giocatore su cui le fonti litigano prende +12 di Decision Score |
| 7 | LP massimizza la somma di 25 score | Ottimizza la panchina come i titolari; nessun vincolo di formazione schierabile |
| 8 | `status` è NULL al 100% | Tutta la logica infortunati/squalificati è codice morto, ma documentata come attiva |

### Le specifiche avevano già previsto quattro di questi difetti

L'analisi dei documenti di requisito (`giocatori/portieri.md`, `giocatori/movimento.md`,
`giocatori/rosa-ideale.md`, `statistiche giocatore`) ha prodotto il risultato più netto dell'audit:
**quattro dei problemi trovati leggendo il codice erano già stati previsti e vietati per iscritto.**

| La spec dice | Il codice fa |
|---|---|
| *"Non deve essere scelto semplicemente in base al rating fantacalcio."* (portieri §8) | Ordina i portieri per rating → Audero titolare del Como |
| *"Non assegnare automaticamente un punteggio basso solamente perché non esiste uno storico Serie A."* (movimento §22) | 202 giocatori a `fantamedia = 0.0` → "Da evitare" |
| *"evitando di usare esclusivamente il nome"* per l'identità (portieri §15) | Chiave = due stringhe di display |
| *"Non sostituire dati validi con `null`... UI mostra ultimo dato valido"* (statistiche §40) | Uno scraper caduto fa sparire il giocatore |

Più due difetti strutturali emersi solo dal confronto con le spec: il modello di valore doveva
essere **moltiplicativo** (`profilo × titolarità × minutaggio`, movimento §21) ed è additivo con la
titolarità che pesa 5 punti su 70; e **i trasferimenti creano righe duplicate** invece di aggiornare
la squadra (confermato in DB: `Bleve Marco` esiste come Lecce *e* come Serie Minori), mentre le spec
richiedono un report `ADDED/REMOVED/TRANSFERRED/UNCHANGED` che non esiste.

Dettaglio completo nella sezione **Spec vs Implementation**.

### Giudizio sintetico

Il progetto **non va buttato né riscritto**. L'architettura regge. Ma **il livello "dati e
metriche" va rifondato**, e in particolare va rifiutata l'idea che esista un solo campo
`price_current` confrontabile fra fonti. Finché quella colonna resta com'è, ogni feature costruita
sopra — per quanto elegante — produce numeri plausibili e falsi.

Stima: **Fase 1+2 (correttezza e integrità dati) sono ~2/3 del valore dell'intero piano.** Tutto il
resto è secondario finché quelle non sono chiuse.

---

## Critical Findings

| ID | Priorità | Area | Problema | Impatto | File |
|----|----------|------|----------|---------|------|
| P0-001 | P0 | Consensus / Dati | `price_current` media 5 fonti su 5 scale diverse (1-40, 1-83, 1-93, 1-142, 1-382) | Ogni metrica prezzo-dipendente è priva di significato | `dashboard/data_access.py:99,137-186` |
| P0-002 | P0 | Metriche | `compute_score` fa fallback da `fantamedia` a `avg_rating`, scale incompatibili | Chi non ha fantamedia viene sistematicamente promosso; riserve davanti a titolari | `ranking/scorer.py:40-52` |
| P0-003 | P0 | Dati | `fantamedia = 0.0` usata come sentinella di dato mancante (202 giocatori) | Giocatori reali di Serie A finiscono in "🚫 Da evitare" | `scrapers/fantacalciopedia.py:41-46` |
| P0-004 | P0 | Dati / Leakage | `appearances`/`fantamedia` senza chiave stagione né campionato | Statistiche estere e di stagioni diverse mischiate nel ranking Serie A | `db/schema.sql:11-22`, `pipeline/run_scraping.py` |
| P0-005 | P0 | Optimizer | LP massimizza la somma degli score di 25 giocatori | Rosa "ottima" senza nessun top player; obiettivo scorrelato dai punti fantacalcio | `ranking/lp_optimizer.py:62-66` |
| P0-006 | P0 | Config / Dati | Universo squadre hardcoded, stagione sbagliata | 3 club di Serie B acquistabili, 3 di Serie A invisibili | `dashboard/data_access.py:13-35`, `scrapers/pianetafanta.py:6-10` |
| P0-007 | P0 | Identità / DB | Chiave giocatore = stringa derivata (`max(name, key=len)`) | Se una fonte cade, il giocatore diventa una riga nuova e perde lo storico | `pipeline/run_scraping.py:17-32`, `matching/player_matcher.py:104-113` |
| P0-008 | P0 | Dati / Metriche | `status` è NULL su 9.327/9.327 righe | Tutta la logica infortuni/squalifiche è morta ma documentata come viva | tutti gli scraper, `ranking/scorer.py:5` |
| P1-001 | P1 | Metriche | `decision_score`: bassa `confidence` **riduce** la penalità di rischio | Chi ha fonti discordanti prende un bonus (+12 pt misurati) | `ranking/scorer.py:157` |
| P1-002 | P1 | Consensus | `confidence` misura accordo sui prezzi, ma è usata come fattore di rischio | ≈0 proprio sui giocatori migliori (scale miste) | `data_access.py:189-207`, `scorer.py:127-157` |
| P1-003 | P1 | Coerenza | Fantasy Value diverso fra pagina ruolo e scheda giocatore | 138/146 difensori mostrano due numeri diversi | `dashboard/data_access.py:454-464` |
| P1-004 | P1 | Coerenza | Price Engine e Auction Intelligence danno "prezzo massimo" contraddittori | Dimarco: max 33.2 (PASS) e max_bid 94.9 nella stessa scheda | `ranking/price_engine.py`, `ranking/auction_intelligence.py` |
| P1-005 | P1 | Dati | `role_mantra` contiene lettere di ruolo classico, non codici Mantra | 3 moduli (tactical_profile, correlation, auction_checklist) computano su una tassonomia inesistente | `scrapers/pianetafanta.py:31`, `ranking/tactical_profile.py:23-35` |
| P1-006 | P1 | Consensus | `appearances`/`status` presi dalla prima fonte non-NULL, senza consenso | Input chiave dello score deciso da un ordine SQL non deterministico | `dashboard/data_access.py:238-241` |
| P1-007 | P1 | Pipeline | `role_classic` deciso da `first.role_classic` | Fonti discordanti sul ruolo risolte a caso, senza log | `pipeline/run_scraping.py:20` |
| P1-008 | P1 | Metriche | `replacement_advantage` ≤ 0 per tutti tranne il #1 del ruolo | Il premio "replacement" è matematicamente morto | `ranking/replacement.py:15-24` |
| P1-009 | P1 | Metriche | `scarcity` ≈ 0 per tutti (decay 4 su ruoli da 150) | Il premio "scarsità" è morto; verificato `max_price == fair_price` ovunque | `ranking/scarcity.py:22-30` |
| P1-010 | P1 | Asta | `compute_dynamic_max_bid` consiglia offerte superiori al budget disponibile | budget 10, 10 slot → consiglia 30 | `ranking/auction_intelligence.py:117` |
| P1-011 | P1 | Asta | Giocatore senza prezzo → `alternatives_remaining = 0` → "Scarsità critica / BUY NOW" | Consiglio d'acquisto aggressivo su dato mancante | `dashboard/data_access.py:776-781` |
| P1-012 | P1 | Budget | Nessuna riserva di crediti per gli slot ancora vuoti | Il sistema può suggerire di spendere tutto e restare con 0 per 20 slot | `dashboard/data_access.py:587`, `ranking/budget.py` |
| P1-013 | P1 | Optimizer | Giocatore in rosa assente da `players_by_role` → rosa da 26 e costo sottostimato | Accade sempre: i filtri scartano ~50% dei giocatori | `ranking/lp_optimizer.py:68-98` |
| P1-014 | P1 | Metriche | `compute_ideal_score` somma grandezze che si contengono a vicenda | Fantasy Value contato 3 volte; punto neutro della forma sbagliato | `ranking/ideal_squad.py:19-94` |
| P1-015 | P1 | Dashboard | Confronto "Rosa Ideale vs LP" su insiemi di dimensione diversa (18 vs 25) | Il grafico dimostra solo che 25 > 18 | `dashboard/pages/5_La_Mia_Rosa.py:257-270` |
| P1-016 | P1 | Pipeline / DB | `insert_quotation` non idempotente; nessun UNIQUE | Nel DB attuale ogni quotazione è **triplicata** | `db/repository.py:30-40`, `db/schema.sql:11-22` |
| P1-017 | P1 | Dashboard / DB | Impossibile rimuovere un giocatore da `my_roster`; `add_opponent_pick` crasha sui duplicati | Un errore di battitura durante l'asta è irreversibile | `db/repository.py:134-181` |
| P1-018 | P1 | Scraper / Test | Il selettore Mantra di `fantacalcio_it` funziona sulla fixture e non in produzione | Test verde su dato che in produzione è sempre `None` | `scrapers/fantacalcio_it.py:25-26` |
| P1-019 | P1 | Cache | `get_data_version` non copre season_stats / set_pieces / players | Ranking servito stale dopo uno scrape di quei dati | `db/repository.py:464-483` |
| P2-001 | P2 | Config | `fantacalcio_it` ha `weight = 0` | Chi ha solo quella fonte per il prezzo ottiene `price_current = None` | `db/schema.sql:81` |
| P2-002 | P2 | Ranking | I tier hanno nomi assoluti ma soglie percentili | Il 15% peggiore di ogni ruolo è sempre "Da evitare", per costruzione | `ranking/tiers.py:102` |
| P2-003 | P2 | Ranking | Giocatore senza tier → 3 stelle "Titolare affidabile" | Default ottimistico su assenza di informazione | `ranking/verdict.py:47` |
| P2-004 | P2 | Metriche | `_percentile_rank` non restituisce mai 100; docstring errata | Off-by-one sistematico su tutti i percentili | `ranking/scorer.py:185-193` |
| P2-005 | P2 | Metriche | `compute_role_comparison` media solo su chi ha il dato | Survivorship bias su gol/assist | `ranking/role_comparison.py:37-46` |
| P2-006 | P2 | Metriche | `UNPROVEN_PENALTY` irraggiungibile (soglia 5 < filtro 15) | Codice morto documentato come attivo | `ranking/scorer.py:13-14` |
| P2-007 | P2 | Performance | N+1 su `get_player_notes`, fuori dalla cache | 156 statement per pagina ruolo, 448 per Decision Center, a ogni rerun | `dashboard/data_access.py:352-353` |
| P2-008 | P2 | Asta | Due definizioni di inflazione nella stessa funzione | Rapporto-di-medie vs media-di-rapporti danno numeri diversi | `ranking/auction_intelligence.py:44-73` |
| P2-009 | P2 | Pipeline | Nessuna transazione di run; commit per riga | Un crash a metà run produce un dataset parziale trattato come valido | `pipeline/run_scraping.py`, `db/repository.py` |
| P2-010 | P2 | Pipeline | Uno scraper che fallisce fa sparire silenziosamente i giocatori sotto `MIN_SOURCES_REQUIRED` | Perdita di dati senza alcun segnale in UI | `pipeline/run_scraping.py:11-16` |
| P2-011 | P2 | Scraper | `float(...)` non protetto in `fantacalcio_it.parse_html` | Una cella vuota uccide l'intera fonte | `scrapers/fantacalcio_it.py:38-39` |
| P2-012 | P2 | Dati | Recency decay e storico prezzi inerti (un solo `scrape_date`) | Feature documentate ma senza dati | `data_access.py:96-109`, `repository.py:291-304` |
| P2-013 | P2 | Consensus | `_detect_outliers` non può mai scattare su `fantamedia`/`avg_rating` | Nessun controllo outlier sulle statistiche | `dashboard/data_access.py:112-131` |
| P2-014 | P2 | DB | 4 tabelle di `schema.sql` assenti dal DB committato | Ogni entry point che salta `init_db` crasha | `data/fantacalcio.db`, `db/connection.py` |
| P2-015 | P2 | Repo | `.gitignore` esclude il DB, ma il DB è tracciato; README dice l'opposto | 43 MB di foto + DB riscritto a ogni run nella history | `.gitignore`, `README.md:68` |
| P2-016 | P2 | Matching | `_initials_conflict` non applicato in `match_name_to_player*` | I due matcher più permissivi sono anche i meno protetti | `matching/player_matcher.py:125-185` |
| P2-017 | P2 | Matching | Pareggi a 100 via `partial_ratio` bypassano la guardia di ambiguità | `"Martinez"` + Inter → restituisce Lautaro, silenziosamente | `matching/player_matcher.py:153` |
| P2-018 | P2 | Matching | Il grouping dipende dall'ordine di arrivo dei record | Risultati non riproducibili se cambia l'ordine degli scraper | `matching/player_matcher.py:47-101` |
| P2-019 | P2 | Matching | `normalize_team` = primi 3 caratteri | `"Hellas Verona"` ≠ `"Verona"`, `"AC Milan"` ≠ `"Milan"` | `matching/player_matcher.py:15-19` |
| P0-009 | P0 | Dati / Spec | Dataset pre-mercato (26/08) mentre le spec impongono lo scraping definitivo a mercato chiuso | Rose non definitive: acquisti mancanti, ceduti ancora presenti | `giocatori/portieri.md:22-31`, `giocatori/movimento.md:723-756` |
| P0-010 | P0 | Dati / Spec | I trasferimenti creano righe duplicate invece di aggiornare la squadra | Confermato in DB: `Bleve Marco` esiste come Lecce **e** Serie Minori | `pipeline/run_scraping.py`, `db/repository.py:5-27` |
| P1-020 | P1 | Metriche / Spec | Fantasy Value additivo dove `movimento.md:685-702` impone `profilo × titolarità × minutaggio` | La titolarità vale 5 punti su ~70: di fatto non incide | `ranking/scorer.py:52` |
| P1-021 | P1 | Ranking / Spec | `portieri.md:187-189` vieta di ordinare i portieri per rating; il codice fa esattamente questo | Depth chart con la gerarchia sbagliata (Audero titolare del Como) | `ranking/goalkeepers.py:1-20` |
| P1-022 | P1 | Metriche / Spec | `movimento.md:719-721` vieta di penalizzare chi non ha storico Serie A; il codice lo fa | Kolo Muani/Ramos in "Da evitare" — il caso che la spec nomina | `ranking/scorer.py:40-52` |
| P2-020 | P2 | Dati | Dati scrapati e mai usati nello scoring: `xg`/`xga`/`ppda`, `goals_conceded`, `punteggio_fcp`, `predicted_appearances` | Il modello portieri richiesto da `rosa-ideale.md:88-125` è già alimentabile e non lo è | `dashboard/components.py:1234-1240`, `dashboard/data_access.py:262` |
| P2-021 | P2 | Pipeline / Spec | `statistiche giocatore:1081-1097` impone "UI mostra ultimo dato valido"; il codice fa sparire il giocatore | Uno scraper caduto cancella giocatori dalla dashboard, senza segnale | `pipeline/run_scraping.py:11-16`, `dashboard/data_access.py:315` |
| P2-022 | P2 | Logging / Spec | `statistiche giocatore:1057-1079` impone log per URL/status/tempo/record estratti | Nessuna diagnostica: un fallimento parziale è invisibile | `pipeline/run_scraping.py`, `scrapers/base.py` |
| P2-023 | P2 | Metriche | `NEUTRAL_TACTICAL_PROFILE = 30` unico per D e C, sotto la mediana di entrambe | Nudge medio sempre positivo e asimmetrico (−0.5/+4.0), non ±7 come dichiarato | `ranking/scorer.py:27-28,54-57` |
| P2-024 | P2 | Metriche | `ROLE_MANTRA_BASE` appiattisce una scala per-reparto della spec in una scala globale | Un "+++++" difensore (45) vale meno di un "+++++" centrocampista (55) | `ranking/tactical_profile.py:23-35` |

---

## Detailed Findings

### [P0-001] `price_current` è la media di cinque scale di prezzo incompatibili

**Area:** Consensus engine / Data pipeline
**File:** `dashboard/data_access.py` (righe 84-99, 137-186), `db/schema.sql` (16)
**Funzione:** `_price_rows`, `_weighted_average`, `_merge_player_rows`
**Stato:** **CONFIRMED**

**Problema**

Le sei fonti pubblicano numeri che si chiamano tutti "prezzo" ma vivono su scale diverse.
Misurato sul DB reale:

| Fonte | n | min | media | max | Che cosa è realmente |
|---|---|---|---|---|---|
| `fantacalcio_it` | 1485 | 1.0 | 7.02 | **36** | Listino classico, scala 1-40 |
| `fantapazz` | 1682 | 1.0 | 16.64 | **83** | Listino, scala propria |
| `pianetafanta` | 1542 | 1.1 | 19.97 | **93** | Listino, scala propria |
| `fantacalcio_online` | 645 | 0.88 | 22.25 | **142** | Crediti reali, lega 8 squadre / 500 |
| `fantanalisi` | 1359 | 1.0 | 21.64 | **382** | Crediti reali "aste live", altro formato |

`AVERAGED_FIELDS` include `price_current`, e `_weighted_average` ne fa una media pesata. Il
risultato non è un prezzo: è la combinazione lineare di cinque unità di misura diverse.

**Perché è un problema**

Peggio della semplice imprecisione: **quale scala vince dipende da quali fonti coprono quel
giocatore**. `_price_rows` usa le fonti "reali" solo se ce ne sono ≥2 (`MIN_REAL_PRICE_SOURCES`),
altrimenti ricade sul listino. Quindi due giocatori dello stesso ruolo, nella stessa pagina,
possono avere prezzi su due scale diverse — senza alcuna indicazione.

**Esempio concreto** (dal DB, verificato)

```
Dimarco (D, Inter)   fc_it 31 | fc_online 55.12 | fantanalisi 146 | fantapazz 41 | pianeta 42.3
  → 2 fonti reali → consensus = (55.12*45 + 146*35)/80 = 94.88

Audero (P, Como)     fc_online 13.09 | fantapazz 1.0 | pianeta 1.1
  → 1 sola fonte reale → fallback listino = (1.0*10 + 1.1*5)/15 = 1.03
```

**1.03 contro 94.88.** Un fattore 92× che non riflette nessun mercato: riflette solo il fatto che
fantanalisi ha coperto Dimarco e non Audero.

**Impatto**

Contamina, in cascata:
`compute_value_for_money` → `value_for_money_percentile` → `compute_decision_score` →
`classify_role` (tier `BASSO_PREZZO`) → `compute_scarcity` → `compute_price_recommendation`
(fair/max/BUY-PASS) → `get_decision_center` → `build_optimal_squad` → `build_ideal_squad` →
`compute_price_inflation` → `compute_dynamic_max_bid`.

Cioè: **ogni singola raccomandazione d'acquisto del prodotto.**

Misurato: Audero `value_for_money = 132.9`; Svilar (titolare Roma, 38 presenze) `9.0`. Il sistema
dichiara Audero **15× più conveniente** del portiere titolare della Roma.

**Riproduzione**

```bash
python - <<'EOF'
import sqlite3
c = sqlite3.connect('data/fantacalcio.db')
for r in c.execute("SELECT source, COUNT(price_current), ROUND(MIN(price_current),2), "
                   "ROUND(AVG(price_current),2), ROUND(MAX(price_current),2) "
                   "FROM quotations WHERE price_current IS NOT NULL GROUP BY source"):
    print(r)
EOF
```

**Soluzione proposta**

Non normalizzare "al volo": **separare i concetti a livello di schema**, perché sono due
grandezze diverse che rispondono a due domande diverse.

1. Aggiungere a `quotations` una colonna `price_scale TEXT NOT NULL` con valori
   `'listino'` (fantacalcio_it, fantapazz, pianetafanta, fantacalciopedia) e
   `'auction_500'` (fantacalcio_online, fantanalisi). Popolata dallo scraper, non inferita.
2. In `_merge_player_rows` produrre **due campi distinti**:
   - `price_listino` — consenso pesato delle sole fonti `listino`, riscalato in **1-40** (la scala
     canonica del fantacalcio classico);
   - `price_auction` — consenso pesato delle sole fonti `auction_500`, in crediti su 500.
   Mai mediarli fra loro.
3. Normalizzare ogni fonte alla propria scala canonica prima di mediare, con un fattore
   `scale_factor` per fonte calcolato **dai dati** (`40 / percentile_99(price_current)` per il
   listino, `500 / somma_attesa` per le aste), salvato in `sources` e ricalcolato a ogni run — non
   una costante hardcoded.
4. `price_current` diventa un alias di `price_auction` con fallback su
   `price_listino * (500/40) * fattore_lega`, **e il fallback va marcato**: aggiungere
   `price_basis TEXT` (`'auction'` / `'listino_converted'`) alla riga merged, ed esporlo in UI
   ("prezzo stimato da listino") così l'utente sa quando sta guardando una conversione.

**Rischio della soluzione**

Alto ma inevitabile: cambia i numeri di tutta l'app. Tutti gli assert numerici nei test vanno
riscritti. **Va fatto per primo**, perché ogni altra correzione su metriche/optimizer è inutile
finché l'input è questo. Mitigazione: introdurre `price_listino`/`price_auction` **accanto** a
`price_current` in un primo commit, verificare le due distribuzioni su Monitoraggio, e solo poi
spostare i consumatori.

---

### [P0-002] Il fallback `fantamedia` → `avg_rating` confronta due scale diverse

**Area:** Metriche
**File:** `ranking/scorer.py` (righe 40-52)
**Funzione:** `compute_score`
**Stato:** **CONFIRMED**

**Problema**

```python
base = row.get("fantamedia")
if base is None:
    base = row.get("avg_rating")
if base is None:
    base = 0.0
score = base * 10 + reliability * 5 - penalty
```

`fantamedia` (voto + bonus/malus) e `avg_rating` (media voto secca) non sono la stessa grandezza.
Per un attaccante differiscono di 1.5-2 punti; **per un portiere `fantamedia < avg_rating`**,
perché i gol subiti sono un malus.

**Perché è un problema**

Il fallback non degrada: **inverte**. Un giocatore *senza* fantamedia viene valutato su una scala
sistematicamente più alta di uno che ce l'ha. E poiché `reliability * 5` vale al massimo 5 punti
(= 0.5 di fantamedia), lo score è di fatto `fantamedia * 10`: nient'altro conta.

**Esempio concreto** (verificato, ranking portieri reale)

```
#1  AUDERO Emil        fm=None  ar=6.20  → score 66.5   (riserva del Como)
#3  Carnesecchi Marco  fm=5.58  ar=6.36  → score 60.7   (titolare Atalanta, 37 pres.)
#5  Svilar Mile        fm=5.45  ar=6.26  → score 59.5   (titolare Roma, 38 pres.)
```

Audero ha una media voto *inferiore* a Carnesecchi (6.20 vs 6.36) e **finisce davanti a lui**,
solo perché non ha fantamedia e viene valutato su un'altra scala.

**Impatto**

Il ranking portieri è invertito ai vertici. Su 32 portieri sopravvissuti ai filtri, chiunque non
abbia fantamedia (fonte Fantacalciopedia mancante) scavalca i titolari. La stessa distorsione
colpisce ogni ruolo, ma sui portieri è massima perché lo scarto fm/ar è massimo.

**Soluzione proposta**

Eliminare il fallback cross-scala. Due opzioni, in ordine di preferenza:

1. **Preferita:** se `fantamedia` manca, `compute_score` non deve inventare una base — deve
   restituire `None` e il giocatore va marcato `insufficient_data` in UI, escluso dai ranking
   e dall'optimizer ma visibile in una sezione "dati incompleti". Onestà > copertura.
2. Se serve comunque un numero: convertire `avg_rating` in una fantamedia stimata **per ruolo**,
   con un offset calibrato sui giocatori che hanno entrambi i valori nel DB
   (`offset[ruolo] = median(fantamedia - avg_rating)` sui ~250 giocatori con entrambi), e marcare
   la riga `fantamedia_estimated = True`. Mai mescolare stimate e misurate senza etichetta.

**Rischio della soluzione**

Opzione 1 riduce la popolazione rankata (oggi 407 giocatori, scenderebbe di ~80). È il
comportamento corretto, ma va comunicato: aggiungere in Monitoraggio un contatore
"giocatori esclusi per dati insufficienti".

---

### [P0-003] `fantamedia = 0.0` è una sentinella di dato mancante trattata come misura reale

**Area:** Data quality
**File:** `scrapers/fantacalciopedia.py` (righe 41-46)
**Funzione:** `parse_html`
**Stato:** **CONFIRMED**

**Problema**

Fantacalciopedia mostra `F.MEDIA 0` per i giocatori che non hanno una fantamedia di Serie A
(neoarrivati dall'estero). Lo scraper fa `float("0")` → `0.0` e lo salva come valore.

**Esempio concreto** (dal DB, verificato — 202 giocatori)

```
RAMOS Goncalo Matias   A  fantamedia=0.0  appearances=30   (Milan, ex PSG)
Kolo Muani Randal      A  fantamedia=0.0  appearances=30   (Juventus, ex PSG)
Vicario Guglielmo      P  fantamedia=0.0  appearances=31   (ex Tottenham)
Mancini Gianluca       D  fantamedia=0.0  appearances=16
Molina Nahuel          D  fantamedia=0.0  appearances=26
Mastantuono Franco     C  fantamedia=0.0  appearances=23
```

**Perché è un problema**

`0.0` non è `None`. Passa il filtro `fantamedia is not None`, entra nella media pesata del
consensus, entra in `compute_score` come `base = 0.0` → `score ≈ 5`, entra nelle medie di ruolo di
`compute_role_comparison`, e finisce nel tier `DA_EVITARE` perché `decision_pct <= 15`.

**Impatto**

Verificato in `get_decision_center`: il bucket "🔴 Evita" contiene giocatori con score 3.9-4.9,
cioè esattamente questi. Il sistema **sconsiglia attivamente** Kolo Muani e Gonçalo Ramos.
Questo è il caso peggiore: non un numero mancante, ma un **consiglio sbagliato con la stessa
confidenza di uno giusto**.

**Soluzione proposta**

1. In `scrapers/fantacalciopedia.py`, trattare `0` come assenza:
   `fantamedia = value if value > 0 else None`. Stessa cosa per `avg_rating` altrove.
   Aggiungere il vincolo a livello DB: `CHECK (fantamedia IS NULL OR fantamedia > 0)`.
2. Aggiungere una **validazione di dominio nel pipeline**, prima della scrittura: una fantamedia
   di Serie A vive fra ~2.0 e ~9.5. Fuori da quella finestra → `None` + `logger.warning` con
   nome, fonte e valore. Vale anche per il limite superiore (vedi P0-004: Malen a 8.84).
3. Combinare con P0-002: senza fantamedia il giocatore non viene rankato, viene mostrato come
   "dati insufficienti".

**Rischio della soluzione**

Basso. Sposta ~200 giocatori da "valutati male" a "non valutati", che è la rappresentazione
corretta.

---

### [P0-004] Statistiche senza chiave di stagione né di campionato

**Area:** Data model / Leakage
**File:** `db/schema.sql` (11-22), `pipeline/run_scraping.py`, `scrapers/fantacalciopedia.py`
**Stato:** **CONFIRMED**

**Problema**

`quotations` ha `scrape_date` (quando l'ho letto) ma **non ha `season`** (a quale stagione si
riferisce il dato). `fantamedia`, `avg_rating` e `appearances` sono statistiche storiche: senza
chiave di stagione non sono interpretabili.

**Perché è un problema**

Tre effetti, tutti confermati:

1. **Contaminazione fra campionati.** Le `appearances` di Vicario (31) e Molina (26) sono di
   Premier/Liga, non di Serie A. Entrano nel filtro `RELIABLE_APPEARANCES_MIN >= 15` e nel calcolo
   di `reliability` come se fossero presenze di Serie A.
2. **Fantamedia implausibili non rilevabili.** Malen Donyell risulta `fantamedia = 8.84` su 19
   presenze — il valore più alto del DB, superiore a qualunque fantamedia reale di Serie A. Non è
   verificabile *perché non si sa di che stagione e campionato sia*. (**LIKELY** contaminazione
   estera: Malen arriva dal Dortmund.) Risultato: **è l'attaccante #1 del ranking**, davanti a
   Lautaro Martinez.
3. **Impossibile rispondere a "cosa sapeva il sistema il giorno X".** `scrape_date` dice quando è
   stato letto, non a cosa si riferisce. Con `player_season_stats` che copre 2016/17→2025/26 e
   `get_all_latest_player_season_stats` che prende semplicemente `ORDER BY season DESC`, un
   giocatore fermo dal 2023 contribuisce con dati di tre anni fa allo stesso titolo di uno attuale.

**Impatto**

Look-ahead vero e proprio non ce n'è (non esiste backtesting), ma c'è **contaminazione
retrospettiva**: dati non comparabili trattati come comparabili, e nessun modo di accorgersene.

**Soluzione proposta**

1. `ALTER TABLE quotations ADD COLUMN stats_season TEXT` e
   `ALTER TABLE quotations ADD COLUMN stats_competition TEXT DEFAULT 'serie_a'`. Popolate dallo
   scraper, `NULL` se la fonte non lo dichiara (e in quel caso il dato **non entra nel consensus
   statistico**: è la scelta onesta, non una perdita).
2. `_weighted_average` per i campi statistici deve filtrare su
   `stats_season == season_corrente_configurata` e `stats_competition == 'serie_a'`.
   La stagione corrente va in configurazione (vedi P0-006), non hardcoded.
3. In `get_all_latest_player_season_stats`, scartare le stagioni più vecchie di N (2) rispetto
   alla corrente, invece di prendere ciecamente la più recente disponibile.
4. Aggiungere a Monitoraggio un pannello "copertura dati": per ogni fonte, quanti giocatori hanno
   statistiche della stagione corrente vs. di stagioni precedenti vs. nessuna.

**Rischio della soluzione**

Medio. Richiede di sapere cosa pubblica ogni fonte — verificabile solo aprendo le pagine reali.
Dove non è determinabile, `NULL` ed esclusione: preferibile a un'assunzione.

---

### [P0-005] Il solver LP ottimizza la funzione obiettivo sbagliata

**Area:** Optimizer
**File:** `ranking/lp_optimizer.py` (righe 62-81)
**Funzione:** `build_optimal_squad`
**Stato:** **CONFIRMED**

**Problema**

```python
problem += pulp.lpSum(variables[pid] * (p.get("score") or 0) for ...)   # obiettivo
problem += pulp.lpSum(variables[pid] for p in candidates) == slots_to_fill
problem += pulp.lpSum(variables[pid] * p["price_current"] for ...) <= budget
```

L'obiettivo è **la somma dei Fantasy Value di tutti e 25 i giocatori**. Ma nel fantacalcio se ne
schierano 11. Il terzo portiere e l'ottavo difensore contribuiscono all'obiettivo esattamente
quanto il titolare.

**Perché è un problema**

Tre difetti indipendenti, tutti nella stessa formulazione:

1. **Obiettivo scorrelato dal risultato.** Massimizzare la somma di 25 score massimizza la *media
   della rosa*, non i punti attesi. La strategia ottima reale del fantacalcio è polarizzata: pochi
   fuoriclasse + riempitivi da 1 credito. Il modello attuale premia esattamente l'opposto —
   distribuisce il budget uniformemente.
2. **`score ≈ fantamedia * 10` non è comparabile fra ruoli.** La fantamedia media di un attaccante
   è ~1.5 punti sopra quella di un portiere, per costruzione del regolamento. Sommandoli si
   introduce un bias strutturale a favore degli attaccanti nell'allocazione del budget.
3. **Nessun vincolo di formazione schierabile.** Niente garantisce che i 25 selezionati possano
   comporre un 3-4-3. E nessun vincolo di max giocatori per squadra: il solver può prendere 6
   giocatori del Como (e infatti ne prende 4).

**Esempio concreto** (riprodotto)

```python
da.get_optimal_squad_lp(conn, mode="from_scratch")
# → status "optimal", costo 499.66/500, 25 giocatori
# → nessuno dei top-5 di nessun ruolo
# → Audero (1.03 cr) titolare, 4 giocatori del Como
```

Con i prezzi di P0-001 il solver **seleziona sistematicamente contro** i giocatori coperti da due
fonti reali — cioè contro i più noti e meglio documentati — perché sono gli unici a comparire sulla
scala 500.

**Impatto**

La feature più autorevole del prodotto ("ottimo matematico garantito") è quella che sbaglia di
più, e lo fa con la massima confidenza.

**Soluzione proposta**

Correggere P0-001 **prima**. Poi, in ordine:

1. **Obiettivo pesato per probabilità di essere schierato.** Sostituire `score` con
   `expected_points = score * P(titolare)`, dove `P(titolare)` è già approssimabile con
   `min(appearances, 38)/38`. È una modifica di due righe che risolve il difetto concettuale
   principale senza introdurre nessuna astrazione.
2. **Normalizzare lo score per ruolo** prima di sommarlo:
   `score_norm = (score - media_ruolo) / std_ruolo`. Rende i termini commensurabili e toglie il
   bias attaccanti.
3. **Vincolo max giocatori per squadra**: `<= 3` per club. Una riga di `lpSum`, e riflette un
   rischio reale (una squadra che crolla affonda mezza rosa).
4. **Vincolo di formazione schierabile**: già garantito da 3-8-8-6, ma va aggiunto un vincolo di
   *qualità minima sui titolari* — es. i migliori 1/3/4/3 per ruolo devono sommare almeno X. In
   alternativa, più semplice: **due obiettivi in sequenza** (prima massimizza gli 11 titolari,
   poi riempi la panchina col residuo). Preferire questa: è più vicina a come si ragiona in asta.
5. Correggere il conteggio slot (vedi P1-013).

**Rischio della soluzione**

Medio. I punti 1-3 sono ~20 righe totali. Il punto 4 va discusso prima di implementarlo: è una
scelta di prodotto, non un bug.

---

### [P0-006] L'universo delle squadre è hardcoded, in due posti, e sbagliato

**Area:** Configurazione / Data quality
**File:** `dashboard/data_access.py` (10-35), `scrapers/pianetafanta.py` (6-10)
**Stato:** **CONFIRMED**

**Problema**

```python
# dashboard/data_access.py
TEAM_ABBREV_TO_FULL = {..., "FRO": "Frosinone", "MON": "Monza", "VEN": "Venezia", ...}
VALID_SERIE_A_TEAM_CODES = {normalize_team(t) for t in TEAM_ABBREV_TO_FULL.values()}
PROMOTED_TEAMS = {"VEN", "Venezia", "FRO", "Frosinone", "MON", "Monza"}

# scrapers/pianetafanta.py
TEAMS = ["ATALANTA", ..., "FROSINONE", ..., "MONZA", ..., "VENEZIA"]
```

Le 20 squadre elencate **non sono le 20 squadre di Serie A**. Il DB conferma: 31 giocatori del
Frosinone, 27 del Monza, 38 del Venezia — tutte squadre di Serie B. Mancano completamente
Cremonese, Pisa e Hellas Verona.

Il resto del dataset è invece coerente con la stagione corrente (Kolo Muani alla Juventus, Rabiot
al Milan, Højlund al Napoli, Sassuolo presente): la lista squadre è **stale rispetto ai dati che
il progetto sta effettivamente scaricando**.

**Perché è un problema**

`is_current_serie_a_team` è un *filtro di sicurezza* pensato per escludere chi non è più in Serie
A ("Estero", "Serie Minori"). Essendo hardcoded e obsoleto, fa il contrario: **autorizza** 96
giocatori di Serie B come acquistabili e **scarta** tre club interi di Serie A. E `PROMOTED_TEAMS`
marca "neopromossa" tre squadre retrocesse.

**Impatto**

- Il solver LP può (e lo fa) mettere in rosa giocatori di Serie B.
- Il depth chart portieri mostra sezioni per squadre inesistenti in A e ne omette tre reali.
- 32 portieri per 20 squadre: metà dei club non ha nemmeno la coppia titolare/riserva richiesta
  da `giocatori/portieri.md`.

**Riproduzione**

```bash
python -c "import sqlite3;c=sqlite3.connect('data/fantacalcio.db');\
print(c.execute('SELECT team,COUNT(*) FROM players GROUP BY team ORDER BY 2 DESC').fetchall())"
```

**Soluzione proposta**

Non aggiornare la costante: **eliminare la costante**.

1. Nuova tabella:
   ```sql
   CREATE TABLE IF NOT EXISTS teams (
       code TEXT PRIMARY KEY,          -- normalize_team()
       full_name TEXT NOT NULL,
       season TEXT NOT NULL,
       is_promoted INTEGER NOT NULL DEFAULT 0,
       UNIQUE(full_name, season)
   );
   ```
2. Popolata da uno scraper (la classifica/lista squadre di una qualsiasi fonte già usata), non a
   mano. `season` in configurazione, un solo posto.
3. `is_current_serie_a_team`, `normalize_team_name`, `PROMOTED_TEAMS` leggono da lì.
4. `scrapers/pianetafanta.py` itera sulla tabella invece che sulla lista hardcoded.
5. **Guardia di sanità nel pipeline**: se le squadre trovate non sono esattamente 20, o se
   differiscono da `teams` per più di 3 club, il run **fallisce con errore** invece di scrivere.
   È il controllo che avrebbe intercettato questo problema mesi fa.

**Rischio della soluzione**

Basso, alto valore. Attenzione: dopo la correzione i giocatori di Frosinone/Monza/Venezia
spariranno e la copertura calerà finché non si scrapa Cremonese/Pisa/Verona. È il comportamento
corretto.

---

### [P0-007] L'identità del giocatore è una stringa derivata, non un ID stabile

**Area:** Architettura / Persistenza
**File:** `pipeline/run_scraping.py` (17-32), `matching/player_matcher.py` (104-113),
`db/repository.py` (5-27)
**Stato:** **CONFIRMED** (per lettura del codice; lo scenario di rottura è **LIKELY**)

**Problema**

```python
# player_matcher.match_records
best_name = max((r.name for r in plain_records), key=len)
best_team = max((r.team for r in plain_records), key=len)
display_groups[(best_name, best_team)] = plain_records

# repository.upsert_player
SELECT id FROM players WHERE canonical_name = ? AND team = ?
```

La chiave primaria logica di un giocatore è **la stringa più lunga fra quelle proposte dalle fonti
che quel giorno hanno risposto**.

**Perché è un problema**

`run_pipeline` cattura le eccezioni di ogni scraper e prosegue:

```python
except Exception as exc:
    logger.error("Scraper %s failed: %s", ...)
```

Se la fonte che forniva il nome più lungo cade, `best_name` cambia. `upsert_player` non trova la
riga, **ne inserisce una nuova**, e tutto lo storico (quotazioni, `fcp_metrics`, `player_notes`,
`player_source_matches` con i `review_status` confermati a mano, `my_roster`) resta agganciato
all'ID vecchio, che diventa un orfano.

La stessa fragilità vale per `team`: nel DB convivono `"Inter"`, `"INTER"` e `"INT"` come team di
giocatori diversi, in funzione di quali fonti li hanno coperti. Il `UNIQUE(canonical_name, team)`
non protegge da questo — lo *codifica*.

**Esempio concreto**

Fantacalciopedia (che fornisce nomi lunghi, `.title()`) va in timeout un giorno. `"Martinez
Lautaro"` diventa `"Martinez L."` (fantacalcio_it). Nuovo `player_id`. L'utente ritrova le proprie
note sparite e il giocatore duplicato nel ranking.

**Impatto**

Rende il sistema **non riproducibile**: lo stesso input in un ordine diverso, o con una fonte in
meno, produce un grafo di identità diverso. È anche la ragione per cui la coda di revisione dei
match (feature ben pensata) può perdere silenziosamente le decisioni umane.

**Soluzione proposta**

Introdurre un'identità stabile e indipendente dal display:

1. Nuova colonna `players.identity_key TEXT UNIQUE`, calcolata come
   `normalize_name(name) + "|" + team_code` — cioè con le **stesse** funzioni di normalizzazione
   già usate dal matcher, non con la stringa di display. `canonical_name`/`team` restano, ma
   diventano puramente decorativi.
2. `upsert_player` cerca su `identity_key`, non su `(canonical_name, team)`.
3. Migrazione una tantum in `_migrate()`: calcolare `identity_key` per le righe esistenti e
   fondere eventuali duplicati (oggi: 0 collisioni, quindi la migrazione è sicura — verificato).
4. `canonical_name` scelto in modo deterministico e stabile (es. sempre dalla fonte con
   `weight_stats` più alto fra quelle presenti, con fallback ordinato), non con `max(key=len)`.
5. **Guardia**: se un run crea più di N nuovi giocatori rispetto al precedente (es. >5%),
   fermarsi con errore. È quasi sempre sintomo di una fonte caduta, non di 40 acquisti veri.

**Rischio della soluzione**

Medio-basso oggi (0 duplicati da fondere), cresce col tempo. Da fare presto.

---

### [P0-008] `status` è NULL al 100%: tutta la logica indisponibilità è codice morto

**Area:** Dati / Metriche
**File:** tutti gli scraper (`status=None`), `ranking/scorer.py` (5,48,90),
`ranking/tiers.py` (50,102), `ranking/ideal_squad.py` (26-30,162), `ranking/verdict.py` (56)
**Stato:** **CONFIRMED**

**Problema**

```bash
sqlite> SELECT status, COUNT(*) FROM quotations GROUP BY status;
None|9327
```

**Nessuno dei sei scraper popola `status`.** Tutti passano `status=None`.

**Perché è un problema**

Non è "una feature non ancora implementata": è **una feature documentata come funzionante**.

- `compute_score`: `penalty = 15 if status in PENALIZED_STATUSES` → mai.
  Docstring: *"penalized when currently unavailable"*. Falso.
- `compute_risk`: `status_penalty = 40` → mai.
- `classify_role`: il primo ramo di `DA_EVITARE` è `status in PENALIZED_STATUSES` → mai.
  `TIER_DESCRIPTIONS[DA_EVITARE]`: *"Indisponibili (infortunio/squalifica)..."*. Falso.
- `build_ideal_squad`: `unavailable_in_roster` è sempre vuoto. La UI mostra "nessun indisponibile"
  come se fosse un'informazione.
- `compute_verdict`: il rischio "Attualmente infortunato" non compare mai.

Peggio: `player_injuries` ha **0 righe** e `player_match_ratings` ha **0 righe**. Quindi
`get_recent_form` torna sempre vuoto e `get_injury_summary` sempre zero — mentre l'interfaccia
presenta quelle sezioni come dati.

**Impatto**

Il sistema **non sa se un giocatore è infortunato** e non lo dice. Un utente che vede "Nessun
rischio particolare rilevato dai dati disponibili" ragionevolmente conclude che il giocatore stia
bene. È una falsa rassicurazione generata dall'assenza di dati.

**Soluzione proposta**

Due interventi, entrambi necessari:

1. **Onestà immediata (poche righe, alto valore).** Ovunque una sezione dipenda da una tabella
   vuota, distinguere "nessun problema" da "nessun dato": `verdict` deve dire *"Stato di
   disponibilità non disponibile: verifica manualmente"*, non *"Nessun rischio rilevato"*. Idem
   per forma recente e infortuni. Aggiungere in Monitoraggio una riga per tabella con conteggio e
   ultimo aggiornamento, così l'assenza di dati è visibile invece che invisibile.
2. **Popolare `status`.** `pipeline/run_injuries.py` e `scrapers/transfermarkt.py` esistono già e
   non sono mai stati eseguiti in produzione (0 righe). Farli girare nello `scheduled_run` e
   derivare `status` da `player_injuries` con `date_to` nel futuro o nullo. In alternativa, la
   maggior parte delle fonti listino espone un'icona di indisponibilità: va verificato sull'HTML
   reale prima di assumere che ci sia.

**Rischio della soluzione**

Il punto 1 è a rischio zero e va fatto subito. Il punto 2 richiede verifica sulle fonti reali.

---

### [P1-001] `decision_score`: una bassa confidenza **riduce** la penalità di rischio

**Area:** Metriche
**File:** `ranking/scorer.py` (127-157)
**Funzione:** `compute_decision_score`
**Stato:** **CONFIRMED**

**Problema**

```python
conf_factor = (confidence if confidence is not None else 50.0) / 100
return round(fantasy_value + value_adjustment - risk * 0.2 * conf_factor, 1)
```

`conf_factor` moltiplica la **penalità**. Confidenza bassa → penalità bassa → punteggio alto.

**Perché è un problema**

È l'inverso della semantica corretta. L'incertezza sui dati di un giocatore è una ragione per
fidarsi *meno* di lui, non per penalizzarlo *meno*. Il commento della funzione non menziona
nemmeno il termine di confidenza: è l'unico pezzo non giustificato di una funzione altrimenti
ampiamente documentata.

**Esempio concreto** (riprodotto)

```python
compute_decision_score(fantasy_value=70, vfm_pct=50, risk=60, confidence=0)   # → 70.0
compute_decision_score(fantasy_value=70, vfm_pct=50, risk=60, confidence=100) # → 58.0
```

**12 punti di vantaggio** a chi ha le fonti in totale disaccordo.

E non è un caso limite: per P0-001 la confidenza è ≈0 proprio sui giocatori migliori.
Misurato: Carnesecchi `confidence 0.0`, Svilar `0.0`, Malen `6.2`, Lautaro `13.0`. Cioè **quasi
tutti i top player girano con la penalità di rischio praticamente azzerata**.

**Soluzione proposta**

Invertire, e separare i due concetti:

```python
# l'incertezza AUMENTA il rischio effettivo, non lo sconta
uncertainty = 1 - (confidence if confidence is not None else 50.0) / 100
effective_risk = risk * (1 + UNCERTAINTY_RISK_WEIGHT * uncertainty)
return round(fantasy_value + value_adjustment - effective_risk * RISK_WEIGHT, 1)
```

con `UNCERTAINTY_RISK_WEIGHT = 0.5` e `RISK_WEIGHT = 0.2` (valori dichiarati, non derivati — da
documentare come tali). Va fatto **dopo** P1-002, perché oggi `confidence` non misura ciò che il
nome suggerisce.

**Rischio della soluzione**

Basso in codice, ma riordina i ranking. Da fare insieme a P0-001/P1-002 in un unico commit
verificato.

---

### [P1-002] `confidence` misura l'accordo sui prezzi ma viene usata come fattore di rischio

**Area:** Consensus
**File:** `dashboard/data_access.py` (189-207, 244), `ranking/scorer.py` (127-157)
**Stato:** **CONFIRMED**

**Problema**

`_consensus_confidence` riceve solo `price_values_by_source`: è **l'accordo delle fonti sul
prezzo**. Poi viaggia sulla riga come `confidence` generica e finisce in `compute_decision_score`
come misura di affidabilità complessiva del giocatore.

Sono tre cose diverse, tutte chiamate "confidenza" nel progetto:

1. accordo delle fonti sul prezzo (`_consensus_confidence`);
2. confidenza del match fuzzy nome↔nome (`player_source_matches.confidence`);
3. quanta fiducia dare alla valutazione del giocatore (quella che `decision_score` vorrebbe).

**Perché è un problema**

Oltre all'omonimia, la formula stessa è fragile:

```python
spread = (max(values) - min(values)) / mean
agreement = max(0.0, 1 - spread)
```

Con scale miste (P0-001) lo spread supera 1 quasi sempre → `agreement = 0`. Misurato:
Carnesecchi con **6 fonti** ottiene `confidence = 0.0`, mentre Audero con **3 fonti** ottiene
`67.9` — perché le sue 2 fonti listino sono quasi identiche fra loro. **Più fonti = meno
confidenza**, esattamente al contrario dell'intento dichiarato nella docstring.

Inoltre `max - min` è una statistica non robusta: un solo outlier determina l'intero valore, e
questo *dopo* che `_detect_outliers` li ha già identificati — l'informazione c'è, non viene usata.

**Soluzione proposta**

1. Rinominare in `price_agreement` e usarla solo dove significa questo (Monitoraggio, badge
   prezzo).
2. Sostituire `(max-min)/mean` con un **coefficiente di variazione robusto**:
   `1 - min(1, IQR / median)`. Insensibile al singolo outlier.
3. Introdurre un `data_confidence` separato, che è ciò che `decision_score` deve consumare, come
   combinazione esplicita di: numero di fonti, `price_agreement`, presenza di fantamedia reale,
   `player_source_matches.confidence` minima fra le fonti del giocatore.
4. Correggere P1-001 usando `data_confidence`.

**Rischio della soluzione**

Basso. Attenzione a `get_monitoring_data`, che filtra su `confidence < 50`: con la formula nuova
la soglia va ritarata.

---

### [P1-003] Lo stesso giocatore ha due Fantasy Value diversi in due pagine

**Area:** Coerenza / Architettura
**File:** `dashboard/data_access.py` (287-334 vs 454-464)
**Stato:** **CONFIRMED**

**Problema**

`_compute_ranked_role` fa:

```python
rows = _attach_fcp_metrics(rows, _conn)
rows = _attach_tactical_profile_inputs(rows, _conn)   # ← season goals/assists, set pieces
return rank_players(rows)
```

`get_player_detail` fa:

```python
merged_rows = _attach_fcp_metrics(_merge_player_rows(rows, ...), conn)
merged = enrich_scores(merged_rows[0])                # ← manca _attach_tactical_profile_inputs
```

Senza `season_goals_scored`/`season_assists`/`set_pieces`, `compute_tactical_profile_score`
restituisce un valore diverso, e `compute_score` lo somma dentro il Fantasy Value.

**Esempio concreto** (riprodotto su tutti i difensori)

```
Dimarco Federico   pagina ruolo 85.01   scheda 82.71   (tps 70.0 vs 47.0)
Bremer Glaison     pagina ruolo 72.97   scheda 71.84
Pavlovic S.        pagina ruolo 71.67   scheda 70.99
→ 138 difensori su 146 con Fantasy Value diverso fra le due viste
```

**Impatto**

È un bug **visibile all'utente**: due schermate della stessa app, stesso giocatore, due numeri.
Distrugge la fiducia più di un errore invisibile. Ed è sintomo di un problema architetturale: il
"come si costruisce una riga giocatore completa" è duplicato in due punti che sono andati in
deriva.

**Soluzione proposta**

Estrarre l'unica funzione che compone una riga completa e farla usare a entrambi i chiamanti:

```python
def _build_player_rows(conn, rows, weights, stats_weights):
    rows = _merge_player_rows(rows, weights, stats_weights=stats_weights)
    rows = _attach_fcp_metrics(rows, conn)
    rows = _attach_tactical_profile_inputs(rows, conn)
    return rows
```

`_compute_ranked_role` e `get_player_detail` la chiamano entrambi. Circa 10 righe, nessuna nuova
astrazione — è esattamente il "minimum necessary change" che il progetto chiede.

**Rischio della soluzione**

Molto basso. `get_player_detail` diventa marginalmente più costosa (due query bulk in più), ma è
già dietro `get_ranked_role`.

**Test richiesto:** per ogni ruolo, per ogni giocatore, `get_player_detail(pid)["score"]` deve
essere identico a `get_ranked_role(role)[i]["score"]`. Va reso un test permanente.

---

### [P1-004] Due motori di prezzo massimo, contraddittori, sulla stessa scheda

**Area:** Coerenza di prodotto
**File:** `ranking/price_engine.py`, `ranking/auction_intelligence.py`,
`dashboard/components.py` (1455-1467)
**Stato:** **CONFIRMED**

**Problema**

Su Dimarco (difensore #1, tier "top", quotazione consensus 94.88):

```
Price Engine          fair_price 25.1   max_price 33.2   status PASS
Auction Intelligence  fair_price 94.88  max_bid   94.9
```

Un fattore ~3× fra i due "prezzi massimi", visualizzati uno sotto l'altro.

Il codice ne è consapevole e lo spiega:

> *"Diverso dal 'Fair Price' dell'Auction Intelligence qui sotto... due punti di vista, non due
> stime in contraddizione."*

**Perché è un problema**

La spiegazione descrive l'intenzione, ma non l'output. Sono numeri sulla **stessa unità di misura
e con lo stesso nome operativo** ("massimo che dovrei offrire"): l'utente in asta deve scegliere
uno dei due, e la scheda non gli dà nessun criterio.

Peggio: il Price Engine dice **PASS su un giocatore che l'app stessa marca "🏆 Top"**, al prezzo
che l'app stessa ha calcolato. È una contraddizione interna, non una differenza di prospettiva.

**Causa radice** (tre difetti che si sommano)

1. `compute_fair_price = score / median_value_for_money * 10`. Ma `value_for_money = score / price`,
   quindi `fair_price` è ancorato ai prezzi correnti del ruolo. Con le scale miste di P0-001 la
   mediana è schiacciata dai giocatori "listino-economici" → il fair price è sistematicamente
   sotto il prezzo di chiunque sia quotato sulla scala 500.
2. `compute_value_for_money` applica un floor a 5 crediti; `compute_fair_price` non lo inverte.
   Per i giocatori sotto quel floor la formula è internamente incoerente.
3. `max_price = fair_price * (1 + premium)` con `premium = 0` sempre (vedi P1-008 e P1-009):
   **misurato, `max_price == fair_price` su ogni riga del Decision Center**. Il "prezzo massimo"
   non è un massimo: è il fair price con un altro nome.

**Soluzione proposta**

1. **Un solo prezzo massimo nel prodotto.** L'Auction Intelligence è quello giusto: parte dal
   prezzo di mercato e tiene conto di budget/slot/inflazione. Il Price Engine va ridotto a ciò
   che sa davvero dire: *"questo giocatore rende più o meno della mediana del ruolo per credito
   speso"* — un indicatore di efficienza, **rinominato** (`value_index`), senza `fair_price`,
   `max_price` né BUY/PASS.
2. Se si vuole tenere un fair price indipendente, non può derivare dai prezzi: va costruito da
   `expected_points` e dal budget totale della lega
   (`fair = expected_points_share * 500`), che è l'unica definizione autoconsistente.
3. Correggere il floor: se si usa `MIN_PRICE_FOR_VALUE` nel numeratore, la formula inversa deve
   tenerne conto.

**Rischio della soluzione**

Rimuove una feature visibile. È la scelta giusta: meglio un numero difendibile che due
contraddittori. Da confermare con l'utente prima di implementare.

---

### [P1-005] `role_mantra` contiene ruoli classici: tre moduli calcolano su una tassonomia inesistente

**Area:** Dati / Scraper
**File:** `scrapers/pianetafanta.py` (31,41), `scrapers/fantacalcio_it.py` (25-26),
`ranking/tactical_profile.py`, `ranking/correlation.py`, `ranking/auction_checklist.py`
**Stato:** **CONFIRMED**

**Problema**

```bash
sqlite> SELECT role_mantra, role_classic, COUNT(*) FROM players GROUP BY 1,2;
NULL|A|160   NULL|C|266   NULL|D|266   NULL|P|89
A|A|6        C|C|8        D|D|5        P|P|3
```

**22 giocatori su 803 hanno `role_mantra`, e per tutti e 22 vale esattamente `role_classic`.**
Provengono da `pianetafanta.py`, che legge `cells[1]` (colonna "R1") e lo salva come Mantra.

`fantacalcio_it` *saprebbe* estrarre i veri codici Mantra — la fixture contiene
`data-value="pc"`, `data-value="por"` — ma in produzione restituisce `None` (altrimenti
vincerebbe: è il primo scraper della lista e `run_pipeline` prende il primo `role_mantra`
non nullo). Vedi P1-018.

**Perché è un problema**

Tre moduli consumano `role_mantra` come tassonomia Mantra (`DC`/`DD`/`DS`/`B`/`E`/`M`/`C`/`T`/
`W`/`A`/`PC`). Con i valori reali:

- **`tactical_profile.py`**: `ROLE_MANTRA_BASE.get("A")` → **50** ("attaccante di raccordo/seconda
  punta"), `get("C")` → **25**, `get("D")` → `None` → fallback 25. Cioè per 6 attaccanti la base
  tattica è quella della seconda punta, per puro omonimo di lettera. Peggio di un valore mancante:
  è un valore *plausibile e sbagliato*.
- **`correlation.py`**: `CONTESTED_ROLE_MANTRA = {"T","W","A","PC","E"}` contiene `"A"`. Due
  attaccanti della stessa squadra vengono segnalati come *"stesso ruolo tattico (A), competono per
  gli stessi bonus"* — che è solo "sono entrambi attaccanti".
- **`auction_checklist.py`**: `OFFENSIVE_DEFENDER_MANTRA = {"E","DD","DS","B"}`,
  `role_mantra == "DC"`, `MIDFIELD_OFFENSIVE_MANTRA = {"T","W","A"}`. Nessuno di questi valori
  esiste nel DB → **5 voci della checklist su 18 sono permanentemente ❌**, qualunque rosa si
  costruisca.

**Impatto**

L'intero "profilo tattico" — presentato come il differenziale del progetto rispetto a un semplice
listino — poggia su un campo vuoto al 97% e sbagliato per il restante 3%.

**Soluzione proposta**

1. **Verificare l'HTML reale di fantacalcio.it** (`th.player-role-mantra span.role-mantra`) con una
   fetch dal vivo, non contro la fixture. Correggere il selettore e **aggiornare la fixture con
   HTML reale**.
2. In `pianetafanta.py`, **non** scrivere `cells[1]` in `role_mantra` finché non è verificato che
   quella colonna contenga codici Mantra. Passare `role_mantra=None`: meglio nessun dato che dato
   della tassonomia sbagliata.
3. **Validare in ingresso**: `run_pipeline` deve rifiutare un `role_mantra` non appartenente al
   vocabolario Mantra, con `logger.warning`. Vale in generale: ogni campo con un vocabolario
   chiuso va validato alla scrittura.
4. Finché `role_mantra` non è popolato, i moduli che lo consumano devono dichiarare
   "profilo tattico non disponibile" invece di calcolare sul fallback (vedi P0-008 punto 1).

**Rischio della soluzione**

Basso. Nel breve termine il tactical profile diventa uniforme (fallback per ruolo), il che
**riduce** artefatti: oggi la differenza fra un giocatore con `role_mantra` e uno senza è rumore.

---

### [P1-006] `appearances` e `status` presi dalla prima fonte non nulla, senza consenso

**Area:** Consensus
**File:** `dashboard/data_access.py` (100, 238-241)
**Stato:** **CONFIRMED**

**Problema**

```python
FILLED_FIELDS = ("status", "appearances")
for field in FILLED_FIELDS:
    result[field] = next((r[field] for r in player_rows if r.get(field) is not None), None)
```

`price_current`, `fantamedia`, `avg_rating` passano per la media pesata con pesi, outlier
detection e recency. `appearances` no: prende **la prima riga non nulla**, in ordine SQL
(`ORDER BY p.canonical_name` — indefinito all'interno di uno stesso giocatore).

**Perché è un problema**

`appearances` non è un campo secondario. Determina:
- `reliability` in `compute_score` e in `compute_risk`;
- il filtro `RELIABLE_APPEARANCES_MIN >= 15`, che **scarta metà del dataset** (803 → 407);
- i tier (`PROVEN_MIN`, `NAILED_ON_MIN`, `UNPROVEN_MAX`);
- `verdict` ("Titolare quasi certo" / "Poche presenze");
- la checklist d'asta.

Due fonti lo popolano (`fantacalciopedia` 1470 righe, `fantacalcio_online` 1068) e **non
concordano**: per Malen, 19 vs 18. Quale vince dipende dall'ordine di ritorno di SQLite.

**Impatto**

Un input critico è deciso in modo arbitrario e non riproducibile. Combinato con P0-004
(nessuna stagione), il valore selezionato può anche riferirsi a un campionato diverso.

**Soluzione proposta**

1. Trattare `appearances` come i campi statistici: **media pesata con `stats_weights`**, arrotondata
   all'intero. È il minimo, e riusa il codice già scritto.
2. Meglio ancora, dopo P0-004: prendere le presenze **della stagione e del campionato dichiarati**,
   preferendo la fonte con `weight_stats` più alto e registrando il disaccordo in
   `price_outlier_sources` (da generalizzare a `outlier_sources_by_field`).
3. Esporre lo scarto in Monitoraggio: "N giocatori con presenze discordanti fra le fonti di oltre
   X" è esattamente il tipo di controllo che manca.

**Rischio della soluzione**

Basso. Cambia il filtro sulla popolazione: da rieseguire e confrontare i conteggi per ruolo.

---

### [P1-007] `role_classic` deciso dalla prima fonte del gruppo

**Area:** Pipeline
**File:** `pipeline/run_scraping.py` (19-20, 26-28)
**Stato:** **CONFIRMED**

**Problema**

```python
first = records[0]
...
player_id = repository.upsert_player(conn, canonical_name, team, first.role_classic, role_mantra, None)
```

Il ruolo è quello del primo record del gruppo. E `upsert_player` **sovrascrive** `role_classic` a
ogni run, senza confronto col valore precedente.

**Perché è un problema**

Le fonti discordano regolarmente sui ruoli di confine (esterno alto listato D o C; trequartista
listato C o A) — è una delle differenze più note fra listini. Qui viene risolta a caso, senza log
e senza traccia.

Il ruolo determina la pagina in cui compare il giocatore, il ruolo contro cui è percentilizzato,
lo slot che occupa nell'LP e il budget di riferimento. Un ruolo sbagliato è un errore
massimamente visibile.

Rischio latente aggiuntivo: `fantacalcio_it.parse_html` fa `ROLE_MAP.get(role_span.get("data-value",""), "")` —
**stringa vuota** per un valore non mappato. Un `role_classic = ""` passerebbe silenziosamente in
`players` (`NOT NULL` non blocca la stringa vuota) e il giocatore sparirebbe da ogni pagina.
Oggi non accade (il DB ha solo P/D/C/A), ma è a un cambio di markup di distanza.

**Soluzione proposta**

1. **Voto di maggioranza pesato** su `weight_stats`, con tie-break deterministico sulla fonte di
   peso più alto. ~8 righe.
2. Registrare il disaccordo: se le fonti non sono unanimi, `logger.warning` + una riga in una
   tabella `player_role_conflicts` (o riusare `player_source_matches`) esposta in Monitoraggio.
   Il ruolo contestato è un'informazione utile in asta, non solo un problema di igiene.
3. Validare: `role_classic` deve essere in `{"P","D","C","A"}` o il record viene scartato con log.
   Sostituire il fallback `""` di `ROLE_MAP.get(..., "")` con `None` + skip.

**Rischio della soluzione**

Basso. Alcuni giocatori cambieranno pagina: atteso e corretto.

---

### [P1-008] `replacement_advantage` è ≤ 0 per tutti tranne il primo del ruolo

**Area:** Metriche
**File:** `ranking/replacement.py` (12-24)
**Stato:** **CONFIRMED**

**Problema**

```python
def compute_replacement_level(player_row, available_role_rows):
    others = [r["score"] for r in available_role_rows if r["player_id"] != player_row["player_id"]]
    return max(others) if others else 0.0
```

Si chiama "replacement level" ma restituisce **il massimo** delle alternative. Quindi
`replacement_advantage = score - max(altri)` è **negativo per chiunque non sia il migliore**.

**Perché è un problema**

Il "replacement level" in analisi sportiva è il livello del giocatore *liberamente disponibile* —
il primo escluso dai roster della lega, cioè l'N-esimo del ruolo con N = slot × squadre. Prendere
il massimo calcola tutt'altro: il divario dal migliore.

E quel valore viene consumato così:

```python
replacement_norm = max(0.0, min(1.0, replacement_advantage / 20.0))
```

Negativo → `max(0.0, ...)` → **0 per tutti**. `REPLACEMENT_PREMIUM_MAX` non si applica mai.

**Evidenza**

Su tutte le righe del Decision Center: `max_price == fair_price`. Nessun premio, mai.

**Soluzione proposta**

Implementare il replacement level vero: con 8 squadre × 8 slot difensori, il difensore di
replacement è il **65°** per score fra i disponibili.

```python
LEAGUE_TEAMS = 8   # in configurazione, non hardcoded qui

def compute_replacement_level(role, available_role_rows, league_teams=LEAGUE_TEAMS):
    scores = sorted((r["score"] for r in available_role_rows), reverse=True)
    idx = ROLE_SLOTS[role] * league_teams
    return scores[idx] if idx < len(scores) else (scores[-1] if scores else 0.0)
```

Così `replacement_advantage` è positivo per i giocatori realmente sopra la soglia di
sostituibilità — che è il segnale che serviva.

**Rischio della soluzione**

Basso e ad alto valore: riattiva un termine oggi morto. `LEAGUE_TEAMS` va reso configurabile
insieme a `total_credits` (oggi 500 hardcoded in cinque punti diversi).

---

### [P1-009] `scarcity` è ≈0 per tutti: la scala di decadimento non è tarata sulla dimensione del ruolo

**Area:** Metriche
**File:** `ranking/scarcity.py` (14-30)
**Stato:** **CONFIRMED**

**Problema**

```python
DECAY_SCALE = 4.0
threshold = player.decision_score * 0.9
comparable = [r for r in available if r.decision_score >= threshold]
return round(100 * math.exp(-len(comparable) / 4.0), 1)
```

Con 146 difensori e 155 centrocampisti, i "comparabili al 90%" sono decine. `exp(-30/4) ≈ 0.0006`
→ scarsità **0.1/100** per chiunque non sia nei primissimi posti.

Due difetti distinti:

1. **`DECAY_SCALE = 4` è tarato per un ruolo da ~10 candidati**, non da 150.
2. **La soglia è un rapporto su una scala a intervalli.** `decision_score` non ha uno zero
   significativo (può essere negativo): `x * 0.9` non è "il 90% della qualità". Per un giocatore
   con `decision_score = -10` la soglia è `-9`, cioè *più alta* del suo stesso valore — e
   praticamente tutti risultano comparabili.

Nota: nel progetto esistono **due** funzioni di scarsità che danno risposte diverse sullo stesso
giocatore. Verificato su Dimarco: `compute_scarcity` → premio 0; `compute_scarcity_tier` (via
`alternatives_remaining`) → 4 alternative, "Media". Sono due definizioni indipendenti dello stesso
concetto.

**Soluzione proposta**

1. Unificare su **una sola** definizione di scarsità (preferire `compute_scarcity_tier`, che ragiona
   su un conteggio interpretabile), e cancellare l'altra.
2. Definire "comparabile" su una **differenza**, non su un rapporto:
   `abs(other.score - player.score) <= COMPARABLE_SCORE_GAP` con `COMPARABLE_SCORE_GAP ≈ 3`
   (≈0.3 di fantamedia, giustificabile).
3. Contare solo le alternative **realmente acquistabili**: non prese, entro il budget residuo, con
   uno slot libero. Oggi `compute_scarcity` conta anche chi non potresti comprare.
4. Tarare il decadimento sugli slot: `exp(-comparable / slot_residui_del_ruolo)`.

**Rischio della soluzione**

Basso. Riattiva un secondo termine morto; da verificare insieme a P1-008 che i premi risultanti
restino nei range dichiarati.

---

### [P1-010] `compute_dynamic_max_bid` può consigliare un'offerta superiore al budget

**Area:** Asta
**File:** `ranking/auction_intelligence.py` (105-127)
**Stato:** **CONFIRMED**

**Problema**

```python
max_bid = max(fair_price, min(uncapped, theoretical)) if theoretical else fair_price
```

Il `max(fair_price, ...)` esterno **annulla il cap di budget**.

**Esempio concreto** (riprodotto)

```python
compute_dynamic_max_bid(fair_price=30, budget_remaining=10, slots_remaining=10)
# → {'max_bid': 30, 'theoretical_budget_cap': 1, 'capped_by_budget': True, ...}
```

Con 10 crediti e 10 slot da riempire, il sistema consiglia di offrirne fino a 30.
`capped_by_budget` è correttamente `True` — e viene ignorato.

Inoltre `realistic_budget_cap` (`theoretical * 0.78`) è calcolato, restituito, documentato... e
**mai usato** nel calcolo di `max_bid`.

**Impatto**

Nella fase finale dell'asta — esattamente quando il budget stringe e il consiglio conta di più —
il consiglio diventa impossibile da seguire.

**Soluzione proposta**

```python
cap = realistic_cap if realistic_cap else theoretical
max_bid = min(uncapped, cap)
```

Niente `max(fair_price, ...)`: se il budget non arriva al fair price, la risposta corretta è
"non puoi permettertelo", non "offri comunque". Aggiungere un flag `affordable: bool` e farlo
mostrare in UI.

**Rischio della soluzione**

Molto basso. Va aggiunto un test proprio su questo scenario.

---

### [P1-011] Un giocatore senza prezzo ottiene "Scarsità critica / BUY NOW"

**Area:** Asta
**File:** `dashboard/data_access.py` (776-781)
**Stato:** **CONFIRMED** (per lettura; raggiungibile ogni volta che `price_current is None`)

**Problema**

```python
alternatives_remaining = len([
    r for r in role_rows
    if r["player_id"] != player_id and not r.get("is_in_roster") and not r.get("taken_by")
    and (fair_price or 0) > 0                      # ← condizione sul giocatore VALUTATO
    and (r.get("score") or 0) >= 0.85 * (player.get("score") or 0)
])
```

`(fair_price or 0) > 0` non dipende da `r`: è una costante dentro la comprehension. Se
`fair_price` è `None` la condizione è falsa per ogni riga → `alternatives_remaining = 0`.

Poi:

```python
compute_scarcity_tier(0)  # → premium 0.25, label "Critica"
compute_auction_timing(...)  # → scarcity "Critica" → action "buy_now"
```

**Impatto**

Il consiglio più aggressivo del sistema ("🟢 BUY NOW — poche alternative, rischi di restare
senza") viene emesso proprio quando **non si conosce il prezzo del giocatore**. È il caso
peggiore: un'assenza di dato che si trasforma in un segnale forte.

E non è raro: `price_current` è `None` per chiunque abbia solo `fantacalcio_it` come fonte di
prezzo (peso 0, vedi P2-001) o solo fonti senza prezzo.

**Soluzione proposta**

1. Spostare la guardia fuori dalla comprehension e restituire subito:
   ```python
   if not fair_price:
       return {..., "scarcity": None, "timing": {"action": "no_data",
               "reason": "Prezzo di consenso non disponibile: nessun consiglio d'asta."}}
   ```
2. In `compute_scarcity_tier`, distinguere `alternatives_remaining = 0` ("nessuna alternativa",
   scarsità reale) da `None` ("non calcolabile"). Sono stati diversi e devono restare tali.

**Rischio della soluzione**

Molto basso. È un caso "fail silently" da trasformare in "fail loudly".

---

### [P1-012] Nessuna riserva di budget per gli slot ancora vuoti

**Area:** Budget
**File:** `dashboard/data_access.py` (587, 956), `ranking/budget.py` (22-44)
**Stato:** **CONFIRMED**

**Problema**

```python
# get_squad_suggestions
and r["price_current"] <= summary["remaining"]
```

`remaining = 500 - spent`. Nessuna sottrazione per gli slot ancora da riempire. Con 500 crediti e
25 slot, il sistema propone come acquistabile un giocatore da 500 crediti — che lascerebbe 0
crediti per 24 giocatori, in una lega dove il minimo è 1 credito a testa.

`compute_max_theoretical_bid` in `auction_intelligence.py` **fa** il calcolo giusto
(`budget - (slots-1)`), ma `get_squad_suggestions`, `get_decision_center` e `get_ideal_formation`
non lo usano.

**Impatto**

Le tre superfici che elencano "cosa posso comprare adesso" mostrano candidati non acquistabili.
In asta è precisamente il momento in cui non si ha tempo di verificare a mano.

**Soluzione proposta**

Esporre in `compute_budget_summary` un campo `spendable` e usarlo ovunque al posto di `remaining`:

```python
total_slots_remaining = sum(s["remaining"] for s in slots.values())
summary["spendable"] = max(0, remaining - max(0, total_slots_remaining - 1))
```

Poi sostituire `summary["remaining"]` con `summary["spendable"]` in `get_squad_suggestions`,
`get_decision_center`, `get_ideal_formation`, `get_optimal_squad_lp`. `remaining` resta per la
visualizzazione del budget.

**Rischio della soluzione**

Basso. A rosa vuota la differenza è 24 crediti su 500 (5%); a fine asta diventa decisiva.

---

### [P1-013] LP: un giocatore in rosa assente dalle liste produce una rosa da 26 e un costo sottostimato

**Area:** Optimizer
**File:** `ranking/lp_optimizer.py` (68-98)
**Stato:** **CONFIRMED**

**Problema**

```python
already_filled = sum(1 for pid in fixed_ids
                     for p in players_by_role.get(role, []) if p["player_id"] == pid)
slots_to_fill = max(needed_total - already_filled, 0)
```

Se un giocatore in rosa non è presente in `players_by_role[role]`, `already_filled` non lo conta:
l'LP compra un roster completo *in aggiunta* a lui. E nel calcolo del costo:

```python
for p in players:
    if p["player_id"] in fixed_ids:
        total_cost += roster_prices.get(p["player_id"], 0)
```

Anche il suo `price_paid` sparisce dal totale.

**Perché non è ipotetico**

`get_optimal_squad_lp` passa `players_by_role = {role: get_ranked_role(conn, role)}`, e
`get_ranked_role` **scarta ~50% del dataset** (`source_count >= 2`, `is_current_serie_a_team`,
`appearances >= 15`). Qualunque acquisto reale che non superi quei filtri innesca il bug.

**Riproduzione**

```python
res = build_optimal_squad(players, budget=100, roster_player_ids={999},
                          taken_ids=set(), mode="constrained", roster_prices={999: 50})
# → 25 giocatori comprati + 1 in rosa = 26; total_cost 25.0, i 50 crediti pagati non contati
```

Bug latente correlato, stessa funzione: se un `player_id` compare in due liste di ruolo, il
dizionario `variables` viene sovrascritto e **la stessa variabile finisce in due vincoli di ruolo**
→ il giocatore viene selezionato due volte (riprodotto). Oggi i ruoli sono disgiunti, ma è
un'assunzione non verificata.

**Soluzione proposta**

1. Costruire l'insieme dei fissi **dalla rosa**, non dalle liste di ruolo: passare a
   `build_optimal_squad` anche `roster_roles = {player_id: role_classic}` (già disponibile da
   `repository.get_roster`) e calcolare `already_filled` da lì.
2. Il costo dei fissi va sommato da `roster_prices`, indipendentemente dalla presenza nelle liste.
3. De-duplicare i candidati per `player_id` prima di creare le variabili, con un `assert` se un id
   compare in due ruoli.
4. Se un giocatore in rosa non è nelle liste, segnalarlo in output
   (`"roster_not_in_pool": [...]`) e mostrarlo in UI — è un'informazione utile, non da nascondere.

**Rischio della soluzione**

Basso, ~15 righe. Test richiesti su entrambi gli scenari.

---

### [P1-014] `compute_ideal_score` somma grandezze che già si contengono a vicenda

**Area:** Metriche
**File:** `ranking/ideal_squad.py` (19-94)
**Stato:** **CONFIRMED**

**Problema**

```python
WEIGHT_FANTASY_VALUE = 0.35
WEIGHT_DECISION_SCORE = 0.25
WEIGHT_FORM = 0.20
WEIGHT_RELIABILITY = 0.10
WEIGHT_VALUE_FOR_MONEY = 0.10   # somma = 1.00

base = fantasy_value*0.35 + decision_score*0.25 + vfm_percentile*0.10
adjusted = base * (1 + reliability*0.10) * (1 + (form-1)*0.20) + penalty
```

Tre difetti distinti:

1. **I pesi non sono pesi.** Tre sono additivi, due moltiplicativi. La somma a 1.00 non significa
   nulla — è una coincidenza di presentazione.
2. **Triplo conteggio.** `decision_score = fantasy_value + f(vfm_percentile) - g(risk)`. Quindi
   `fantasy_value` è contato due volte (0.35 diretto + 0.25 dentro decision_score) e
   `vfm_percentile` due volte (0.10 diretto + dentro decision_score). Il commento nel codice
   sostiene che usare il percentile invece del rapporto grezzo evita il doppio conteggio — evita
   il problema di *scala*, non il doppio conteggio.
3. **`reliability` contato tre volte:** in `compute_score` (`reliability*5`), in `compute_risk`
   (`unreliability*60` → dentro `decision_score`), e qui come moltiplicatore.

**Bug aggiuntivo nella forma**

```python
return max(0.5, min(1.3, 0.5 + (avg / 7.5)))
```

Il commento dice *"fantavoto medio ~6 = neutrale"*. Ma `0.5 + 6/7.5 = 1.3` = **massimo**. Il
punto neutro reale è `avg = 3.75`, che nel fantacalcio è un'annata catastrofica. Con questa
formula **ogni giocatore con dati di forma prende il bonus massimo**.

(Oggi inerte: `player_match_ratings` è vuota e `get_ideal_formation` non passa mai
`recent_form_by_player`. È una bomba a orologeria, non un bug attivo.)

**Soluzione proposta**

1. Non sommare `fantasy_value` e `decision_score`. **Scegliere uno solo.** `decision_score` è già
   il numero "tutto compreso": usare quello, con `reliability`/`form` come modificatori
   moltiplicativi espliciti. La funzione si riduce a ~15 righe.
2. Correggere la forma: neutro a 6.0 → `1.0 + (avg - 6.0) * 0.1`, clampato a [0.7, 1.3].
3. Se si tengono più termini additivi, **normalizzarli sulla stessa scala prima di pesarli**
   (z-score o percentile). Sommare uno score 0-100 con un percentile 0-100 con una fantamedia×10
   non è una media pesata.
4. Rimuovere `WEIGHT_*` dal totale-1.00 o renderlo vero.

**Rischio della soluzione**

Basso: `compute_ideal_score` alimenta solo l'ordinamento della Rosa Ideale euristica.

---

### [P1-015] Il confronto "Rosa Ideale vs LP" mette a confronto 18 giocatori contro 25

**Area:** Dashboard
**File:** `dashboard/pages/5_La_Mia_Rosa.py` (257-270)
**Stato:** **CONFIRMED**

**Problema**

```python
ideal_total_score = sum(p["score"] for role in starters for p in starters.get(role, [])) \
                  + sum(p["score"] for role in bench   for p in bench.get(role, []))
comparison_df = pd.DataFrame({"Fantasy Value totale": [ideal_total_score, lp_result["total_score"]]}, ...)
```

`starters` = 11 (formazione), `bench` = `BENCH_COVERAGE` = 2+2+2+1 = 7. Totale **18**.
`lp_result["total_score"]` somma **25** giocatori.

Didascalia: *"quanto guadagna il solver matematico"*.

**Impatto**

Il grafico non misura la qualità dei due approcci: misura che 25 addendi positivi superano 18. Il
solver "vince" sempre, di circa il 40%, anche se scegliesse peggio giocatore per giocatore. È un
benchmark che non può fallire — quindi non informa.

**Soluzione proposta**

Confrontare su una base comune. Due scelte, entrambe accettabili:

- **Media per giocatore** invece della somma (`total_score / n`), che risponde a "quale metodo
  sceglie giocatori migliori"; oppure
- **somma dei soli 11 titolari** per entrambi (per l'LP, i migliori 1/3/4/3 per ruolo), che
  risponde a "quale rosa segna di più" — la domanda che interessa davvero.

Preferire la seconda, e mostrare anche il costo totale accanto: senza il costo, "punteggio più
alto" non significa "scelta migliore".

**Rischio della soluzione**

Nullo, è solo presentazione.

---

### [P1-016] Il pipeline non è idempotente: nel DB attuale ogni quotazione è triplicata

**Area:** Pipeline / Database
**File:** `db/repository.py` (30-40), `db/schema.sql` (11-22), `pipeline/run_scraping.py`
**Stato:** **CONFIRMED**

**Problema**

`insert_quotation` è una `INSERT` semplice, e `quotations` non ha nessun vincolo di unicità.
Rieseguire il pipeline lo stesso giorno duplica ogni riga.

**Evidenza** (dal DB reale)

```
Carnesecchi Marco:  3 righe fantacalcio_it, 3 fantacalcio_online, 3 fantacalciopedia,
                    3 fantanalisi, 3 fantapazz, 3 pianetafanta  — tutte scrape_date 2026-08-26
Audero Emil:        2 righe per fonte
```

9.327 righe per ~3.100 quotazioni reali.

**Perché non è (ancora) catastrofico**

`get_latest_quotations` seleziona `ORDER BY scrape_date DESC, id DESC LIMIT 1` per
`(player_id, source)`, quindi il consensus vede una riga sola per fonte. **Il ranking non è
corrotto** — questa è una nota importante: il difetto è contenuto, non propagato.

**Cosa rompe comunque**

- `get_source_stats` → `record_count` gonfiato di 3× in Monitoraggio;
- `get_price_history` → il grafico "andamento quotazione" ripete ogni punto 3 volte;
- crescita del DB a 3×/run, e il DB è versionato in git (P2-015);
- `_merge_player_rows` calcola `source_count = len(player_rows)`: corretto oggi solo perché la
  query a monte deduplica. Nessuna difesa se un chiamante passa righe grezze.

**Soluzione proposta**

1. `CREATE UNIQUE INDEX IF NOT EXISTS idx_quotations_unique ON quotations(player_id, source, scrape_date);`
2. `insert_quotation` → `INSERT ... ON CONFLICT(player_id, source, scrape_date) DO UPDATE SET ...`.
   Una riesecuzione aggiorna invece di duplicare: l'idempotenza che il README già promette.
3. Migrazione in `_migrate()`: cancellare i duplicati tenendo `MAX(id)` per chiave, **prima** di
   creare l'indice (altrimenti fallisce).
   ```sql
   DELETE FROM quotations WHERE id NOT IN (
       SELECT MAX(id) FROM quotations GROUP BY player_id, source, scrape_date);
   ```
4. Stesso trattamento per `player_source_matches` (già `UNIQUE`, ok) e verifica su
   `player_set_pieces`/`player_match_ratings` (già `UNIQUE`, ok).

**Rischio della soluzione**

Basso. La `DELETE` va eseguita su una copia del DB e verificata (`SELECT COUNT(*)` prima/dopo:
atteso ~9.327 → ~3.100) prima di committare.

---

### [P1-017] Impossibile rimuovere un giocatore dalla propria rosa; i duplicati crashano

**Area:** Dashboard / Persistenza
**File:** `db/repository.py` (134-181), `db/schema.sql` (35-49),
`dashboard/pages/5_La_Mia_Rosa.py`
**Stato:** **CONFIRMED**

**Problema**

Tre difetti che si combinano:

1. **Nessuna `remove_roster_entry`.** Il repository ha `remove_opponent_pick`, ma niente per
   `my_roster`. La pagina "La Mia Rosa" ha un bottone "Rimuovi" **solo** per gli acquisti degli
   avversari.
2. **`my_roster` non ha `UNIQUE(player_id)`.** Un doppio click su "Conferma" inserisce due volte
   lo stesso giocatore, che risulta pagato due volte in `compute_budget_summary`
   (`spent = sum(price_paid)`) e occupa due slot.
3. **`opponent_picks` ha `UNIQUE(player_id)` ma `add_opponent_pick` fa una `INSERT` semplice** →
   `sqlite3.IntegrityError` non gestita, che in Streamlit si presenta come traceback in pagina.

**Impatto**

Il contesto d'uso è un'asta dal vivo: si digita in fretta, si sbaglia, si deve correggere in
pochi secondi. Un errore di battitura sul prezzo è **irreversibile dall'interfaccia** e falsa
budget, slot, inflazione e ogni consiglio successivo per il resto dell'asta.

**Soluzione proposta**

1. `repository.remove_roster_entry(conn, roster_id)` (per `my_roster.id`, non per `player_id`) +
   bottone "Rimuovi" accanto a ogni giocatore in rosa, come già esiste per gli avversari.
2. `UNIQUE(player_id)` su `my_roster` (con migrazione che deduplica prima) e
   `ON CONFLICT DO UPDATE SET price_paid = excluded.price_paid` — così una seconda conferma
   *corregge* il prezzo invece di duplicare la riga.
3. `add_opponent_pick` → `ON CONFLICT(player_id) DO UPDATE`.
4. Guardia incrociata: un giocatore non può essere contemporaneamente in `my_roster` e in
   `opponent_picks`. Da controllare a livello applicativo con messaggio chiaro.

**Rischio della soluzione**

Basso e alto valore d'uso.

---

### [P1-018] Il selettore Mantra funziona sulla fixture e non in produzione

**Area:** Scraper / Testing
**File:** `scrapers/fantacalcio_it.py` (25-26), `fixtures/fantacalcio_it_sample.html`,
`tests/test_fantacalcio_it_scraper.py`
**Stato:** **LIKELY** (evidenza forte, richiede una fetch dal vivo per essere CONFIRMED)

**Problema**

La fixture contiene i codici Mantra reali:

```
role-mantra" data-value="pc" title="Punta centrale"
role-mantra" data-value="por" title="Portiere"
```

Il parser li estrae correttamente e il test passa. Ma nel DB **nessun giocatore ha un codice
Mantra**, pur essendoci 1.485 righe `fantacalcio_it`, e `fantacalcio_it` è il **primo** scraper
della lista in `scheduled_run.py` — quindi `next((r.role_mantra for r in records if r.role_mantra), None)`
avrebbe preferito il suo valore, se ci fosse stato.

Conclusione: in produzione `role_mantra_span.get("data-value")` restituisce `None`. L'HTML reale
è cambiato rispetto alla fixture (o quella parte è resa lato client).

**Perché conta più del singolo campo**

È il caso didattico del punto "non fidarti dei test":

```
il test passa  →  il selettore è corretto  →  il dato arriva
```

Nessuno dei tre passaggi implica il successivo. La fixture è una fotografia congelata; il test
verifica il parser contro la fotografia, non il sistema contro il mondo. E il fallimento è
**silenzioso**: nessun log, nessuna metrica, il campo semplicemente resta `NULL` per sempre.

**Soluzione proposta**

1. Fetch dal vivo, confronto con la fixture, aggiornamento di entrambi.
2. **Assertion di copertura nel pipeline** — la difesa vera: al termine del run, per ogni campo
   atteso da ogni fonte, verificare che la percentuale di valori non nulli sia sopra una soglia
   configurata (es. `fantacalcio_it.role_mantra >= 80%`). Sotto soglia → `logger.error` +
   riga in Monitoraggio. Questo intercetta *qualunque* cambio di markup, non solo questo.
3. Aggiungere in Monitoraggio una matrice fonte × campo con la copertura effettiva. Sarebbe stato
   sufficiente ad accorgersene subito.

**Rischio della soluzione**

Basso. Il punto 2 è ~30 righe ed è probabilmente il singolo controllo con il miglior rapporto
valore/costo di tutto questo documento.

---

### [P1-019] `get_data_version` non copre tutte le fonti del ranking

**Area:** Cache
**File:** `db/repository.py` (464-483), `dashboard/data_access.py` (287-334)
**Stato:** **CONFIRMED**

**Problema**

`_compute_ranked_role` legge da: `quotations`, `fcp_metrics`, `player_season_stats`,
`player_set_pieces`, `players`, `sources`, `player_source_matches`.

`get_data_version` copre solo: `quotations`, `fcp_metrics`, `sources`, `player_source_matches`.

**Impatto**

Dopo `run_set_pieces.py` o `run_fcp_metrics.py` (che scrive anche `player_season_stats`), il
ranking resta servito dalla cache con i vecchi `tactical_profile_score` fino allo scadere del
`ttl=3600` o al riavvio. L'utente vede dati vecchi senza alcun segnale.

**Soluzione proposta**

Aggiungere alla tupla:

```sql
(SELECT MAX(id) FROM player_season_stats),
(SELECT MAX(id) FROM player_set_pieces),
(SELECT MAX(id) FROM players)
```

Restano lookup indicizzati su tabelle piccole: il costo dichiarato nel commento resta valido.

**Rischio della soluzione**

Nullo.

---

## Architecture Problems

**Quello che funziona.** La pipeline dichiarata nel brief è realmente rispettata:

```
scrapers/ → matching/ → pipeline/ → db/repository.py → dashboard/data_access.py → dashboard/pages/
```

Nessuna query SQL nelle pagine; `sqlite3` importato solo in `db/`; le pagine di ruolo sono di 6
righe. `ranking/*.py` è composto di funzioni pure che non toccano il DB. **Questa è la ragione per
cui i problemi di questo documento sono correggibili senza riscrivere il progetto**, e va detto
chiaramente perché è merito reale.

**A1 — `data_access.py` è tre moduli in un file (1.045 righe).** Contiene: (a) il consensus engine
(`_merge_player_rows`, `_weighted_average`, `_detect_outliers`, `_consensus_confidence`), (b) le
costanti di dominio (squadre, soglie), (c) l'orchestrazione delle query per la UI. Il consensus
engine in particolare **non appartiene a `dashboard/`**: è logica di pipeline, e il fatto che stia
lì è la ragione per cui `_merge_player_rows` viene richiamata in quattro posti diversi con
argomenti leggermente diversi (P1-003). Estrarre `consensus/engine.py`; le costanti di dominio
vanno in DB (P0-006).

**A2 — Il consensus è ricalcolato a ogni lettura, mai materializzato.** Non esiste una tabella con
il risultato del consenso: viene ricomputato da `dashboard/`, dietro una cache di Streamlit. Tre
conseguenze: (1) è impossibile sapere *cosa* il sistema aveva calcolato ieri; (2) qualsiasi
consumatore non-Streamlit (script, notebook, test) ricalcola con parametri potenzialmente diversi;
(3) la correttezza del ranking dipende da una cache di presentazione. Una tabella
`player_consensus(player_id, scrape_date, price_*, fantamedia, appearances, confidence, ...)`
scritta dal pipeline risolve tutti e tre e rende il sistema riproducibile.

**A3 — Doppioni concettuali.** Il progetto ha **due** ottimizzatori (`ideal_squad.py` euristico,
`lp_optimizer.py` esatto), **due** motori di prezzo massimo (`price_engine`,
`auction_intelligence`), **due** definizioni di scarsità (`compute_scarcity`,
`compute_scarcity_tier`), **due** definizioni di inflazione dentro la stessa funzione, e **tre**
`_percentile_rank` identiche (`scorer.py`, `tiers.py`, `role_comparison.py`). Non sono varianti
studiate: sono strati accumulati. Ognuna di queste coppie va ridotta a una, oppure va documentato
esplicitamente perché coesistono e quale ha la precedenza in UI.

**A4 — Le regole di lega sono hardcoded e sparse.** `500` compare in `budget.py`,
`auction_intelligence.py` (×2), `data_access.py`; `ROLE_SLOTS` è duplicato in `budget.py` e
`lp_optimizer.py`; il numero di squadre della lega non esiste come concetto (serve per P1-008).
Serve una tabella `league_config` (o almeno un modulo `config.py`) con `total_credits`,
`teams_count`, `role_slots`, `season`, `formation`.

**A5 — Nessun confine "dato acquisito" / "dato derivato".** `quotations` mescola prezzi (mercato),
statistiche (storia) e stato (attuale), con un solo `scrape_date` e nessuna stagione. Sono tre
cicli di vita diversi con tre frequenze di aggiornamento diverse. È la radice di P0-001 e P0-004.
Direzione corretta: `quotations` per i soli prezzi, `player_stats` per le statistiche (con
`season` e `competition`), `player_status` per la disponibilità.

**A6 — Nessun oggetto "run".** Non esiste `scraping_runs(id, started_at, finished_at, status,
sources_ok, sources_failed, records_written)`. Senza di esso non si può: sapere se l'ultimo run è
andato a buon fine, distinguere "fonte assente" da "fonte fallita", fare rollback, o mostrare
all'utente "dati aggiornati al ... da N fonti su 6".

---

## Data Problems

**D1 — Cinque scale di prezzo in una colonna.** Vedi P0-001. È il problema numero uno del
progetto.

**D2 — Sentinelle di dato mancante trattate come misure.** `fantamedia = 0.0` per 202 giocatori
(P0-003). Vale in generale: nessun campo numerico dovrebbe accettare uno zero non validato.

**D3 — Nessuna chiave di stagione né di campionato.** Vedi P0-004. Statistiche di Premier League e
di Serie A convivono nella stessa colonna senza distinzione.

**D4 — Universo squadre sbagliato.** Vedi P0-006. 96 giocatori di Serie B acquistabili, 3 club di
Serie A assenti.

**D5 — `status` vuoto al 100%, `player_injuries` e `player_match_ratings` a 0 righe.** Vedi P0-008.
Feature presentate come attive che non hanno mai avuto dati.

**D6 — `role_mantra` popolato al 3% e con la tassonomia sbagliata.** Vedi P1-005.

**D7 — Un solo `scrape_date` in tutto il DB (2026-08-26).** Conseguenze: il decadimento per
recency (`_recency_weight`) è matematicamente inerte (tutti i pesi identici); il grafico "andamento
quotazione" ha un punto solo; `get_price_history` non ha una storia. Non è un bug — è
un'infrastruttura costruita per dati che non sono ancora stati raccolti. Va detto in UI ("storico
non ancora disponibile") invece di mostrare un grafico vuoto.

**D8 — Quotazioni triplicate.** Vedi P1-016.

**D9 — Normalizzazione squadra troncata a 3 caratteri.** `normalize_team` prende i primi 3
caratteri alfabetici. Verificato:

```
"Hellas Verona" → "hel"   vs  "Verona" → "ver"   ✗ non corrispondono
"AC Milan"      → "acm"   vs  "Milan"  → "mil"   ✗
"FC Inter"      → "fci"   vs  "Inter"  → "int"   ✗
"Internazionale"→ "int"   vs  "Inter"  → "int"   ✓
```

Qualunque fonte che prefissi il nome del club spacca la squadra in due entità, e i giocatori
falliscono `is_current_serie_a_team` e spariscono. Serve una tabella di alias
(`team_aliases(alias, team_code)`) popolata dai valori realmente osservati, non una regola
sintattica.

**D10 — Matching per cognome nudo: persona sbagliata, silenziosamente.** Verificato:

```python
match_name_to_player("Martinez", "Inter", [Lautaro Martinez, Josep Martinez])
# → Martinez Lautaro
```

`fuzz.partial_ratio("martinez", "martinez lautaro") == 100` e `== 100` anche contro
`"martinez josep"`. Con `best_score = 100 >= NEAR_EXACT_SCORE`, la guardia di ambiguità viene
**saltata** e vince il primo in ordine di lista. Inoltre `_initials_conflict` — che esiste
proprio per questo caso e funziona — **non è applicato** in `match_name_to_player` né in
`match_name_to_player_any_team`, solo nel grouping. Usato da `fantacalcio_rigoristi` e
`fantacalcio_voti`: un rigorista può essere attribuito al compagno di squadra sbagliato.

**Correzione:** (a) applicare `_initials_conflict` anche lì; (b) se il punteggio migliore è
raggiunto da più di un candidato, restituire `None` **anche sopra `NEAR_EXACT_SCORE`** — un
pareggio perfetto è il caso in cui *meno* si può scegliere, non di più.

**D11 — Il grouping dipende dall'ordine di arrivo.** `_group_records_with_confidence` confronta
ogni record con i gruppi *già creati*, la cui identità è il **primo** record entrato. Ordine
diverso → gruppi diversi. Combinato con P0-007, questo rende il pipeline non riproducibile.
Correzione minima: ordinare `all_records` deterministicamente (per fonte con peso decrescente,
poi per nome normalizzato) prima del grouping, e documentarlo come invariante.

---

## Metric Problems

**M1 — `compute_score` è `fantamedia × 10`, e nient'altro.** Il termine `reliability * 5` vale al
massimo 5 punti, cioè 0.5 di fantamedia. La correzione tattica vale ±7 e solo per D/C. Il nome
"Fantasy Value" promette una sintesi multi-fattore; la funzione è un riscalamento di un singolo
campo proveniente da una singola fonte. Non è necessariamente sbagliato — la fantamedia *è* il
predittore migliore — ma va detto, invece di suggerire una composizione che non c'è.

**M2 — Gli score non sono confrontabili fra ruoli, ma vengono sommati.** La fantamedia media di un
attaccante supera strutturalmente quella di un portiere (i portieri subiscono malus per i gol
presi). Verificato: score medio attaccanti ~75, portieri ~60. `lp_optimizer` e `ideal_squad`
**sommano** score fra ruoli: il budget scivola verso gli attaccanti per un artefatto di scala, non
per una scelta. Correzione: normalizzare per ruolo (z-score) prima di qualunque somma cross-ruolo.

**M3 — `compute_value_for_money` divide per un prezzo che non è un prezzo.** Vedi P0-001. Il
`MIN_PRICE_FOR_VALUE = 5` è una toppa ragionevole al sintomo (rapporti esplosivi vicino allo zero)
ma non alla causa, e introduce un'incoerenza con `compute_fair_price` che non lo inverte.

**M4 — `compute_risk` conta due volte l'indisponibilità.** `unreliability * 60` deriva dalle
presenze (basse spesso *perché* infortunato) e `fcp_penalty` include `injury_resistance_pct`
(basso *perché* infortunato). Stesso fenomeno, due termini. Da tenere solo se si accetta
esplicitamente il doppio peso; altrimenti usare `injury_resistance_pct` **al posto** della
componente presenze quando è disponibile.

**M5 — La penalità "unproven" è irraggiungibile.** `UNPROVEN_APPEARANCES_THRESHOLD = 5`, ma
`_compute_ranked_role` filtra già a `appearances >= 15`. Il ramo non viene mai eseguito nel flusso
principale. Codice morto documentato come attivo — o si abbassa il filtro, o si rimuove la
penalità.

**M6 — Presenze ignote trattate meglio di presenze basse.** `appearances is None` → `reliability
= 0.5` e **nessuna** penalità unproven; `appearances = 1` → `reliability = 0.026` e penalità
piena. L'assenza di informazione risulta migliore di un'informazione negativa. Incoerente con
`_reliability_factor` in `ideal_squad.py`, che per `None` usa `0.70`. Due default diversi per lo
stesso concetto in due file.

**M7 — `_percentile_rank` non restituisce mai 100 e la docstring è sbagliata.** `bisect_left` su
una lista che **contiene** il valore restituisce il numero di elementi *strettamente minori*; la
docstring dice "greater than or equal to". Il migliore di 146 ottiene 99.3, non 100. Errore
piccolo ma sistematico, e replicato in tre copie della funzione (`scorer`, `tiers`,
`role_comparison`). Da unificare in un solo modulo e correggere in
`(bisect_left + bisect_right) / 2 / n * 100` (percentile mid-rank, gestisce anche i pareggi).

**M8 — `compute_player_quality` mappa 5.0–8.0 su 0–100 e poi ci mette dentro la fantamedia.** Il
fallback `avg_rating → fantamedia` (righe 67-69) è lo stesso errore di scala di P0-002, in un'altra
funzione. La finestra 5.0-8.0 è dichiarata come scelta, e va bene — ma va applicata a una sola
grandezza.

**M9 — I tier hanno nomi assoluti e soglie relative.** `decision_pct <= 15` → `DA_EVITARE`: il 15%
peggiore di ogni ruolo finisce lì **per costruzione**, anche in un ruolo dove tutti sono buoni.
Simmetricamente `score_pct >= 90` → `TOP`. Le etichette ("Da evitare", "Top") comunicano un
giudizio assoluto che la matematica non sostiene. O si passa a soglie assolute su `score`, o si
rinominano i tier in termini relativi ("Primo 10% del ruolo").

**M10 — Chi non rientra in nessun tier riceve 3 stelle su 5.** `TIER_STARS.get(tier, 3)` in
`verdict.py`: `classify_role` lascia deliberatamente non classificati i giocatori che non rientrano
in nessuna regola, e il verdetto li presenta come *"Titolare affidabile"*. Un default ottimistico
su assenza di classificazione. Deve essere `None` → "Non classificabile con i dati disponibili".

**M11 — `compute_role_comparison` ha survivorship bias.** La media di ruolo è calcolata sui soli
giocatori che hanno il campo. Per `season_goals_scored` (popolato per ~540 su 803, e `NULL` per i
portieri) la "media del ruolo" è la media di chi ha dati, e il percentile del giocatore è calcolato
contro quel sottoinsieme. Correzione: dichiarare la copertura ("media su 89 di 146 difensori") o
trattare l'assenza come 0 dove ha senso (gol = 0 è un'informazione, non un'assenza).

**M12 — `tactical_profile` mescola realizzato e previsto nello stesso termine.**
`goals = season_goals_scored or _numeric_avg_from_range(predicted_goals)`: i gol dell'anno scorso e
i gol *previsti* da Fantacalciopedia entrano nella stessa somma con lo stesso peso. E
`season_goals_scored` viene da `get_all_latest_player_season_stats`, che prende la stagione più
recente *disponibile* — anche se è 2016/17. Servono due termini separati, o almeno un fattore di
sconto sul previsto e un limite di anzianità sul realizzato.

---

## Consensus Problems

**C1 — Il consenso sui prezzi media unità di misura diverse.** Vedi P0-001. Tutto il resto di
questa sezione è secondario rispetto a questo.

**C2 — I pesi delle fonti non sono giustificati e non sono verificabili.** `fantacalcio_online 45,
fantanalisi 35, fantapazz 10, pianetafanta 5, fantacalciopedia 5, fantacalcio_it 0`. Il commento
nello schema dice "Valori scelti dall'utente" — è una dichiarazione onesta, e va bene come punto di
partenza. Il problema è che **non esiste alcun modo di sapere se sono giusti**: non c'è
retro-verifica contro i prezzi realmente pagati, e i pesi restano invariati a prescindere dai
risultati.

Non serve MLOps. Serve una cosa sola: `my_roster` e `opponent_picks` **contengono già** i prezzi
realmente pagati. Basta una schermata in Monitoraggio che mostri, per ogni fonte, l'errore medio
assoluto fra il suo prezzo e il prezzo realmente pagato, sugli acquisti registrati. Dopo un'asta
sola i pesi diventano un dato invece che un'opinione.

**C3 — Il consenso "statistico" è un passthrough a fonte singola.** Verificato:
`fantamedia` viene **solo** da `fantacalciopedia` (1.470 righe, zero dalle altre cinque);
`avg_rating` **solo** da `fantacalcio_online` (1.068). Quindi la media pesata su `stats_weights`
restituisce il valore della singola fonte, e `_detect_outliers` (che richiede ≥3 valori) **non può
mai scattare** su questi campi. Il progetto ha l'infrastruttura di un consenso multi-fonte sulle
statistiche e i dati di una fonte sola. Da dire esplicitamente in Monitoraggio.

**C4 — `weight = 0` è una trappola silenziosa.** `fantacalcio_it` ha peso prezzo 0. Se è l'unica
fonte di prezzo di un giocatore, `weight_total = 0` e `_weighted_average` restituisce `None` — il
giocatore perde il prezzo, viene escluso dall'LP, dai suggerimenti e dal Decision Center, e da
`compute_value_for_money`. Nessun log. Un peso 0 dovrebbe significare "escludi", non "produci
silenziosamente `None`": va gestito esplicitamente (escludere la fonte a monte) e loggato.

**C5 — `_consensus_confidence` è anti-monotona nel numero di fonti.** Verificato: Carnesecchi
(6 fonti) ottiene `0.0`, Audero (3 fonti) ottiene `67.9`. La causa immediata è C1, ma la formula
`(max-min)/mean` è comunque non robusta: dipende interamente dai due estremi. Vedi P1-002.

**C6 — La penalità outlier è applicata dopo aver già incluso l'outlier nella mediana.**
`_detect_outliers` calcola la mediana su **tutti** i valori, incluso quello anomalo. Con 3 fonti,
una molto sbagliata sposta la mediana quanto basta a non essere rilevata. Con `len < 3` non fa
nulla — e con 2 fonti reali su 6 (il caso normale per i prezzi), questo è il caso normale.
Correzione: mediana robusta calcolata su un sottoinsieme trimmed, oppure MAD invece della
deviazione relativa alla mediana.

**C7 — `MIN_SOURCES_REQUIRED = 2` fa sparire i giocatori quando uno scraper fallisce.**
`run_pipeline` registra l'eccezione e prosegue. Un giocatore coperto da 2 fonti scende a 1 e
**sparisce dalla dashboard senza alcun messaggio**. La regola è sensata; l'assenza di segnalazione
no. Serve l'oggetto "run" (A6) e un avviso in testa alla dashboard: "ultimo aggiornamento: 4 fonti
su 6".

---

## Optimizer Problems

**O1 — L'obiettivo è la somma di 25 score.** Vedi P0-005. È il problema strutturale: massimizza la
qualità media della rosa, non i punti attesi degli 11 schierati.

**O2 — Nessun vincolo di concentrazione per club.** L'ottimo prodotto contiene 4 giocatori del
Como. Nessun limite. Rischio reale (una squadra che crolla trascina mezza rosa) risolvibile con
una riga di `lpSum`.

**O3 — Nessun vincolo di formazione schierabile.** 3-8-8-6 garantisce i numeri, non che gli 11
migliori compongano un modulo valido. Con `role_classic` a 4 valori il rischio è basso; diventa
reale con il Mantra.

**O4 — Conteggio slot e costo sbagliati in modalità `constrained`.** Vedi P1-013. Si attiva
ogni volta che un giocatore in rosa non supera i filtri di `get_ranked_role`, cioè spesso.

**O5 — `infeasible` è un vicolo cieco.** `build_optimal_squad` restituisce
`{"status": "infeasible"}` senza dire *perché*. La UI mostra "budget insufficiente", che è solo
una delle cause possibili (le altre: candidati insufficienti in un ruolo dopo i filtri, tutti i
candidati senza prezzo, tutti presi). Con un LP è banale distinguerle: verificare a monte, per ogni
ruolo, `len(candidates) >= slots_to_fill`, e riportare quale vincolo fallisce.

**O6 — Nessuna gestione dei pareggi né alternative.** Il solver restituisce una sola soluzione. In
asta serve sapere quali sono le rose *quasi* ottime — perché la migliore diventa irraggiungibile
appena qualcuno ti soffia un giocatore. Un semplice ciclo che riottimizza escludendo a turno il
giocatore più caro (5-10 iterazioni) dà un ventaglio di piani B utilissimo, a costo quasi nullo.

**O7 — Duplicazione della variabile se un `player_id` compare in due ruoli.** Verificato: viene
selezionato due volte. Latente oggi, ma è un'assunzione non verificata.

**O8 — L'euristica e l'LP non sono confrontabili.** Vedi P1-015. E `build_ideal_squad` ha un difetto
proprio: è greedy per ruolo nell'ordine del dict, quindi il primo ruolo può consumare tutto il
budget lasciando gli altri scoperti; i giocatori troppo cari vengono saltati silenziosamente senza
comparire in `missing`.

---

## Database Problems

**DB1 — Domanda chiave: "posso ricostruire cosa sapeva il sistema in una data?"** → **No.**

- `quotations` è append-only con `scrape_date` — questa parte è giusta.
- Ma `players` (ruolo, squadra, nome) è **upsert in place**: un cambio di ruolo o di squadra
  sovrascrive il passato senza traccia.
- `player_season_stats`, `player_anagrafica`, `player_transfermarkt_ids` sono upsert in place.
- Il **risultato del consenso non è mai persistito** (A2): anche con le quotazioni storiche non si
  può riprodurre lo score di ieri, perché i pesi in `sources` sono anch'essi upsert in place.
- Non c'è oggetto "run" (A6).

Conseguenza operativa: è impossibile verificare a posteriori se un consiglio fosse giustificato dai
dati del momento — cioè è impossibile migliorare il sistema imparando dai propri errori.

**DB2 — Nessun vincolo di unicità su `quotations`.** Vedi P1-016. Dati triplicati.

**DB3 — Nessuna `season` su `quotations`.** Vedi P0-004.

**DB4 — Foreign key dichiarate ma non applicate.** Tutte le tabelle dichiarano
`REFERENCES players(id)`, ma SQLite non applica le FK senza `PRAGMA foreign_keys = ON`, che
`get_connection` non esegue. Le referenze sono documentazione, non vincoli: nulla impedisce righe
orfane (esattamente lo scenario di P0-007). **Correzione a una riga:** aggiungere
`conn.execute("PRAGMA foreign_keys = ON")` in `get_connection` — dopo aver verificato che non ci
siano già orfani.

**DB5 — `my_roster` senza `UNIQUE(player_id)`, `opponent_picks` senza upsert.** Vedi P1-017.

**DB6 — Il DB committato è disallineato dallo schema.** `data/fantacalcio.db` non contiene 4
tabelle che `schema.sql` dichiara: `player_advanced_stats`, `team_fixture_difficulty`,
`player_anagrafica`, `player_fantanalisi_valuations`. La dashboard chiama `init_db` all'avvio e
quindi funziona, ma **qualunque entry point che apra il DB con `get_connection` senza `init_db`
crasha** con `no such table` (verificato). `scripts/simulate_auctions.py` va controllato. E il
disallineamento significa che quelle 4 pipeline non sono mai state eseguite in produzione: le
sezioni UI che le consumano sono sempre vuote.

**DB7 — Nessun `PRAGMA journal_mode = WAL`.** Il commento in `connection.py` riconosce che
Streamlit e il pipeline scrivono/leggono in contemporanea e imposta `timeout=30`. WAL è la
soluzione vera per lettori-concorrenti-a-uno-scrittore, ed è una riga.

**DB8 — Nessun indice su `my_roster(player_id)` / `opponent_picks(player_id)`.** Irrilevante a
questa scala (0-25 righe), ma `get_ranked_role` fa una query per giocatore su `player_notes`
(P2-007) e quella tabella un indice ce l'ha (via `UNIQUE`).

---

## Scraper / Import Problems

**S1 — Idempotenza: no.** Vedi P1-016. Il README la promette, il codice non la implementa (tranne
`clear_quotations_for_source_and_date`, usata solo per gli import storici — dove il problema era
già stato riconosciuto e risolto correttamente).

**S2 — Nessuna transazione di run.** Ogni `insert_quotation` fa il proprio `conn.commit()`. Un
crash a metà pipeline lascia un dataset parziale con lo `scrape_date` di oggi, che
`get_latest_quotations` selezionerà come "il più recente". Il sistema **preferisce attivamente i
dati parziali** a quelli completi del giorno prima. Correzione: una transazione per l'intero run,
con commit finale, e una riga in `scraping_runs` (A6).

**S3 — Fallimento parziale silenzioso.** Vedi C7. `logger.error` su un file di log che nessuno
apre; nessun segnale in UI.

**S4 — Parsing fragile senza guardie.** `scrapers/fantacalcio_it.py`:

```python
price_current=float(price_current_td.get_text(strip=True)) if price_current_td else None
```

Il ternario protegge dal tag mancante, non dal **contenuto non numerico** (`"-"`, `""`, `"n.d."`).
Una `ValueError` risale fino a `run_pipeline`, che scarta **l'intera fonte** per quel run: 1.485
record persi per una cella. Da sostituire con l'helper `_parse_float` che
`fantacalcio_online.py`/`pianetafanta.py` già hanno — è già scritto, basta condividerlo in
`scrapers/base.py`.

**S5 — Nessun rate limiting né throttling.** `base.py` fa retry con backoff (bene), ma nulla
limita la frequenza. `pianetafanta` fa 20 interazioni Playwright in sequenza; `run_pipeline` chiama
`find_photo_url` (Wikipedia) per **ogni giocatore senza foto, a ogni run**, senza cache né
throttle: ~800 richieste sincrone dentro il ciclo di matching. Va aggiunto un `time.sleep`
configurabile e, soprattutto, va saltata la ricerca foto per i giocatori che ce l'hanno già (oggi
il controllo è solo `photo_record`, non "esiste già un file locale").

**S6 — `upsert_player` chiamata due volte per ogni giocatore con foto.** Una prima senza foto, poi
di nuovo con. Due `UPDATE` + due `commit` per ~800 giocatori. Da unificare.

**S7 — Nessuna validazione di dominio in ingresso.** Nulla verifica che `role_classic ∈ {P,D,C,A}`,
che `fantamedia ∈ [2, 10]`, che `appearances ∈ [0, 38]`, che `team` sia una squadra reale, che
`role_mantra` appartenga al vocabolario Mantra. Ogni finding di questa sezione e della sezione Data
sarebbe stato intercettato in ingresso da un unico punto di validazione in `run_pipeline`. **È il
singolo intervento con il miglior rapporto valore/costo del documento** (~40 righe).

**S8 — Nessun monitoraggio di copertura per campo.** Vedi P1-018. Un cambio di markup che azzera
un campo è invisibile. Serve la matrice fonte × campo in Monitoraggio, con soglie.

**S9 — Le fixture sono fotografie congelate senza data.** Nessuna dice quando è stata catturata né
contro quale versione della pagina. Un test verde su una fixture di sei mesi fa non dice nulla
sulla produzione. Aggiungere un commento con data/URL in testa a ogni fixture, e un test
`@pytest.mark.live` (escluso dal run normale) che verifica i selettori dal vivo.

**S10 — `pianetafanta` estrae il nome con `split(team_upper)`.** Se il nome della squadra non è
nella cella, `split` restituisce la stringa intera e il nome include del testo spurio. Nessuna
verifica. Va aggiunto un controllo esplicito con log quando il separatore non c'è.

---

## Dashboard Problems

**DA1 — La separazione dei layer è corretta.** Va detto: le pagine di ruolo sono di 6 righe,
nessun SQL nelle pagine, tutto l'accesso passa da `data_access`. Solo `5_La_Mia_Rosa.py` (316
righe) contiene un po' di aggregazione che apparterrebbe a `data_access` (P1-015), ed è
l'eccezione.

**DA2 — La dashboard esegue il consensus engine.** Vedi A2. Non è "la UI che fa troppo": è che il
consensus engine vive nel package sbagliato e viene invocato a ogni richiesta.

**DA3 — Numeri incoerenti fra viste.** Fantasy Value (P1-003, 138/146 difensori) e prezzo massimo
(P1-004, fattore 3×). Sono i due difetti che l'utente vede per primi.

**DA4 — N+1 fuori dalla cache.** Verificato: `get_ranked_role("D")` esegue **156 statement SQL**
per 146 giocatori — una `get_player_notes` a testa, nel ciclo *dopo* `_compute_ranked_role`, quindi
fuori dalla cache. Si ripete a ogni rerun di Streamlit, cioè a ogni click. `get_decision_center`:
**448 statement**. `get_auction_intelligence`: **328**. A questa scala sono 30-90 ms — non urgente,
ma è un `get_all_player_notes(conn) -> dict` da 5 righe che elimina il problema alla radice.

**DA5 — Nessun indicatore di freschezza né di salute dei dati in testa alla dashboard.** La pagina
Monitoraggio esiste ed è ben fatta, ma è una pagina separata che si apre di proposito. Un utente
in asta guarda le pagine di ruolo e non ha modo di sapere che il dato è di tre giorni fa o che due
fonti su sei sono fallite. Serve una banda in testa: "dati al 26/08, 6 fonti su 6, 407 giocatori
valutati, 396 esclusi per dati insufficienti".

**DA6 — Nessuna distinzione visiva fra "misurato" e "stimato/mancante".** Un prezzo derivato da 2
fonti reali e uno derivato da 2 listini appaiono identici. Una fantamedia reale e un fallback su
`avg_rating` appaiono identici. Dopo P0-001/P0-002 questa distinzione **esiste nel dato** e va
mostrata: un badge, un colore, un asterisco.

**DA7 — `add_roster_entry` senza possibilità di annullare.** Vedi P1-017. In un contesto d'asta è
il difetto di usabilità più grave.

**DA8 — Le sezioni alimentate da tabelle vuote non lo dicono.** Forma recente, infortuni, calci
piazzati, statistiche avanzate, valutazioni fantanalisi: tutte con 0 righe. La UI mostra sezioni
vuote o valori neutri, indistinguibili da "nessun problema rilevato". Vedi P0-008 punto 1.

**DA9 — `st.cache_data(ttl=30)` su `_cached_auction_intelligence`.** Durante un'asta 30 secondi
sono un'eternità: il budget cambia a ogni acquisto e la funzione dipende da `budget_remaining`.
Va usata la stessa strategia a fingerprint di `get_data_version`, estesa a `my_roster` e
`opponent_picks`.

---

## Testing Gaps

**Il quadro.** 300 test, tutti verdi, in 31 secondi — e il sistema produce una rosa "ottima" senza
top player, un portiere di riserva al primo posto e Kolo Muani fra i giocatori da evitare. I test
sono **buoni test di implementazione** (parser contro fixture, funzioni pure contro input
costruiti) e **non esistono test di dominio**. La distinzione che il brief chiede è esattamente
questa, e il progetto sta interamente da un lato.

Manca inoltre qualsiasi test **contro il database reale**: tutti costruiscono DB usa e getta con
3-5 giocatori sintetici, dove le scale di prezzo sono coerenti per costruzione e i bug di questo
documento non possono manifestarsi.

### Test mancanti prioritari

```
TEST: le scale di prezzo sono commensurabili
  Input          per ogni fonte, distribuzione di price_current sul DB reale
  Expected       p99 di ogni fonte entro ±25% dalla mediana dei p99 delle altre
  Current        p99 fra 36 e 382 — fattore 10×
  Why matters    è P0-001; questo test da solo avrebbe impedito l'intero problema
```

```
TEST: coerenza dello score fra le viste
  Input          per ogni ruolo, ogni giocatore
  Expected       get_player_detail(pid)["score"] == get_ranked_role(role)[i]["score"]
  Current        138/146 difensori differiscono
  Why matters    è P1-003; è il bug visibile all'utente
```

```
TEST: la rosa ottima contiene almeno un top player per ruolo
  Input          get_optimal_squad_lp(mode="from_scratch") sul DB reale
  Expected       almeno 1 dei top-10 di ogni ruolo compare nella rosa
  Current        0 su 4 ruoli
  Why matters    test di dominio: verifica il RISULTATO, non il solver
```

```
TEST: nessuna fantamedia fuori dal dominio Serie A
  Input          tutte le righe quotations
  Expected       fantamedia IS NULL OR 2.0 <= fantamedia <= 9.5
  Current        202 righe a 0.0; massimo 8.84 su 19 presenze
  Why matters    P0-003 + P0-004
```

```
TEST: l'universo squadre corrisponde alla stagione configurata
  Input          SELECT DISTINCT team FROM players (esclusi Estero/Serie Minori)
  Expected       esattamente le 20 squadre della tabella teams per la stagione corrente
  Current        include Frosinone, Monza, Venezia; mancano Cremonese, Pisa, Verona
  Why matters    P0-006
```

```
TEST: bassa confidenza non migliora mai il decision_score
  Input          compute_decision_score(70, 50, 60, conf) per conf in 0..100
  Expected       monotona non crescente al calare di conf
  Current        conf=0 → 70.0 ; conf=100 → 58.0 (monotona INVERSA)
  Why matters    P1-001
```

```
TEST: max_bid non supera mai il budget disponibile
  Input          compute_dynamic_max_bid(fair_price=30, budget=10, slots=10)
  Expected       max_bid <= 1
  Current        max_bid = 30
  Why matters    P1-010
```

```
TEST: il pipeline è idempotente
  Input          run_pipeline(...) due volte con gli stessi record e la stessa data
  Expected       COUNT(*) FROM quotations identico; ranking identico
  Current        righe raddoppiate (il DB reale è a 3×)
  Why matters    P1-016
```

```
TEST: cognome nudo ambiguo non risolve
  Input          match_name_to_player("Martinez", "Inter", [Lautaro, Josep])
  Expected       None
  Current        Martinez Lautaro
  Why matters    P2-017/D10 — attribuzione alla persona sbagliata
```

```
TEST: LP con giocatore in rosa assente dal pool
  Input          roster_player_ids={999} con 999 non presente in players_by_role
  Expected       25 giocatori totali; total_cost include il price_paid di 999
  Current        26 giocatori; price_paid ignorato
  Why matters    P1-013
```

```
TEST: alias di squadra
  Input          normalize_team per "Hellas Verona"/"Verona", "AC Milan"/"Milan"
  Expected       stesso codice squadra
  Current        hel/ver, acm/mil
  Why matters    D9
```

```
TEST: il grouping è indipendente dall'ordine
  Input          match_records(records) e match_records(shuffled(records))
  Expected       stessi gruppi
  Current        non verificato — LIKELY diverso
  Why matters    D11 / riproducibilità
```

```
TEST: copertura per fonte e per campo
  Input          per ogni (fonte, campo) atteso, % di valori non nulli
  Expected       sopra la soglia configurata
  Current        fantacalcio_it.role_mantra = 0%, status = 0% su tutte le fonti
  Why matters    P1-018 / P0-008 — intercetta i cambi di markup
```

### Test da correggere

- `tests/test_lp_optimizer.py` verifica che il solver rispetti i vincoli, mai che il risultato sia
  sensato. Aggiungere almeno un caso "il giocatore nettamente migliore e conveniente **deve**
  essere selezionato".
- I test degli scraper girano tutti su fixture non datate. Aggiungere data/URL e un marker `live`.
- `tests/test_data_access.py` costruisce DB con prezzi già coerenti fra fonti. Aggiungere un caso
  con scale volutamente diverse, che oggi passerebbe silenziosamente.

---

## Spec vs Implementation

> Sezione aggiunta dopo l'analisi di `giocatori/portieri.md`, `giocatori/movimento.md`,
> `giocatori/rosa-ideale.md` e `statistiche giocatore` — i documenti che definiscono cosa il
> sistema *deve* fare. Vale la regola del brief: **il codice reale ha priorità sulla
> documentazione, ma dove la documentazione è una specifica di requisito (non una descrizione),
> la divergenza è un difetto del codice, non della documentazione.**

Il risultato più significativo di questa lettura: **le specifiche avevano già previsto e vietato
esplicitamente quattro dei difetti trovati nell'audit del codice.** Non sono sviste — sono requisiti
scritti e non implementati.

| La spec dice | Il codice fa |
|---|---|
| *"Non deve essere scelto semplicemente in base al rating fantacalcio. La gerarchia della squadra viene prima del rating."* (portieri §8) | Ordina i portieri per `score`, cioè per rating |
| *"Non assegnare automaticamente un punteggio basso solamente perché non esiste uno storico Serie A."* (movimento §22) | `fantamedia = 0.0` → score ≈ 5 → tier "Da evitare" |
| *"evitando di usare esclusivamente il nome"* per l'identità giocatore (portieri §15) | Chiave = `(canonical_name, team)`, entrambe stringhe di display |
| *"Non sostituire automaticamente dati validi con `null`... UI MOSTRA ULTIMO DATO VALIDO"* (statistiche §40) | Uno scraper caduto fa sparire il giocatore dalla dashboard |
| *"È consentito mantenere una configurazione delle 20 squadre, purché anche questa venga verificata/aggiornata per la stagione corrente"* (portieri §4) | Lista hardcoded in due file, mai verificata, stagione sbagliata |

---

### [P0-009] Il dataset è pre-mercato, mentre le specifiche impongono il post-mercato

**Area:** Dati / Processo · **Stato:** **CONFIRMED**
**File:** `giocatori/portieri.md` §2/§19, `giocatori/movimento.md` §23, `data/fantacalcio.db`

**Problema**

Entrambe le specifiche fissano lo stesso vincolo, in modo non ambiguo:

> *"Lo scraping definitivo deve essere eseguito: **1 settembre 2026, a mercato chiuso**. Lo scraping
> deve quindi rappresentare la rosa delle squadre successiva alla chiusura del calciomercato, non la
> situazione precedente. Non utilizzare una lista statica preparata settimane prima."*

Il DB contiene un unico `scrape_date`: **2026-08-26**. Il mercato è ancora aperto.

**Perché è un problema**

Non è una questione di freschezza generica: è la ragione per cui il dataset contiene giocatori con
squadra non definitiva, e per cui i giocatori marcati `"Estero"` / `"Serie Minori"` (51 righe)
convivono con quelli di Serie A. Ed è aggravato dal fatto che **il sistema non ha alcun meccanismo
per recepire il mercato** (P0-010): rieseguire lo scraping il 1 settembre, così com'è, non
produrrebbe il risultato richiesto — aggiungerebbe i nuovi acquisti lasciando i ceduti al loro posto.

**Impatto**

Il vincolo di processo è rispettabile a mano (basta lanciare il pipeline il 1 settembre), ma il
vincolo *funzionale* — "la lista finale deve rappresentare esclusivamente la rosa reale dopo la
chiusura del mercato" — non lo è, perché manca P0-010.

**Soluzione proposta**

Risolvere P0-010, poi rilanciare il pipeline completo a mercato chiuso e verificare il report dei
trasferimenti prima di considerare il dataset definitivo.

---

### [P0-010] I trasferimenti creano righe duplicate invece di aggiornare la squadra

**Area:** Dati / Identità · **Stato:** **CONFIRMED**
**File:** `pipeline/run_scraping.py`, `db/repository.py:5-27`, `db/schema.sql:1-9`

**Problema**

`players` ha `UNIQUE(canonical_name, team)` e `upsert_player` cerca per `(canonical_name, team)`.
**La squadra fa parte della chiave.** Quindi un giocatore che cambia squadra non viene aggiornato:
viene *inserito come nuovo giocatore*, e la riga vecchia resta.

E non esiste alcun percorso di cancellazione: nessuna `DELETE FROM players`, nessun concetto di
"non più in rosa". L'unica difesa è il filtro `is_current_serie_a_team` a valle — che è rotto
(P0-006) e che comunque nasconde, non rimuove.

**Evidenza** (dal DB reale)

```
id=534  "Bleve Marco"  team="Lecce"
id=752  "BLEVE Marco"  team="Serie Minori"
```

La stessa persona, due `player_id`, due storici separati. Ed è l'unico caso *rilevabile* perché il
nome normalizzato coincide: un trasferimento fra due club di Serie A produrrebbe lo stesso
duplicato senza che nulla lo segnali.

**Perché è un problema**

Le specifiche sono esplicite su questo punto — `portieri.md` §9/§11/§12 e `movimento.md` §23:

> *"Un giocatore ceduto deve essere rimosso dalla squadra precedente."*
> *"Il controllo deve essere effettuato sul dato `current_team` e non sul dato storico."*

E `portieri.md` §14 richiede un report esplicito dei cambiamenti:

```
ADDED / REMOVED / TRANSFERRED / UNCHANGED
```

Nulla di tutto questo esiste. Non c'è confronto fra run, non c'è diff, non c'è log.

**Impatto**

Al 1 settembre, dopo il mercato: rose gonfiate di giocatori ceduti, duplicati invisibili, e
`my_roster`/note/`review_status` agganciati all'ID sbagliato. È lo stesso meccanismo di P0-007, con
un innesco molto più frequente (ogni trasferimento, non solo una fonte caduta).

**Soluzione proposta**

1. Applicare P0-007 (`identity_key` **senza** la squadra: `normalize_name(name)` + data di nascita
   quando disponibile da `player_anagrafica`). La squadra diventa un attributo aggiornabile, non
   parte dell'identità.
2. `upsert_player` aggiorna `team` sulla riga esistente e, se cambia, registra il trasferimento.
3. Nuova tabella `player_transfers(player_id, from_team, to_team, detected_at)`, popolata dal
   pipeline.
4. Marcare come non attivi i giocatori assenti dall'ultimo run completo — colonna
   `players.last_seen_scrape_date`, e filtro a valle su quella invece che sulla lista squadre
   hardcoded. **Non cancellare**: lo storico resta, il giocatore smette di essere proposto.
5. Report di fine run con i quattro gruppi `ADDED / REMOVED / TRANSFERRED / UNCHANGED`, in log e in
   Monitoraggio, come richiesto da `portieri.md` §14.

**Rischio della soluzione**

Medio. Il punto 4 va tarato con attenzione: un giocatore assente perché la sua *unica* fonte è
caduta non deve essere marcato come ceduto. Condizionare la marcatura a un run con tutte le fonti
riuscite (richiede `scraping_runs`, TASK-006).

---

### [P1-020] Fantasy Value è additivo dove la specifica impone un modello moltiplicativo

**Area:** Metriche · **Stato:** **CONFIRMED**
**File:** `ranking/scorer.py:52`, `giocatori/movimento.md` §21

**Problema**

La specifica definisce il modello di valore in modo esplicito:

> ```
> PROFILO OFFENSIVO × PROBABILITÀ TITOLARITÀ × MINUTAGGIO PREVISTO
> ```
> *"deve determinare il valore finale."*

L'implementazione:

```python
score = base * 10 + reliability * 5 - penalty
```

Additiva, e con la titolarità che vale **al massimo 5 punti su ~70** — cioè lo 0.5 di fantamedia.

**Perché è un problema**

La differenza fra additivo e moltiplicativo non è stilistica. Nel modello della spec, un giocatore
con profilo eccellente e titolarità 0.3 vale il 30% del suo potenziale. Nel modello implementato
vale il suo potenziale pieno meno 3.5 punti. La specifica lo dice a chiare lettere nella riga
precedente:

> *"Un giocatore estremamente offensivo ma destinato alla panchina non deve automaticamente superare
> un titolare."*

Che è esattamente ciò che accade: `score ≈ fantamedia * 10` e la titolarità è rumore.

**Impatto**

È la stessa radice di P0-005 (l'obiettivo dell'LP) e spiega perché il solver riempie la rosa di
giocatori a mezza titolarità. Correggere qui corregge anche là.

**Soluzione proposta**

```python
starter_probability = min(appearances, 38) / 38     # già calcolato, oggi come `reliability`
score = base * 10 * (MIN_STARTER_FLOOR + (1 - MIN_STARTER_FLOOR) * starter_probability) - penalty
```

con `MIN_STARTER_FLOOR ≈ 0.5` per non azzerare chi ha poche presenze ma è un nuovo acquisto (spec
§22). Da fare **insieme** a P1-022, altrimenti si penalizzano due volte i giocatori senza storico.

**Rischio della soluzione**

Medio-alto: riordina il ranking in modo sostanziale. È però il modello che la spec richiede, e
rende `expected_points` (TASK-016) coerente con `score` invece che una seconda definizione.

---

### [P1-021] Il depth chart portieri usa il rating, che la specifica vieta esplicitamente

**Area:** Ranking · **Stato:** **CONFIRMED**
**File:** `ranking/goalkeepers.py`, `giocatori/portieri.md` §7/§8

**Problema**

La specifica ordina le priorità per determinare il titolare — gerarchia esplicita della fonte,
poi formazione probabile/depth chart/presenze, poi recenza — e chiude con:

> *"Non deve essere scelto semplicemente in base al rating fantacalcio. **La gerarchia della squadra
> viene prima del rating.**"*

`build_goalkeeper_depth_chart` fa `sorted(keepers, key=lambda r: r["score"], reverse=True)`.

Il docstring del modulo è onesto e riconosce il compromesso ("nothing in this codebase scrapes that
today"). Ma la spec non lascia margine: non è una semplificazione accettabile, è il comportamento
vietato.

**Perché conta ora**

Combinato con P0-002, il risultato è concretamente sbagliato: **Audero è il portiere #1 del Como**
perché non ha fantamedia e viene valutato su `avg_rating`. Anche la Priorità 2 della spec
("numero di presenze") sarebbe bastata a evitarlo — le presenze ci sono nel DB e non vengono usate
per la gerarchia.

**Soluzione proposta**

1. **Immediato, senza nuovo scraping:** ordinare per `appearances` (Priorità 2 della spec), con
   `score` solo come tie-break. È una riga, e usa un dato già presente.
2. **Corretto:** scrapare una gerarchia esplicita. Le fonti listino distinguono spesso il titolare;
   in alternativa `player_advanced_stats.minutes_percentile` (già previsto in schema) è un proxy
   diretto della Priorità 2.
3. Aggiungere il controllo anti-errore di `portieri.md` §13: 20 squadre, ≥2 portieri ciascuna, 40
   totali, nessun duplicato. Oggi ne sopravvivono **32 per 20 squadre** — il controllo fallirebbe,
   ed è esattamente l'informazione che serve.

---

### [P1-022] Chi non ha storico Serie A viene penalizzato, contro un divieto esplicito

**Area:** Metriche · **Stato:** **CONFIRMED**
**File:** `ranking/scorer.py:40-52`, `giocatori/movimento.md` §22

**Problema**

La specifica dedica una sezione intera ai nuovi arrivati e si chiude con:

> *"Non assegnare automaticamente un punteggio basso solamente perché non esiste uno storico Serie A."*

E indica cosa usare al suo posto: ruolo tattico nella nuova squadra, statistiche della stagione
precedente, ruolo e minutaggio nel club precedente, valutazione economica, probabile titolarità.

L'implementazione fa il contrario: `fantamedia = 0.0` → `base = 0.0` → `score ≈ 5` → tier
"🚫 Da evitare". Sono **202 giocatori**, fra cui Kolo Muani, Gonçalo Ramos, Mancini, Molina,
Mastantuono — cioè precisamente la categoria che la spec voleva proteggere.

**Soluzione proposta**

Va oltre la correzione di P0-003 (che si limita a non fingere che 0.0 sia una misura). Serve il
percorso alternativo che la spec descrive:

1. `fantamedia` assente → **non** ricadere su `avg_rating` (P0-002) e **non** assegnare 0.
2. Usare `player_season_stats` della stagione precedente, anche di un altro campionato,
   **marcandola come tale** (`stats_competition`, TASK-008), con un fattore di sconto dichiarato
   per la differenza di campionato.
3. In assenza anche di quella, usare il prezzo di consenso come stima di aspettativa di mercato —
   che è il punto 5 dell'elenco della spec — e marcare la riga `estimated`.
4. Mostrarli in una sezione dedicata ("nuovi arrivi, senza storico Serie A") invece di mescolarli
   al ranking come se fossero valutati.

**Rischio della soluzione**

Il punto 3 introduce una stima derivata dal prezzo, che rischia di essere circolare se poi si
confronta con il prezzo (`value_for_money`). Va marcata e **esclusa** dalle metriche prezzo-relative.

---

### [P2-020] Dati scrapati, salvati, mostrati — e mai usati per valutare

**Area:** Dati / Metriche · **Stato:** **CONFIRMED**

Quattro dataset sono raccolti e non entrano in nessuno score:

| Dato | Righe | Dove finisce | Cosa dice la spec |
|---|---|---|---|
| `team_strength` (xG/xGA/PPDA) | 20 squadre | 3 metriche sulla scheda | `rosa-ideale.md` §4: il portiere va valutato su *"gol subiti, probabilità di clean sheet, qualità della difesa"* |
| `player_season_stats.goals_conceded` | 142 | tabella stagioni | idem |
| `punteggio_fcp` | 542 | attaccato alla riga, mai letto | — |
| `predicted_appearances` | 542 | solo scritto in DB | `movimento.md` §21: *"minutaggio previsto"* è un fattore del valore finale |

**Perché è significativo**

`rosa-ideale.md` §4 descrive un modello portieri a quattro fattori (titolarità, gol subiti,
probabilità di clean sheet, qualità individuale). L'implementazione ne usa **uno** (una fantamedia
che, per i portieri, è quella meno affidabile — vedi P0-002). Gli altri tre sono già alimentabili
con dati presenti nel database: `xga` per squadra è il proxy diretto della probabilità di clean
sheet, `goals_conceded` è il gol subiti, `appearances` è la titolarità.

Non è un problema di dati mancanti: è un problema di dati raccolti e non collegati.

**Soluzione proposta**

Uno score portieri dedicato, che è anche l'unico posto dove `tactical_profile_score` restituisce
`None` lasciando un vuoto:

```python
def compute_goalkeeper_score(row, team_xga):
    starter = min(row["appearances"], 38) / 38
    clean_sheet_proxy = 1 / (1 + team_xga)     # xga più basso -> più clean sheet
    ...
```

Coefficienti dichiarati, non fittati (non c'è storico per fittarli) — stessa filosofia già adottata
e documentata in `price_engine.py`. E `predicted_appearances` va usato al posto di `appearances`
per i giocatori senza storico Serie A (collega a P1-022).

**Nota temporale:** `team_strength.scrape_date` è `2026-08-27`, le quotazioni sono `2026-08-26`.
Unire dati di giorni diversi senza dichiararlo è la stessa classe di problema di P0-004, in piccolo.

---

### [P2-021] Un fallimento di scraping cancella giocatori, invece di mostrare l'ultimo dato valido

**Area:** Pipeline · **Stato:** **CONFIRMED**
**File:** `pipeline/run_scraping.py:11-16`, `dashboard/data_access.py:315`, `statistiche giocatore` §40

**Problema**

La specifica prescrive il comportamento esatto in caso di cambio HTML della fonte:

```
SCRAPER ERROR → LOG → DATA NON AGGIORNATA → UI MOSTRA ULTIMO DATO VALIDO
```

> *"Non sostituire automaticamente dati validi con `null`."*

L'implementazione: `run_pipeline` registra l'errore e prosegue; il giocatore perde una fonte; se
scende sotto `MIN_SOURCES_REQUIRED = 2` **sparisce dalla dashboard**. Nessun avviso.

Nota: la struttura del DB *permetterebbe* il comportamento corretto — `quotations` è append-only e
`get_latest_quotations` prende l'ultima riga per `(player_id, source)`, quindi **il dato del giorno
prima è ancora lì**. La query lo userebbe naturalmente. È il filtro a valle che cancella il
giocatore, non l'assenza del dato.

**Soluzione proposta**

1. Contare le fonti su una finestra temporale (es. ultimi 7 giorni) invece che sull'ultimo run:
   `MIN_SOURCES_REQUIRED` si applica alle fonti che hanno dati *recenti*, non a quelle che hanno
   risposto *oggi*.
2. Marcare la riga con l'età del dato per fonte ed esporla (`stale_sources`).
3. Banda in testa alla dashboard: "fonte X non aggiornata da N giorni" (TASK-028).

**Rischio della soluzione** Basso. Richiede `scraping_runs` (TASK-006) per distinguere "fonte
fallita" da "fonte che non copre questo giocatore".

---

### [P2-022] Il logging degli scraper richiesto dalla specifica non esiste

**Area:** Logging · **Stato:** **CONFIRMED**
**File:** `pipeline/run_scraping.py`, `scrapers/base.py`, `statistiche giocatore` §39

La spec elenca cosa registrare per ogni scraping: `URL, timestamp, status code, tempo risposta,
success/failure, errore, numero dati estratti`.

Registrato oggi: una sola riga `logger.error("Scraper %s failed: %s")` in caso di eccezione. Nessun
conteggio di record, nessun tempo, nessuno status code, nulla in caso di successo parziale.

Conseguenza pratica: un parser che smette di trovare un campo (P1-018, il caso `role_mantra`) non
produce **nessuna** traccia. Coincide con TASK-023 (matrice di copertura fonte × campo), che va
esteso per coprire anche i requisiti di §39.

---

### [P2-023] Il "nudge" tattico non è centrato e non è simmetrico

**Area:** Metriche · **Stato:** **CONFIRMED**
**File:** `ranking/scorer.py:16-29, 54-57`

Il commento dichiara: *"Centered on a fixed neutral baseline... only a clearly above/below-average
tactical profile moves the score, and only by a bounded +/-7 at the extremes."*

Misurato sui dati reali con `NEUTRAL_TACTICAL_PROFILE = 30.0`:

```
D:  n=146  mediana 31.0  nudge medio +0.22  range [-0.50, +4.00]
C:  n=155  mediana 38.3  nudge medio +0.83  range [-0.50, +4.00]
```

Tre scostamenti dall'intento dichiarato: (1) la baseline è **sotto** la mediana di entrambi i ruoli,
quindi il nudge medio è positivo, non nullo; (2) è **differenziale fra ruoli** (+0.83 ai
centrocampisti contro +0.22 ai difensori), il che sposta il budget verso il centrocampo per un
artefatto; (3) l'escursione reale è −0.5/+4.0, non ±7.

**Soluzione:** baseline per ruolo, calcolata come mediana della distribuzione osservata invece che
come costante. Due righe. Impatto piccolo in valore assoluto ma elimina un bias sistematico e
allinea comportamento e documentazione.

---

### [P2-024] `ROLE_MANTRA_BASE` appiattisce una scala per-reparto in una scala globale

**Area:** Metriche · **Stato:** **CONFIRMED**
**File:** `ranking/tactical_profile.py:23-35`, `giocatori/movimento.md` §18

Il commento dice che i valori sono *"calibrated from the explicit ordering in movimento.md sez. 18"*.
Ma la spec usa una scala `+++++` … `-` **separata per reparto**: `QUINTO OFFENSIVO +++++` fra i
difensori e `TREQUARTISTA +++++` fra i centrocampisti sono entrambi il massimo del proprio reparto.

Il codice li mappa su un unico asse 0-100: `E = 45`, `T = 55`. Il miglior profilo difensivo vale
meno del miglior profilo di centrocampo. Analogamente `PRIMA PUNTA FINALIZZATORE +++++` diventa
`PC = 40`, il più basso fra i profili offensivi.

Poiché `compute_score` applica poi un'unica baseline a D e C (P2-023), l'errore si compone.

**Soluzione:** normalizzare `ROLE_MANTRA_BASE` **all'interno di ogni reparto** su 0-100, così
`+++++` vale 100 sia per un difensore sia per un centrocampista — che è ciò che la spec intende.
Da fare solo dopo aver risolto P1-005 (oggi il campo è vuoto al 97%, quindi la calibrazione è
accademica).

---

### Requisiti di specifica non implementati (nessun difetto, solo assenza)

Elencati per completezza — non sono bug, sono funzionalità mai realizzate. Utile sapere che
esistono a specifica prima di considerarle "idee nuove".

| Spec | Requisito | Stato | Bloccato da |
|---|---|---|---|
| `statistiche giocatore` §16 | Volatilità: deviazione standard, mediana, % giornate sopra 8 / sotto 6, % con bonus/malus | Assente | `player_match_ratings` vuota |
| `statistiche giocatore` §15 | Indice di affidabilità che includa volatilità e dipendenza dai bonus | Parziale (solo presenze + FCP) | idem |
| `statistiche giocatore` §28 | Score 0-100 con sottoscore nominati (Bonus/Titolarità/Rendimento/Affidabilità/Calendario/Prezzo/Rischio) e **pesi modificabili dal motore** | Decomposizione diversa, non limitata a 0-100, pesi hardcoded | — |
| `statistiche giocatore` §18 | Calendario nella scheda | Codice presente, tabella assente dal DB | `run_fixture_difficulty` mai eseguito |
| `statistiche giocatore` §20 | Squalifiche | Assente | nessuna fonte (vedi P0-008) |
| `statistiche giocatore` §22 | Allenatore | Assente | nessuna fonte |
| `portieri.md` §14 | Report `ADDED / REMOVED / TRANSFERRED / UNCHANGED` | Assente | P0-010 |
| `portieri.md` §13 | Controlli anti-errore (20 squadre, 40 portieri, duplicati) | Parziale (`warnings`/`missing`) | P0-006 |
| `portieri.md` §16 | `goalkeeper_rank` persistito | Assente (calcolato a runtime) | P1-021 |
| `movimento.md` §24 | Profilo decomposto (`tactical_profile`, `offensive_profile_score`, `starter_probability`, …) | Un solo numero aggregato | P1-005 |
| `movimento.md` §19 | Bonus per corner e vice-battitori | Solo rigori/punizioni | fonte |

---

# Implementation Plan

> **Regola d'ordine:** le fasi 1 e 2 vanno completate prima delle altre. Correggere metriche o
> optimizer su input sbagliati produce solo un errore diverso.

## Phase 1 — Critical correctness

### TASK-001 — Separare le scale di prezzo

**Priority:** P0 · **Finding:** P0-001
**Files:** `db/schema.sql`, `db/connection.py`, `db/repository.py`, `dashboard/data_access.py`, tutti gli scraper

**Problem:** `price_current` media 5 scale incompatibili (p99 da 36 a 382).

**Required change:** Separare prezzi-listino e prezzi-asta in due campi distinti, mai mediati fra loro.

**Implementation details:**
1. `ALTER TABLE quotations ADD COLUMN price_scale TEXT` in `_migrate()`; backfill:
   `'auction_500'` per `fantacalcio_online`/`fantanalisi`, `'listino'` per le altre.
2. Ogni scraper dichiara la propria scala (costante di modulo, passata a `insert_quotation`).
3. `_merge_player_rows` produce `price_listino` e `price_auction` con due chiamate separate a
   `_weighted_average`, ciascuna sulle sole fonti della propria scala.
4. `price_current` = `price_auction` se disponibile, altrimenti
   `price_listino * LISTINO_TO_AUCTION_FACTOR`; aggiungere `price_basis` (`'auction'` /
   `'listino_converted'`) alla riga merged.
5. `LISTINO_TO_AUCTION_FACTOR` calcolato dai dati (rapporto delle mediane fra le due famiglie sui
   giocatori che hanno entrambe), salvato in `sources`, ricalcolato a ogni run. **Non** una
   costante hardcoded.

**Dependencies:** nessuna. **È il primo task.**

**Tests required:** test scale commensurabili; test `price_basis` corretto; test che nessuna media
combini fonti di scale diverse; snapshot delle distribuzioni prima/dopo.

**Acceptance criteria:**
- Nessun giocatore ha un rapporto prezzo/mediana-di-ruolo > 10× per artefatto di copertura.
- Audero e Svilar (stesso ruolo) hanno prezzi entro lo stesso ordine di grandezza.
- `price_basis` è esposto in `get_ranked_role`.

---

### TASK-002 — Eliminare il fallback fantamedia→avg_rating e le sentinelle zero

**Priority:** P0 · **Findings:** P0-002, P0-003
**Files:** `ranking/scorer.py`, `scrapers/fantacalciopedia.py`, `pipeline/run_scraping.py`, `db/schema.sql`

**Problem:** Due scale confuse in `base`; `fantamedia = 0.0` trattata come misura (202 giocatori).

**Required change:** `fantamedia` mancante → il giocatore non è rankato, è marcato
`insufficient_data`. Zero → `None` alla fonte.

**Implementation details:**
1. `scrapers/fantacalciopedia.py`: `fantamedia = v if v and v > 0 else None`.
2. `CHECK (fantamedia IS NULL OR fantamedia > 0)` (nuova tabella; per l'esistente, `UPDATE ... SET
   fantamedia = NULL WHERE fantamedia = 0` in `_migrate()`).
3. `compute_score`: rimuovere il fallback su `avg_rating`; se `fantamedia is None` → `None`.
4. `enrich_scores` propaga `insufficient_data = True`; `rank_players` li esclude
   dall'ordinamento e li restituisce in una lista separata.
5. `_compute_ranked_role` non li filtra via: li marca, così la dashboard può mostrarli.

**Dependencies:** TASK-001 (per non ritarare due volte).

**Tests required:** portiere senza fantamedia non supera un portiere con fantamedia; nessuna
fantamedia = 0 nel DB; conteggio degli esclusi stabile e riportato.

**Acceptance criteria:**
- Audero non è più il portiere #1.
- I 202 giocatori a fantamedia 0 sono in "dati insufficienti", non in "Da evitare".

---

### TASK-003 — Universo squadre dal database

**Priority:** P0 · **Finding:** P0-006
**Files:** `db/schema.sql`, nuovo `scrapers/teams.py` (o riuso di una fonte esistente),
`dashboard/data_access.py`, `scrapers/pianetafanta.py`

**Problem:** 20 squadre hardcoded in due file, con 3 club di Serie B e senza 3 di Serie A.

**Required change:** Tabella `teams` popolata da scraping, con `season`; nessuna lista hardcoded.

**Implementation details:**
1. Tabella `teams(code, full_name, season, is_promoted)` come in P0-006.
2. `LEAGUE_SEASON` in una nuova configurazione (`config.py` o tabella `league_config`).
3. `is_current_serie_a_team`, `normalize_team_name`, `PROMOTED_TEAMS` leggono da `teams`.
4. `pianetafanta.TEAMS` iterata dalla tabella.
5. Guardia nel pipeline: se le squadre trovate ≠ 20, o differiscono da `teams` per >3 club →
   run fallito con errore.

**Dependencies:** nessuna (parallelizzabile con TASK-001).

**Tests required:** test universo squadre; test guardia che fallisce con 19 o 21 squadre.

**Acceptance criteria:** nessun giocatore di Serie B nel ranking; le 20 squadre corrispondono alla
stagione configurata; nessuna lista squadre hardcoded nel codice.

---

### TASK-004 — Onestà sui dati assenti

**Priority:** P0 · **Finding:** P0-008
**Files:** `ranking/verdict.py`, `ranking/tiers.py`, `dashboard/components.py`, `dashboard/pages/7_Monitoraggio.py`

**Problem:** Assenza di dato presentata come assenza di problema.

**Required change:** Distinguere ovunque "nessun problema" da "nessun dato".

**Implementation details:**
1. `compute_verdict`: se `status is None` → rischio *"Disponibilità non verificata: controlla
   manualmente"*, non silenzio. Se `tier is None` → `stars = None`, headline "Non classificabile".
2. Sezioni forma recente / infortuni / calci piazzati / statistiche avanzate: se la tabella è
   vuota, mostrare "Dato non ancora raccolto" invece di una sezione vuota.
3. `TIER_DESCRIPTIONS[DA_EVITARE]` non deve più promettere il rilevamento degli infortuni.
4. Monitoraggio: tabella con riga per tabella-dati (righe, ultimo aggiornamento, pipeline che la
   popola). Verde/giallo/rosso.

**Dependencies:** nessuna. **Zero rischio, altissimo valore: fattibile subito.**

**Tests required:** verdict senza status non produce "Nessun rischio rilevato"; giocatore senza tier
non ottiene 3 stelle.

**Acceptance criteria:** nessuna schermata afferma o suggerisce l'assenza di un problema quando il
dato corrispondente non esiste.

---

### TASK-004b — Gerarchia portieri per presenze, non per rating

**Priority:** P1 · **Finding:** P1-021 · **Files:** `ranking/goalkeepers.py`, `dashboard/components.py`

**Problem:** `portieri.md` §8 vieta l'ordinamento per rating; il codice ordina per `score`.

**Implementation details:**
1. `sorted(keepers, key=lambda r: (r.get("appearances") or 0, r["score"]), reverse=True)` — Priorità 2
   della spec, con `score` come solo tie-break.
2. Aggiungere i controlli anti-errore di `portieri.md` §13 all'output: numero di squadre, squadre
   con <2 portieri, totale portieri, duplicati. Esporli in UI (la struttura `warnings`/`missing`
   c'è già, va estesa).

**Dependencies:** nessuna. ~5 righe, e corregge un risultato oggi visibilmente sbagliato.

**Tests required:** a parità di score vince chi ha più presenze; i controlli §13 segnalano le
squadre incomplete.

**Acceptance criteria:** Audero non è più titolare del Como; il chart dichiara quante squadre non
raggiungono i 2 portieri.

---

## Phase 2 — Data integrity

### TASK-004c — Trasferimenti: aggiornare invece di duplicare

**Priority:** P0 · **Findings:** P0-010, P0-009 · **Files:** `db/schema.sql`, `db/connection.py`,
`db/repository.py`, `pipeline/run_scraping.py`

**Problem:** La squadra fa parte della chiave del giocatore: un trasferimento crea una riga nuova
(confermato: `Bleve Marco` esiste due volte). Nessun report dei cambiamenti.

**Implementation details:**
1. `identity_key` **senza** la squadra (estende TASK-007): `normalize_name(name)` + `birth_date` da
   `player_anagrafica` quando disponibile.
2. `upsert_player` aggiorna `team` sulla riga esistente; se cambia, scrive in
   `player_transfers(player_id, from_team, to_team, detected_at)`.
3. `players.last_seen_scrape_date`; i giocatori non visti nell'ultimo run **completo** (tutte le
   fonti ok — richiede `scraping_runs`) sono marcati non attivi, **mai cancellati**.
4. Report di fine run `ADDED / REMOVED / TRANSFERRED / UNCHANGED` (`portieri.md` §14) in log e in
   Monitoraggio.
5. Migrazione: fondere i duplicati esistenti (oggi 1 rilevabile — `Bleve Marco`), riassegnando
   quotazioni e metriche all'ID più vecchio.

**Dependencies:** TASK-006 (`scraping_runs`), TASK-007 (`identity_key`).

**Tests required:** un giocatore che cambia squadra mantiene lo stesso `player_id` e lo storico;
compare in `TRANSFERRED`; un giocatore assente non viene cancellato ma marcato non attivo.

**Acceptance criteria:** rieseguendo il pipeline con una squadra cambiata per un giocatore,
`COUNT(*) FROM players` non aumenta.

---

### TASK-005 — Validazione di dominio in ingresso

**Priority:** P0/P1 · **Findings:** S7, P1-005, P1-007, P0-003
**Files:** nuovo `pipeline/validation.py`, `pipeline/run_scraping.py`

**Problem:** Nessun controllo fra scraper e database.

**Required change:** Un unico punto di validazione che ogni `PlayerRecord` deve superare.

**Implementation details:**
```python
def validate_record(record) -> tuple[PlayerRecord, list[str]]:
    """Ritorna il record ripulito e la lista dei problemi trovati.
    I campi non validi diventano None (mai un valore inventato)."""
```
Regole: `role_classic ∈ {P,D,C,A}` (altrimenti record scartato + log);
`role_mantra ∈ MANTRA_CODES` o `None`; `fantamedia ∈ [2.0, 9.5]` o `None`;
`avg_rating ∈ [3.0, 9.0]` o `None`; `appearances ∈ [0, 38]` o `None`;
`price_current > 0` o `None`; `team` presente in `teams` o record scartato.
Ogni scarto → `logger.warning` con fonte, nome, campo, valore, e conteggio aggregato a fine run.

**Dependencies:** TASK-003 (per la validazione squadra).

**Tests required:** uno per regola, con input valido e non valido.

**Acceptance criteria:** nessun valore fuori dominio raggiunge il DB; il log di fine run riporta
gli scarti per fonte e per campo.

---

### TASK-006 — Idempotenza e transazione di run

**Priority:** P1 · **Findings:** P1-016, S2, A6
**Files:** `db/schema.sql`, `db/connection.py`, `db/repository.py`, `pipeline/run_scraping.py`

**Implementation details:**
1. Deduplicare `quotations` in `_migrate()` (`DELETE ... WHERE id NOT IN (SELECT MAX(id) ... GROUP BY
   player_id, source, scrape_date)`), poi creare l'indice `UNIQUE`.
2. `insert_quotation` → `ON CONFLICT DO UPDATE`.
3. Tabella `scraping_runs(id, started_at, finished_at, status, sources_ok, sources_failed, records_written)`.
4. `run_pipeline` avvolge tutto in una transazione; commit unico; su eccezione, rollback e
   `status='failed'`.
5. Rimuovere i `conn.commit()` per riga dal repository (o renderli condizionali).

**Dependencies:** TASK-005 consigliato prima.

**Tests required:** doppia esecuzione → stesso `COUNT(*)`; crash simulato a metà → nessuna scrittura
parziale; `scraping_runs` popolata.

**Acceptance criteria:** `quotations` scende da ~9.327 a ~3.100 righe senza cambiare il ranking;
due run consecutivi lasciano il DB identico.

---

### TASK-007 — Identità stabile del giocatore

**Priority:** P0 · **Finding:** P0-007
**Files:** `db/schema.sql`, `db/connection.py`, `db/repository.py`, `matching/player_matcher.py`, `pipeline/run_scraping.py`

**Implementation details:**
1. `players.identity_key TEXT UNIQUE` = `normalize_name(name) + "|" + normalize_team(team)`.
2. Backfill in `_migrate()` (verificato: 0 collisioni attuali, migrazione sicura).
3. `upsert_player` cerca su `identity_key`.
4. `canonical_name`/`team` scelti in modo deterministico (fonte con `weight_stats` più alto fra le
   presenti, ordine di fallback fisso), non con `max(key=len)`.
5. Guardia: >5% di nuovi giocatori in un run → errore.

**Dependencies:** TASK-003 (alias squadra).

**Tests required:** una fonte assente non crea giocatori nuovi; `identity_key` stabile al variare
dell'ordine dei record.

**Acceptance criteria:** rimuovendo uno scraper e rieseguendo, `COUNT(*) FROM players` non cambia.

---

### TASK-008 — Stagione e campionato sulle statistiche

**Priority:** P0 · **Finding:** P0-004
**Files:** `db/schema.sql`, `db/connection.py`, tutti gli scraper con statistiche, `dashboard/data_access.py`

**Implementation details:**
1. `quotations.stats_season TEXT`, `quotations.stats_competition TEXT`.
2. Ogni scraper le popola; `NULL` se non determinabile.
3. `_weighted_average` sui campi statistici filtra su stagione corrente + `serie_a`; i record con
   `NULL` non entrano nel consenso statistico.
4. `get_all_latest_player_season_stats`: scartare stagioni più vecchie di 2 rispetto alla corrente.

**Dependencies:** TASK-003 (`LEAGUE_SEASON`). Richiede verifica su cosa espone ogni fonte.

**Tests required:** una statistica di un'altra stagione non entra nel consenso; contatore in
Monitoraggio dei giocatori con statistiche di stagione ignota.

**Acceptance criteria:** nessuna statistica non-Serie-A entra nel ranking; Monitoraggio riporta la
copertura per stagione.

---

### TASK-009 — Matching: alias squadra e ambiguità

**Priority:** P1/P2 · **Findings:** D9, D10, D11, P2-016, P2-017, P2-018
**Files:** `matching/player_matcher.py`, `db/schema.sql`

**Implementation details:**
1. Tabella `team_aliases(alias, team_code)`; `normalize_team` la consulta prima del troncamento a 3.
2. Applicare `_initials_conflict` in `match_name_to_player` e `match_name_to_player_any_team`.
3. Se il punteggio migliore è raggiunto da più di un candidato → `None`, **anche sopra**
   `NEAR_EXACT_SCORE`.
4. Ordinare `all_records` deterministicamente prima del grouping.

**Dependencies:** TASK-003.

**Tests required:** "Hellas Verona" == "Verona"; `match_name_to_player("Martinez","Inter",[...])`
→ `None`; grouping invariante allo shuffle.

**Acceptance criteria:** nessun match ambiguo risolto silenziosamente; `match_records` deterministica.

---

## Phase 3 — Metrics

### TASK-010 — Correggere `decision_score` e `confidence`

**Priority:** P1 · **Findings:** P1-001, P1-002
**Files:** `ranking/scorer.py`, `dashboard/data_access.py`

**Implementation details:**
1. Rinominare `_consensus_confidence` → `price_agreement`; formula robusta `1 - min(1, IQR/median)`.
2. Nuovo `data_confidence` (numero fonti, price_agreement, fantamedia reale, confidenza minima di
   match) sulla riga merged.
3. `compute_decision_score`: l'incertezza **aumenta** il rischio effettivo (vedi P1-001).
4. Ritarare la soglia `confidence < 50` in `get_monitoring_data`.

**Dependencies:** TASK-001, TASK-002.

**Tests required:** monotonia (confidenza più alta non deve mai migliorare il punteggio a parità di
resto); `price_agreement` non cala all'aumentare del numero di fonti concordi.

---

### TASK-011 — Consenso su `appearances` e `role_classic`

**Priority:** P1 · **Findings:** P1-006, P1-007
**Files:** `dashboard/data_access.py`, `pipeline/run_scraping.py`

**Implementation details:**
1. Rimuovere `appearances` da `FILLED_FIELDS`; media pesata su `stats_weights`, arrotondata.
2. `role_classic` per voto di maggioranza pesato, tie-break deterministico.
3. Registrare i disaccordi (ruolo e presenze) ed esporli in Monitoraggio.

**Dependencies:** TASK-008.

**Tests required:** presenze discordanti → media pesata attesa; ruoli discordanti → maggioranza +
conflitto registrato.

---

### TASK-011b — Modello di valore moltiplicativo e nuovi arrivi

**Priority:** P1 · **Findings:** P1-020, P1-022, P2-023, P2-024
**Files:** `ranking/scorer.py`, `ranking/tactical_profile.py`

**Problem:** `movimento.md` §21 impone `profilo × titolarità × minutaggio`; il codice è additivo con
la titolarità che pesa 5 punti su 70. E §22 vieta di penalizzare chi non ha storico Serie A.

**Implementation details:**
1. `score = base * 10 * (MIN_STARTER_FLOOR + (1 - MIN_STARTER_FLOOR) * starter_probability) - penalty`,
   `MIN_STARTER_FLOOR ≈ 0.5`.
2. `starter_probability` da `appearances`, con fallback su `predicted_appearances` (già in DB, oggi
   inutilizzato) per chi non ha storico Serie A.
3. Nuovi arrivi: percorso alternativo di `movimento.md` §22 (stagione precedente anche estera, con
   sconto dichiarato per campionato; prezzo di consenso come ultima risorsa), riga marcata
   `estimated` ed **esclusa** dalle metriche prezzo-relative per non creare circolarità.
4. `NEUTRAL_TACTICAL_PROFILE` per ruolo, calcolata come mediana osservata invece che costante 30.
5. `ROLE_MANTRA_BASE` normalizzata dentro ogni reparto su 0-100 (solo dopo P1-005).

**Dependencies:** TASK-002, TASK-008. Da fare **insieme** a TASK-016 (l'LP userà lo stesso
`expected_points` invece di una seconda definizione).

**Tests required:** un giocatore con profilo alto e 5 presenze non supera un titolare equivalente;
un nuovo arrivo senza storico Serie A non finisce in "Da evitare"; nudge tattico medio ≈ 0 per
entrambi i ruoli.

**Acceptance criteria:** Kolo Muani e Gonçalo Ramos escono dal bucket "Evita"; la titolarità
cambia visibilmente l'ordinamento.

---

### TASK-012 — Sanare i termini morti e i doppi conteggi

**Priority:** P1/P2 · **Findings:** P1-008, P1-009, P1-014, M5, M6, M7, M10
**Files:** `ranking/replacement.py`, `ranking/scarcity.py`, `ranking/ideal_squad.py`,
`ranking/scorer.py`, `ranking/tiers.py`, `ranking/verdict.py`, nuovo `ranking/percentile.py`

**Implementation details:**
1. `compute_replacement_level` = N-esimo per score con `N = ROLE_SLOTS[role] * LEAGUE_TEAMS`.
2. Unificare le due scarsità; comparabilità su differenza di score, non su rapporto; contare solo
   le alternative realmente acquistabili.
3. `compute_ideal_score`: un solo termine di qualità (`decision_score`), reliability/form come
   moltiplicatori; correggere il punto neutro della forma a 6.0.
4. Unificare le tre `_percentile_rank` in `ranking/percentile.py` con mid-rank.
5. Coerenza dei default per `appearances is None` (0.5 vs 0.70) — sceglierne uno.
6. `verdict`: `tier is None` → nessuna stella, non 3.

**Dependencies:** TASK-010.

**Tests required:** `replacement_advantage > 0` per una quota ragionevole dei giocatori; premi di
scarsità non nulli e nei range dichiarati; `compute_ideal_score` non contiene `fantasy_value` due
volte; percentile del migliore = 100.

---

## Phase 4 — Ranking / Consensus

### TASK-013 — Materializzare il consenso

**Priority:** P1 · **Findings:** A2, DB1
**Files:** `db/schema.sql`, nuovo `consensus/engine.py`, `pipeline/run_scraping.py`, `dashboard/data_access.py`

**Implementation details:**
1. Spostare `_merge_player_rows`/`_weighted_average`/`_detect_outliers`/`price_agreement` da
   `dashboard/data_access.py` a `consensus/engine.py` (**spostamento, non riscrittura**).
2. Tabella `player_consensus(player_id, scrape_date, price_listino, price_auction, price_basis,
   fantamedia, avg_rating, appearances, source_count, price_agreement, data_confidence)`,
   `UNIQUE(player_id, scrape_date)`.
3. Il pipeline la scrive a fine run; `data_access` la legge.
4. Salvare i pesi usati in `scraping_runs` per la riproducibilità.

**Dependencies:** Fasi 1-3.

**Acceptance criteria:** si può rispondere a "quale era il prezzo di consenso di X il giorno Y".

---

### TASK-014 — Unificare la vista del giocatore

**Priority:** P1 · **Finding:** P1-003
**Files:** `dashboard/data_access.py`

**Implementation details:** estrarre `_build_player_rows(conn, rows, weights, stats_weights)` e
farla usare sia da `_compute_ranked_role` sia da `get_player_detail`.

**Dependencies:** nessuna. **Può essere fatto subito, ~10 righe.**

**Tests required:** il test di coerenza sugli score, reso permanente su tutti i ruoli.

**Acceptance criteria:** zero discrepanze fra pagina ruolo e scheda giocatore.

---

### TASK-015 — Un solo motore di prezzo massimo

**Priority:** P1 · **Finding:** P1-004
**Files:** `ranking/price_engine.py`, `ranking/auction_intelligence.py`, `dashboard/components.py`

**Implementation details:**
1. Ridurre `price_engine` a un indice di efficienza (`value_index`), senza `fair_price`,
   `max_price` né BUY/PASS. Rinominare di conseguenza.
2. L'Auction Intelligence resta l'unico "quanto posso offrire".
3. Rimuovere dalla scheda la didascalia che giustifica la doppia stima.

**Dependencies:** TASK-001, TASK-012. **Da confermare con l'utente prima di implementare** (rimuove
una feature visibile).

---

## Phase 5 — Optimizer

### TASK-016 — Correggere la funzione obiettivo

**Priority:** P0 · **Finding:** P0-005
**Files:** `ranking/lp_optimizer.py`, `dashboard/data_access.py`

**Implementation details:**
1. `expected_points = score_normalizzato_per_ruolo * min(appearances,38)/38`.
2. Score normalizzato per ruolo (z-score) prima di qualunque somma cross-ruolo.
3. Vincolo `<= 3` giocatori per club.
4. Opzionale, da discutere: due obiettivi in sequenza (titolari, poi panchina).

**Dependencies:** TASK-001, TASK-002, TASK-012.

**Tests required:** la rosa ottima contiene almeno un top-10 per ruolo; nessun club con più di 3
giocatori; il giocatore chiaramente migliore e conveniente è sempre selezionato.

**Acceptance criteria:** la rosa prodotta è difendibile davanti a un fantallenatore esperto.

---

### TASK-017 — Correggere slot, costi e diagnostica dell'LP

**Priority:** P1 · **Findings:** P1-013, O5, O6, O7
**Files:** `ranking/lp_optimizer.py`, `dashboard/data_access.py`, `dashboard/pages/5_La_Mia_Rosa.py`

**Implementation details:**
1. `roster_roles` passato esplicitamente; `already_filled` calcolato da lì.
2. Costo dei fissi sempre da `roster_prices`.
3. De-duplicare i candidati per `player_id`; `assert` sui ruoli sovrapposti.
4. `infeasible` con causa esplicita (budget / candidati insufficienti / tutti senza prezzo).
5. `roster_not_in_pool` in output e in UI.
6. 5-10 soluzioni alternative escludendo a turno il giocatore più caro.
7. Correggere il confronto euristica-vs-LP (P1-015) su base comune.

**Dependencies:** TASK-016.

---

### TASK-018 — Budget riservato e max bid sostenibile

**Priority:** P1 · **Findings:** P1-012, P1-010, P1-011
**Files:** `ranking/budget.py`, `ranking/auction_intelligence.py`, `dashboard/data_access.py`

**Implementation details:**
1. `summary["spendable"]`; sostituire `remaining` in tutti i punti di filtro.
2. `max_bid = min(uncapped, realistic_cap)`; niente `max(fair_price, ...)`; flag `affordable`.
3. Guardia su `fair_price is None` prima del calcolo di `alternatives_remaining`.
4. `compute_scarcity_tier` distingue `0` da `None`.

**Dependencies:** nessuna. **Fattibile presto, alto valore d'uso.**

**Tests required:** i tre casi riprodotti in P1-010/P1-011/P1-012.

---

## Phase 6 — Architecture

### TASK-019 — Configurazione di lega centralizzata

**Priority:** P2 · **Finding:** A4
**Files:** nuovo `config.py` o tabella `league_config`, `ranking/budget.py`, `ranking/lp_optimizer.py`, `ranking/auction_intelligence.py`, `dashboard/data_access.py`

`total_credits`, `teams_count`, `role_slots`, `season`, `formation` in un solo posto. Rimuovere i
`500` e i `ROLE_SLOTS` duplicati.

### TASK-020 — Vincoli e pragma del database

**Priority:** P2 · **Findings:** DB4, DB5, DB7, P1-017
**Files:** `db/connection.py`, `db/schema.sql`, `db/repository.py`, `dashboard/pages/5_La_Mia_Rosa.py`

`PRAGMA foreign_keys = ON` (dopo verifica orfani) e `PRAGMA journal_mode = WAL`;
`UNIQUE(player_id)` su `my_roster` con upsert; `add_opponent_pick` upsert;
`remove_roster_entry` + bottone in UI; guardia rosa/avversari mutuamente esclusivi.

### TASK-021 — Rimuovere i doppioni concettuali

**Priority:** P3 · **Finding:** A3
Ridurre a uno: le due scarsità (TASK-012), i due motori di prezzo (TASK-015), le tre
`_percentile_rank` (TASK-012), le due definizioni di inflazione (P2-008). Per ciò che resta
duplicato, documentare esplicitamente perché.

---

## Phase 7 — Testing

### TASK-022 — Test di dominio sul database reale

**Priority:** P1 · **Files:** nuovo `tests/test_domain_invariants.py`

Implementare i test della sezione "Testing Gaps" che girano contro `data/fantacalcio.db`
(marker `@pytest.mark.realdb`, saltati se il file manca). Sono i test che verificano il
**risultato**, non il codice.

### TASK-023 — Monitoraggio di copertura per fonte e campo

**Priority:** P1 · **Findings:** P1-018, S8
**Files:** `pipeline/validation.py`, `dashboard/pages/7_Monitoraggio.py`, `db/schema.sql`

Matrice fonte × campo con % di valori non nulli, soglie configurate per coppia, `logger.error` +
riga rossa in Monitoraggio sotto soglia. **Probabilmente il singolo controllo con il miglior
rapporto valore/costo del documento.**

### TASK-024 — Datare le fixture e aggiungere i test live

**Priority:** P2 · **Finding:** S9
Intestazione con data/URL su ogni fixture; test `@pytest.mark.live` che verificano i selettori dal
vivo, esclusi dal run normale.

---

## Phase 8 — Performance

### TASK-025 — Eliminare l'N+1 sulle note

**Priority:** P2 · **Finding:** P2-007
`repository.get_all_player_notes(conn) -> dict` e uso in `get_ranked_role`. Da 156 a 6 statement
per pagina ruolo.

### TASK-025b — Collegare i dati già raccolti allo scoring

**Priority:** P2 · **Finding:** P2-020 · **Files:** nuovo `ranking/goalkeeper_score.py`,
`ranking/scorer.py`, `dashboard/data_access.py`

**Problem:** `xg`/`xga`/`ppda` (20 squadre), `goals_conceded` (142 righe), `punteggio_fcp` e
`predicted_appearances` (542) sono raccolti, salvati, mostrati — e non entrano in nessuno score.
`rosa-ideale.md` §4 richiede un modello portieri a quattro fattori; ne è implementato uno.

**Implementation details:**
1. `compute_goalkeeper_score(row, team_xga)` con i quattro fattori della spec: titolarità
   (`appearances`), gol subiti (`goals_conceded` per 90), proxy clean sheet (`1/(1+team_xga)`),
   qualità (`avg_rating`). Coefficienti dichiarati, non fittati — come già fatto in `price_engine.py`.
2. Usarlo al posto di `compute_score` per `role_classic == "P"`, dove oggi
   `tactical_profile_score` è `None` e lascia un vuoto.
3. `predicted_appearances` come fallback di `starter_probability` (TASK-011b).
4. Decidere su `punteggio_fcp`: usarlo o smettere di scraparlo. Oggi è puro costo.
5. Attenzione al disallineamento temporale: `team_strength.scrape_date` (27/08) ≠ quotazioni
   (26/08) — dichiararlo, come per TASK-008.

**Dependencies:** TASK-002, TASK-011b.

**Tests required:** un portiere di una difesa solida supera uno di pari fantamedia in una difesa
che subisce molto; nessuno score portiere dipende ancora dal solo `avg_rating`.

---

### TASK-026 — Cache dell'Auction Intelligence coerente col budget

**Priority:** P2 · **Finding:** DA9
Sostituire `ttl=30` con un fingerprint che includa `my_roster` e `opponent_picks`.

### TASK-027 — Foto: cache e throttle

**Priority:** P2 · **Finding:** S5
Saltare `find_photo_url` se il file locale esiste già; `time.sleep` configurabile; una sola
`upsert_player` per giocatore.

---

## Phase 9 — UI

### TASK-028 — Banda di freschezza e salute dei dati

**Priority:** P1 · **Finding:** DA5
In testa a ogni pagina: data dell'ultimo run, fonti riuscite/totali, giocatori valutati, giocatori
esclusi per dati insufficienti.

### TASK-029 — Distinguere misurato da stimato

**Priority:** P1 · **Finding:** DA6
Badge/colore su prezzo (`price_basis`), fantamedia (reale vs assente) e presenze (concordi vs
discordi). Il dato per farlo esiste dopo la Fase 1.

### TASK-030 — Correggere il confronto Rosa Ideale vs LP

**Priority:** P2 · **Finding:** P1-015
Confronto sui soli 11 titolari per entrambi, con il costo totale accanto.

---

# Sonnet Instructions

## Come usare questo documento

Questo documento è il risultato di un audit eseguito sul codice e sul database reali. **Non è una
specifica da implementare alla cieca.**

### Regole operative

1. **Leggi tutto il documento prima di toccare qualsiasi file.** I finding sono interconnessi:
   correggere P0-005 (LP) senza P0-001 (scale di prezzo) produce un risultato sbagliato diverso.

2. **Verifica ogni finding sul codice reale prima di agire.** Ogni finding riporta file, funzione e
   riga. Aprili. Se il codice non corrisponde a quanto descritto, **fermati e segnalalo**: il
   codice può essere cambiato dopo l'audit.

3. **Non implementare nulla di marcato LIKELY o POSSIBLE senza averlo prima confermato.** I finding
   CONFIRMED includono il comando di riproduzione: eseguilo, verifica di ottenere lo stesso
   risultato, poi correggi.

4. **Ordine obbligatorio: prima tutti i P0, poi i P1, poi il resto.** Segui le fasi
   dell'Implementation Plan. Non saltare avanti perché un task sembra più facile.

5. **Rispetta `claude.md`.** In particolare: modifica minima necessaria, nessun refactoring
   cosmetico, nessuna nuova astrazione non richiesta. Se un fix sta in 20 righe, non farne 200. Le
   soluzioni proposte in questo documento sono già dimensionate per questo; se ti trovi a
   introdurre classi, factory o layer di astrazione, **hai frainteso**.

6. **Mantieni la compatibilità dove è possibile.** Aggiungi colonne, non rinominarle. Introduci i
   campi nuovi *accanto* a quelli vecchi, sposta i consumatori, e solo alla fine rimuovi i vecchi.
   `_migrate()` in `db/connection.py` è il posto per le migrazioni idempotenti — è già impostato
   correttamente, usalo.

7. **Scrivi un test per ogni correzione P0/P1, prima della correzione.** Il test deve fallire sul
   codice attuale e passare dopo. Se non fallisce prima, non stai testando ciò che credi.

8. **Esegui `pytest` dopo ogni gruppo di modifiche**, non alla fine. 300 test passano oggi: se ne
   rompi, capisci se il test era sbagliato (probabile per i test numerici sulle metriche) o se hai
   introdotto una regressione. **Non aggiustare un test finché non hai capito quale delle due
   cose è.**

9. **Dopo ogni fase, riesegui i controlli su dati reali** riportati nei finding, e confronta:

   ```bash
   # ranking per ruolo, top 5
   python - <<'EOF'
   import sys, types
   st = types.ModuleType("streamlit")
   st.cache_data = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))
   sys.modules['streamlit'] = st
   from db.connection import get_connection
   from dashboard import data_access as da
   conn = get_connection('data/fantacalcio.db')
   for role in "PDCA":
       for r in da.get_ranked_role(conn, role)[:5]:
           print(role, r['canonical_name'], round(r['score'],1), r['price_current'])
   EOF
   ```

   Salva l'output **prima** di iniziare. Ogni variazione deve essere spiegabile da una correzione
   che hai fatto di proposito. Una variazione che non sai spiegare è una regressione.

10. **Aggiorna la documentazione insieme al codice.** `README.md` (struttura, deploy),
    `db/schema.sql` (i commenti sono ottimi: mantienili accurati), e le docstring — che in questo
    progetto contengono la motivazione delle scelte e sono in più punti **diventate false**
    (P0-008, M5). Una docstring che descrive un comportamento che non esiste è peggio di nessuna
    docstring.

11. **Se una correzione riduce la copertura dei dati** (meno giocatori rankati, meno prezzi), è
    quasi sempre il comportamento corretto: stai smettendo di inventare. **Ma dillo esplicitamente**
    nel report e rendilo visibile in Monitoraggio.

12. **Non nascondere i problemi che non puoi risolvere.** Se una correzione richiede un dato che
    non esiste (es. la vera tassonomia Mantra, o `status`), la risposta corretta è dichiarare
    l'assenza in UI (TASK-004), non inventare un fallback plausibile. Metà dei finding di questo
    documento nasce esattamente da fallback plausibili.

### Da dove partire

Nell'ordine, i primi quattro interventi:

1. **TASK-014** (~10 righe, rischio nullo) — elimina la discrepanza di Fantasy Value fra le pagine.
   Bug visibile all'utente, correzione banale.
2. **TASK-004** (rischio nullo) — smettere di presentare l'assenza di dati come assenza di
   problemi. Non richiede nuovi dati, solo onestà.
3. **TASK-001** (il grosso) — separare le scale di prezzo. **Tutto il resto dipende da questo.**
4. **TASK-002** — eliminare il fallback di scala e le sentinelle zero.

### Cosa NON fare

- Non riscrivere l'architettura. La separazione dei layer è buona e va conservata.
- Non introdurre ORM, dependency injection, event bus, pattern strategy. Nessun finding li richiede.
- Non toccare `dashboard/components.py` (1.812 righe) se non per i finding che lo nominano
  esplicitamente. È grande ma è UI, ed è la parte meno rischiosa del sistema.
- Non "sistemare" i pesi delle fonti a occhio. Sono una scelta dichiarata dell'utente (C2): il
  compito è renderli **verificabili**, non sostituirli con altri numeri altrettanto arbitrari.
- Non rimuovere le guardie di ambiguità del matcher. Funzionano — vanno estese, non tolte.

### Come riportare il lavoro

Per ogni task completato:

```
TASK-NNN — [IMPLEMENTATO | VERIFICATO]
File modificati:
Test aggiunti:
Comando eseguito e output:
Variazioni osservate nel ranking (attese vs inattese):
Problemi residui / limitazioni introdotte:
```

Usa **IMPLEMENTATO** quando il codice è scritto ma non verificato sui dati reali.
Usa **VERIFICATO** solo dopo aver rieseguito i controlli e confrontato l'output.
