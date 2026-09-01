"""Perché quel giocatore non ha un prezzo di consenso — e quali di quei casi
sono un errore di identità invece che un giocatore marginale.

Il backlog (BACKLOG-2026-08-31 §4) poneva la domanda giusta senza la
risposta: "sono giocatori marginali (allora va bene così) o è un problema di
matching che li stacca dalle loro quotazioni?". Sui dati del 31/08 la
risposta è **entrambe le cose, in proporzioni molto diverse per gravità**:

- ~36 sono davvero marginali: primavera e riserve che solo
  fantacalcio_online elenca, senza prezzo su nessuna fonte. Restare fuori
  da ranking e optimizer è il comportamento corretto, non un bug.
- ~24 sono **identità spezzate**, e fra loro ci sono titolari veri
  (Di Gregorio, Perin, Lukaku, Angelino, Nkunku, Gutierrez, Circati). Una
  fonte li chiama col solo cognome ("Nkunku"), un'altra col nome completo
  ("Nkunku Christopher"): due `identity_key` diversi, due righe in
  `players`, e la riga nuova vede una fonte sola — sotto il minimo di due
  fonti reali che serve per un prezzo di consenso. Il dato delle altre
  cinque fonti resta attaccato alla riga vecchia, che nel frattempo è stata
  marcata inattiva.

**Perché questo script esiste invece di una correzione automatica nella
pipeline.** `db/repository.upsert_player` documenta questo identico caso
come limite noto e rinviato: un prototipo che risolveva la cosa col fuzzy
matching è stato provato e *revertito*, perché univa in silenzio giocatori
diversi con nomi simili. Rifarlo dentro la pipeline a ridosso di un'asta
significherebbe riportare quel rischio in produzione. Qui la regola è molto
più stretta del fuzzy matching — stessa squadra, e i token del nome corto
devono essere un prefisso esatto di quelli del nome lungo, con un solo
candidato possibile — e soprattutto non gira da sola: il default è
guardare, e il merge si chiede.

    python scripts/diagnose_missing_prices.py            # solo diagnosi
    python scripts/diagnose_missing_prices.py --merge    # unisce le identità spezzate
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection, merge_players
from matching.player_matcher import normalize_name, normalize_team

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")


def _tokens(name: str) -> list:
    return normalize_name(name).split()


def find_split_identity(player: dict, all_players: list) -> dict | None:
    """La riga più vecchia che è quasi certamente la stessa persona, o None.

    Tre condizioni, tutte necessarie, e volutamente più severe di una
    somiglianza fuzzy:

    1. stessa squadra normalizzata — un cognome uguale in due squadre
       diverse sono due persone finché non si dimostra il contrario;
    2. i token del nome più corto sono un **prefisso** di quelli del più
       lungo ("nkunku" ⊂ "nkunku christopher"), non un sottoinsieme sparso
       né una distanza di edit: "Nkunku" e "Nkunké" restano distinti;
    3. il candidato è **uno solo**. Due omonimi nella stessa squadra fanno
       fallire la regola invece di farla scegliere — è esattamente il caso
       su cui il prototipo fuzzy revertito sbagliava.

    Il candidato deve anche essere più vecchio (id minore): la riga nuova è
    quella nata dallo scrape che ha cambiato forma al nome, e la storia sta
    su quella vecchia.
    """
    my_tokens = _tokens(player["canonical_name"])
    my_team = normalize_team(player["team"] or "")
    if not my_tokens or not my_team:
        return None

    candidates = []
    for other in all_players:
        if other["id"] >= player["id"]:
            continue
        if normalize_team(other["team"] or "") != my_team:
            continue
        other_tokens = _tokens(other["canonical_name"])
        short, long_ = sorted((my_tokens, other_tokens), key=len)
        if short and short != long_ and long_[:len(short)] == short:
            candidates.append(other)

    return candidates[0] if len(candidates) == 1 else None


def diagnose(conn, scrape_date: str) -> dict:
    unpriced = [dict(r) for r in conn.execute(
        """
        SELECT p.id, p.canonical_name, p.team, p.role_classic,
               (SELECT COUNT(*) FROM quotations q
                 WHERE q.player_id = p.id AND q.scrape_date = ?
                   AND q.price_current IS NOT NULL) AS priced_sources
        FROM player_consensus pc JOIN players p ON p.id = pc.player_id
        WHERE pc.scrape_date = ? AND pc.price_basis IS NULL AND p.active = 1
        ORDER BY p.role_classic, p.canonical_name
        """,
        (scrape_date, scrape_date),
    )]
    all_players = [dict(r) for r in conn.execute(
        "SELECT id, canonical_name, team FROM players ORDER BY id"
    )]

    split, marginal, single_source = [], [], []
    for player in unpriced:
        candidate = find_split_identity(player, all_players)
        if candidate is not None:
            split.append((player, candidate))
        elif player["priced_sources"] == 0:
            marginal.append(player)
        else:
            single_source.append(player)
    return {"split": split, "marginal": marginal, "single_source": single_source}


def _report(result: dict) -> None:
    split, marginal, single = result["split"], result["marginal"], result["single_source"]
    print(f"\nIDENTITÀ SPEZZATE — {len(split)}")
    print("  Stessa persona su due righe: la riga nuova vede una fonte sola.")
    for player, candidate in split:
        print(f"    {player['canonical_name'][:26]:<27}({player['team'][:10]:<10}) id={player['id']}"
              f"  <-  id={candidate['id']} {candidate['canonical_name'][:26]} ({candidate['team']})")

    print(f"\nMARGINALI — {len(marginal)}")
    print("  Nessuna fonte pubblica un prezzo: primavera e riserve. Corretto così.")
    for player in marginal[:10]:
        print(f"    {player['canonical_name'][:26]:<27}({player['team'][:10]:<10}) {player['role_classic']}")
    if len(marginal) > 10:
        print(f"    ... e altri {len(marginal) - 10}")

    print(f"\nUNA SOLA FONTE, NESSUN CANDIDATO — {len(single)}")
    print("  Prezzo su una fonte sola e nessuna riga gemella: da guardare a mano.")
    for player in single:
        print(f"    {player['canonical_name'][:26]:<27}({player['team'][:10]:<10}) {player['role_classic']}")
    print()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--merge", action="store_true",
                        help="unisci le identità spezzate nella riga più vecchia")
    parser.add_argument("--date", help="scrape_date da analizzare (default: l'ultimo)")
    args = parser.parse_args(argv)

    conn = get_connection(DB_PATH)
    scrape_date = args.date or conn.execute(
        "SELECT MAX(scrape_date) FROM player_consensus"
    ).fetchone()[0]
    print(f"Diagnosi prezzi mancanti — scrape_date {scrape_date}")

    result = diagnose(conn, scrape_date)
    _report(result)

    if args.merge and result["split"]:
        for player, candidate in result["split"]:
            merge_players(conn, candidate["id"], player["id"])
            print(f"  unito {player['canonical_name']} (id={player['id']}) "
                  f"in id={candidate['id']}")
        conn.commit()
        print(f"\n{len(result['split'])} identità unite. Rilancia la "
              f"materializzazione del consenso per vedere i prezzi aggiornati:")
        print("  python -c \"from db.connection import get_connection; "
              "from pipeline.run_scraping import _materialize_consensus; "
              f"c=get_connection('data/fantacalcio.db'); _materialize_consensus(c,'{scrape_date}')\"")
    elif result["split"]:
        print("Nessuna modifica fatta. Per unirle: --merge")
    conn.close()


if __name__ == "__main__":
    main()
