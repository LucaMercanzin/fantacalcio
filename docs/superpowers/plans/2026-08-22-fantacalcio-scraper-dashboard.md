# Fantacalcio Scraper & Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python system that scrapes Fantacalcio player quotations from multiple sites, stores/history them in SQLite, computes a per-role ranking, and shows the result in a local Streamlit dashboard as Panini-style player cards across 4 role pages plus a "My Roster" credits page.

**Architecture:** Modular scraper adapters (one per site) normalize data into a shared `PlayerRecord` shape and feed a SQLite database. A matching module reconciles the same player across sources. A scoring module computes a ranking per role from the latest stored data. A Streamlit multipage app reads the database directly (no separate API layer) to render searchable/sortable card grids per role and a roster/budget page. A scheduler script re-runs the scrape+match+score pipeline periodically via Windows Task Scheduler.

**Tech Stack:** Python 3.11+, `requests` + `beautifulsoup4` (HTML scraping), `sqlite3` (stdlib), `streamlit` (dashboard), `pandas` (data shaping in dashboard), `rapidfuzz` (name matching), `pytest` (tests).

## Global Constraints

- Runs entirely locally — no cloud deployment, no external hosting.
- SQLite database file at `fantacalcio/data/fantacalcio.db`; photos at `fantacalcio/data/photos/`.
- No LLM/API calls inside the running program — `player_notes` text is written manually (by the user, with Claude's help in a separate conversation), never generated automatically by the scraping/dashboard code.
- Roster rules: 500 total credits, 25 players (3 P, 8 D, 8 C, 6 A) — hardcoded as defaults, not user-configurable in this plan.
- Start with 2 scraper adapters (Fantacalcio.it, Gazzetta.it) to prove the pipeline end-to-end; additional adapters are added later by following the same `BaseScraper` interface, out of scope for this plan.
- A scraper adapter failing must never stop the others — isolate errors per adapter.

---

## File Structure

```
fantacalcio/
  requirements.txt
  db/
    schema.sql
    connection.py
    repository.py
  scrapers/
    base.py
    fantacalcio_it.py
    gazzetta.py
  matching/
    player_matcher.py
  ranking/
    scorer.py
  pipeline/
    run_scraping.py
  dashboard/
    app.py
    data_access.py
    components.py
    pages/
      1_Portieri.py
      2_Difensori.py
      3_Centrocampisti.py
      4_Attaccanti.py
      5_La_Mia_Rosa.py
  data/
    fantacalcio.db      (created at runtime)
    photos/              (created at runtime)
  tests/
    test_db_repository.py
    test_scraper_base.py
    test_fantacalcio_it_scraper.py
    test_gazzetta_scraper.py
    test_player_matcher.py
    test_scorer.py
    test_data_access.py
  fixtures/
    fantacalcio_it_sample.html
    gazzetta_sample.html
```

---

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `fantacalcio/requirements.txt`
- Create: `fantacalcio/pytest.ini`
- Create: `fantacalcio/tests/__init__.py`

**Interfaces:**
- Produces: a working `pytest` command runnable from `fantacalcio/`.

- [ ] **Step 1: Create requirements.txt**

```
requests==2.32.3
beautifulsoup4==4.12.3
streamlit==1.38.0
pandas==2.2.2
rapidfuzz==3.9.6
pytest==8.3.2
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 3: Create empty tests package marker**

```python
# fantacalcio/tests/__init__.py
```

- [ ] **Step 4: Install dependencies**

Run: `cd fantacalcio && pip install -r requirements.txt`
Expected: all packages install without error.

- [ ] **Step 5: Verify pytest runs (no tests yet)**

Run: `cd fantacalcio && pytest`
Expected: "no tests ran" / exit code 0 (no collection errors).

- [ ] **Step 6: Commit**

```bash
git add fantacalcio/requirements.txt fantacalcio/pytest.ini fantacalcio/tests/__init__.py
git commit -m "chore: scaffold fantacalcio project with test runner"
```

---

### Task 2: Database schema and connection helper

**Files:**
- Create: `fantacalcio/db/schema.sql`
- Create: `fantacalcio/db/connection.py`
- Test: `fantacalcio/tests/test_db_repository.py` (connection portion only in this task)

**Interfaces:**
- Produces: `connection.get_connection(db_path: str) -> sqlite3.Connection`, `connection.init_db(db_path: str) -> None` (creates tables from schema.sql if not present).

- [ ] **Step 1: Write schema.sql**

```sql
-- fantacalcio/db/schema.sql
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    team TEXT NOT NULL,
    role_classic TEXT NOT NULL,
    role_mantra TEXT,
    photo_path TEXT,
    UNIQUE(canonical_name, team)
);

CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    price_current REAL,
    price_initial REAL,
    status TEXT,
    fantamedia REAL,
    avg_rating REAL,
    appearances INTEGER
);

CREATE TABLE IF NOT EXISTS my_roster (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    price_paid REAL NOT NULL,
    date_added TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE REFERENCES players(id),
    notes TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

- [ ] **Step 2: Write failing test for init_db**

```python
# fantacalcio/tests/test_db_repository.py
import sqlite3
from db.connection import init_db, get_connection

def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert {"players", "quotations", "my_roster", "player_notes"} <= tables
    conn.close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_db_repository.py::test_init_db_creates_tables -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db.connection'`

- [ ] **Step 4: Implement connection.py**

```python
# fantacalcio/db/connection.py
import sqlite3
import os


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_connection(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_db_repository.py::test_init_db_creates_tables -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add fantacalcio/db/schema.sql fantacalcio/db/connection.py fantacalcio/tests/test_db_repository.py
git commit -m "feat: add sqlite schema and connection helper"
```

---

### Task 3: Repository layer (players, quotations, roster, notes CRUD)

**Files:**
- Create: `fantacalcio/db/repository.py`
- Modify: `fantacalcio/tests/test_db_repository.py` (add repository tests)

**Interfaces:**
- Consumes: `db.connection.get_connection`, `db.connection.init_db`
- Produces:
  - `repository.upsert_player(conn, canonical_name: str, team: str, role_classic: str, role_mantra: str | None, photo_path: str | None) -> int` (returns player_id)
  - `repository.insert_quotation(conn, player_id: int, source: str, scrape_date: str, price_current: float | None, price_initial: float | None, status: str | None, fantamedia: float | None, avg_rating: float | None, appearances: int | None) -> None`
  - `repository.get_latest_quotations(conn, role_classic: str) -> list[dict]` (one row per player+source, only the most recent `scrape_date` per player)
  - `repository.add_roster_entry(conn, player_id: int, price_paid: float, date_added: str) -> None`
  - `repository.get_roster(conn) -> list[dict]`
  - `repository.upsert_player_notes(conn, player_id: int, notes: str, updated_at: str) -> None`
  - `repository.get_player_notes(conn, player_id: int) -> str | None`

- [ ] **Step 1: Write failing tests**

```python
# fantacalcio/tests/test_db_repository.py (append)
from db import repository


def test_upsert_player_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    id1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    id2 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    assert id1 == id2
    conn.close()


def test_insert_and_get_latest_quotations(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-01",
        price_current=35, price_initial=30, status="ok",
        fantamedia=6.8, avg_rating=6.5, appearances=30,
    )
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-10",
        price_current=38, price_initial=30, status="ok",
        fantamedia=6.8, avg_rating=6.5, appearances=30,
    )

    latest = repository.get_latest_quotations(conn, role_classic="A")

    assert len(latest) == 1
    assert latest[0]["price_current"] == 38
    conn.close()


def test_roster_add_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.add_roster_entry(conn, player_id, price_paid=40, date_added="2026-08-20")
    roster = repository.get_roster(conn)

    assert len(roster) == 1
    assert roster[0]["price_paid"] == 40
    conn.close()


def test_player_notes_upsert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    repository.upsert_player_notes(conn, player_id, "Ottimo investimento", "2026-08-20")
    repository.upsert_player_notes(conn, player_id, "Aggiornato: preferire vice", "2026-08-21")

    notes = repository.get_player_notes(conn, player_id)

    assert notes == "Aggiornato: preferire vice"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd fantacalcio && pytest tests/test_db_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db.repository'`

- [ ] **Step 3: Implement repository.py**

```python
# fantacalcio/db/repository.py
import sqlite3


def upsert_player(conn: sqlite3.Connection, canonical_name: str, team: str,
                   role_classic: str, role_mantra: str | None,
                   photo_path: str | None) -> int:
    cursor = conn.execute(
        "SELECT id FROM players WHERE canonical_name = ? AND team = ?",
        (canonical_name, team),
    )
    row = cursor.fetchone()
    if row:
        conn.execute(
            "UPDATE players SET role_classic = ?, role_mantra = ?, photo_path = "
            "COALESCE(?, photo_path) WHERE id = ?",
            (role_classic, role_mantra, photo_path, row["id"]),
        )
        conn.commit()
        return row["id"]

    cursor = conn.execute(
        "INSERT INTO players (canonical_name, team, role_classic, role_mantra, photo_path) "
        "VALUES (?, ?, ?, ?, ?)",
        (canonical_name, team, role_classic, role_mantra, photo_path),
    )
    conn.commit()
    return cursor.lastrowid


def insert_quotation(conn: sqlite3.Connection, player_id: int, source: str,
                      scrape_date: str, price_current: float | None,
                      price_initial: float | None, status: str | None,
                      fantamedia: float | None, avg_rating: float | None,
                      appearances: int | None) -> None:
    conn.execute(
        "INSERT INTO quotations (player_id, source, scrape_date, price_current, "
        "price_initial, status, fantamedia, avg_rating, appearances) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (player_id, source, scrape_date, price_current, price_initial, status,
         fantamedia, avg_rating, appearances),
    )
    conn.commit()


def get_latest_quotations(conn: sqlite3.Connection, role_classic: str) -> list[dict]:
    cursor = conn.execute(
        """
        SELECT q.*, p.canonical_name, p.team, p.role_classic, p.role_mantra, p.photo_path
        FROM quotations q
        JOIN players p ON p.id = q.player_id
        WHERE p.role_classic = ?
          AND q.scrape_date = (
              SELECT MAX(q2.scrape_date) FROM quotations q2
              WHERE q2.player_id = q.player_id AND q2.source = q.source
          )
        ORDER BY p.canonical_name
        """,
        (role_classic,),
    )
    return [dict(row) for row in cursor.fetchall()]


def add_roster_entry(conn: sqlite3.Connection, player_id: int, price_paid: float,
                      date_added: str) -> None:
    conn.execute(
        "INSERT INTO my_roster (player_id, price_paid, date_added) VALUES (?, ?, ?)",
        (player_id, price_paid, date_added),
    )
    conn.commit()


def get_roster(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute(
        """
        SELECT r.id, r.player_id, r.price_paid, r.date_added,
               p.canonical_name, p.team, p.role_classic
        FROM my_roster r
        JOIN players p ON p.id = r.player_id
        ORDER BY r.date_added
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def upsert_player_notes(conn: sqlite3.Connection, player_id: int, notes: str,
                         updated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO player_notes (player_id, notes, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET notes = excluded.notes,
                                              updated_at = excluded.updated_at
        """,
        (player_id, notes, updated_at),
    )
    conn.commit()


def get_player_notes(conn: sqlite3.Connection, player_id: int) -> str | None:
    cursor = conn.execute(
        "SELECT notes FROM player_notes WHERE player_id = ?", (player_id,)
    )
    row = cursor.fetchone()
    return row["notes"] if row else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd fantacalcio && pytest tests/test_db_repository.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/db/repository.py fantacalcio/tests/test_db_repository.py
git commit -m "feat: add repository CRUD for players, quotations, roster, notes"
```

---

### Task 4: Scraper base interface and PlayerRecord

**Files:**
- Create: `fantacalcio/scrapers/base.py`
- Test: `fantacalcio/tests/test_scraper_base.py`

**Interfaces:**
- Produces:
  - `PlayerRecord` dataclass with fields: `name: str`, `team: str`, `role_classic: str`, `role_mantra: str | None`, `price_current: float | None`, `price_initial: float | None`, `status: str | None`, `fantamedia: float | None`, `avg_rating: float | None`, `appearances: int | None`, `photo_url: str | None`, `source: str`
  - `BaseScraper` abstract class with method `fetch(self) -> list[PlayerRecord]`

- [ ] **Step 1: Write failing test**

```python
# fantacalcio/tests/test_scraper_base.py
import pytest
from scrapers.base import BaseScraper, PlayerRecord


def test_player_record_holds_expected_fields():
    record = PlayerRecord(
        name="Lautaro Martinez", team="Inter", role_classic="A", role_mantra="Pu",
        price_current=38, price_initial=30, status="ok", fantamedia=6.8,
        avg_rating=6.5, appearances=30, photo_url="http://example.com/p.jpg",
        source="fantacalcio_it",
    )
    assert record.name == "Lautaro Martinez"
    assert record.source == "fantacalcio_it"


def test_base_scraper_fetch_is_abstract():
    class IncompleteScraper(BaseScraper):
        pass

    with pytest.raises(TypeError):
        IncompleteScraper()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_scraper_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.base'`

- [ ] **Step 3: Implement base.py**

```python
# fantacalcio/scrapers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PlayerRecord:
    name: str
    team: str
    role_classic: str
    role_mantra: str | None
    price_current: float | None
    price_initial: float | None
    status: str | None
    fantamedia: float | None
    avg_rating: float | None
    appearances: int | None
    photo_url: str | None
    source: str


class BaseScraper(ABC):
    @abstractmethod
    def fetch(self) -> list[PlayerRecord]:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_scraper_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/scrapers/base.py fantacalcio/tests/test_scraper_base.py
git commit -m "feat: add scraper base interface and PlayerRecord"
```

---

### Task 5: Fantacalcio.it scraper adapter

**Files:**
- Create: `fantacalcio/scrapers/fantacalcio_it.py`
- Create: `fantacalcio/fixtures/fantacalcio_it_sample.html`
- Test: `fantacalcio/tests/test_fantacalcio_it_scraper.py`

**Interfaces:**
- Consumes: `scrapers.base.BaseScraper`, `scrapers.base.PlayerRecord`
- Produces: `FantacalcioItScraper(BaseScraper)` with `fetch(self) -> list[PlayerRecord]`, and `parse_html(html: str) -> list[PlayerRecord]` (pure function, used by the test so no network call is needed).

**Important:** the CSS selectors below are a best-effort based on how Fantacalcio.it's quotazioni table is commonly structured (an HTML `<table>` with one `<tr>` per player and columns for role, name, team, current price, initial price). Before running this against the live site, the implementer MUST open the real quotazioni page in a browser, inspect the actual table structure, and adjust the selectors in `parse_html` to match — the fixture-driven test only proves the parsing logic is internally consistent, not that it matches the live DOM.

- [ ] **Step 1: Create HTML fixture**

```html
<!-- fantacalcio/fixtures/fantacalcio_it_sample.html -->
<html><body>
<table class="table-quotazioni">
  <tr class="player-row">
    <td class="role">A</td>
    <td class="name">Lautaro Martinez</td>
    <td class="team">Inter</td>
    <td class="price-current">38</td>
    <td class="price-initial">30</td>
    <td class="fantamedia">6.8</td>
    <td class="avg-rating">6.5</td>
    <td class="appearances">30</td>
    <td class="status">ok</td>
    <td class="photo"><img src="https://www.fantacalcio.it/img/players/12345.png" /></td>
  </tr>
  <tr class="player-row">
    <td class="role">P</td>
    <td class="name">Yann Sommer</td>
    <td class="team">Inter</td>
    <td class="price-current">15</td>
    <td class="price-initial">12</td>
    <td class="fantamedia">6.2</td>
    <td class="avg-rating">6.1</td>
    <td class="appearances">28</td>
    <td class="status">infortunato</td>
    <td class="photo"><img src="https://www.fantacalcio.it/img/players/67890.png" /></td>
  </tr>
</table>
</body></html>
```

- [ ] **Step 2: Write failing test**

```python
# fantacalcio/tests/test_fantacalcio_it_scraper.py
import os
from scrapers.fantacalcio_it import parse_html

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "fantacalcio_it_sample.html"
)


def test_parse_html_extracts_players():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html)

    assert len(records) == 2
    lautaro = next(r for r in records if r.name == "Lautaro Martinez")
    assert lautaro.team == "Inter"
    assert lautaro.role_classic == "A"
    assert lautaro.price_current == 38
    assert lautaro.price_initial == 30
    assert lautaro.fantamedia == 6.8
    assert lautaro.status == "ok"
    assert lautaro.photo_url == "https://www.fantacalcio.it/img/players/12345.png"
    assert lautaro.source == "fantacalcio_it"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_fantacalcio_it_scraper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.fantacalcio_it'`

- [ ] **Step 4: Implement fantacalcio_it.py**

```python
# fantacalcio/scrapers/fantacalcio_it.py
import requests
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://www.fantacalcio.it/quotazioni-fantacalcio"


def parse_html(html: str) -> list[PlayerRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for row in soup.select("tr.player-row"):
        img = row.select_one("td.photo img")
        records.append(PlayerRecord(
            name=row.select_one("td.name").get_text(strip=True),
            team=row.select_one("td.team").get_text(strip=True),
            role_classic=row.select_one("td.role").get_text(strip=True),
            role_mantra=None,
            price_current=float(row.select_one("td.price-current").get_text(strip=True)),
            price_initial=float(row.select_one("td.price-initial").get_text(strip=True)),
            status=row.select_one("td.status").get_text(strip=True),
            fantamedia=float(row.select_one("td.fantamedia").get_text(strip=True)),
            avg_rating=float(row.select_one("td.avg-rating").get_text(strip=True)),
            appearances=int(row.select_one("td.appearances").get_text(strip=True)),
            photo_url=img["src"] if img else None,
            source="fantacalcio_it",
        ))
    return records


class FantacalcioItScraper(BaseScraper):
    def fetch(self) -> list[PlayerRecord]:
        response = requests.get(QUOTAZIONI_URL, timeout=30)
        response.raise_for_status()
        return parse_html(response.text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_fantacalcio_it_scraper.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add fantacalcio/scrapers/fantacalcio_it.py fantacalcio/fixtures/fantacalcio_it_sample.html fantacalcio/tests/test_fantacalcio_it_scraper.py
git commit -m "feat: add Fantacalcio.it scraper adapter"
```

---

### Task 6: Gazzetta.it scraper adapter

**Files:**
- Create: `fantacalcio/scrapers/gazzetta.py`
- Create: `fantacalcio/fixtures/gazzetta_sample.html`
- Test: `fantacalcio/tests/test_gazzetta_scraper.py`

**Interfaces:**
- Consumes: `scrapers.base.BaseScraper`, `scrapers.base.PlayerRecord`
- Produces: `GazzettaScraper(BaseScraper)` with `fetch(self) -> list[PlayerRecord]`, and `parse_html(html: str) -> list[PlayerRecord]`.

**Important:** same caveat as Task 5 — selectors are a best-effort placeholder structure; the implementer must verify against the live Gazzetta Fantacalcio quotazioni page and adjust `parse_html` accordingly before relying on live data.

- [ ] **Step 1: Create HTML fixture**

```html
<!-- fantacalcio/fixtures/gazzetta_sample.html -->
<html><body>
<div class="quotazioni-list">
  <div class="player-item" data-role="A">
    <span class="player-name">Lautaro Martinez</span>
    <span class="player-team">Inter</span>
    <span class="quotazione-attuale">37</span>
    <span class="quotazione-iniziale">29</span>
    <span class="media-voto">6.7</span>
    <img class="player-photo" src="https://www.gazzetta.it/img/players/lautaro.png" />
  </div>
  <div class="player-item" data-role="P">
    <span class="player-name">Yann Sommer</span>
    <span class="player-team">Inter</span>
    <span class="quotazione-attuale">14</span>
    <span class="quotazione-iniziale">11</span>
    <span class="media-voto">6.1</span>
    <img class="player-photo" src="https://www.gazzetta.it/img/players/sommer.png" />
  </div>
</div>
</body></html>
```

- [ ] **Step 2: Write failing test**

```python
# fantacalcio/tests/test_gazzetta_scraper.py
import os
from scrapers.gazzetta import parse_html

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "gazzetta_sample.html"
)


def test_parse_html_extracts_players():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html)

    assert len(records) == 2
    lautaro = next(r for r in records if r.name == "Lautaro Martinez")
    assert lautaro.team == "Inter"
    assert lautaro.role_classic == "A"
    assert lautaro.price_current == 37
    assert lautaro.price_initial == 29
    assert lautaro.avg_rating == 6.7
    assert lautaro.photo_url == "https://www.gazzetta.it/img/players/lautaro.png"
    assert lautaro.source == "gazzetta"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_gazzetta_scraper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.gazzetta'`

- [ ] **Step 4: Implement gazzetta.py**

```python
# fantacalcio/scrapers/gazzetta.py
import requests
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, PlayerRecord

QUOTAZIONI_URL = "https://www.gazzetta.it/fantacalcio/quotazioni"


def parse_html(html: str) -> list[PlayerRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for item in soup.select("div.player-item"):
        img = item.select_one("img.player-photo")
        records.append(PlayerRecord(
            name=item.select_one("span.player-name").get_text(strip=True),
            team=item.select_one("span.player-team").get_text(strip=True),
            role_classic=item.get("data-role", ""),
            role_mantra=None,
            price_current=float(item.select_one("span.quotazione-attuale").get_text(strip=True)),
            price_initial=float(item.select_one("span.quotazione-iniziale").get_text(strip=True)),
            status=None,
            fantamedia=None,
            avg_rating=float(item.select_one("span.media-voto").get_text(strip=True)),
            appearances=None,
            photo_url=img["src"] if img else None,
            source="gazzetta",
        ))
    return records


class GazzettaScraper(BaseScraper):
    def fetch(self) -> list[PlayerRecord]:
        response = requests.get(QUOTAZIONI_URL, timeout=30)
        response.raise_for_status()
        return parse_html(response.text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_gazzetta_scraper.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add fantacalcio/scrapers/gazzetta.py fantacalcio/fixtures/gazzetta_sample.html fantacalcio/tests/test_gazzetta_scraper.py
git commit -m "feat: add Gazzetta.it scraper adapter"
```

---

### Task 7: Player matcher (cross-source name reconciliation)

**Files:**
- Create: `fantacalcio/matching/player_matcher.py`
- Test: `fantacalcio/tests/test_player_matcher.py`

**Interfaces:**
- Consumes: `scrapers.base.PlayerRecord`
- Produces: `match_records(records: list[PlayerRecord]) -> dict[tuple[str, str], list[PlayerRecord]]` — groups records from different sources into the same canonical `(canonical_name, team)` key when they refer to the same player (same team + fuzzy name match ratio >= 85), and `normalize_name(name: str) -> str` (lowercase, strip accents/punctuation, for matching only — the original `name` is preserved on the record for display).

- [ ] **Step 1: Write failing test**

```python
# fantacalcio/tests/test_player_matcher.py
from scrapers.base import PlayerRecord
from matching.player_matcher import match_records, normalize_name


def _record(name, team, source):
    return PlayerRecord(
        name=name, team=team, role_classic="A", role_mantra=None,
        price_current=10, price_initial=10, status="ok", fantamedia=6,
        avg_rating=6, appearances=10, photo_url=None, source=source,
    )


def test_normalize_name_strips_case_and_punctuation():
    assert normalize_name("Lautaro Martinez") == normalize_name("lautaro   martinez")


def test_match_records_groups_same_player_across_sources():
    records = [
        _record("Lautaro Martinez", "Inter", "fantacalcio_it"),
        _record("Lautaro", "Inter", "gazzetta"),
        _record("Yann Sommer", "Inter", "fantacalcio_it"),
    ]

    groups = match_records(records)

    assert len(groups) == 2
    lautaro_group = next(v for k, v in groups.items() if "Lautaro" in k[0])
    assert len(lautaro_group) == 2
    assert {r.source for r in lautaro_group} == {"fantacalcio_it", "gazzetta"}


def test_match_records_keeps_different_teams_separate():
    records = [
        _record("Marco Rossi", "Milan", "fantacalcio_it"),
        _record("Marco Rossi", "Roma", "gazzetta"),
    ]

    groups = match_records(records)

    assert len(groups) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_player_matcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matching.player_matcher'`

- [ ] **Step 3: Implement player_matcher.py**

```python
# fantacalcio/matching/player_matcher.py
import re
import unicodedata
from rapidfuzz import fuzz
from scrapers.base import PlayerRecord


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^a-zA-Z\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def match_records(records: list[PlayerRecord]) -> dict[tuple[str, str], list[PlayerRecord]]:
    groups: dict[tuple[str, str], list[PlayerRecord]] = {}

    for record in records:
        team = record.team
        norm_name = normalize_name(record.name)

        matched_key = None
        for (existing_name, existing_team) in groups:
            if existing_team != team:
                continue
            if fuzz.ratio(norm_name, existing_name) >= 85:
                matched_key = (existing_name, existing_team)
                break

        if matched_key:
            groups[matched_key].append(record)
        else:
            groups[(norm_name, team)] = [record]
            # store original name for readability by re-keying with a display tuple
    # re-key groups so the exposed key uses the longest (most complete) name seen
    display_groups: dict[tuple[str, str], list[PlayerRecord]] = {}
    for (_, team), recs in groups.items():
        best_name = max((r.name for r in recs), key=len)
        display_groups[(best_name, team)] = recs
    return display_groups
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_player_matcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/matching/player_matcher.py fantacalcio/tests/test_player_matcher.py
git commit -m "feat: add cross-source player name matching"
```

---

### Task 8: Ranking scorer

**Files:**
- Create: `fantacalcio/ranking/scorer.py`
- Test: `fantacalcio/tests/test_scorer.py`

**Interfaces:**
- Consumes: rows shaped like `repository.get_latest_quotations` output (`dict` with `fantamedia`, `avg_rating`, `appearances`, `status`, `price_current` keys).
- Produces: `compute_score(row: dict) -> float` and `rank_players(rows: list[dict]) -> list[dict]` (returns the input rows sorted best-to-worst, each with an added `"score"` key).

Scoring formula: `score = (fantamedia_or_avg_rating * 10) + (appearances_reliability * 5) - status_penalty`, where:
- `fantamedia_or_avg_rating` = `fantamedia` if present, else `avg_rating`, else `0`.
- `appearances_reliability` = `min(appearances, 38) / 38` if `appearances` is present, else `0.5` (neutral).
- `status_penalty` = `15` if status is `"infortunato"` or `"squalificato"`, else `0`.

- [ ] **Step 1: Write failing test**

```python
# fantacalcio/tests/test_scorer.py
from ranking.scorer import compute_score, rank_players


def test_compute_score_uses_fantamedia_when_present():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "ok"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 0


def test_compute_score_falls_back_to_avg_rating():
    row = {"fantamedia": None, "avg_rating": 6.0, "appearances": None, "status": "ok"}
    score = compute_score(row)
    assert score == 6.0 * 10 + 0.5 * 5 - 0


def test_compute_score_penalizes_injured_status():
    row = {"fantamedia": 7.0, "avg_rating": None, "appearances": 38, "status": "infortunato"}
    score = compute_score(row)
    assert score == 7.0 * 10 + 1.0 * 5 - 15


def test_rank_players_orders_best_to_worst():
    rows = [
        {"canonical_name": "Low", "fantamedia": 5.0, "avg_rating": None, "appearances": 38, "status": "ok"},
        {"canonical_name": "High", "fantamedia": 8.0, "avg_rating": None, "appearances": 38, "status": "ok"},
    ]

    ranked = rank_players(rows)

    assert [r["canonical_name"] for r in ranked] == ["High", "Low"]
    assert ranked[0]["score"] > ranked[1]["score"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ranking.scorer'`

- [ ] **Step 3: Implement scorer.py**

```python
# fantacalcio/ranking/scorer.py
PENALIZED_STATUSES = {"infortunato", "squalificato"}


def compute_score(row: dict) -> float:
    base = row.get("fantamedia")
    if base is None:
        base = row.get("avg_rating")
    if base is None:
        base = 0.0

    appearances = row.get("appearances")
    reliability = (min(appearances, 38) / 38) if appearances is not None else 0.5

    penalty = 15 if row.get("status") in PENALIZED_STATUSES else 0

    return base * 10 + reliability * 5 - penalty


def rank_players(rows: list[dict]) -> list[dict]:
    scored = []
    for row in rows:
        enriched = dict(row)
        enriched["score"] = compute_score(row)
        scored.append(enriched)
    return sorted(scored, key=lambda r: r["score"], reverse=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_scorer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/ranking/scorer.py fantacalcio/tests/test_scorer.py
git commit -m "feat: add per-role ranking scorer"
```

---

### Task 9: Photo download helper

**Files:**
- Modify: `fantacalcio/scrapers/base.py` (no change needed) — Create new file instead:
- Create: `fantacalcio/scrapers/photo_downloader.py`
- Test: `fantacalcio/tests/test_photo_downloader.py`

**Interfaces:**
- Produces: `download_photo(photo_url: str | None, player_id: int, photos_dir: str) -> str | None` — downloads the image to `<photos_dir>/<player_id>.jpg` and returns the local path, or returns `None` if `photo_url` is `None` or the download fails (never raises).

- [ ] **Step 1: Write failing test**

```python
# fantacalcio/tests/test_photo_downloader.py
from unittest.mock import patch, Mock
from scrapers.photo_downloader import download_photo


def test_download_photo_returns_none_when_no_url(tmp_path):
    result = download_photo(None, player_id=1, photos_dir=str(tmp_path))
    assert result is None


def test_download_photo_saves_file_and_returns_path(tmp_path):
    fake_response = Mock()
    fake_response.content = b"fake-image-bytes"
    fake_response.raise_for_status = Mock()

    with patch("scrapers.photo_downloader.requests.get", return_value=fake_response):
        result = download_photo(
            "https://example.com/photo.png", player_id=42, photos_dir=str(tmp_path)
        )

    assert result == str(tmp_path / "42.jpg")
    with open(result, "rb") as f:
        assert f.read() == b"fake-image-bytes"


def test_download_photo_returns_none_on_request_failure(tmp_path):
    with patch("scrapers.photo_downloader.requests.get", side_effect=Exception("boom")):
        result = download_photo(
            "https://example.com/photo.png", player_id=42, photos_dir=str(tmp_path)
        )

    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_photo_downloader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.photo_downloader'`

- [ ] **Step 3: Implement photo_downloader.py**

```python
# fantacalcio/scrapers/photo_downloader.py
import os
import requests


def download_photo(photo_url: str | None, player_id: int, photos_dir: str) -> str | None:
    if not photo_url:
        return None

    os.makedirs(photos_dir, exist_ok=True)
    dest_path = os.path.join(photos_dir, f"{player_id}.jpg")

    try:
        response = requests.get(photo_url, timeout=15)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(response.content)
        return dest_path
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_photo_downloader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/scrapers/photo_downloader.py fantacalcio/tests/test_photo_downloader.py
git commit -m "feat: add player photo downloader with graceful failure"
```

---

### Task 10: Scraping pipeline orchestrator

**Files:**
- Create: `fantacalcio/pipeline/run_scraping.py`
- Test: `fantacalcio/tests/test_run_scraping.py`

**Interfaces:**
- Consumes: `scrapers.base.BaseScraper`, `matching.player_matcher.match_records`, `scrapers.photo_downloader.download_photo`, `db.repository.upsert_player`, `db.repository.insert_quotation`
- Produces: `run_pipeline(scrapers: list[BaseScraper], conn, photos_dir: str, scrape_date: str) -> None` — calls `fetch()` on each scraper (catching and logging exceptions per-scraper so one failure doesn't stop the rest), merges results via `match_records`, and for each matched group: upserts the player once (using the first record's team/role/name, preferring a record that has a `photo_url` for the photo download), then inserts one quotation row per source record.

- [ ] **Step 1: Write failing test**

```python
# fantacalcio/tests/test_run_scraping.py
from db.connection import init_db, get_connection
from db import repository
from scrapers.base import BaseScraper, PlayerRecord
from pipeline.run_scraping import run_pipeline


class FakeScraperA(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Lautaro Martinez", team="Inter", role_classic="A", role_mantra=None,
            price_current=38, price_initial=30, status="ok", fantamedia=6.8,
            avg_rating=6.5, appearances=30, photo_url="https://example.com/l.jpg",
            source="fantacalcio_it",
        )]


class FailingScraper(BaseScraper):
    def fetch(self):
        raise RuntimeError("site is down")


class FakeScraperB(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Lautaro", team="Inter", role_classic="A", role_mantra=None,
            price_current=37, price_initial=29, status="ok", fantamedia=None,
            avg_rating=6.7, appearances=None, photo_url=None,
            source="gazzetta",
        )]


def test_run_pipeline_merges_sources_and_survives_failures(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    photos_dir = str(tmp_path / "photos")

    run_pipeline(
        scrapers=[FakeScraperA(), FailingScraper(), FakeScraperB()],
        conn=conn,
        photos_dir=photos_dir,
        scrape_date="2026-08-22",
    )

    latest = repository.get_latest_quotations(conn, role_classic="A")
    sources = {row["source"] for row in latest}

    assert sources == {"fantacalcio_it", "gazzetta"}
    assert len({row["player_id"] for row in latest}) == 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_run_scraping.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.run_scraping'`

- [ ] **Step 3: Implement run_scraping.py**

```python
# fantacalcio/pipeline/run_scraping.py
import logging
from scrapers.base import BaseScraper
from scrapers.photo_downloader import download_photo
from matching.player_matcher import match_records
from db import repository

logger = logging.getLogger(__name__)


def run_pipeline(scrapers: list[BaseScraper], conn, photos_dir: str, scrape_date: str) -> None:
    all_records = []
    for scraper in scrapers:
        try:
            all_records.extend(scraper.fetch())
        except Exception as exc:
            logger.error("Scraper %s failed: %s", scraper.__class__.__name__, exc)

    groups = match_records(all_records)

    for (canonical_name, team), records in groups.items():
        first = records[0]
        photo_record = next((r for r in records if r.photo_url), None)

        player_id = repository.upsert_player(
            conn, canonical_name, team, first.role_classic, first.role_mantra, None,
        )

        if photo_record:
            local_path = download_photo(photo_record.photo_url, player_id, photos_dir)
            if local_path:
                repository.upsert_player(
                    conn, canonical_name, team, first.role_classic, first.role_mantra,
                    local_path,
                )

        for record in records:
            repository.insert_quotation(
                conn, player_id, record.source, scrape_date,
                record.price_current, record.price_initial, record.status,
                record.fantamedia, record.avg_rating, record.appearances,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_run_scraping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/pipeline/run_scraping.py fantacalcio/tests/test_run_scraping.py
git commit -m "feat: add scraping pipeline orchestrator with per-adapter fault isolation"
```

---

### Task 11: Roster/budget calculator

**Files:**
- Create: `fantacalcio/ranking/budget.py`
- Test: `fantacalcio/tests/test_budget.py`

**Interfaces:**
- Consumes: rows shaped like `repository.get_roster` output (`role_classic`, `price_paid` keys).
- Produces: `compute_budget_summary(roster_rows: list[dict], total_credits: int = 500) -> dict` returning:
  ```python
  {
      "total_credits": 500,
      "spent": <float>,
      "remaining": <float>,
      "slots": {
          "P": {"filled": <int>, "total": 3, "remaining": <int>},
          "D": {"filled": <int>, "total": 8, "remaining": <int>},
          "C": {"filled": <int>, "total": 8, "remaining": <int>},
          "A": {"filled": <int>, "total": 6, "remaining": <int>},
      },
  }
  ```

- [ ] **Step 1: Write failing test**

```python
# fantacalcio/tests/test_budget.py
from ranking.budget import compute_budget_summary


def test_compute_budget_summary_tracks_spent_and_slots():
    roster_rows = [
        {"role_classic": "A", "price_paid": 40},
        {"role_classic": "A", "price_paid": 30},
        {"role_classic": "P", "price_paid": 10},
    ]

    summary = compute_budget_summary(roster_rows)

    assert summary["total_credits"] == 500
    assert summary["spent"] == 80
    assert summary["remaining"] == 420
    assert summary["slots"]["A"] == {"filled": 2, "total": 6, "remaining": 4}
    assert summary["slots"]["P"] == {"filled": 1, "total": 3, "remaining": 2}
    assert summary["slots"]["D"] == {"filled": 0, "total": 8, "remaining": 8}
    assert summary["slots"]["C"] == {"filled": 0, "total": 8, "remaining": 8}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_budget.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ranking.budget'`

- [ ] **Step 3: Implement budget.py**

```python
# fantacalcio/ranking/budget.py
ROLE_SLOTS = {"P": 3, "D": 8, "C": 8, "A": 6}


def compute_budget_summary(roster_rows: list[dict], total_credits: int = 500) -> dict:
    spent = sum(row["price_paid"] for row in roster_rows)

    filled_by_role = {role: 0 for role in ROLE_SLOTS}
    for row in roster_rows:
        role = row["role_classic"]
        if role in filled_by_role:
            filled_by_role[role] += 1

    slots = {
        role: {
            "filled": filled_by_role[role],
            "total": total,
            "remaining": total - filled_by_role[role],
        }
        for role, total in ROLE_SLOTS.items()
    }

    return {
        "total_credits": total_credits,
        "spent": spent,
        "remaining": total_credits - spent,
        "slots": slots,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_budget.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/ranking/budget.py fantacalcio/tests/test_budget.py
git commit -m "feat: add roster budget and slot summary calculator"
```

---

### Task 12: Dashboard data access layer

**Files:**
- Create: `fantacalcio/dashboard/data_access.py`
- Test: `fantacalcio/tests/test_data_access.py`

**Interfaces:**
- Consumes: `db.connection.get_connection`, `db.repository.get_latest_quotations`, `db.repository.get_roster`, `db.repository.get_player_notes`, `ranking.scorer.rank_players`
- Produces:
  - `get_ranked_role(conn, role_classic: str) -> list[dict]` — latest quotations for the role, ranked (with `"score"`), each row enriched with `"notes"` (from `get_player_notes`, or `""`), `"is_in_roster"` (bool), sorted by rank by default.
  - `search_and_sort(rows: list[dict], query: str, sort_by: str) -> list[dict]` — `query` filters by case-insensitive substring on `canonical_name` (empty string = no filter); `sort_by` is one of `"rank"` (default, preserves incoming order), `"team"` (alphabetical), `"price"` (descending by `price_current`).

- [ ] **Step 1: Write failing test**

```python
# fantacalcio/tests/test_data_access.py
from db.connection import init_db, get_connection
from db import repository
from dashboard.data_access import get_ranked_role, search_and_sort


def test_get_ranked_role_includes_notes_and_roster_flag(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)
    p2 = repository.upsert_player(conn, "Dusan Vlahovic", "Juventus", "A", "Pu", None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-22", 38, 30, "ok", 7.0, 6.8, 30)
    repository.insert_quotation(conn, p2, "fantacalcio_it", "2026-08-22", 25, 22, "ok", 6.0, 6.0, 30)
    repository.upsert_player_notes(conn, p1, "Top pick", "2026-08-22")
    repository.add_roster_entry(conn, p2, 25, "2026-08-22")

    ranked = get_ranked_role(conn, "A")

    assert ranked[0]["canonical_name"] == "Lautaro Martinez"
    assert ranked[0]["notes"] == "Top pick"
    assert ranked[0]["is_in_roster"] is False
    vlahovic = next(r for r in ranked if r["canonical_name"] == "Dusan Vlahovic")
    assert vlahovic["notes"] == ""
    assert vlahovic["is_in_roster"] is True
    conn.close()


def test_search_and_sort_filters_by_name():
    rows = [
        {"canonical_name": "Lautaro Martinez", "team": "Inter", "price_current": 38},
        {"canonical_name": "Dusan Vlahovic", "team": "Juventus", "price_current": 25},
    ]

    result = search_and_sort(rows, query="lautaro", sort_by="rank")

    assert len(result) == 1
    assert result[0]["canonical_name"] == "Lautaro Martinez"


def test_search_and_sort_sorts_by_team():
    rows = [
        {"canonical_name": "Lautaro Martinez", "team": "Inter", "price_current": 38},
        {"canonical_name": "Dusan Vlahovic", "team": "Juventus", "price_current": 25},
    ]

    result = search_and_sort(rows, query="", sort_by="team")

    assert [r["team"] for r in result] == ["Inter", "Juventus"]


def test_search_and_sort_sorts_by_price_descending():
    rows = [
        {"canonical_name": "Lautaro Martinez", "team": "Inter", "price_current": 38},
        {"canonical_name": "Dusan Vlahovic", "team": "Juventus", "price_current": 45},
    ]

    result = search_and_sort(rows, query="", sort_by="price")

    assert [r["canonical_name"] for r in result] == ["Dusan Vlahovic", "Lautaro Martinez"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_data_access.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dashboard.data_access'`

- [ ] **Step 3: Implement data_access.py**

```python
# fantacalcio/dashboard/data_access.py
from db import repository
from ranking.scorer import rank_players


def get_ranked_role(conn, role_classic: str) -> list[dict]:
    rows = repository.get_latest_quotations(conn, role_classic)
    ranked = rank_players(rows)

    roster_player_ids = {r["player_id"] for r in repository.get_roster(conn)}

    for row in ranked:
        row["notes"] = repository.get_player_notes(conn, row["player_id"]) or ""
        row["is_in_roster"] = row["player_id"] in roster_player_ids

    return ranked


def search_and_sort(rows: list[dict], query: str, sort_by: str) -> list[dict]:
    filtered = rows
    if query:
        query_lower = query.lower()
        filtered = [r for r in rows if query_lower in r["canonical_name"].lower()]

    if sort_by == "team":
        return sorted(filtered, key=lambda r: r["team"])
    if sort_by == "price":
        return sorted(filtered, key=lambda r: r["price_current"] or 0, reverse=True)
    return filtered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_data_access.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/dashboard/data_access.py fantacalcio/tests/test_data_access.py
git commit -m "feat: add dashboard data access with search and sort"
```

---

### Task 13: Card component and role page renderer

**Files:**
- Create: `fantacalcio/dashboard/components.py`
- Create: `fantacalcio/dashboard/pages/1_Portieri.py`
- Create: `fantacalcio/dashboard/pages/2_Difensori.py`
- Create: `fantacalcio/dashboard/pages/3_Centrocampisti.py`
- Create: `fantacalcio/dashboard/pages/4_Attaccanti.py`
- Create: `fantacalcio/dashboard/app.py`

**Interfaces:**
- Consumes: `dashboard.data_access.get_ranked_role`, `dashboard.data_access.search_and_sort`
- Produces: `components.render_role_page(conn, role_classic: str, role_label: str) -> None` (Streamlit UI: title, search box, sort selector, grid of player cards); `components.render_player_card(row: dict, rank: int) -> None` (renders one Panini-style card via `st.container`+`st.image`+`st.markdown`).

This task has no automated test (Streamlit UI rendering) — verification is manual per Step 4.

- [ ] **Step 1: Implement components.py**

```python
# fantacalcio/dashboard/components.py
import os
import streamlit as st
from dashboard.data_access import get_ranked_role, search_and_sort

PLACEHOLDER_COLORS = {"P": "#f4c542", "D": "#4caf50", "C": "#2196f3", "A": "#e53935"}


def render_player_card(row: dict, rank: int) -> None:
    with st.container(border=True):
        cols = st.columns([1, 2])
        with cols[0]:
            photo_path = row.get("photo_path")
            if photo_path and os.path.exists(photo_path):
                st.image(photo_path, width=90)
            else:
                color = PLACEHOLDER_COLORS.get(row["role_classic"], "#999999")
                st.markdown(
                    f"<div style='width:90px;height:90px;border-radius:50%;"
                    f"background:{color};display:flex;align-items:center;"
                    f"justify-content:center;color:white;font-size:32px;'>"
                    f"{row['canonical_name'][0]}</div>",
                    unsafe_allow_html=True,
                )
        with cols[1]:
            roster_tag = " ⭐ IN ROSA" if row["is_in_roster"] else ""
            st.markdown(f"**#{rank} {row['canonical_name']}**{roster_tag}")
            st.caption(f"{row['team']} · Rating {row['score']:.1f}")
            st.write(
                f"Quotazione: {row.get('price_current', '-')}  "
                f"(iniziale {row.get('price_initial', '-')})  · Fonte: {row['source']}"
            )
            if row.get("fantamedia"):
                st.write(f"Fantamedia: {row['fantamedia']}")
            if row.get("status") and row["status"] not in ("ok", None):
                st.warning(f"Stato: {row['status']}")
            if row["notes"]:
                st.info(row["notes"])


def render_role_page(conn, role_classic: str, role_label: str) -> None:
    st.title(role_label)

    query = st.text_input("Cerca giocatore per nome")
    sort_by = st.selectbox("Ordina per", ["rank", "team", "price"], format_func=lambda v: {
        "rank": "Ranking", "team": "Squadra", "price": "Quotazione",
    }[v])

    rows = get_ranked_role(conn, role_classic)
    rows = search_and_sort(rows, query=query, sort_by=sort_by)

    for i, row in enumerate(rows, start=1):
        render_player_card(row, rank=i)
```

- [ ] **Step 2: Implement app.py (shared connection + entry point)**

```python
# fantacalcio/dashboard/app.py
import os
import streamlit as st
from db.connection import get_connection, init_db

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fantacalcio.db")


def get_db_connection():
    if "db_conn" not in st.session_state:
        init_db(DB_PATH)
        st.session_state.db_conn = get_connection(DB_PATH)
    return st.session_state.db_conn


st.set_page_config(page_title="Fantacalcio Dashboard", layout="wide")
st.title("Fantacalcio Dashboard")
st.write("Seleziona una pagina dal menu a sinistra: Portieri, Difensori, Centrocampisti, Attaccanti, La Mia Rosa.")
```

- [ ] **Step 3: Implement the 4 role pages**

```python
# fantacalcio/dashboard/pages/1_Portieri.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.app import get_db_connection
from dashboard.components import render_role_page

render_role_page(get_db_connection(), "P", "Portieri")
```

```python
# fantacalcio/dashboard/pages/2_Difensori.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.app import get_db_connection
from dashboard.components import render_role_page

render_role_page(get_db_connection(), "D", "Difensori")
```

```python
# fantacalcio/dashboard/pages/3_Centrocampisti.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.app import get_db_connection
from dashboard.components import render_role_page

render_role_page(get_db_connection(), "C", "Centrocampisti")
```

```python
# fantacalcio/dashboard/pages/4_Attaccanti.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.app import get_db_connection
from dashboard.components import render_role_page

render_role_page(get_db_connection(), "A", "Attaccanti")
```

- [ ] **Step 4: Manual verification**

Run: `cd fantacalcio && streamlit run dashboard/app.py`
Expected: browser opens to `http://localhost:8501`; sidebar shows 4 pages (5th added in Task 14); each role page loads without error (empty grid is fine — no data scraped yet), search box and sort selector are visible and functional.

- [ ] **Step 5: Commit**

```bash
git add fantacalcio/dashboard/components.py fantacalcio/dashboard/app.py fantacalcio/dashboard/pages/1_Portieri.py fantacalcio/dashboard/pages/2_Difensori.py fantacalcio/dashboard/pages/3_Centrocampisti.py fantacalcio/dashboard/pages/4_Attaccanti.py
git commit -m "feat: add Panini-style card dashboard with 4 role pages, search and sort"
```

---

### Task 14: "La Mia Rosa" page

**Files:**
- Create: `fantacalcio/dashboard/pages/5_La_Mia_Rosa.py`
- Modify: `fantacalcio/dashboard/data_access.py` (add helper)
- Modify: `fantacalcio/tests/test_data_access.py` (add test for new helper)

**Interfaces:**
- Consumes: `ranking.budget.compute_budget_summary`, `db.repository.get_roster`, `db.repository.add_roster_entry`, `db.repository.upsert_player`
- Produces: `data_access.find_player_by_name(conn, name: str) -> dict | None` (case-insensitive exact match on `canonical_name`, used by the roster page's "add player" form to resolve a typed name to a `player_id`).

- [ ] **Step 1: Write failing test for find_player_by_name**

```python
# fantacalcio/tests/test_data_access.py (append)
from dashboard.data_access import find_player_by_name


def test_find_player_by_name_case_insensitive(tmp_path):
    from db.connection import init_db, get_connection
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    repository.upsert_player(conn, "Lautaro Martinez", "Inter", "A", "Pu", None)

    found = find_player_by_name(conn, "lautaro martinez")

    assert found is not None
    assert found["canonical_name"] == "Lautaro Martinez"
    conn.close()


def test_find_player_by_name_returns_none_when_missing(tmp_path):
    from db.connection import init_db, get_connection
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    found = find_player_by_name(conn, "Nobody")

    assert found is None
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fantacalcio && pytest tests/test_data_access.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_player_by_name'`

- [ ] **Step 3: Implement find_player_by_name in data_access.py**

```python
# fantacalcio/dashboard/data_access.py (append)
def find_player_by_name(conn, name: str) -> dict | None:
    cursor = conn.execute(
        "SELECT * FROM players WHERE LOWER(canonical_name) = LOWER(?)", (name,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fantacalcio && pytest tests/test_data_access.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Implement 5_La_Mia_Rosa.py**

```python
# fantacalcio/dashboard/pages/5_La_Mia_Rosa.py
import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import streamlit as st
from dashboard.app import get_db_connection
from dashboard.data_access import find_player_by_name
from db import repository
from ranking.budget import compute_budget_summary

conn = get_db_connection()

st.title("La Mia Rosa")

with st.form("add_player_form"):
    name = st.text_input("Nome giocatore (esatto)")
    price = st.number_input("Prezzo pagato", min_value=1, step=1)
    submitted = st.form_submit_button("Aggiungi alla rosa")

    if submitted:
        player = find_player_by_name(conn, name)
        if not player:
            st.error(f"Giocatore '{name}' non trovato nel database.")
        else:
            repository.add_roster_entry(
                conn, player["id"], float(price), date.today().isoformat()
            )
            st.success(f"{player['canonical_name']} aggiunto alla rosa.")

roster = repository.get_roster(conn)
summary = compute_budget_summary(roster)

st.subheader("Crediti")
col1, col2, col3 = st.columns(3)
col1.metric("Totali", summary["total_credits"])
col2.metric("Spesi", summary["spent"])
col3.metric("Rimanenti", summary["remaining"])

st.subheader("Slot per ruolo")
role_labels = {"P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"}
cols = st.columns(4)
for col, (role, label) in zip(cols, role_labels.items()):
    slot = summary["slots"][role]
    col.metric(label, f"{slot['filled']}/{slot['total']}")

st.subheader("Giocatori acquistati")
if roster:
    st.table([
        {"Nome": r["canonical_name"], "Ruolo": r["role_classic"],
         "Prezzo": r["price_paid"], "Data": r["date_added"]}
        for r in roster
    ])
else:
    st.write("Nessun giocatore ancora aggiunto.")
```

- [ ] **Step 6: Manual verification**

Run: `cd fantacalcio && streamlit run dashboard/app.py`
Expected: "La Mia Rosa" appears as 5th sidebar page; adding a player that exists in the DB succeeds and updates credits/slots; adding a non-existent name shows an error; role pages (Task 13) now show "⭐ IN ROSA" tag for players added here.

- [ ] **Step 7: Commit**

```bash
git add fantacalcio/dashboard/pages/5_La_Mia_Rosa.py fantacalcio/dashboard/data_access.py fantacalcio/tests/test_data_access.py
git commit -m "feat: add La Mia Rosa page with credits and slot tracking"
```

---

### Task 15: Scheduling script and Task Scheduler setup

**Files:**
- Create: `fantacalcio/pipeline/scheduled_run.py`
- Create: `fantacalcio/docs/task_scheduler_setup.md`

**Interfaces:**
- Consumes: `pipeline.run_scraping.run_pipeline`, `db.connection.init_db`, `db.connection.get_connection`, `scrapers.fantacalcio_it.FantacalcioItScraper`, `scrapers.gazzetta.GazzettaScraper`
- Produces: a standalone script runnable via `python pipeline/scheduled_run.py` with no arguments, safe to invoke from Task Scheduler.

- [ ] **Step 1: Implement scheduled_run.py**

```python
# fantacalcio/pipeline/scheduled_run.py
import logging
import os
from datetime import date
from db.connection import init_db, get_connection
from scrapers.fantacalcio_it import FantacalcioItScraper
from scrapers.gazzetta import GazzettaScraper
from pipeline.run_scraping import run_pipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "fantacalcio.db")
PHOTOS_DIR = os.path.join(BASE_DIR, "data", "photos")
LOG_PATH = os.path.join(BASE_DIR, "data", "scraping.log")


def main() -> None:
    logging.basicConfig(
        filename=LOG_PATH, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    scrapers = [FantacalcioItScraper(), GazzettaScraper()]
    run_pipeline(scrapers, conn, PHOTOS_DIR, date.today().isoformat())
    conn.close()
    logging.info("Scraping run complete")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual verification**

Run: `cd fantacalcio && python pipeline/scheduled_run.py`
Expected: exits without error; `data/fantacalcio.db` and `data/scraping.log` exist and contain a "Scraping run complete" entry. (Live scraping may still fail selector matching per the Task 5/6 caveat — the important check here is that a failure in one scraper doesn't crash the script, and the log records it.)

- [ ] **Step 3: Document Task Scheduler setup**

```markdown
<!-- fantacalcio/docs/task_scheduler_setup.md -->
# Schedulare lo scraping con Windows Task Scheduler

1. Apri "Utilità di pianificazione" (Task Scheduler).
2. "Crea attività di base" → nome: "Fantacalcio Scraping Giornaliero".
3. Trigger: giornaliero, orario a scelta (es. 08:00).
4. Azione: "Avvia un programma".
   - Programma/script: percorso completo di `python.exe` (es. `C:\Python311\python.exe`)
   - Aggiungi argomenti: percorso completo di `pipeline\scheduled_run.py`
   - Inizia in: cartella `fantacalcio` (es. `C:\Users\<utente>\Projects\AI-Projects\fantacalcio`)
5. Salva. Verifica i log in `data/scraping.log` dopo la prima esecuzione schedulata.
```

- [ ] **Step 4: Commit**

```bash
git add fantacalcio/pipeline/scheduled_run.py fantacalcio/docs/task_scheduler_setup.md
git commit -m "feat: add scheduled scraping entry point and Task Scheduler docs"
```

---

## Self-Review Notes

- **Spec coverage:** modular per-site scrapers (Tasks 4-6), fault isolation (Task 10), SQLite history (Tasks 2-3), player matching (Task 7), ranking formula (Task 8), photo download with placeholder fallback (Tasks 9, 13), 4 role pages + search + sort by name/team/price (Tasks 13), editable notes surfaced read-only in dashboard (Task 12-13; writing notes remains a manual DB/Claude-assisted step outside this plan, per spec), roster/credits page with budget+slot tracking and roster highlighting (Tasks 11, 14), scheduling (Task 15). All covered.
- **Out of scope confirmed still out of scope:** no cloud deploy, no in-app note generation via API, no live formations/voti — none of the tasks above introduce these.
- **Type consistency checked:** `PlayerRecord` fields used identically across Tasks 4-10; `get_latest_quotations` dict keys (`price_current`, `fantamedia`, `avg_rating`, `appearances`, `status`, `canonical_name`, `team`, `player_id`, `source`, `photo_path`) match what `scorer.py`, `data_access.py`, and `components.py` all read; `compute_budget_summary` output shape matches what `5_La_Mia_Rosa.py` consumes.
