# Fantacalcio Dashboard

Dashboard Streamlit di supporto all'asta del Fantacalcio: scraping multi-fonte delle quotazioni, matching e consenso ponderato tra fonti, ranking/Fantasy Value per ruolo, e schede giocatore in stile Apple-like con Auction Intelligence, Price Engine e Decision Center.

**App live:** https://lucamercanzin-fantacalcio-dashboardapp-ft0lei.streamlit.app/ (Streamlit Community Cloud, si aggiorna da sola a ogni push su `main`)

## Stack

- **Python 3.11** (`runtime.txt`)
- **Streamlit** — dashboard multipagina
- **SQLite** (stdlib `sqlite3`) — `data/fantacalcio.db`
- **requests + BeautifulSoup4** — scraping HTML
- **pandas** — shaping dati nella dashboard
- **rapidfuzz** — matching nomi giocatore tra fonti
- **PuLP** — ottimizzazione lineare (rosa ideale)
- **Pillow** — analisi immagini (esclusione stemmi/placeholder dalle foto giocatore)
- **Playwright** — scraping di pagine che richiedono un browser
- **pytest** — test suite

## Requisiti

```bash
pip install -r requirements.txt
```

## Sviluppo locale

```bash
streamlit run dashboard/app.py
```

Apri `http://localhost:8501`.

## Aggiornamento dati (scraping)

La pipeline gira in locale, schedulata (vedi [`docs/task_scheduler_setup.md`](docs/task_scheduler_setup.md)):

```bash
python pipeline/scheduled_run.py
```

Esegue in sequenza tutti gli scraper delle quotazioni, il matching tra fonti e lo scoring, scrivendo su `data/fantacalcio.db`. Log in `data/scraping.log`.

Script mirati per dati specifici (foto, infortuni, voti storici, calci piazzati, forza squadra, metriche Fantacalciopedia) sono in `pipeline/run_*.py`.

## Test

```bash
pytest
```

## Deploy

L'app è collegata a **Streamlit Community Cloud** (repo → webhook `share.streamlit.io` → redeploy automatico a ogni push su `main`). Non serve alcuna azione manuale dopo il push, salvo la primissima connessione del repo (già fatta).

## Struttura del progetto

```
dashboard/    # app Streamlit multipagina (pages/, componenti UI, accesso dati)
scrapers/     # un adapter per fonte (fantacalcio.it, Fantacalciopedia, Transfermarkt, ...)
pipeline/     # orchestrazione: scraping → matching → scoring, script pianificati
matching/     # riconciliazione dello stesso giocatore tra fonti diverse (rapidfuzz)
ranking/      # Fantasy Value, Price Engine, scarcity, budget, rosa ideale (PuLP), tier
db/           # schema SQLite, connessione, repository
tests/        # test pytest (uno per scraper/modulo)
fixtures/     # HTML di esempio usati dai test degli scraper
scripts/      # utility standalone (es. simulazione aste)
data/         # database SQLite + foto giocatore (versionati in git)
docs/         # spec e piani di implementazione (storico decisioni)
giocatori/    # note sui criteri di selezione/composizione rosa
grafica/      # specifica visiva della UI (card giocatore Apple-like)
```

## Documentazione

### Visione e roadmap

| File | Contenuto |
|---|---|
| [`visione-progetto.md`](visione-progetto.md) | Visione fondativa del progetto: cosa deve fare la dashboard oltre a mostrare quotazioni, roadmap realistica con le fonti dati attuali. |
| [`impossibile-analisi-avanzata.md`](impossibile-analisi-avanzata.md) | Idee di analisi avanzata (Price Engine su storico multi-stagione, tracking data, Trend Detection) non raggiungibili con le fonti dati attuali — riferimento futuro, non roadmap attiva. |
| [`impossibile-asta-live.md`](impossibile-asta-live.md) | Auction Intelligence in tempo reale che richiederebbe un feed live dell'asta (Nomination Strategy, Real-Time Auction State automatico) — non raggiungibile con un'asta vocale/in presenza. |
| [`impossibile-mlops-governance.md`](impossibile-mlops-governance.md) | Infrastruttura MLOps (model registry, backtesting, A/B testing dei modelli) — sproporzionata per un progetto singolo. |

### Design e piani di implementazione

| File | Contenuto |
|---|---|
| [`docs/superpowers/plans/2026-08-22-fantacalcio-scraper-dashboard.md`](docs/superpowers/plans/2026-08-22-fantacalcio-scraper-dashboard.md) | Piano di implementazione originale: architettura scraper → matching → scoring → dashboard. |
| [`docs/superpowers/specs/2026-08-22-fantacalcio-scraper-design.md`](docs/superpowers/specs/2026-08-22-fantacalcio-scraper-design.md) | Design tecnico dello scraper e della dashboard. |
| [`docs/superpowers/specs/2026-08-25-fcp-metrics-design.md`](docs/superpowers/specs/2026-08-25-fcp-metrics-design.md) | Design delle metriche extra da Fantacalciopedia (pagine dettaglio giocatore). |
| [`docs/superpowers/specs/2026-08-26-price-engine-decision-center-design.md`](docs/superpowers/specs/2026-08-26-price-engine-decision-center-design.md) | Design di Price Engine, Scarcity, Replacement Level, Marginal Squad Value, Decision Center e scraper fantanalisi/squadre. |
| [`docs/superpowers/specs/2026-08-26-ui-nav-tiers-simulation-design.md`](docs/superpowers/specs/2026-08-26-ui-nav-tiers-simulation-design.md) | Design di Rosa Ideale in sidebar, navigazione diretta su Monitoraggio, rivalutazione tier, simulazione aste. |
| [`grafica/grafica.md`](grafica/grafica.md) | Specifica visiva Apple-like della card giocatore (layout, palette, tipografia, micro-interazioni) — implementata in `dashboard/components.py`. |

### Guide operative

| File | Contenuto |
|---|---|
| [`docs/task_scheduler_setup.md`](docs/task_scheduler_setup.md) | Come schedulare `pipeline/scheduled_run.py` con Windows Task Scheduler. |

### Criteri di selezione giocatori/rosa

| File | Contenuto |
|---|---|
| [`giocatori/portieri.md`](giocatori/portieri.md) | Criterio di selezione dei portieri da includere nel dataset (titolare + riserva per squadra). |
| [`giocatori/movimento.md`](giocatori/movimento.md) | Criterio di selezione basato su profilo tattico/offensivo reale, non solo ruolo ufficiale. |
| [`giocatori/rosa-ideale.md`](giocatori/rosa-ideale.md) | Come costruire una rosa ideale: profondità della rosa, gestione di infortuni/rotazioni/turnover. |
