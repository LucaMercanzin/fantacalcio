"""Unico punto di ingresso della pipeline schedulata.

Fino al 31/08/2026 questo script lanciava **solo** i 6 scraper delle
quotazioni. Gli altri undici runner in `pipeline/` erano orfani: esistevano,
avevano i loro test, e nessuno li chiamava mai. Che sette tabelle
(`player_injuries`, `player_set_pieces`, `player_advanced_stats`,
`player_anagrafica`, `player_match_ratings`, `team_fixture_difficulty`,
`player_fantanalisi_valuations`) fossero **tutte** a zero righe non era una
coincidenza: era la conseguenza diretta di questo file
(BACKLOG-2026-08-31 §5).

Adesso ogni runner è dichiarato in `JOBS` con la sua cadenza. Tre proprietà
che il vecchio script non aveva e che qui contano più della completezza:

1. **Isolamento degli errori.** Ogni job gira nel suo try/except. Se
   Transfermarkt risponde 503, gli infortuni falliscono e basta: le
   quotazioni della stessa nottata restano scritte.
2. **Cadenze diverse.** Task Scheduler lancia un comando solo, ma gli
   infortuni vanno aggiornati ogni giorno e l'anagrafica quasi mai. La
   cadenza è dichiarata qui e ricordata in `pipeline_job_runs`.
3. **Il fallimento non consuma la cadenza.** Solo un run riuscito aggiorna
   `last_success_at`, quindi un job che fallisce resta scaduto e viene
   ritentato al giro dopo invece di essere saltato per una settimana.

Uso:

    python pipeline/scheduled_run.py              # tutti i job scaduti
    python pipeline/scheduled_run.py --list       # cosa girerebbe, e perché
    python pipeline/scheduled_run.py --only injuries set_pieces
    python pipeline/scheduled_run.py --only injuries --force
"""

import argparse
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

# Task Scheduler e README lanciano `python pipeline/scheduled_run.py`, che
# mette `pipeline/` su sys.path e non la radice del progetto: senza questa
# riga gli import qui sotto falliscono con ModuleNotFoundError: No module
# named 'db'. Stesso bootstrap di dashboard/app.py, per la stessa ragione.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import repository
from db.connection import get_connection, init_db
from pipeline import (
    run_fantanalisi_valuations,
    run_fcp_metrics,
    run_fixture_difficulty,
    run_historical_prices,
    run_injuries,
    run_match_ratings,
    run_photos_transfermarkt,
    run_player_advanced_stats,
    run_player_anagrafica,
    run_set_pieces,
    run_team_strength,
)
from pipeline.run_scraping import run_pipeline
from scrapers.fantacalcio_it import FantacalcioItScraper
from scrapers.fantacalcio_online import FantacalcioOnlineScraper
from scrapers.fantacalciopedia import FantaCalciopediaScraper
from scrapers.fantanalisi import FantanalisiScraper
from scrapers.fantapazz import FantapazzScraper
from scrapers.pianetafanta import PianetaFantaScraper

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
PHOTOS_DIR = os.path.join(BASE_DIR, "data", "photos")
LOG_PATH = os.path.join(BASE_DIR, "data", "scraping.log")


@dataclass(frozen=True)
class Job:
    """Un runner della pipeline più la sua cadenza.

    `every_days` è un minimo, non un appuntamento: il job gira al primo run
    dello scheduler in cui sono passati almeno tanti giorni dall'ultimo
    successo. Se la macchina resta spenta una settimana, al riavvio parte
    tutto quello che nel frattempo è scaduto — una volta sola, non sette.
    """

    name: str
    every_days: int
    run: Callable
    why: str


def _run_quotations(conn) -> dict:
    """I 6 scraper delle quotazioni: l'unica cosa che lo scheduler faceva
    prima del 31/08/2026, e l'unica che deve girare per prima — popola
    `players`, a cui tutti gli altri job si agganciano per player_id."""
    scrapers = [
        FantacalcioItScraper(), FantaCalciopediaScraper(), FantapazzScraper(),
        PianetaFantaScraper(), FantacalcioOnlineScraper(), FantanalisiScraper(),
    ]
    return run_pipeline(scrapers, conn, PHOTOS_DIR, date.today().isoformat())


# L'ordine è quello di esecuzione: le quotazioni per prime perché creano e
# riattivano i giocatori; tutto il resto si aggancia a quei player_id.
JOBS = (
    Job("quotations", 1, _run_quotations,
        "prezzi e anagrafica base: è il cuore, tutto il resto vi si aggancia"),
    Job("match_ratings", 1, run_match_ratings.run,
        "i voti dell'ultima giornata giocata cambiano ogni turno"),
    Job("injuries", 1, run_injuries.run,
        "lo stato fisico è la cosa che invecchia più in fretta di tutte"),
    Job("set_pieces", 7, run_set_pieces.run,
        "rigoristi e punizioni: gerarchie che cambiano di rado ma pesano molto"),
    Job("fantanalisi_valuations", 7, run_fantanalisi_valuations.run,
        "fair price e max bid di una fonte terza, utili come contraddittorio"),
    Job("player_advanced_stats", 7, run_player_advanced_stats.run,
        "statistiche avanzate per giocatore, stabili nel breve"),
    Job("fixture_difficulty", 7, run_fixture_difficulty.run,
        "difficoltà del calendario: si muove col procedere della stagione"),
    Job("team_strength", 7, run_team_strength.run,
        "forza squadra: idem, ha senso ricalcolarla settimanalmente"),
    Job("fcp_metrics", 7, run_fcp_metrics.run,
        "investment stability / injury resistance, 5s di delay per pagina"),
    Job("photos", 30, run_photos_transfermarkt.run,
        "le foto cambiano solo con i trasferimenti"),
    Job("anagrafica", 30, run_player_anagrafica.run,
        "età, piede, altezza: praticamente immutabili a stagione in corso"),
    Job("historical_prices", 90, run_historical_prices.run,
        "listini delle stagioni passate: per definizione non cambiano più"),
)

JOBS_BY_NAME = {job.name: job for job in JOBS}


def is_due(job: Job, last_success_at: str | None, today: date) -> bool:
    """Un job mai riuscito è sempre scaduto. `last_success_at` è un timestamp
    ISO completo ma qui conta solo il giorno: la cadenza è in giorni, e
    confrontare gli orari renderebbe l'esito dipendente dall'ora in cui Task
    Scheduler è configurato."""
    if not last_success_at:
        return True
    return (today - date.fromisoformat(last_success_at[:10])).days >= job.every_days


def select_jobs(only: list | None, force: bool, job_runs: dict, today: date) -> list:
    """Restituisce (job, motivo) per ogni job da eseguire, nell'ordine di
    `JOBS`. `--only` restringe l'insieme ma non salta la cadenza: per quello
    serve `--force`, così `--only injuries` due volte nello stesso giorno non
    ri-scarica 838 pagine per sbaglio."""
    candidates = JOBS if not only else [JOBS_BY_NAME[name] for name in only]
    selected = []
    for job in candidates:
        last_success = (job_runs.get(job.name) or {}).get("last_success_at")
        if force:
            selected.append((job, "forzato"))
        elif is_due(job, last_success, today):
            selected.append((job, "mai eseguito" if not last_success
                             else f"ultimo successo {last_success[:10]}"))
    return selected


def run_jobs(conn, jobs_to_run: list) -> dict:
    """Esegue i job in sequenza, ognuno isolato. Ritorna il conteggio
    ok/falliti: è il valore che finisce nel log a fine run e che rende
    verificabile a colpo d'occhio se la nottata è andata bene."""
    ok, failed = 0, 0
    for job, reason in jobs_to_run:
        started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        logger.info("Job %s: avvio (%s)", job.name, reason)
        repository.record_pipeline_job_run(conn, job.name, started_at, "running")
        try:
            result = job.run(conn)
        except Exception as exc:
            failed += 1
            logger.exception("Job %s: fallito", job.name)
            repository.record_pipeline_job_run(
                conn, job.name, started_at, "failed", f"{type(exc).__name__}: {exc}",
            )
            continue
        ok += 1
        detail = str(result) if result is not None else None
        logger.info("Job %s: ok %s", job.name, detail or "")
        repository.record_pipeline_job_run(
            conn, job.name, started_at, "ok", detail,
            success_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
    return {"ok": ok, "failed": failed}


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--only", nargs="+", metavar="JOB", choices=sorted(JOBS_BY_NAME),
        help="esegui solo questi job (rispettando comunque la cadenza)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="ignora la cadenza ed esegui comunque i job selezionati",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="mostra cadenza, ultimo successo e cosa girerebbe adesso, senza eseguire",
    )
    return parser.parse_args(argv)


def sweep_interrupted(conn, job_runs: dict) -> list:
    """Marca come 'interrotto' i job rimasti 'running' da un processo morto.

    Un job scrive 'running' quando parte e lo sovrascrive quando finisce: se
    il processo viene ucciso nel mezzo — Ctrl+C, la macchina che si spegne,
    il task che viene fermato — quel 'running' resta in tabella per sempre e
    continua a raccontare che il job sta girando. È successo due volte in un
    giorno (player_advanced_stats e injuries, 01/09/2026).

    La regola è netta e non euristica: `scheduled_run.py` è l'unico punto di
    ingresso della pipeline e non è previsto che due istanze girino insieme
    (vedi docs/task_scheduler_setup.md — un'unica attività giornaliera), per
    cui **se questo processo sta partendo adesso, nessun job di un processo
    precedente può essere ancora in corso**. Va fatto all'avvio, prima che
    run_jobs scriva i propri 'running', o cancellerebbe quelli veri.

    Restituisce i nomi ripuliti, così il chiamante può dirlo invece di
    correggere il dato in silenzio."""
    stale = [name for name, run in job_runs.items() if run.get("last_status") == "running"]
    for name in stale:
        run = job_runs[name]
        repository.record_pipeline_job_run(
            conn, name, run.get("last_started_at") or "", "interrotto",
            "processo terminato prima della fine del job",
        )
        run["last_status"] = "interrotto"
        logger.warning("Job %s era rimasto 'running': marcato interrotto", name)
    return stale


def _print_status(job_runs: dict, today: date) -> None:
    due = {job.name for job, _ in select_jobs(None, False, job_runs, today)}
    print(f"{'job':<24} {'ogni':>6}  {'ultimo successo':<19} {'stato':<11} scaduto")
    for job in JOBS:
        run = job_runs.get(job.name) or {}
        last = (run.get("last_success_at") or "-")[:19]
        print(f"{job.name:<24} {job.every_days:>4}g  {last:<19} "
              f"{run.get('last_status') or '-':<11} {'SI' if job.name in due else 'no'}")


def main(argv=None) -> None:
    args = _parse_args(argv)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    try:
        job_runs = repository.get_pipeline_job_runs(conn)
        today = date.today()
        # Prima di qualsiasi cosa: nessun job di un processo precedente
        # può essere ancora in corso se questo sta partendo adesso.
        for name in sweep_interrupted(conn, job_runs):
            print(f"Job {name}: era rimasto 'running' da un run terminato male, "
                  f"marcato interrotto.")
        if args.list:
            _print_status(job_runs, today)
            return
        jobs_to_run = select_jobs(args.only, args.force, job_runs, today)
        if not jobs_to_run:
            logger.info("Nessun job scaduto")
            print("Nessun job scaduto.")
            return
        summary = run_jobs(conn, jobs_to_run)
    finally:
        conn.close()
    logger.info("Run completo: %d ok, %d falliti", summary["ok"], summary["failed"])
    print(f"Run completo: {summary['ok']} ok, {summary['failed']} falliti.")


if __name__ == "__main__":
    main()
