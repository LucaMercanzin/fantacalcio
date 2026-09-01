import logging
import os
from datetime import date

from db import repository
from db.connection import get_connection, init_db
from matching.player_matcher import match_name_to_player
from scrapers.fantanalisi import FantanalisiScraper
from scrapers.fantanalisi_giocatore import FantanalisiGiocatoreScraper

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "player_advanced_stats.log")

SOURCE = "fantanalisi"


def _already_done_today(conn, scrape_date: str) -> set:
    """player_id già scritti oggi da questa fonte. UNIQUE(player_id, source,
    scrape_date) rende la scrittura idempotente, quindi rifarli non
    sbaglierebbe niente — costerebbe solo un'altra navigazione Playwright a
    testa, che è tutto il costo di questo run."""
    return {
        row[0] for row in conn.execute(
            "SELECT player_id FROM player_advanced_stats WHERE source = ? AND scrape_date = ?",
            (SOURCE, scrape_date),
        )
    }


def run(conn) -> dict:
    """Ogni giocatore viene scritto appena la sua pagina è stata letta, non
    alla fine di tutte e ~500.

    Il motivo è concreto: la scansione dura decine di minuti con Playwright,
    e nella versione precedente il database restava intatto finché non
    finiva. Un'interruzione a metà — è successo il 01/09/2026 — lasciava
    `player_advanced_stats` a **zero righe** dopo 45 minuti di lavoro. Ora un
    run interrotto conserva quello che ha già letto, e quello successivo
    riparte dai soli giocatori che mancano."""
    records = FantanalisiScraper().fetch()
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]
    today = date.today().isoformat()
    done = _already_done_today(conn, today)

    # Il matching gira prima dello scraping, non dopo: sapere a quale
    # player_id corrisponde una pagina è ciò che permette di saltarla se
    # quel giocatore è già a posto, ed è l'unico modo di non ripagare le
    # navigazioni già fatte in un run interrotto.
    unmatched = []
    todo = {}
    for record in records:
        if not record.detail_url:
            continue
        player = match_name_to_player(record.name, record.team, players)
        if player is None:
            unmatched.append(record.name)
            logger.info("No match for %s (%s)", record.name, record.team)
            continue
        if player["id"] in done:
            continue
        todo[record.detail_url] = (record, player)

    if done:
        logger.info("Ripresa: %d giocatori già scritti oggi, ne restano %d",
                    len(done), len(todo))

    matched = 0
    failed = 0
    for detail_url, percentiles in FantanalisiGiocatoreScraper().iter_many(list(todo)):
        record, player = todo[detail_url]
        if percentiles is None:
            failed += 1
            logger.error("Detail fetch failed for %s", record.name)
            continue
        # Una riga con tutti i percentili a NULL viene scritta lo stesso, e
        # non è un errore: fantanalisi pubblica "n.d." per i portieri (che un
        # radar xG/xA non ce l'hanno) e per chi non ha abbastanza dati
        # Understat — verificato sulla pagina live di Soulé, dove le sei
        # metriche sono letteralmente "n.d.". Su 505 righe sono 188, di cui
        # 62 portieri. Serve scriverle per due ragioni: dicono "guardato
        # oggi, la fonte non ha niente" invece di "mai guardato", e sono ciò
        # che permette a _already_done_today di non riaprire quelle 188
        # pagine a ogni ripresa. A valle si comportano come una riga assente,
        # perché ogni consumatore controlla i singoli campi.
        repository.insert_player_advanced_stats(
            conn, player["id"], percentiles["xg90_percentile"],
            percentiles["xa90_percentile"], percentiles["shots90_percentile"],
            percentiles["key_passes90_percentile"], percentiles["involvement_percentile"],
            percentiles["minutes_percentile"], SOURCE, today,
        )
        matched += 1

    return {
        "matched": matched, "skipped": len(done), "failed": failed, "unmatched": unmatched,
    }


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    result = run(conn)
    conn.close()
    logger.info(
        "Advanced stats run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
