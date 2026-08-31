"""'Prova del 9': spot-check di plausibilita' sul vivo.

Sceglie una fonte a caso fra gli scraper di quotazioni (quelli che
espongono fetch() -> list[PlayerRecord], vedi scrapers/base.py), la
interroga DAL VIVO (richiesta HTTP/Playwright reale contro il sito
vero, nessuna fixture), sceglie un giocatore a caso fra i risultati e
fa passare quel singolo record per pipeline.validation.validate_record
- la stessa funzione che la pipeline reale usa prima di scrivere su
quotations - per verificare che ruolo, squadra, fantamedia/avg_rating/
appearances e prezzo rientrino nei range plausibili gia' definiti li'.

Non e' un test automatico da CI (dipende dalla rete e dal markup reale
del sito in quel momento esatto - lo stesso motivo per cui
AUDIT_2026-08-31.md sez. 4.4 non ha potuto verificare pianetafanta.it
da un ambiente cloud): e' uno strumento manuale, da lanciare quando si
vuole un riscontro veloce che un selettore non si sia rotto
silenziosamente sui dati live, oltre a quanto gia' coperto dai test
con fixture congelate.

Uso: python scripts/prova_del_9.py [--source fantacalcio_it] [--seed 42]
"""

import argparse
import os
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import repository
from db.connection import get_connection
from pipeline.validation import (
    APPEARANCES_RANGE,
    AVG_RATING_RANGE,
    FANTAMEDIA_RANGE,
    validate_record,
)
from scrapers.fantacalcio_it import FantacalcioItScraper
from scrapers.fantacalcio_online import FantacalcioOnlineScraper
from scrapers.fantacalciopedia import FantaCalciopediaScraper
from scrapers.fantanalisi import FantanalisiScraper
from scrapers.fantapazz import FantapazzScraper
from scrapers.pianetafanta import PianetaFantaScraper

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fantacalcio.db")

# Solo le fonti che restituiscono list[PlayerRecord] (scrapers/base.py) sono
# comparabili con pipeline.validation.validate_record: fantacalcio_rigoristi
# e fantacalcio_voti hanno una forma dato diversa (rigoristi/voti per
# giornata), fantanalisi_calendario/fantanalisi_squadre restituiscono dati
# per squadra, non per giocatore.
SOURCES = {
    "fantacalcio_it": (FantacalcioItScraper, "https://www.fantacalcio.it"),
    "fantacalcio_online": (FantacalcioOnlineScraper, "https://api.fantacalcio-online.com"),
    "fantacalciopedia": (FantaCalciopediaScraper, "https://www.fantacalciopedia.com"),
    "fantanalisi": (FantanalisiScraper, "https://www.fantanalisi.it"),
    "fantapazz": (FantapazzScraper, "https://www.fantapazz.com"),
    "pianetafanta": (PianetaFantaScraper, "https://www.pianetafanta.it"),
}

RECORD_FIELDS = (
    "name", "team", "role_classic", "role_mantra", "price_current",
    "price_initial", "status", "fantamedia", "avg_rating", "appearances",
    "stats_season", "stats_competition",
)


def _fmt(value):
    return "—" if value is None else value


def main():
    parser = argparse.ArgumentParser(
        description="Prova del 9: prende una fonte e un giocatore a caso dal vivo "
                     "e ne verifica la plausibilita' dei valori.")
    parser.add_argument("--source", choices=sorted(SOURCES), default=None,
                         help="Fonte da interrogare; default: scelta a caso.")
    parser.add_argument("--seed", type=int, default=None,
                         help="Seed random, per rendere ripetibile la scelta fonte+giocatore.")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    source_name = args.source or rng.choice(sorted(SOURCES))
    scraper_cls, base_url = SOURCES[source_name]

    print(f"Fonte scelta: {source_name} ({scraper_cls.__name__})")
    print(f"Base URL: {base_url}")
    print("Interrogo la fonte dal vivo...\n")

    try:
        records = scraper_cls().fetch()
    except Exception as exc:
        print(f"ERRORE durante il fetch dal vivo: {exc!r}")
        print("Puo' voler dire: sito irraggiungibile da questo ambiente, markup "
              "cambiato in modo che nessun selettore piu' matcha, o blocco anti-bot.")
        sys.exit(1)

    if not records:
        print("ATTENZIONE: la fonte non ha restituito alcun giocatore. "
              "Selettore rotto o pagina cambiata (nessuna eccezione, ma 0 righe).")
        sys.exit(1)

    print(f"Ricevuti {len(records)} giocatori dal vivo.")

    record = rng.choice(records)
    print(f"\nArticolo a caso: {record.name} ({record.team}, {record.role_classic})")
    print("-" * 60)
    for field in RECORD_FIELDS:
        print(f"  {field:20s} {_fmt(getattr(record, field, None))}")
    detail_url = record.detail_url
    if detail_url and not detail_url.startswith("http"):
        detail_url = base_url.rstrip("/") + "/" + detail_url.lstrip("/")

    conn = get_connection(DB_PATH)
    try:
        valid_team_codes = repository.get_current_season_team_codes(conn)
        alias_map = repository.get_team_aliases(conn)
    finally:
        conn.close()

    cleaned, problems = validate_record(record, valid_team_codes, alias_map)

    print("\nVerdetto plausibilita' (stessa validazione della pipeline reale, "
          "pipeline/validation.py):")
    if cleaned is None:
        print(f"  SCARTATO — {'; '.join(problems)}")
    elif problems:
        print(f"  Valori fuori range azzerati: {'; '.join(problems)}")
    else:
        print("  Tutti i valori rientrano nei range plausibili (nessuna anomalia rilevata).")

    print(f"\nRange di riferimento: fantamedia {FANTAMEDIA_RANGE}, "
          f"avg_rating {AVG_RATING_RANGE}, appearances {APPEARANCES_RANGE}, "
          f"price_current > 0.")

    if detail_url:
        print(f"\nPer un confronto visivo diretto con la pagina reale: {detail_url}")
    else:
        print(f"\nQuesta fonte non espone una pagina per singolo giocatore: "
              f"per un confronto visivo apri {base_url} e cerca \"{record.name}\".")

    print("\nQuesto e' un controllo manuale (dipende da rete e markup dal vivo), "
          "non sostituisce i test automatici con fixture in tests/.")


if __name__ == "__main__":
    main()
