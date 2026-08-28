# Scheda Giocatore — Dati Esterni (Anagrafica, xG/xA, Calendario) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the three remaining `statistiche giocatore` gaps that need data this project doesn't have yet — anagrafica (età/altezza/piede/nazionalità/numero maglia), player-level xG/xA (and related per-90 percentiles), and fixture-difficulty per team — by extending the two external sources already integrated (Transfermarkt, Fantanalisi), not adding a new site.

**Architecture:** Every source URL and HTML shape below was verified live this session (not guessed): the Transfermarkt player-profile page is server-rendered (plain `requests`+BeautifulSoup, exactly how `scrapers/transfermarkt.py` already fetches it for the photo) and exposes anagrafica via `itemprop` microdata + an `info-table__content` key/value table; the Fantanalisi player-detail page (`/giocatori/{id}-{slug}`) is a JS-rendered Next.js app (needs Playwright, exactly how `scrapers/fantanalisi_squadre.py` already scrapes `/squadre`) whose per-90 percentile radar renders as `<circle><title>{Name} — {Metric}: {N}° percentile</title></circle>` inside an SVG; the Fantanalisi calendario page (`/calendario`) is the same Next.js pattern and exposes a ranked "prime 5 giornate" softness score (0-100) per team as `<button><span class="truncate">{Team}</span>...<span class="num">{score}</span></button>` under a `.card` headed "Chi parte in discesa" (attack-facing) with a second toggle button for the defense-facing view. Each of the three follows the codebase's existing two-phase scraper pattern (`scrapers/fantacalciopedia.py` + `pipeline/run_fcp_metrics.py`: a listing scrape that captures a `detail_url` per row via `PlayerRecord.detail_url` — already a field on `PlayerRecord`, unused by `scrapers/fantanalisi.py` today — then a per-record detail fetch) or the single-page pattern (`scrapers/fantanalisi_squadre.py` + `pipeline/run_team_strength.py`), reusing the historicized-table convention (`team_strength`) or the upsert-in-place convention (`player_transfermarkt_ids`) depending on whether the data changes over the season.

**Tech Stack:** Python 3.11, Playwright (Fantanalisi, JS-rendered), `requests`+BeautifulSoup4 (Transfermarkt, server-rendered — via `scrapers/base.py`), sqlite3, pytest.

## Global Constraints

- **Scope is exactly**: anagrafica (Transfermarkt), player-level per-90 percentiles (Fantanalisi), team fixture-difficulty for the "prime 5 giornate" window, both attack-facing and defense-facing (Fantanalisi). **Squalifiche (suspensions) as a distinct entity is explicitly OUT of scope** — no clean source was found (Transfermarkt's `/verletzungen/` table is injuries only); do not invent one.
- **Do not scrape Fantanalisi's own proprietary computed valuations** if encountered on these pages (Fair Price, Expected Price, Max Bid, Tier badge, Risk badge, VORP, "Player Type" labels like "Esplosivo"). This project computes its own equivalents (`ranking/scorer.py`, `ranking/tiers.py`, `ranking/verdict.py`) — pull only the raw/factual fields this plan names.
- **robots.txt compliance already verified**: `fantanalisi.it/robots.txt` allows `/giocatori`, `/squadre`, `/calendario` (only blocks logged-in-user interactive paths: `/api/`, `/asta`, `/piano`, `/prepara`, `/strategia`, `/squadra` singular, `/simulazione`, `/riparazione`, `/stagione`, `/leghe`, `/impostazioni`, `/profilo`, `/import`, `/confronta`). `transfermarkt.it/robots.txt` only blocks the `wget` user-agent and allows everyone else — `scrapers/transfermarkt.py` already operates within this.
- **Rate limiting**: follow `pipeline/run_injuries.py`'s and `pipeline/run_fcp_metrics.py`'s existing convention — a `time.sleep(REQUEST_DELAY_SECONDS)` after every per-player request, module-level constant, 1.5-5s depending on source (Playwright page navigations are already slow; use 1.5s. `requests`-based Transfermarkt calls: match `run_injuries.py`'s existing 1.5s).
- **Never invent a value**: if a field isn't present on the page for a given player (e.g. a neopromossa team with no percentile history, a player with no Transfermarkt match), store `None` — do not guess or default to a placeholder number. This mirrors `scrapers/fantanalisi_squadre.py`'s existing "squadra neopromossa → xg/xga/ppda stay None" behavior.
- **`db/schema.sql`**: new tables only, via `CREATE TABLE IF NOT EXISTS` — no ALTER TABLE, no migration script needed (see `db/connection.py:27`'s comment: this is exactly why new columns on *existing* tables would need special handling, but these are brand-new tables, which `CREATE TABLE IF NOT EXISTS` safely adds to any existing database on next `init_db()`).
- **Matching to existing players**: reuse `matching.player_matcher.match_name_to_player` (already used by `pipeline/run_fcp_metrics.py`) for the Fantanalisi tasks, and the existing `repository.get_transfermarkt_id`/`upsert_transfermarkt_id` + `scrapers.transfermarkt.search_player_id` (already used by `pipeline/run_injuries.py`) for the Transfermarkt task. Do not write a third matching mechanism.
- Match existing repo conventions: one test file per new module (`tests/test_<module>.py`), scraper `parse_*` functions are pure (take pre-shaped Python data, not live HTML/DOM) so they're testable without Playwright or network — see `tests/test_fantanalisi_squadre_scraper.py` for the exact shape to follow.

---

## File Structure

- Modify: `db/schema.sql` — 3 new tables: `player_anagrafica`, `player_advanced_stats`, `team_fixture_difficulty`.
- Modify: `db/repository.py` — CRUD functions for the 3 new tables.
- Modify: `scrapers/transfermarkt.py` — new `parse_player_profile(html)` + `fetch_player_profile(transfermarkt_id)`.
- Modify: `scrapers/fantanalisi.py` — populate the already-existing-but-unused `PlayerRecord.detail_url` field.
- Create: `scrapers/fantanalisi_giocatore.py` — per-player percentile-radar scraper.
- Create: `scrapers/fantanalisi_calendario.py` — team fixture-difficulty scraper.
- Create: `pipeline/run_player_anagrafica.py`, `pipeline/run_player_advanced_stats.py`, `pipeline/run_fixture_difficulty.py`.
- Modify: `dashboard/data_access.py` — `get_player_extra` (anagrafica), `get_player_detail` (advanced stats), a new `get_fixture_difficulty(conn, team)`.
- Modify: `dashboard/components.py` — `render_player_detail` (anagrafica line + percentile block, near the existing tier caption and role-comparison block) and the team-info area (fixture difficulty).

---

### Task 1: Schema and repository functions for the 3 new tables

**Files:**
- Modify: `db/schema.sql`
- Modify: `db/repository.py`
- Test: `tests/test_db_repository.py`

**Interfaces:**
- Produces: `repository.upsert_player_anagrafica(conn, player_id, birth_date, height_cm, foot, nationality, shirt_number, updated_at)`, `repository.get_player_anagrafica(conn, player_id) -> dict | None`, `repository.insert_player_advanced_stats(conn, player_id, xg90_percentile, xa90_percentile, shots90_percentile, key_passes90_percentile, involvement_percentile, minutes_percentile, source, scrape_date)`, `repository.get_latest_player_advanced_stats(conn, player_id) -> dict | None`, `repository.insert_team_fixture_difficulty(conn, team, difficulty_attack, difficulty_defense, window_label, source, scrape_date)`, `repository.get_all_latest_team_fixture_difficulty(conn, window_label="prime 5 giornate") -> dict` (team -> row).

- [ ] **Step 1: Add the 3 tables to `db/schema.sql`**

Append at the end of the file:

```sql
-- Anagrafica (età/altezza/piede/nazionalità/numero maglia), fonte
-- Transfermarkt (scrapers/fantanalisi... no: scrapers/transfermarkt.py,
-- PROFILE_URL). Non cambia in corso di stagione (a parte trasferimenti/
-- numero maglia): upsert-in-place come player_transfermarkt_ids, non
-- storicizzata come le quotazioni.
CREATE TABLE IF NOT EXISTS player_anagrafica (
    player_id INTEGER PRIMARY KEY REFERENCES players(id),
    birth_date TEXT,
    height_cm INTEGER,
    foot TEXT,
    nationality TEXT,
    shirt_number INTEGER,
    updated_at TEXT NOT NULL
);

-- Percentili per-90 (xG/xA/tiri/rifiniture/coinvolgimento/minuti) rispetto
-- al ruolo, fonte Understat via fantanalisi.it/giocatori/{id}-{slug}
-- (scrapers/fantanalisi_giocatore.py). Storicizzata come team_strength: i
-- percentili si spostano nel corso della stagione, una riga per scrape.
CREATE TABLE IF NOT EXISTS player_advanced_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    xg90_percentile INTEGER,
    xa90_percentile INTEGER,
    shots90_percentile INTEGER,
    key_passes90_percentile INTEGER,
    involvement_percentile INTEGER,
    minutes_percentile INTEGER,
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    UNIQUE(player_id, source, scrape_date)
);
CREATE INDEX IF NOT EXISTS idx_player_advanced_stats_player
    ON player_advanced_stats(player_id);

-- Difficoltà del calendario (finestra "prime 5 giornate", scala 0-100:
-- 0=più duro, 100=più morbido), fonte fantanalisi.it/calendario
-- (scrapers/fantanalisi_calendario.py). difficulty_attack = morbidezza per
-- chi attacca (quanto concede l'avversario), difficulty_defense = per la
-- porta (quanto poco segna l'avversario). Storicizzata come team_strength:
-- la finestra "prime 5" si sposta di giornata in giornata.
CREATE TABLE IF NOT EXISTS team_fixture_difficulty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    difficulty_attack INTEGER,
    difficulty_defense INTEGER,
    window_label TEXT NOT NULL,
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    UNIQUE(team, window_label, source, scrape_date)
);
CREATE INDEX IF NOT EXISTS idx_team_fixture_difficulty_team
    ON team_fixture_difficulty(team);
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_db_repository.py`:

```python
def test_player_anagrafica_upsert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Jamal Musiala", "Estero", "C", None, None)

    repository.upsert_player_anagrafica(
        conn, player_id, birth_date="2003-02-26", height_cm=184, foot="destro",
        nationality="Germania", shirt_number=10, updated_at="2026-08-27",
    )

    profile = repository.get_player_anagrafica(conn, player_id)
    assert profile["birth_date"] == "2003-02-26"
    assert profile["height_cm"] == 184
    assert profile["foot"] == "destro"
    assert profile["shirt_number"] == 10
    conn.close()


def test_player_anagrafica_get_returns_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "No Profile", "Inter", "C", None, None)

    assert repository.get_player_anagrafica(conn, player_id) is None
    conn.close()


def test_player_anagrafica_upsert_overwrites_in_place(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Jamal Musiala", "Estero", "C", None, None)

    repository.upsert_player_anagrafica(
        conn, player_id, "2003-02-26", 184, "destro", "Germania", 10, "2026-08-01",
    )
    repository.upsert_player_anagrafica(
        conn, player_id, "2003-02-26", 184, "destro", "Germania", 42, "2026-08-27",
    )

    profile = repository.get_player_anagrafica(conn, player_id)
    assert profile["shirt_number"] == 42
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM player_anagrafica WHERE player_id = ?", (player_id,),
    ).fetchone()
    assert rows["n"] == 1
    conn.close()


def test_player_advanced_stats_insert_and_get_latest(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)

    repository.insert_player_advanced_stats(
        conn, player_id, xg90_percentile=53, xa90_percentile=43,
        shots90_percentile=22, key_passes90_percentile=63,
        involvement_percentile=34, minutes_percentile=43,
        source="fantanalisi", scrape_date="2026-08-27",
    )

    latest = repository.get_latest_player_advanced_stats(conn, player_id)
    assert latest["xg90_percentile"] == 53
    assert latest["xa90_percentile"] == 43
    conn.close()


def test_player_advanced_stats_get_latest_returns_none_when_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "No Stats", "Inter", "A", None, None)

    assert repository.get_latest_player_advanced_stats(conn, player_id) is None
    conn.close()


def test_player_advanced_stats_is_historicized_not_overwritten(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)

    repository.insert_player_advanced_stats(
        conn, player_id, 50, 40, 20, 60, 30, 40, "fantanalisi", "2026-08-20",
    )
    repository.insert_player_advanced_stats(
        conn, player_id, 53, 43, 22, 63, 34, 43, "fantanalisi", "2026-08-27",
    )

    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM player_advanced_stats WHERE player_id = ?", (player_id,),
    ).fetchone()
    assert rows["n"] == 2
    latest = repository.get_latest_player_advanced_stats(conn, player_id)
    assert latest["xg90_percentile"] == 53
    conn.close()


def test_team_fixture_difficulty_insert_and_get_all_latest(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    repository.insert_team_fixture_difficulty(
        conn, "Venezia", difficulty_attack=65, difficulty_defense=58,
        window_label="prime 5 giornate", source="fantanalisi", scrape_date="2026-08-27",
    )

    latest = repository.get_all_latest_team_fixture_difficulty(conn)
    assert latest["Venezia"]["difficulty_attack"] == 65
    assert latest["Venezia"]["difficulty_defense"] == 58
    conn.close()


def test_team_fixture_difficulty_is_historicized_not_overwritten(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    repository.insert_team_fixture_difficulty(
        conn, "Venezia", 60, 55, "prime 5 giornate", "fantanalisi", "2026-08-20",
    )
    repository.insert_team_fixture_difficulty(
        conn, "Venezia", 65, 58, "prime 5 giornate", "fantanalisi", "2026-08-27",
    )

    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM team_fixture_difficulty WHERE team = 'Venezia'",
    ).fetchone()
    assert rows["n"] == 2
    latest = repository.get_all_latest_team_fixture_difficulty(conn)
    assert latest["Venezia"]["difficulty_attack"] == 65
    conn.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_db_repository.py -k "anagrafica or advanced_stats or fixture_difficulty" -v`
Expected: FAIL with `AttributeError: module 'db.repository' has no attribute 'upsert_player_anagrafica'` (and similar for the others — none of these functions exist yet).

- [ ] **Step 4: Implement the repository functions**

Append to `db/repository.py`:

```python
def upsert_player_anagrafica(conn: sqlite3.Connection, player_id: int, birth_date,
                              height_cm, foot, nationality, shirt_number,
                              updated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO player_anagrafica
            (player_id, birth_date, height_cm, foot, nationality, shirt_number, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            birth_date = excluded.birth_date, height_cm = excluded.height_cm,
            foot = excluded.foot, nationality = excluded.nationality,
            shirt_number = excluded.shirt_number, updated_at = excluded.updated_at
        """,
        (player_id, birth_date, height_cm, foot, nationality, shirt_number, updated_at),
    )
    conn.commit()


def get_player_anagrafica(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        """
        SELECT birth_date, height_cm, foot, nationality, shirt_number
        FROM player_anagrafica WHERE player_id = ?
        """,
        (player_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def insert_player_advanced_stats(conn: sqlite3.Connection, player_id: int,
                                  xg90_percentile, xa90_percentile, shots90_percentile,
                                  key_passes90_percentile, involvement_percentile,
                                  minutes_percentile, source: str, scrape_date: str) -> None:
    conn.execute(
        """
        INSERT INTO player_advanced_stats
            (player_id, xg90_percentile, xa90_percentile, shots90_percentile,
             key_passes90_percentile, involvement_percentile, minutes_percentile,
             source, scrape_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, source, scrape_date) DO UPDATE SET
            xg90_percentile = excluded.xg90_percentile,
            xa90_percentile = excluded.xa90_percentile,
            shots90_percentile = excluded.shots90_percentile,
            key_passes90_percentile = excluded.key_passes90_percentile,
            involvement_percentile = excluded.involvement_percentile,
            minutes_percentile = excluded.minutes_percentile
        """,
        (player_id, xg90_percentile, xa90_percentile, shots90_percentile,
         key_passes90_percentile, involvement_percentile, minutes_percentile,
         source, scrape_date),
    )
    conn.commit()


def get_latest_player_advanced_stats(conn: sqlite3.Connection, player_id: int):
    cursor = conn.execute(
        """
        SELECT xg90_percentile, xa90_percentile, shots90_percentile,
               key_passes90_percentile, involvement_percentile, minutes_percentile,
               scrape_date
        FROM player_advanced_stats
        WHERE player_id = ?
        ORDER BY scrape_date DESC, id DESC
        LIMIT 1
        """,
        (player_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def insert_team_fixture_difficulty(conn: sqlite3.Connection, team: str,
                                    difficulty_attack, difficulty_defense,
                                    window_label: str, source: str,
                                    scrape_date: str) -> None:
    conn.execute(
        """
        INSERT INTO team_fixture_difficulty
            (team, difficulty_attack, difficulty_defense, window_label, source, scrape_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(team, window_label, source, scrape_date) DO UPDATE SET
            difficulty_attack = excluded.difficulty_attack,
            difficulty_defense = excluded.difficulty_defense
        """,
        (team, difficulty_attack, difficulty_defense, window_label, source, scrape_date),
    )
    conn.commit()


def get_all_latest_team_fixture_difficulty(conn: sqlite3.Connection,
                                            window_label: str = "prime 5 giornate") -> dict:
    cursor = conn.execute(
        """
        SELECT team, difficulty_attack, difficulty_defense, scrape_date
        FROM team_fixture_difficulty t1
        WHERE window_label = ? AND scrape_date = (
            SELECT MAX(scrape_date) FROM team_fixture_difficulty t2
            WHERE t2.team = t1.team AND t2.window_label = t1.window_label
        )
        """,
        (window_label,),
    )
    return {row["team"]: dict(row) for row in cursor.fetchall()}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_db_repository.py -k "anagrafica or advanced_stats or fixture_difficulty" -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add db/schema.sql db/repository.py tests/test_db_repository.py
git commit -m "feat: schema and repository CRUD for anagrafica, advanced stats, fixture difficulty"
```

---

### Task 2: Transfermarkt anagrafica extraction

**Files:**
- Modify: `scrapers/transfermarkt.py`
- Test: `tests/test_transfermarkt_scraper.py`
- Test fixture: `fixtures/transfermarkt_profile_sample.html`

**Interfaces:**
- Consumes: none beyond what `scrapers/transfermarkt.py` already imports (`re`, `BeautifulSoup`, `scrapers.base`).
- Produces: `parse_player_profile(html: str) -> dict` (keys: `birth_date`, `height_cm`, `foot`, `nationality`, `shirt_number`, all `None` when absent — never guessed), `fetch_player_profile(transfermarkt_id: int) -> dict` (does its own `base.get(PROFILE_URL...)`, independent of `fetch_photo_url` — do not refactor `fetch_photo_url`, it's already tested and used by the existing photo pipeline; a second HTTP GET per player during a separate pipeline run is the same cost `run_injuries.py` already pays for its own independent fetch).

- [ ] **Step 1: Save a real fixture**

Create `fixtures/transfermarkt_profile_sample.html` by saving the actual HTML this session fetched from `https://www.transfermarkt.it/-/profil/spieler/580195` (Jamal Musiala) — or re-fetch it fresh with `scrapers.base.get()` and save `.text`. Confirmed present in that response: `<li class="data-header__label">Nato il:<span itemprop="birthDate" class="data-header__content">26/02/2003 (23)</span></li>`, `<li class="data-header__label">Nazionalità:<span itemprop="nationality" class="data-header__content"><img ... alt="Germania" .../>Germania</span></li>`, `<li class="data-header__label">Altezza:<span itemprop="height" class="data-header__content">1,84 m</span></li>`, `<span class="info-table__content info-table__content--regular">Piede:</span><span class="info-table__content info-table__content--bold">destro</span>`, `<span class="data-header__shirt-number">#10</span>`.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_transfermarkt_scraper.py`:

```python
def test_parse_player_profile_extracts_anagrafica():
    html = _read_fixture("transfermarkt_profile_sample.html")

    profile = parse_player_profile(html)

    assert profile["birth_date"] == "2003-02-26"
    assert profile["height_cm"] == 184
    assert profile["foot"] == "destro"
    assert profile["nationality"] == "Germania"
    assert profile["shirt_number"] == 10


def test_parse_player_profile_handles_missing_fields_gracefully():
    profile = parse_player_profile("<html><body>Pagina senza profilo</body></html>")

    assert profile == {
        "birth_date": None, "height_cm": None, "foot": None,
        "nationality": None, "shirt_number": None,
    }
```

Add the import at the top of the file:

```python
from scrapers.transfermarkt import parse_player_profile
```
(alongside whatever's already imported there — check the file's existing import line and extend it, don't duplicate).

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_transfermarkt_scraper.py -k parse_player_profile -v`
Expected: FAIL with `ImportError: cannot import name 'parse_player_profile'`.

- [ ] **Step 4: Implement `parse_player_profile` and `fetch_player_profile`**

Append to `scrapers/transfermarkt.py`:

```python
import datetime as _dt


def _parse_birth_date(text: str):
    """'26/02/2003 (23)' -> '2003-02-26' (ISO), dropping the trailing age in
    parentheses — the age is derivable, storing it would drift stale."""
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return _dt.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _parse_height_cm(text: str):
    """'1,84 m' -> 184."""
    match = re.search(r"(\d)[.,](\d{2})", text)
    if not match:
        return None
    return int(match.group(1)) * 100 + int(match.group(2))


def parse_player_profile(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    profile = {
        "birth_date": None, "height_cm": None, "foot": None,
        "nationality": None, "shirt_number": None,
    }

    birth_el = soup.select_one('span[itemprop="birthDate"]')
    if birth_el:
        profile["birth_date"] = _parse_birth_date(birth_el.get_text(strip=True))

    height_el = soup.select_one('span[itemprop="height"]')
    if height_el:
        profile["height_cm"] = _parse_height_cm(height_el.get_text(strip=True))

    nationality_el = soup.select_one('span[itemprop="nationality"]')
    if nationality_el:
        # Testo del <span> meno l'alt/testo dell'eventuale <img> bandiera:
        # get_text(strip=True) sullo span intero include già solo il testo,
        # l'img non contribuisce testo — basta prendere il primo paese per
        # un giocatore con più nazionalità.
        text = nationality_el.get_text(" ", strip=True)
        profile["nationality"] = text.split(",")[0].strip() if text else None

    shirt_el = soup.select_one("span.data-header__shirt-number")
    if shirt_el:
        match = re.search(r"\d+", shirt_el.get_text(strip=True))
        profile["shirt_number"] = int(match.group()) if match else None

    # "Piede:" non ha un itemprop dedicato — è una coppia label/valore nella
    # info-table generica: il label è un <span> con questo testo esatto, il
    # valore è lo <span> immediatamente successivo nello stesso genitore.
    for label in soup.select("span.info-table__content--regular"):
        if label.get_text(strip=True) == "Piede:":
            value_el = label.find_next_sibling("span", class_="info-table__content--bold")
            if value_el:
                profile["foot"] = value_el.get_text(strip=True)
            break

    return profile


def fetch_player_profile(transfermarkt_id: int) -> dict:
    """Anagrafica (età/altezza/piede/nazionalità/numero maglia) — stessa
    PROFILE_URL di fetch_photo_url ma fetch indipendente: pipeline separate
    per dominio dato (vedi run_injuries.py/run_photos), non condividono la
    response tra loro in questo codebase."""
    response = base.get(PROFILE_URL.format(id=transfermarkt_id))
    return parse_player_profile(response.text)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_transfermarkt_scraper.py -v`
Expected: all pass, including the 2 new ones.

- [ ] **Step 6: Commit**

```bash
git add scrapers/transfermarkt.py tests/test_transfermarkt_scraper.py fixtures/transfermarkt_profile_sample.html
git commit -m "feat: parse anagrafica from Transfermarkt player profile"
```

---

### Task 3: Transfermarkt anagrafica pipeline + wire into player detail

**Files:**
- Create: `pipeline/run_player_anagrafica.py`
- Modify: `dashboard/data_access.py` (`get_player_extra`, around line 419)
- Modify: `dashboard/components.py` (`render_player_detail`, the header area around the existing tier caption)
- Test: `tests/test_run_player_anagrafica.py`
- Test: `tests/test_components.py`

**Interfaces:**
- Consumes: `scrapers.transfermarkt.search_player_id`, `fetch_player_profile` (Task 2); `repository.get_transfermarkt_id`, `upsert_transfermarkt_id`, `upsert_player_anagrafica`, `get_player_anagrafica` (Task 1).
- Produces: `pipeline.run_player_anagrafica.run(conn) -> dict` (`{"matched": int, "unmatched": list}`), `get_player_extra(conn, player_id)["anagrafica"]` (dict or `None`).

- [ ] **Step 1: Write `pipeline/run_player_anagrafica.py`**

Mirror `pipeline/run_injuries.py` exactly (same player loop, same Transfermarkt-id lookup/cache pattern), swapping the injuries fetch for the profile fetch:

```python
import logging
import os
import time
from datetime import date
from db.connection import init_db, get_connection
from db import repository
from scrapers.transfermarkt import search_player_id, fetch_player_profile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "player_anagrafica.log")

REQUEST_DELAY_SECONDS = 1.5


def run(conn) -> dict:
    cursor = conn.execute("SELECT id, canonical_name, team FROM players")
    players = [dict(row) for row in cursor.fetchall()]

    today = date.today().isoformat()
    matched = 0
    unmatched = []

    for player in players:
        player_id = player["id"]
        transfermarkt_id = repository.get_transfermarkt_id(conn, player_id)

        if transfermarkt_id is None:
            try:
                transfermarkt_id = search_player_id(player["canonical_name"], player["team"])
            except Exception as exc:
                logging.error("Search failed for %s: %s", player["canonical_name"], exc)
                unmatched.append(player["canonical_name"])
                continue
            if transfermarkt_id is None:
                logging.info("No Transfermarkt match for %s", player["canonical_name"])
                unmatched.append(player["canonical_name"])
                continue
            repository.upsert_transfermarkt_id(conn, player_id, transfermarkt_id, today)
            time.sleep(REQUEST_DELAY_SECONDS)

        try:
            profile = fetch_player_profile(transfermarkt_id)
        except Exception as exc:
            logging.error("Profile fetch failed for %s: %s", player["canonical_name"], exc)
            continue

        repository.upsert_player_anagrafica(
            conn, player_id, profile["birth_date"], profile["height_cm"],
            profile["foot"], profile["nationality"], profile["shirt_number"], today,
        )
        matched += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return {"matched": matched, "unmatched": unmatched}


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
    logging.info(
        "Player anagrafica run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_run_player_anagrafica.py`:

```python
from db.connection import init_db, get_connection
from db import repository
from pipeline.run_player_anagrafica import run


def test_run_saves_anagrafica_for_matched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Jamal Musiala", "Estero", "C", None, None)
    repository.upsert_transfermarkt_id(conn, player_id, 580195, "2026-08-01")

    monkeypatch.setattr(
        "pipeline.run_player_anagrafica.fetch_player_profile",
        lambda tid: {
            "birth_date": "2003-02-26", "height_cm": 184, "foot": "destro",
            "nationality": "Germania", "shirt_number": 10,
        },
    )
    import pipeline.run_player_anagrafica as mod
    monkeypatch.setattr(mod, "REQUEST_DELAY_SECONDS", 0)

    result = run(conn)

    assert result["matched"] == 1
    profile = repository.get_player_anagrafica(conn, player_id)
    assert profile["height_cm"] == 184
    conn.close()


def test_run_skips_player_with_no_transfermarkt_match(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    repository.upsert_player(conn, "Nobody Real", "Inter", "C", None, None)

    monkeypatch.setattr(
        "pipeline.run_player_anagrafica.search_player_id", lambda name, team_hint=None: None,
    )
    import pipeline.run_player_anagrafica as mod
    monkeypatch.setattr(mod, "REQUEST_DELAY_SECONDS", 0)

    result = run(conn)

    assert result["matched"] == 0
    assert "Nobody Real" in result["unmatched"]
    conn.close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_run_player_anagrafica.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.run_player_anagrafica'`.

- [ ] **Step 4: Run test to verify it passes**

(The Step 1 file already contains the full implementation — this step is just running the test now that the module exists.)

Run: `pytest tests/test_run_player_anagrafica.py -v`
Expected: 2 passed.

- [ ] **Step 5: Wire anagrafica into `get_player_extra` and the player-detail header**

In `dashboard/data_access.py`, modify `get_player_extra` (currently at line 419):

```python
def get_player_extra(conn, player_id: int) -> dict:
    return {
        "transfermarkt_id": repository.get_transfermarkt_id(conn, player_id),
        "anagrafica": repository.get_player_anagrafica(conn, player_id),
    }
```

In `dashboard/components.py`, `render_player_detail` already calls `extra = get_player_extra(conn, row["player_id"])` (line 1131 pre-Task-3) and uses `extra['transfermarkt_id']` right after. Add the anagrafica line immediately after that existing Transfermarkt-link block:

```python
    anagrafica = extra.get("anagrafica")
    if anagrafica:
        parts = []
        if anagrafica.get("birth_date"):
            from datetime import date as _date
            born = _date.fromisoformat(anagrafica["birth_date"])
            age = (_date.today() - born).days // 365
            parts.append(f"{age} anni")
        if anagrafica.get("height_cm"):
            parts.append(f"{anagrafica['height_cm']} cm")
        if anagrafica.get("foot"):
            parts.append(f"piede {anagrafica['foot']}")
        if anagrafica.get("nationality"):
            parts.append(anagrafica["nationality"])
        if anagrafica.get("shirt_number"):
            parts.append(f"#{anagrafica['shirt_number']}")
        if parts:
            st.caption(" · ".join(parts))
```

- [ ] **Step 6: Write the render test**

Append to `tests/test_components.py`:

```python
def test_render_player_detail_shows_anagrafica_when_present(tmp_path, monkeypatch):
    conn, row = _base_player_row(tmp_path)
    monkeypatch.setattr(
        "dashboard.components.get_player_extra",
        lambda conn, player_id: {
            "transfermarkt_id": None,
            "anagrafica": {
                "birth_date": "2003-02-26", "height_cm": 184, "foot": "destro",
                "nationality": "Germania", "shirt_number": 10,
            },
        },
    )

    at = _run_player_detail(conn, row)

    assert any("184 cm" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_omits_anagrafica_when_absent(tmp_path, monkeypatch):
    conn, row = _base_player_row(tmp_path)
    monkeypatch.setattr(
        "dashboard.components.get_player_extra",
        lambda conn, player_id: {"transfermarkt_id": None, "anagrafica": None},
    )

    at = _run_player_detail(conn, row)

    assert not any("cm" in c.value for c in at.caption)
    conn.close()
```

- [ ] **Step 7: Run all component/data_access tests**

Run: `pytest tests/test_components.py tests/test_data_access.py tests/test_run_player_anagrafica.py -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add pipeline/run_player_anagrafica.py dashboard/data_access.py dashboard/components.py tests/test_run_player_anagrafica.py tests/test_components.py
git commit -m "feat: anagrafica pipeline and player-detail display"
```

---

### Task 4: Fantanalisi listing scraper captures `detail_url`

**Files:**
- Modify: `scrapers/fantanalisi.py`
- Test: `tests/test_fantanalisi_scraper.py`

**Interfaces:**
- Produces: `PlayerRecord.detail_url` populated (e.g. `"/giocatori/2-malen"`) for every row — the field already exists on `PlayerRecord` (`scrapers/base.py:84`, default `None`), this task is the first to fill it in `fantanalisi.py`.

**Verified live this session**: the listing table's name cell is `<td class="td font-medium"><a class="hover:text-verde" href="/giocatori/2-malen">Malen</a></td>` — same column (`COL_NAME = 2`) `parse_rows` already reads for the name text.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_fantanalisi_scraper.py`:

```python
def test_parse_rows_captures_detail_url():
    cells = ["", "A", "Malen", "Titolare", "Roma", "36", "207", "7.72", "6.41",
             "25+4", "32", "240", "382", "", "264", "1", "", ""]
    hrefs = ["/giocatori/2-malen"]

    records = parse_rows([cells], hrefs)

    assert records[0].detail_url == "/giocatori/2-malen"


def test_parse_rows_detail_url_is_none_when_row_has_no_link():
    cells = ["", "A", "Malen", "Titolare", "Roma", "36", "207", "7.72", "6.41",
             "25+4", "32", "240", "382", "", "264", "1", "", ""]

    records = parse_rows([cells], [None])

    assert records[0].detail_url is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fantanalisi_scraper.py -k detail_url -v`
Expected: FAIL — `parse_rows` currently takes only one argument (`row_texts`), so this raises `TypeError: parse_rows() takes 1 positional argument but 2 were given`.

- [ ] **Step 3: Update `parse_rows` and `fetch()` to capture the href**

In `scrapers/fantanalisi.py`, change the signature and body of `parse_rows` (existing function, currently `def parse_rows(row_texts: list) -> list:`):

```python
def parse_rows(row_texts: list, hrefs: list = None) -> list:
    hrefs = hrefs or [None] * len(row_texts)
    records = []
    for cells, href in zip(row_texts, hrefs):
        if len(cells) <= COL_ASTE_LIVE:
            continue
        role = cells[COL_ROLE].strip()
        name = cells[COL_NAME].strip()
        team = cells[COL_TEAM].strip()
        if not (role and name and team):
            continue

        records.append(PlayerRecord(
            name=name,
            team=team,
            role_classic=role,
            role_mantra=None,
            price_current=_parse_price(cells[COL_ASTE_LIVE]),
            price_initial=None,
            status=None,
            fantamedia=None,
            avg_rating=None,
            appearances=None,
            photo_url=None,
            source="fantanalisi",
            detail_url=href,
        ))
    return records
```

And in `FantanalisiScraper.fetch()`, add a second `eval_on_selector_all` call for the hrefs right after the existing `row_texts` extraction:

```python
            row_texts = page.eval_on_selector_all(
                TABLE_SELECTOR,
                "rows => rows.map(r => Array.from(r.cells).map(c => c.textContent.trim()))",
            )
            hrefs = page.eval_on_selector_all(
                TABLE_SELECTOR,
                "rows => rows.map(r => { const a = r.querySelector('a[href^=\\\"/giocatori/\\\"]'); return a ? a.getAttribute('href') : null; })",
            )
            browser.close()
        return parse_rows(row_texts, hrefs)
```

(Replace the existing `return parse_rows(row_texts)` line and the `browser.close()` line right above it with this block — `hrefs` must be fetched before `browser.close()`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fantanalisi_scraper.py -v`
Expected: all pass, including the 2 new ones.

- [ ] **Step 5: Commit**

```bash
git add scrapers/fantanalisi.py tests/test_fantanalisi_scraper.py
git commit -m "feat: capture player detail_url in fantanalisi listing scraper"
```

---

### Task 5: Fantanalisi per-player percentile-radar scraper

**Files:**
- Create: `scrapers/fantanalisi_giocatore.py`
- Test: `tests/test_fantanalisi_giocatore_scraper.py`

**Interfaces:**
- Consumes: `PlayerRecord.detail_url` (Task 4).
- Produces: `parse_percentile_titles(titles: list) -> dict` (pure function, keys matching `player_advanced_stats` columns minus `player_id`/`source`/`scrape_date`), `FantanalisiGiocatoreScraper.fetch_many(detail_urls: list) -> dict` (`{detail_url: dict_of_percentiles_or_None}`).

**Verified live this session** (Playwright `page.content()` against `https://www.fantanalisi.it/giocatori/10-kolo-muani`): the per-90 percentile radar is an SVG whose data points are `<circle ...><title>Kolo Muani — xG/90: 53° percentile</title></circle>` (one `circle` per metric: xG/90, xA/90, Tiri/90, Rifin. [=key passes], Coinv. [=involvement/xGChain], Minuti), reachable via the CSS selector `circle title` (or more precisely `svg circle` then read each circle's child `title` text). Only ONE such radar exists per page (verified: `html.count('<svg')` == 5 total SVGs on the page but only the player's own radar carries `percentile` in its circle titles — a second overlay polygon for role-average comparison shares the same SVG, no extra circles/titles).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fantanalisi_giocatore_scraper.py`:

```python
from scrapers.fantanalisi_giocatore import parse_percentile_titles

SAMPLE_TITLES = [
    "Kolo Muani — xG/90: 53° percentile",
    "Kolo Muani — xA/90: 43° percentile",
    "Kolo Muani — Tiri/90: 22° percentile",
    "Kolo Muani — Rifin.: 63° percentile",
    "Kolo Muani — Coinv.: 34° percentile",
    "Kolo Muani — Minuti: 43° percentile",
]


def test_parse_percentile_titles_extracts_all_metrics():
    result = parse_percentile_titles(SAMPLE_TITLES)

    assert result == {
        "xg90_percentile": 53, "xa90_percentile": 43, "shots90_percentile": 22,
        "key_passes90_percentile": 63, "involvement_percentile": 34,
        "minutes_percentile": 43,
    }


def test_parse_percentile_titles_ignores_unrelated_titles():
    result = parse_percentile_titles(["Some unrelated tooltip text"])

    assert result == {
        "xg90_percentile": None, "xa90_percentile": None, "shots90_percentile": None,
        "key_passes90_percentile": None, "involvement_percentile": None,
        "minutes_percentile": None,
    }


def test_parse_percentile_titles_handles_empty_list():
    result = parse_percentile_titles([])

    assert all(v is None for v in result.values())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fantanalisi_giocatore_scraper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.fantanalisi_giocatore'`.

- [ ] **Step 3: Implement `scrapers/fantanalisi_giocatore.py`**

```python
"""Scraper per i percentili per-90 (xG/xA/tiri/rifiniture/coinvolgimento/
minuti) esposti sulla pagina di dettaglio giocatore di
https://www.fantanalisi.it/giocatori/{id}-{slug} — complementare a
scrapers/fantanalisi.py (che scrappa la sola tabella /giocatori).

Ogni pagina renderizza un radar SVG con un <circle> per metrica; il valore
percentile è nel testo del suo <title> figlio, formato
"{Nome} — {Metrica}: {N}° percentile" (verificato live sulla pagina di
Randal Kolo Muani, id 10). Solo il radar del giocatore stesso ha circle con
"percentile" nel title — un eventuale overlay di confronto ruolo condivide
lo stesso <svg> senza aggiungere circle/title propri.
"""

import re

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.fantanalisi.it"

# Etichette esatte usate dal sito per ciascuna metrica del radar -> colonna
# player_advanced_stats corrispondente.
METRIC_KEY_MAP = {
    "xG/90": "xg90_percentile",
    "xA/90": "xa90_percentile",
    "Tiri/90": "shots90_percentile",
    "Rifin.": "key_passes90_percentile",
    "Coinv.": "involvement_percentile",
    "Minuti": "minutes_percentile",
}

TITLE_PATTERN = re.compile(r"([A-Za-zÀ-ÿ./]+):\s*(\d+)°?\s*percentile")


def parse_percentile_titles(titles: list) -> dict:
    result = {key: None for key in METRIC_KEY_MAP.values()}
    for title in titles or []:
        match = TITLE_PATTERN.search(title)
        if not match:
            continue
        key = METRIC_KEY_MAP.get(match.group(1).strip())
        if key:
            result[key] = int(match.group(2))
    return result


class FantanalisiGiocatoreScraper:
    def fetch_many(self, detail_urls: list) -> dict:
        """detail_urls: PlayerRecord.detail_url values (relative paths like
        '/giocatori/10-kolo-muani'). Returns {detail_url: percentile dict or
        None on fetch failure} — one browser launch for the whole batch, one
        page navigation per url, matching the cost profile pipeline scripts
        already budget for per-record fetches (see run_fcp_metrics.py)."""
        results = {}
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            for detail_url in detail_urls:
                try:
                    page.goto(f"{BASE_URL}{detail_url}", timeout=45000)
                    page.wait_for_selector("circle title", timeout=15000)
                    titles = page.eval_on_selector_all(
                        "circle title", "els => els.map(e => e.textContent)",
                    )
                    results[detail_url] = parse_percentile_titles(titles)
                except Exception:
                    results[detail_url] = None
            browser.close()
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fantanalisi_giocatore_scraper.py -v`
Expected: 3 passed.

- [ ] **Step 5: Manual verification against the live page (required — this is the one selector in this plan not covered by an automated test, since it needs a real browser)**

Run this one-off script and confirm it prints 6 non-`None` values:

```python
from scrapers.fantanalisi_giocatore import FantanalisiGiocatoreScraper
results = FantanalisiGiocatoreScraper().fetch_many(["/giocatori/10-kolo-muani"])
print(results)
```

If any value is unexpectedly `None`, re-open the live page's rendered DOM (`page.content()` after `page.goto` + a `page.wait_for_timeout(2000)`) and adjust `TITLE_PATTERN`/the selector to match — do not proceed to Task 6 until this prints real percentile values.

- [ ] **Step 6: Commit**

```bash
git add scrapers/fantanalisi_giocatore.py tests/test_fantanalisi_giocatore_scraper.py
git commit -m "feat: parse per-90 percentile radar from Fantanalisi player detail page"
```

---

### Task 6: Advanced-stats pipeline + wire into player detail

**Files:**
- Create: `pipeline/run_player_advanced_stats.py`
- Modify: `dashboard/data_access.py` (`get_player_detail`, around line 445)
- Modify: `dashboard/components.py` (`render_player_detail`, near the existing `_render_role_comparison` call)
- Test: `tests/test_run_player_advanced_stats.py`
- Test: `tests/test_data_access.py`, `tests/test_components.py`

**Interfaces:**
- Consumes: `scrapers.fantanalisi.FantanalisiScraper` (Task 4), `scrapers.fantanalisi_giocatore.FantanalisiGiocatoreScraper` (Task 5), `matching.player_matcher.match_name_to_player`, `repository.insert_player_advanced_stats`/`get_latest_player_advanced_stats` (Task 1).
- Produces: `pipeline.run_player_advanced_stats.run(conn) -> dict` (`{"matched": int, "unmatched": list}`), `get_player_detail(...)["advanced_stats"]` (dict or `None`).

- [ ] **Step 1: Write `pipeline/run_player_advanced_stats.py`**

Mirror `pipeline/run_fcp_metrics.py`'s structure (listing scrape with `detail_url`, match by name+team, batch detail-fetch), but batched through `fetch_many` instead of one fetch per record (Playwright browser reuse):

```python
import logging
import os
from datetime import date

from db.connection import init_db, get_connection
from db import repository
from matching.player_matcher import match_name_to_player
from scrapers.fantanalisi import FantanalisiScraper
from scrapers.fantanalisi_giocatore import FantanalisiGiocatoreScraper

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "player_advanced_stats.log")

SOURCE = "fantanalisi"


def run(conn) -> dict:
    records = FantanalisiScraper().fetch()
    players = [dict(row) for row in conn.execute("SELECT id, canonical_name, team FROM players")]

    detail_urls_by_record = {
        record.detail_url: record for record in records if record.detail_url
    }
    percentiles_by_url = FantanalisiGiocatoreScraper().fetch_many(
        list(detail_urls_by_record.keys())
    )

    today = date.today().isoformat()
    matched = 0
    unmatched = []

    for detail_url, record in detail_urls_by_record.items():
        percentiles = percentiles_by_url.get(detail_url)
        if percentiles is None:
            logging.error("Detail fetch failed for %s", record.name)
            continue

        player = match_name_to_player(record.name, record.team, players)
        if player is None:
            unmatched.append(record.name)
            logging.info("No match for %s (%s)", record.name, record.team)
            continue

        repository.insert_player_advanced_stats(
            conn, player["id"], percentiles["xg90_percentile"],
            percentiles["xa90_percentile"], percentiles["shots90_percentile"],
            percentiles["key_passes90_percentile"], percentiles["involvement_percentile"],
            percentiles["minutes_percentile"], SOURCE, today,
        )
        matched += 1

    return {"matched": matched, "unmatched": unmatched}


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
    logging.info(
        "Advanced stats run complete: %d matched, %d unmatched",
        result["matched"], len(result["unmatched"]),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_run_player_advanced_stats.py`:

```python
from db.connection import init_db, get_connection
from db import repository
from scrapers.base import PlayerRecord
import pipeline.run_player_advanced_stats as mod


def _record(name, team, detail_url):
    return PlayerRecord(
        name=name, team=team, role_classic="A", role_mantra=None,
        price_current=None, price_initial=None, status=None, fantamedia=None,
        avg_rating=None, appearances=None, photo_url=None, source="fantanalisi",
        detail_url=detail_url,
    )


def test_run_saves_advanced_stats_for_matched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Randal Kolo Muani", "Juventus", "A", None, None)

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Randal Kolo Muani", "Juventus", "/giocatori/10-x")],
        })(),
    )
    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {
            "fetch_many": lambda self, urls: {
                "/giocatori/10-x": {
                    "xg90_percentile": 53, "xa90_percentile": 43,
                    "shots90_percentile": 22, "key_passes90_percentile": 63,
                    "involvement_percentile": 34, "minutes_percentile": 43,
                },
            },
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 1
    latest = repository.get_latest_player_advanced_stats(conn, player_id)
    assert latest["xg90_percentile"] == 53
    conn.close()


def test_run_skips_unmatched_players(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiScraper",
        lambda: type("S", (), {
            "fetch": lambda self: [_record("Nobody Real", "Inter", "/giocatori/1-x")],
        })(),
    )
    monkeypatch.setattr(
        "pipeline.run_player_advanced_stats.FantanalisiGiocatoreScraper",
        lambda: type("G", (), {
            "fetch_many": lambda self, urls: {"/giocatori/1-x": {
                "xg90_percentile": 10, "xa90_percentile": 10, "shots90_percentile": 10,
                "key_passes90_percentile": 10, "involvement_percentile": 10,
                "minutes_percentile": 10,
            }},
        })(),
    )

    result = mod.run(conn)

    assert result["matched"] == 0
    assert "Nobody Real" in result["unmatched"]
    conn.close()
```

- [ ] **Step 3: Run test to verify it fails, then passes**

Run: `pytest tests/test_run_player_advanced_stats.py -v`
First run expected: FAIL (`ModuleNotFoundError`) before Step 1's file exists — since Step 1 already wrote it, this run should just pass: 2 passed.

- [ ] **Step 4: Wire into `get_player_detail` and `render_player_detail`**

In `dashboard/data_access.py`, in `get_player_detail` (around line 445+, right after the `role_comparison` addition from the prior plan), add:

```python
    merged["advanced_stats"] = repository.get_latest_player_advanced_stats(conn, player_id)
```

In `dashboard/components.py`, add a small render helper near `_render_role_comparison` and call it from `render_player_detail` right after that existing call:

```python
def _render_advanced_stats(row: dict) -> None:
    stats = row.get("advanced_stats")
    if not stats:
        return
    st.markdown("**Percentili per-90 (xG/xA, Understat)**")
    labels = {
        "xg90_percentile": "xG/90", "xa90_percentile": "xA/90",
        "shots90_percentile": "Tiri/90", "key_passes90_percentile": "Rifiniture/90",
        "involvement_percentile": "Coinvolgimento", "minutes_percentile": "Minuti",
    }
    for key, label in labels.items():
        value = stats.get(key)
        if value is None:
            continue
        st.progress(min(max(int(value), 0), 100), text=f"{label}: {value}° percentile")
```

And in `render_player_detail`, right after the existing `_render_role_comparison(row)` call, add `_render_advanced_stats(row)`.

- [ ] **Step 5: Write the render + data_access tests**

Append to `tests/test_data_access.py`:

```python
def test_get_player_detail_includes_advanced_stats(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Player One", "Inter", "A", None, None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, p1, source, "2026-08-22", 20, 20, "ok", 7.0, 7.0, 30)
    repository.insert_player_advanced_stats(
        conn, p1, 53, 43, 22, 63, 34, 43, "fantanalisi", "2026-08-27",
    )

    detail = get_player_detail(conn, p1)

    assert detail["advanced_stats"]["xg90_percentile"] == 53
    conn.close()
```

Append to `tests/test_components.py`:

```python
def test_render_player_detail_shows_advanced_stats_when_present(tmp_path):
    conn, row = _base_player_row(tmp_path, advanced_stats={
        "xg90_percentile": 53, "xa90_percentile": 43, "shots90_percentile": 22,
        "key_passes90_percentile": 63, "involvement_percentile": 34, "minutes_percentile": 43,
    })

    at = _run_player_detail(conn, row)

    assert any("xG/90" in p.label for p in at.progress if hasattr(p, "label"))
    conn.close()


def test_render_player_detail_omits_advanced_stats_when_absent(tmp_path):
    conn, row = _base_player_row(tmp_path, advanced_stats=None)

    at = _run_player_detail(conn, row)

    assert not at.exception
    conn.close()
```

- [ ] **Step 6: Run all affected tests**

Run: `pytest tests/test_run_player_advanced_stats.py tests/test_data_access.py tests/test_components.py -v`
Expected: all pass. If `at.progress` items don't expose `.label` in the installed Streamlit testing version, inspect `at.progress[0]` in a debugger/REPL first and adjust the assertion to whatever attribute actually carries the `text=` argument — don't guess blindly, the `AppTest` framework's exact attribute names vary by Streamlit version.

- [ ] **Step 7: Commit**

```bash
git add pipeline/run_player_advanced_stats.py dashboard/data_access.py dashboard/components.py tests/test_run_player_advanced_stats.py tests/test_data_access.py tests/test_components.py
git commit -m "feat: advanced-stats pipeline and player-detail percentile display"
```

---

### Task 7: Fantanalisi fixture-difficulty scraper + pipeline + wire into UI

**Files:**
- Create: `scrapers/fantanalisi_calendario.py`
- Create: `pipeline/run_fixture_difficulty.py`
- Modify: `dashboard/data_access.py` (new `get_fixture_difficulty`)
- Modify: `dashboard/components.py` (team-info area of `render_player_detail`)
- Test: `tests/test_fantanalisi_calendario_scraper.py`, `tests/test_run_fixture_difficulty.py`, `tests/test_components.py`

**Interfaces:**
- Produces: `parse_team_scores(rows: list) -> list` (pure function, `rows` = `[{"team": str, "score": str}, ...]` → `[{"team": str, "score": int}, ...]`), `FantanalisiCalendarioScraper.fetch() -> dict` (`{"attack": [...], "defense": [...]}`, each a list from `parse_team_scores`), `save_fixture_difficulty(conn, attack_records, defense_records, window_label="prime 5 giornate", source="fantanalisi", scrape_date=None) -> int`, `get_fixture_difficulty(conn, team: str) -> dict | None`.

**Verified live this session** (Playwright `page.content()` against `https://www.fantanalisi.it/calendario`): the default view is a `.card` headed "Chi parte in discesa" containing one `<button>` per team: `<button ...><span class="truncate ... font-semibold" ...>Venezia</span><span class="h-2 ...">...</span><span class="num text-right text-[12px]" ...>65</span></button>` — team name in `span.truncate`, score in `span.num`. This is the "prime 5 giornate" / "per chi attacca" (attack-facing) view by default; a sibling `<button title="morbidezza = quanto POCO segna l'avversario di giornata">🧤 Per la porta</button>` toggles to the defense-facing equivalent (same list shape, different underlying numbers) — clicking it and re-reading the same selector gets the defense view. **Explicitly out of scope**: the full 38-matchday per-fixture breakdown (opponent code + home/away per giornata) requires per-team click interaction to reveal, a materially different (heavier, more fragile) scraping pattern than every other scraper in this codebase uses — only the "prime 5 giornate" summary score is scraped here.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fantanalisi_calendario_scraper.py`:

```python
from scrapers.fantanalisi_calendario import parse_team_scores

SAMPLE_ROWS = [
    {"team": "Venezia", "score": "65"},
    {"team": "Juventus", "score": "62"},
]


def test_parse_team_scores_extracts_team_and_score():
    records = parse_team_scores(SAMPLE_ROWS)

    assert records == [
        {"team": "Venezia", "score": 65},
        {"team": "Juventus", "score": 62},
    ]


def test_parse_team_scores_skips_rows_without_team_name():
    records = parse_team_scores([{"team": "", "score": "50"}])

    assert records == []


def test_parse_team_scores_handles_non_numeric_score():
    records = parse_team_scores([{"team": "Venezia", "score": "-"}])

    assert records == [{"team": "Venezia", "score": None}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fantanalisi_calendario_scraper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.fantanalisi_calendario'`.

- [ ] **Step 3: Implement `scrapers/fantanalisi_calendario.py`**

```python
"""Scraper per la difficoltà di calendario (finestra "prime 5 giornate",
scala 0-100: 0=più duro, 100=più morbido) esposta da
https://www.fantanalisi.it/calendario — complementare a
scrapers/fantanalisi_squadre.py.

La vista di default è un .card intitolato "Chi parte in discesa": un
<button> per squadra con il nome in <span class="truncate"> e il punteggio
in <span class="num"> — è la vista "per chi attacca" (morbidezza =
quanto concede l'avversario). Un secondo bottone "🧤 Per la porta" attiva
la vista "per la porta" (stesso shape, punteggi diversi). Solo la finestra
"prime 5 giornate" è scrappata qui — il dettaglio giornata-per-giornata
richiederebbe interazione per-squadra, fuori scope (vedi plan)."""

from datetime import date

from playwright.sync_api import sync_playwright

CALENDARIO_URL = "https://www.fantanalisi.it/calendario"

TEAM_ROW_SELECTOR = ".card button:has(span.num)"
DEFENSE_TOGGLE_SELECTOR = 'button:has-text("Per la porta")'


def parse_team_scores(rows: list) -> list:
    records = []
    for row in rows:
        team = (row.get("team") or "").strip()
        if not team:
            continue
        score_text = (row.get("score") or "").strip()
        score = int(score_text) if score_text.isdigit() else None
        records.append({"team": team, "score": score})
    return records


class FantanalisiCalendarioScraper:
    def _read_rows(self, page) -> list:
        return page.eval_on_selector_all(
            TEAM_ROW_SELECTOR,
            """buttons => buttons.map(b => ({
                team: (b.querySelector('span.truncate') || {}).textContent || '',
                score: (b.querySelector('span.num') || {}).textContent || ''
            }))""",
        )

    def fetch(self) -> dict:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(CALENDARIO_URL, timeout=45000)
            page.wait_for_selector(TEAM_ROW_SELECTOR, timeout=20000)

            attack_rows = self._read_rows(page)

            page.click(DEFENSE_TOGGLE_SELECTOR, timeout=10000)
            page.wait_for_timeout(1000)
            defense_rows = self._read_rows(page)

            browser.close()
        return {
            "attack": parse_team_scores(attack_rows),
            "defense": parse_team_scores(defense_rows),
        }


def save_fixture_difficulty(conn, attack_records: list, defense_records: list,
                             window_label: str = "prime 5 giornate",
                             source: str = "fantanalisi", scrape_date: str = None) -> int:
    from db import repository

    scrape_date = scrape_date or date.today().isoformat()
    defense_by_team = {r["team"]: r["score"] for r in defense_records}

    saved = 0
    for record in attack_records:
        repository.insert_team_fixture_difficulty(
            conn, record["team"], record["score"],
            defense_by_team.get(record["team"]), window_label, source, scrape_date,
        )
        saved += 1
    return saved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fantanalisi_calendario_scraper.py -v`
Expected: 3 passed.

- [ ] **Step 5: Manual verification against the live page (required — the click-based defense toggle isn't covered by the pure-function tests)**

```python
from scrapers.fantanalisi_calendario import FantanalisiCalendarioScraper
result = FantanalisiCalendarioScraper().fetch()
print(len(result["attack"]), len(result["defense"]))
print(result["attack"][:3])
```

Expected: both lists have ~20 entries (one per Serie A team) with non-`None` integer scores. If `DEFENSE_TOGGLE_SELECTOR` or `TEAM_ROW_SELECTOR` don't match (0 rows, or the click times out), re-inspect the live rendered DOM (`page.content()`) and correct the selectors — do not proceed to Step 6 with an unverified selector.

- [ ] **Step 6: Write `pipeline/run_fixture_difficulty.py`**

```python
import logging
import os
from datetime import date
from db.connection import init_db, get_connection
from scrapers.fantanalisi_calendario import FantanalisiCalendarioScraper, save_fixture_difficulty

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
LOG_PATH = os.path.join(BASE_DIR, "data", "fixture_difficulty.log")

SOURCE = "fantanalisi"


def run(conn) -> dict:
    result = FantanalisiCalendarioScraper().fetch()
    today = date.today().isoformat()
    saved = save_fixture_difficulty(
        conn, result["attack"], result["defense"], source=SOURCE, scrape_date=today,
    )
    return {"teams": saved}


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
    logging.info("Fixture difficulty run complete: %d squadre", result["teams"])


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Write the pipeline test**

Create `tests/test_run_fixture_difficulty.py`:

```python
from db.connection import init_db, get_connection
from db import repository
import pipeline.run_fixture_difficulty as mod


def test_run_saves_attack_and_defense_scores(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    monkeypatch.setattr(
        "pipeline.run_fixture_difficulty.FantanalisiCalendarioScraper",
        lambda: type("S", (), {
            "fetch": lambda self: {
                "attack": [{"team": "Venezia", "score": 65}],
                "defense": [{"team": "Venezia", "score": 58}],
            },
        })(),
    )

    result = mod.run(conn)

    assert result["teams"] == 1
    latest = repository.get_all_latest_team_fixture_difficulty(conn)
    assert latest["Venezia"]["difficulty_attack"] == 65
    assert latest["Venezia"]["difficulty_defense"] == 58
    conn.close()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_run_fixture_difficulty.py -v`
Expected: 1 passed.

- [ ] **Step 9: Wire into `dashboard/data_access.py` and `dashboard/components.py`**

In `dashboard/data_access.py`, add:

```python
def get_fixture_difficulty(conn, team: str) -> dict:
    """Difficoltà calendario "prime 5 giornate" (0-100, più alto = più
    morbido) per team — normalize_team_name(row["team"]) prima di chiamare,
    la tabella è keyed sul nome canonico completo come team_strength."""
    all_teams = repository.get_all_latest_team_fixture_difficulty(conn)
    return all_teams.get(team)
```

In `dashboard/components.py`, in `render_player_detail`, find where `row["team"]` is already displayed (the `fc-card-team`/header area) and add right after it:

```python
    fixture = get_fixture_difficulty(conn, row["team"])
    if fixture and fixture.get("difficulty_attack") is not None:
        st.caption(
            f"Calendario prime 5 giornate: {fixture['difficulty_attack']}/100 "
            "(più alto = più morbido)"
        )
```

Add `get_fixture_difficulty` to the existing `from dashboard.data_access import (...)` block in `dashboard/components.py` (alongside `get_player_extra` etc.).

- [ ] **Step 10: Write the render test**

Append to `tests/test_components.py`:

```python
def test_render_player_detail_shows_fixture_difficulty_when_present(tmp_path, monkeypatch):
    conn, row = _base_player_row(tmp_path)
    monkeypatch.setattr(
        "dashboard.components.get_fixture_difficulty",
        lambda conn, team: {"difficulty_attack": 65, "difficulty_defense": 58},
    )

    at = _run_player_detail(conn, row)

    assert any("prime 5 giornate" in c.value for c in at.caption)
    conn.close()
```

- [ ] **Step 11: Run all affected tests**

Run: `pytest tests/test_fantanalisi_calendario_scraper.py tests/test_run_fixture_difficulty.py tests/test_components.py tests/test_data_access.py -v`
Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add scrapers/fantanalisi_calendario.py pipeline/run_fixture_difficulty.py dashboard/data_access.py dashboard/components.py tests/test_fantanalisi_calendario_scraper.py tests/test_run_fixture_difficulty.py tests/test_components.py
git commit -m "feat: fixture-difficulty scraper, pipeline, and player-detail display"
```

---

### Task 8: Full-suite regression check and README/docs index update

**Files:**
- Modify: `README.md` (docs index, if one exists listing pipeline scripts — check `README.md`'s structure first; only add an entry if that section already exists, following the existing entries' exact format).

- [ ] **Step 1: Run the entire test suite**

Run: `pytest tests/ -q`
Expected: all tests pass (existing + everything added in Tasks 1-7), 0 failures.

- [ ] **Step 2: Manual smoke test**

Run `streamlit run dashboard/app.py`, open a player's detail page for a player with populated anagrafica/advanced_stats/fixture_difficulty (may need to run the 3 new pipeline scripts against the real `data/fantacalcio.db` first: `python -m pipeline.run_player_anagrafica`, `python -m pipeline.run_player_advanced_stats`, `python -m pipeline.run_fixture_difficulty` — each can take a while, especially the two Playwright-based ones over ~500 players/20 teams; consider testing against a handful of players first if the plan's implementer wants a fast check, but a full pipeline run should also be exercised at least once before calling this plan done). Confirm the anagrafica caption, percentile bars, and fixture-difficulty caption all render without exceptions.

- [ ] **Step 3: Commit any doc updates**

```bash
git add README.md
git commit -m "docs: note new anagrafica/advanced-stats/fixture-difficulty pipelines"
```
(Skip this commit entirely if README.md has no natural place for this — do not force an addition that doesn't fit its existing structure.)
