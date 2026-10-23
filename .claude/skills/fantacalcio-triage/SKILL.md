---
name: fantacalcio-triage
description: Diagnosi di problemi nel progetto Fantacalcio — dati errati, mancanti o vecchi, giocatori duplicati o spariti, prezzi e punteggi incoerenti, rosa ottimale non valida o fuori budget, dato giusto mostrato male nella dashboard. Separa pipeline dati, ranking/ottimizzatore e interfaccia prima di proporre un fix. Non usarla per feature nuove o lavoro solo grafico (per lo stile della dashboard c'è developing-with-streamlit).
---

# Triage Fantacalcio

## 1. Classifica il sintomo prima di aprire il codice
| Livello | Segnali | Dove guardare |
| --- | --- | --- |
| Dati / pipeline | valori mancanti o vecchi, duplicati, giocatori usciti ancora presenti, job fallito | `python pipeline/scheduled_run.py --list`, tabella `pipeline_job_runs`, `data/scraping.log`, `scrapers/`, `matching/`, `consensus/` |
| Ranking / ottimizzatore | punteggi incoerenti tra viste, rosa non fattibile, budget sforato | `ranking/` (`lp_optimizer.py`, `budget.py`, `price_engine.py`, `scorer.py`), `config.py` |
| Interfaccia | dato corretto nel DB ma mostrato male, cache non aggiornata | `dashboard/` (`data_access.py`, `components.py`, `player_detail.py`, `pages/`) |

Conferma il livello con una query o un test prima di correggere: un errore visibile a valle nasce spesso a monte. Un fix nella UI che nasconde un dato sbagliato non è un fix.

## 2. Invarianti (fonte: codice attuale — riverificali se cambiano)
- Budget e slot vivono solo in `config.py`: `TOTAL_CREDITS` (oggi 500) e `ROLE_SLOTS` (oggi P3 / D8 / C8 / A6). Non ridefinirli altrove.
- `CURRENT_SEASON` deriva dalla data odierna ed è sovrascrivibile con `FANTACALCIO_SEASON`.
- L'ottimizzatore è un problema PuLP binario in `ranking/lp_optimizer.py`: se lo stato non è `Optimal` restituisce una rosa vuota, quindi distingui "infeasible" da "dati mancanti".
- Invarianti eseguibili in `tests/test_domain_invariants.py`: prezzo ≤ budget, score coerente tra dettaglio e ranking, fantamedia nel dominio Serie A, squadre coerenti con la stagione, rosa ottimale fattibile, titolari presenti nel ranking.

## 3. Verifica riproducibile
- Test mirato: `pytest tests/test_<modulo>.py -q`
- Invarianti sul DB reale: `pytest tests/test_domain_invariants.py -m realdb -q` (saltati se manca `data/fantacalcio.db`)
- Selettori contro il sito vivo, solo se serve: `pytest -m live tests/test_<scraper>_scraper.py`
- Stato e cadenze dei job: `python pipeline/scheduled_run.py --list`. `--only <job>` e soprattutto `--force` scrivono nel DB: dichiaralo prima di eseguirli.
- Preferisci le fixture in `fixtures/` e i test esistenti a esperimenti manuali sul DB.

## 4. Vincoli
- `data/fantacalcio.db` e `data/photos/` sono tracciati in Git e la dashboard su Streamlit Cloud si aggiorna dal push su `main`: nessuna modifica al DB committata senza dirlo esplicitamente.
- Dati estratti da fonti esterne: confronta tu la pagina sorgente campo per campo (memoria di progetto "Scraper cross-check").
- Nel resoconto separa: livello della causa, fix, test eseguiti, dati da rigenerare.
