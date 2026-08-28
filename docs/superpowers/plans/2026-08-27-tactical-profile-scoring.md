# Tactical Profile Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score difensori and centrocampisti by their real tactical/offensive profile (quinto/terzino offensivo, trequartista, mediano, ecc.), not just their official role, per `giocatori/movimento.md` and `giocatori/rosa-ideale.md`.

**Architecture:** Fantacalcio.it's own "Ruolo Mantra" taxonomy (`por/dc/dd/ds/b/e/m/c/t/w/a/pc`) already encodes almost exactly the tactical taxonomy the specs ask for (quinto=`e`, trequartista=`t`, mediano=`m`, seconda punta=`a`, ecc.) — confirmed live on `fantacalcio.it/quotazioni-fantacalcio` (`data-filter-role-mantra` attribute + `span.role.role-mantra[data-value]`), and the `fantacalcio_it_sample.html` fixture already contains this markup unused. So instead of scraping new xG/xA/shots data (a much larger, riskier undertaking — no source for that currently exists in this codebase), this plan: (1) captures `role_mantra` from the primary source, (2) combines it with goals/assists already in `player_season_stats` and set-piece hierarchy already in `player_set_pieces` into a new `tactical_profile_score` (0-100, a separated score like `player_quality`/`risk`), and (3) folds a small, bounded nudge from it into the existing `score` (Fantasy Value) for difensori/centrocampisti only — the two departments both specs single out.

**Tech Stack:** Python 3.11, BeautifulSoup4 (existing `fantacalcio_it.py` scraper), sqlite3, pytest.

## Global Constraints

- Keep `compute_score`'s existing behavior for portieri and attaccanti unchanged — both specs focus the tactical-profile adjustment on difensori/centrocampisti; attaccanti's goal threat is already captured well by `fantamedia`.
- Never make `tactical_profile_score` a coequal term with `fantamedia` in `compute_score` — follow the existing "small bounded nudge, not a replacement" pattern already documented for `VALUE_ADJUSTMENT_WEIGHT` in `ranking/scorer.py` (a past version of `compute_decision_score` weighted an adjustment too heavily and let a lesser player outrank a clearly better one — do not repeat that mistake here).
- No new external scraper/data source in this plan — everything must come from data already in the schema (`player_season_stats`, `player_set_pieces`, `fcp_metrics`) or already present on a page a scraper already fetches (`role_mantra` on fantacalcio.it's existing quotazioni page).
- Match existing repo conventions: one test file per module (`tests/test_<module>.py`), `tests/fixtures/*.html` for scraper fixtures, tunable weights as named module-level constants with a comment explaining the choice (see `FCP_RISK_WEIGHT`, `VALUE_ADJUSTMENT_WEIGHT` in `ranking/scorer.py` for the house style).

---

## File Structure

- `scrapers/fantacalcio_it.py` — modify `parse_html` to extract `role_mantra`.
- `pipeline/run_scraping.py` — modify `run_pipeline` to prefer a non-`None` `role_mantra` among matched records instead of blindly using `records[0]`.
- `ranking/tactical_profile.py` — **new**: `compute_tactical_profile_score(row)`, the role-mantra tier table, and the goals/assists/set-piece production bonus.
- `ranking/scorer.py` — modify `compute_score` and `enrich_scores` to fold in the new score.
- `db/repository.py` — **new** bulk-fetch functions `get_all_latest_player_season_stats` and `get_all_player_set_pieces`, mirroring the existing `get_all_latest_fcp_metrics` pattern.
- `dashboard/data_access.py` — modify `_attach_fcp_metrics` (rename concerns slightly) to also merge season stats and set pieces into ranked rows, and to carry `predicted_goals`/`predicted_assists`.
- Tests: `tests/test_fantacalcio_it_scraper.py`, `tests/test_run_scraping.py`, `tests/test_tactical_profile.py` (new), `tests/test_scorer.py`, `tests/test_db_repository.py`, `tests/test_data_access.py`.

---

### Task 1: Capture `role_mantra` in the fantacalcio.it scraper

**Files:**
- Modify: `scrapers/fantacalcio_it.py`
- Test: `tests/test_fantacalcio_it_scraper.py`
- Fixture (already has the markup, no change needed): `fixtures/fantacalcio_it_sample.html`

**Interfaces:**
- Produces: `PlayerRecord.role_mantra` populated with an uppercase 2-letter-or-less code (`POR`, `DC`, `DD`, `DS`, `B`, `E`, `M`, `C`, `T`, `W`, `A`, `PC`) instead of always `None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_fantacalcio_it_scraper.py`:

```python
def test_parse_html_extracts_role_mantra():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    records = parse_html(html)

    martinez = next(r for r in records if r.name == "Martinez L.")
    assert martinez.role_mantra == "PC"

    sommer = next(r for r in records if r.name == "Sommer")
    assert sommer.role_mantra == "POR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fantacalcio_it_scraper.py::test_parse_html_extracts_role_mantra -v`
Expected: FAIL — `assert None == "PC"`

- [ ] **Step 3: Implement**

In `scrapers/fantacalcio_it.py`, inside `parse_html`, add the extraction and pass it through:

```python
    for row in soup.select("tr.player-row"):
        role_span = row.select_one("th.player-role-classic span.role")
        role_mantra_span = row.select_one("th.player-role-mantra span.role-mantra")
        name_span = row.select_one("th.player-name a.player-name span")
        team_td = row.select_one("td.player-team")
        price_initial_td = row.select_one("td.player-classic-initial-price")
        price_current_td = row.select_one("td.player-classic-current-price")

        if not (role_span and name_span and team_td):
            continue

        role_mantra = None
        if role_mantra_span and role_mantra_span.get("data-value"):
            role_mantra = role_mantra_span["data-value"].upper()

        records.append(PlayerRecord(
            name=name_span.get_text(strip=True),
            team=team_td.get_text(strip=True),
            role_classic=ROLE_MAP.get(role_span.get("data-value", ""), ""),
            role_mantra=role_mantra,
            price_current=float(price_current_td.get_text(strip=True)) if price_current_td else None,
            price_initial=float(price_initial_td.get_text(strip=True)) if price_initial_td else None,
            status=None,
            fantamedia=None,
            avg_rating=None,
            appearances=None,
            photo_url=None,
            source="fantacalcio_it",
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fantacalcio_it_scraper.py -v`
Expected: PASS (both the new test and the pre-existing `test_parse_html_extracts_players`)

- [ ] **Step 5: Commit**

```bash
git add scrapers/fantacalcio_it.py tests/test_fantacalcio_it_scraper.py
git commit -m "feat: capture ruolo mantra from fantacalcio.it quotazioni"
```

---

### Task 2: Prefer a non-null `role_mantra` when merging sources

**Context:** `run_pipeline` currently does `first = records[0]` and always uses `first.role_mantra` — with every scraper except fantacalcio.it now returning `None` (pianetafanta still does but isn't wired into `pipeline/scheduled_run.py`), whichever source happens to sort first in the matched group can silently blank out a real value.

**Files:**
- Modify: `pipeline/run_scraping.py`
- Test: `tests/test_run_scraping.py`

**Interfaces:**
- Produces: `upsert_player` is called with the first non-`None` `role_mantra` among the matched records for a player, falling back to `None` only if every record has it.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_run_scraping.py`:

```python
class FakeScraperWithMantra(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Martinez L.", team="Inter", role_classic="A", role_mantra=None,
            price_current=37, price_initial=29, status="ok", fantamedia=None,
            avg_rating=6.7, appearances=None, photo_url=None,
            source="gazzetta",
        )]


class FakeScraperMantraSource(BaseScraper):
    def fetch(self):
        return [PlayerRecord(
            name="Lautaro Martinez", team="Inter", role_classic="A", role_mantra="PC",
            price_current=38, price_initial=30, status="ok", fantamedia=6.8,
            avg_rating=6.5, appearances=30, photo_url=None,
            source="fantacalcio_it",
        )]


def test_run_pipeline_keeps_role_mantra_even_when_first_source_lacks_it(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    run_pipeline(
        scrapers=[FakeScraperWithMantra(), FakeScraperMantraSource()],
        conn=conn,
        photos_dir=str(tmp_path / "photos"),
        scrape_date="2026-08-22",
        skip_photos=True,
    )

    row = conn.execute("SELECT role_mantra FROM players").fetchone()
    assert row["role_mantra"] == "PC"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_scraping.py::test_run_pipeline_keeps_role_mantra_even_when_first_source_lacks_it -v`
Expected: FAIL — `role_mantra` is `None` (came from `records[0]`, the gazzetta record).

- [ ] **Step 3: Implement**

In `pipeline/run_scraping.py`, replace the `first = records[0]` role_mantra usage:

```python
    for (canonical_name, team), records_with_confidence in groups.items():
        records = [record for record, _ in records_with_confidence]
        first = records[0]
        role_mantra = next((r.role_mantra for r in records if r.role_mantra), None)
        photo_record = next((r for r in records if r.photo_url), None)

        player_id = repository.upsert_player(
            conn, canonical_name, team, first.role_classic, role_mantra, None,
        )

        photo_url = photo_record.photo_url if photo_record else None
        if not photo_url and not skip_photos:
            photo_url = find_photo_url(canonical_name, team)

        if photo_url:
            local_path = download_photo(photo_url, player_id, photos_dir)
            if local_path:
                repository.upsert_player(
                    conn, canonical_name, team, first.role_classic, role_mantra,
                    local_path,
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_scraping.py -v`
Expected: PASS (all tests in the file, including the pre-existing merge test)

- [ ] **Step 5: Commit**

```bash
git add pipeline/run_scraping.py tests/test_run_scraping.py
git commit -m "fix: keep role_mantra from any matched source, not just the first"
```

---

### Task 3: Bulk repository fetchers for season stats and set pieces

**Context:** `dashboard/data_access._attach_fcp_metrics` already shows the pattern needed (fetch everything once via a `player_id -> data` dict, merge into rows in a loop) for `fcp_metrics`. `player_season_stats` and `player_set_pieces` need the same bulk-fetch treatment — the existing `get_player_season_stats`/`get_player_set_pieces` are per-player only, which would mean N+1 queries if called per row in a ranked list.

**Files:**
- Modify: `db/repository.py`
- Test: `tests/test_db_repository.py`

**Interfaces:**
- Produces: `get_all_latest_player_season_stats(conn) -> dict[int, dict]` (player_id -> most recent season's row, same shape as one row from `get_player_season_stats`).
- Produces: `get_all_player_set_pieces(conn) -> dict[int, list[dict]]` (player_id -> list of `{category, rank, source, updated_at}`, same shape as `get_player_set_pieces`'s rows).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_db_repository.py` (follow the existing file's `init_db`/`get_connection` tmp_path fixture pattern used by its other tests):

```python
def test_get_all_latest_player_season_stats_returns_most_recent_season(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(str(tmp_path / "test.db"))
    player_id = repository.upsert_player(conn, "Nico Paz", "Como", "C", "T", None)

    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        {"season": "2024/25", "appearances": 30, "goals_scored": 5, "goals_conceded": None,
         "assists": 4, "avg_rating": 6.3, "yellow_cards": 3, "red_cards": 0},
        {"season": "2025/26", "appearances": 10, "goals_scored": 3, "goals_conceded": None,
         "assists": 2, "avg_rating": 6.6, "yellow_cards": 1, "red_cards": 0},
    ], scraped_at="2026-08-27")

    result = repository.get_all_latest_player_season_stats(conn)

    assert result[player_id]["season"] == "2025/26"
    assert result[player_id]["goals_scored"] == 3
    conn.close()


def test_get_all_player_set_pieces_groups_by_player(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(str(tmp_path / "test.db"))
    player_id = repository.upsert_player(conn, "Calhanoglu", "Inter", "C", "M", None)

    repository.replace_player_set_pieces(conn, "fantacalcio_it", [
        (player_id, "rigori", 1, "2026-08-27"),
        (player_id, "punizioni", 1, "2026-08-27"),
    ])

    result = repository.get_all_player_set_pieces(conn)

    categories = {sp["category"] for sp in result[player_id]}
    assert categories == {"rigori", "punizioni"}
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db_repository.py -k "season_stats_returns_most_recent or set_pieces_groups_by_player" -v`
Expected: FAIL — `AttributeError: module 'db.repository' has no attribute 'get_all_latest_player_season_stats'`

- [ ] **Step 3: Implement**

Add to `db/repository.py`, next to `get_all_latest_fcp_metrics`:

```python
def get_all_latest_player_season_stats(conn: sqlite3.Connection) -> dict:
    """player_id -> most recent season's row (by season string, descending),
    for bulk merge into ranking rows — same pattern as
    get_all_latest_fcp_metrics."""
    cursor = conn.execute(
        """
        SELECT s.* FROM player_season_stats s
        WHERE s.id = (
            SELECT s2.id FROM player_season_stats s2
            WHERE s2.player_id = s.player_id
            ORDER BY s2.season DESC, s2.id DESC
            LIMIT 1
        )
        """
    )
    return {row["player_id"]: dict(row) for row in cursor.fetchall()}


def get_all_player_set_pieces(conn: sqlite3.Connection) -> dict:
    """player_id -> list of {category, rank, source, updated_at}, for bulk
    merge into ranking rows — same pattern as get_all_latest_fcp_metrics."""
    cursor = conn.execute(
        "SELECT player_id, category, rank, source, updated_at FROM player_set_pieces"
    )
    result: dict = {}
    for row in cursor.fetchall():
        result.setdefault(row["player_id"], []).append({
            "category": row["category"], "rank": row["rank"],
            "source": row["source"], "updated_at": row["updated_at"],
        })
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db_repository.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add db/repository.py tests/test_db_repository.py
git commit -m "feat: bulk fetchers for season stats and set pieces"
```

---

### Task 4: `ranking/tactical_profile.py` — the scoring module

**Files:**
- Create: `ranking/tactical_profile.py`
- Test: `tests/test_tactical_profile.py`

**Interfaces:**
- Consumes: a row dict with `role_classic`, `role_mantra`, `season_goals_scored`, `season_assists`, `predicted_goals` (range string like `"12/15"` or `None`), `predicted_assists`, `set_pieces` (list of `{category, rank}` dicts or `None`) — these are the keys Task 6 will populate on ranked rows.
- Produces: `compute_tactical_profile_score(row: dict) -> float | None` — `None` for portieri (`role_classic == "P"`), otherwise 0-100.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tactical_profile.py`:

```python
from ranking.tactical_profile import compute_tactical_profile_score


def test_goalkeepers_have_no_tactical_profile_score():
    row = {"role_classic": "P", "role_mantra": "POR"}
    assert compute_tactical_profile_score(row) is None


def test_quinto_offensivo_scores_higher_than_centrale_puro():
    quinto = {"role_classic": "D", "role_mantra": "E"}
    centrale = {"role_classic": "D", "role_mantra": "DC"}
    assert compute_tactical_profile_score(quinto) > compute_tactical_profile_score(centrale)


def test_trequartista_scores_higher_than_mediano():
    trequartista = {"role_classic": "C", "role_mantra": "T"}
    mediano = {"role_classic": "C", "role_mantra": "M"}
    assert compute_tactical_profile_score(trequartista) > compute_tactical_profile_score(mediano)


def test_goals_and_assists_lift_the_score():
    plain = {"role_classic": "C", "role_mantra": "C"}
    productive = {
        "role_classic": "C", "role_mantra": "C",
        "season_goals_scored": 8, "season_assists": 7,
    }
    assert compute_tactical_profile_score(productive) > compute_tactical_profile_score(plain)


def test_penalty_taker_gets_a_set_piece_bonus():
    base = {"role_classic": "D", "role_mantra": "DC"}
    rigorista = {
        "role_classic": "D", "role_mantra": "DC",
        "set_pieces": [{"category": "rigori", "rank": 1}],
    }
    assert compute_tactical_profile_score(rigorista) > compute_tactical_profile_score(base)


def test_missing_role_mantra_falls_back_to_role_classic_baseline():
    row = {"role_classic": "D", "role_mantra": None}
    score = compute_tactical_profile_score(row)
    assert score is not None and 0 <= score <= 100


def test_predicted_goals_used_when_no_season_stats_yet():
    # New signing (movimento.md sez. 22): no player_season_stats row yet,
    # falls back to Fantacalciopedia's "gol previsti" range.
    row = {
        "role_classic": "A", "role_mantra": "PC",
        "predicted_goals": "12/15", "predicted_assists": "3/5",
    }
    no_data = {"role_classic": "A", "role_mantra": "PC"}
    assert compute_tactical_profile_score(row) > compute_tactical_profile_score(no_data)


def test_score_is_clipped_to_0_100():
    row = {
        "role_classic": "C", "role_mantra": "T",
        "season_goals_scored": 40, "season_assists": 40,
        "set_pieces": [{"category": "rigori", "rank": 1}, {"category": "punizioni", "rank": 1}],
    }
    assert compute_tactical_profile_score(row) == 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tactical_profile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ranking.tactical_profile'`

- [ ] **Step 3: Implement**

Create `ranking/tactical_profile.py`:

```python
"""fantasy_profile_score (giocatori/movimento.md sez. 15/18, giocatori/
rosa-ideale.md sez. 2/24): how much a player's REAL tactical role, not his
official role_classic, is worth to a fantacalcio squad.

Fantacalcio.it's own "Ruolo Mantra" taxonomy (role_mantra: por/dc/dd/ds/b/e/
m/c/t/w/a/pc) already encodes almost exactly the tactical profile the specs
describe — quinto offensivo = "e", trequartista = "t", mediano = "m",
seconda punta = "a" — so this module builds on that instead of needing new
xG/xA/shots scraping infrastructure that doesn't exist in this codebase.

Deliberately a SEPARATE score (like ranking.scorer.compute_player_quality/
compute_risk), not folded wholesale into Fantasy Value: only
ranking.scorer.compute_score applies a small, bounded nudge from it, and
only for difensori/centrocampisti — see that module's TACTICAL_PROFILE_WEIGHT.
"""

# 0-100 baseline per role_mantra code, calibrated from the explicit ordering
# in movimento.md sez. 18 (+++++ / ++++ / +++ / ++ / + / -). Deliberately
# leaves headroom below 100 for the production bonus below to lift a
# genuinely prolific player of any profile — a "DC" who scores 10 goals a
# season should still be able to outscore a "T" who never touches the ball
# in the final third.
ROLE_MANTRA_BASE = {
    "DC": 20,   # centrale puro
    "DD": 35,   # terzino destro
    "DS": 35,   # terzino sinistro
    "B": 30,    # braccetto
    "E": 45,    # quinto/esterno di centrocampo — top difensivo per lo spec
    "M": 10,    # mediano — "-" nello spec
    "C": 25,    # centrocampista centrale
    "T": 55,    # trequartista — top per lo spec
    "W": 50,    # ala/esterno offensivo
    "A": 50,    # attaccante di raccordo/seconda punta
    "PC": 40,   # punta centrale — il gol atteso lo spinge oltre coi bonus sotto
}

# Usato solo quando role_mantra manca (fonte non ancora scrappata per quel
# giocatore): baseline neutra per reparto, non penalizzante né premiante.
ROLE_CLASSIC_FALLBACK_BASE = {"D": 25, "C": 25, "A": 35}

GOALS_WEIGHT = 3.0
ASSISTS_WEIGHT = 2.5
SET_PIECE_RANK1_BONUS = 12.0
SET_PIECE_RANK2_BONUS = 5.0
SET_PIECE_CATEGORIES = {"rigori", "punizioni"}

# Tetto al contributo di gol+assist+piazzati, cosi' un singolo giocatore da
# 40 gol non manda la produzione a valori assurdi rispetto alla base
# tattica — coerente con lo stile "aggiustamento limitato" gia' usato in
# ranking.scorer (VALUE_ADJUSTMENT_WEIGHT).
PRODUCTION_CAP = 45.0


def _numeric_avg_from_range(text) -> float:
    """"12/15" -> 13.5. Fantacalciopedia's predicted_goals/predicted_assists
    format (see scrapers.fantacalciopedia.parse_detail). None/unparseable
    -> None."""
    if not text:
        return None
    parts = str(text).replace(",", ".").split("/")
    try:
        values = [float(p.strip()) for p in parts if p.strip()]
    except ValueError:
        return None
    return sum(values) / len(values) if values else None


def compute_tactical_profile_score(row: dict):
    """None for portieri (role_classic == "P") — clean sheets/gol subiti are
    already scored by ranking.scorer, a tactical/offensive profile doesn't
    apply. Otherwise 0-100."""
    role_classic = row.get("role_classic")
    if role_classic == "P":
        return None

    role_mantra = row.get("role_mantra")
    base = ROLE_MANTRA_BASE.get(role_mantra) if role_mantra else None
    if base is None:
        base = ROLE_CLASSIC_FALLBACK_BASE.get(role_classic, 20)

    goals = row.get("season_goals_scored")
    if goals is None:
        goals = _numeric_avg_from_range(row.get("predicted_goals"))
    assists = row.get("season_assists")
    if assists is None:
        assists = _numeric_avg_from_range(row.get("predicted_assists"))

    production = 0.0
    if goals is not None:
        production += goals * GOALS_WEIGHT
    if assists is not None:
        production += assists * ASSISTS_WEIGHT

    for set_piece in row.get("set_pieces") or []:
        if set_piece.get("category") not in SET_PIECE_CATEGORIES:
            continue
        if set_piece.get("rank") == 1:
            production += SET_PIECE_RANK1_BONUS
        elif set_piece.get("rank") == 2:
            production += SET_PIECE_RANK2_BONUS

    production = min(production, PRODUCTION_CAP)

    return round(max(0.0, min(100.0, base + production)), 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tactical_profile.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add ranking/tactical_profile.py tests/test_tactical_profile.py
git commit -m "feat: fantasy_profile_score from ruolo mantra + gol/assist/piazzati"
```

---

### Task 5: Fold the tactical profile into `ranking/scorer.py`

**Files:**
- Modify: `ranking/scorer.py`
- Test: `tests/test_scorer.py`

**Interfaces:**
- Consumes: `ranking.tactical_profile.compute_tactical_profile_score(row)` (Task 4).
- Produces: `enrich_scores(row)["tactical_profile_score"]` (always present, `None` for portieri); `compute_score(row)` nudged by it for `role_classic in ("D", "C")` only.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scorer.py`:

```python
def test_compute_score_rewards_offensive_tactical_profile_for_defenders():
    base = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "D", "role_mantra": "DC",
    }
    quinto_offensivo = {
        **base, "role_mantra": "E", "season_goals_scored": 4, "season_assists": 5,
    }
    assert compute_score(quinto_offensivo) > compute_score(base)


def test_compute_score_does_not_use_tactical_profile_for_attaccanti():
    base = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "A", "role_mantra": "PC",
    }
    same_but_winger_mantra = {**base, "role_mantra": "W"}
    # role_mantra differs but role_classic "A" isn't nudged by tactical
    # profile in compute_score — attaccanti are scored on fantamedia alone.
    assert compute_score(base) == compute_score(same_but_winger_mantra)


def test_enrich_scores_exposes_tactical_profile_score():
    row = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "C", "role_mantra": "T",
    }
    enriched = enrich_scores(row)
    assert enriched["tactical_profile_score"] is not None
    assert 0 <= enriched["tactical_profile_score"] <= 100


def test_enrich_scores_tactical_profile_score_none_for_portieri():
    row = {
        "fantamedia": 6.0, "avg_rating": None, "appearances": 38, "status": "ok",
        "role_classic": "P", "role_mantra": "POR",
    }
    assert enrich_scores(row)["tactical_profile_score"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -k "tactical_profile" -v`
Expected: FAIL — `compute_score` doesn't change with `role_mantra`; `enrich_scores(row)` has no `"tactical_profile_score"` key.

- [ ] **Step 3: Implement**

In `ranking/scorer.py`, add the import and two new constants near the top:

```python
import bisect

from ranking.tactical_profile import compute_tactical_profile_score

PENALIZED_STATUSES = {"infortunato", "squalificato"}
```

```python
# compute_score nudges Fantasy Value by tactical_profile_score for
# difensori/centrocampisti only (giocatori/movimento.md, giocatori/
# rosa-ideale.md both single out these two reparti — attaccanti's threat
# is already captured by fantamedia/gol). Centered on a fixed neutral
# baseline rather than added raw, so an average-profile player isn't
# inflated relative to portieri/attaccanti scores compute_score also
# produces (ideal_squad/lp_optimizer sum "score" across roles): only a
# clearly above/below-average tactical profile moves the score, and only by
# a bounded +/-7 at the extremes — small next to fantamedia's *10 term, same
# "adjustment, not a coequal term" philosophy as VALUE_ADJUSTMENT_WEIGHT
# below.
TACTICAL_PROFILE_WEIGHT = 0.10
NEUTRAL_TACTICAL_PROFILE = 30.0
TACTICAL_PROFILE_ROLES = {"D", "C"}
```

Modify `compute_score` to add the nudge before returning:

```python
def compute_score(row: dict) -> float:
    """..."""
    base = row.get("fantamedia")
    if base is None:
        base = row.get("avg_rating")
    if base is None:
        base = 0.0

    appearances = row.get("appearances")
    reliability = (min(appearances, 38) / 38) if appearances is not None else 0.5

    penalty = 15 if row.get("status") in PENALIZED_STATUSES else 0
    if appearances is not None and appearances < UNPROVEN_APPEARANCES_THRESHOLD:
        penalty += UNPROVEN_PENALTY * (1 - appearances / UNPROVEN_APPEARANCES_THRESHOLD)

    score = base * 10 + reliability * 5 - penalty

    if row.get("role_classic") in TACTICAL_PROFILE_ROLES:
        tactical = compute_tactical_profile_score(row)
        if tactical is not None:
            score += (tactical - NEUTRAL_TACTICAL_PROFILE) * TACTICAL_PROFILE_WEIGHT

    return score
```

Add `tactical_profile_score` to `enrich_scores`:

```python
def enrich_scores(row: dict) -> dict:
    """..."""
    enriched = dict(row)
    fantasy_value = compute_score(row)
    enriched["score"] = fantasy_value
    enriched["player_quality"] = compute_player_quality(row)
    enriched["risk"] = compute_risk(row)
    enriched["tactical_profile_score"] = compute_tactical_profile_score(row)
    enriched["value_for_money"] = compute_value_for_money(fantasy_value, row.get("price_current"))
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorer.py -v`
Expected: PASS (all tests in the file, including the pre-existing ones — the neutral baseline of 30 means a plain "C"/"DC" player without production stats should barely move; double check `test_rank_players_orders_best_to_worst` and the other pre-existing tests still pass unchanged since none of them set `role_classic`/`role_mantra`, so `row.get("role_classic") in TACTICAL_PROFILE_ROLES` is `False` and the nudge is skipped entirely for them).

- [ ] **Step 5: Commit**

```bash
git add ranking/scorer.py tests/test_scorer.py
git commit -m "feat: nudge Fantasy Value by tactical profile for D/C, expose as a separated score"
```

---

### Task 6: Merge season stats, set pieces and predicted gol/assist into ranked rows

**Files:**
- Modify: `dashboard/data_access.py`
- Test: `tests/test_data_access.py`

**Interfaces:**
- Consumes: `db.repository.get_all_latest_player_season_stats` and `get_all_player_set_pieces` (Task 3).
- Produces: every row from `get_ranked_role`/`_compute_ranked_role` gains `season_goals_scored`, `season_assists`, `set_pieces`, `predicted_goals`, `predicted_assists` — the exact keys `ranking.tactical_profile.compute_tactical_profile_score` (Task 4) reads, so `rank_players` (called inside `_compute_ranked_role`) now has everything it needs.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_data_access.py` (follow that file's existing fixture-setup pattern — check how it seeds `fcp_metrics` for its current `_attach_fcp_metrics`-adjacent tests and mirror it for `player_season_stats`/`player_set_pieces`):

```python
def test_compute_ranked_role_merges_season_stats_and_set_pieces(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    player_id = repository.upsert_player(conn, "Calhanoglu", "Inter", "C", "M", None)
    repository.insert_quotation(
        conn, player_id, "fantacalcio_it", "2026-08-27",
        price_current=20, price_initial=18, status="ok",
        fantamedia=6.5, avg_rating=6.5, appearances=30,
    )
    repository.insert_quotation(
        conn, player_id, "fantanalisi", "2026-08-27",
        price_current=21, price_initial=19, status="ok",
        fantamedia=6.4, avg_rating=6.4, appearances=30,
    )
    repository.upsert_player_season_stats(conn, player_id, "fantacalciopedia", [
        {"season": "2025/26", "appearances": 30, "goals_scored": 6, "goals_conceded": None,
         "assists": 5, "avg_rating": 6.5, "yellow_cards": 2, "red_cards": 0},
    ], scraped_at="2026-08-27")
    repository.replace_player_set_pieces(conn, "fantacalcio_it", [
        (player_id, "rigori", 1, "2026-08-27"),
    ])

    rows = get_ranked_role(conn, "C")

    row = next(r for r in rows if r["player_id"] == player_id)
    assert row["season_goals_scored"] == 6
    assert row["season_assists"] == 5
    assert {sp["category"] for sp in row["set_pieces"]} == {"rigori"}
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_access.py::test_compute_ranked_role_merges_season_stats_and_set_pieces -v`
Expected: FAIL — `KeyError: 'season_goals_scored'`

- [ ] **Step 3: Implement**

In `dashboard/data_access.py`, extend `_attach_fcp_metrics` to also carry the predicted gol/assist range strings (small addition, same loop):

```python
def _attach_fcp_metrics(rows: list, conn) -> list:
    """..."""
    metrics_by_player = repository.get_all_latest_fcp_metrics(conn)
    for row in rows:
        metrics = metrics_by_player.get(row["player_id"])
        if not metrics:
            continue
        row["alg_fcp"] = metrics["alg_fcp"]
        row["punteggio_fcp"] = metrics["punteggio_fcp"]
        row["investment_stability_pct"] = metrics["investment_stability_pct"]
        row["injury_resistance_pct"] = metrics["injury_resistance_pct"]
        row["fcp_skills"] = metrics["skills"]
        row["predicted_goals"] = metrics["predicted_goals"]
        row["predicted_assists"] = metrics["predicted_assists"]
    return rows


def _attach_tactical_profile_inputs(rows: list, conn) -> list:
    """Merges season goals/assists (player_season_stats) and set-piece
    hierarchy (player_set_pieces) into each row — the two data sources
    ranking.tactical_profile.compute_tactical_profile_score needs on top of
    role_mantra (already on the row from the players table join) and the
    predicted_goals/predicted_assists _attach_fcp_metrics adds above."""
    season_stats_by_player = repository.get_all_latest_player_season_stats(conn)
    set_pieces_by_player = repository.get_all_player_set_pieces(conn)
    for row in rows:
        season_stats = season_stats_by_player.get(row["player_id"])
        row["season_goals_scored"] = season_stats["goals_scored"] if season_stats else None
        row["season_assists"] = season_stats["assists"] if season_stats else None
        row["set_pieces"] = set_pieces_by_player.get(row["player_id"], [])
    return rows
```

Wire it into `_compute_ranked_role`, right after the existing `_attach_fcp_metrics` call:

```python
    rows = _attach_fcp_metrics(rows, _conn)
    rows = _attach_tactical_profile_inputs(rows, _conn)
    return rank_players(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_access.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add dashboard/data_access.py tests/test_data_access.py
git commit -m "feat: merge season stats and set pieces into ranked rows for tactical scoring"
```

---

### Task 7: Surface the tactical profile on the player detail page

**Files:**
- Modify: `dashboard/components.py`
- Test: `tests/test_components.py`

**Interfaces:**
- Consumes: `row["tactical_profile_score"]`, `row["role_mantra"]` (already displayed at line ~953).

**Note on testing Streamlit UI functions:** first read `tests/test_components.py` to see how it already tests `render_player_detail`/`render_player_card` (e.g. via `streamlit.testing.v1.AppTest`, or by monkeypatching `st`) and match that exact approach for the new test — do not introduce a second testing style for the same file.

- [ ] **Step 1: Write the failing test**

Using the harness already established in `tests/test_components.py` for `render_player_detail`, add a test asserting that when `row["tactical_profile_score"]` is a number, `render_player_detail(row)` renders a metric containing "Profilo tattico" and the score value, and that when `row["tactical_profile_score"]` is `None` (e.g. a portiere), rendering does not raise and no "Profilo tattico" metric appears.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_components.py -k profilo_tattico -v`
Expected: FAIL — no "Profilo tattico" metric is rendered yet.

- [ ] **Step 3: Implement**

In `dashboard/components.py`, inside `render_player_detail`, add a metric next to the existing `info_cols2` row (after `Presenze`) — find the block:

```python
    info_cols2 = st.columns(4)
    info_cols2[0].metric("Media voto", row.get("avg_rating", "-"), help=METRIC_HELP["media_voto"])
    info_cols2[1].metric("Presenze", row.get("appearances", "-"), help=METRIC_HELP["presenze"])
```

and add a third metric using the two free columns already allocated in that `st.columns(4)` row:

```python
    tactical_score = row.get("tactical_profile_score")
    if tactical_score is not None:
        info_cols2[2].metric(
            "Profilo tattico", f"{tactical_score:.0f}/100",
            help="Quanto il ruolo REALE del giocatore (giocatori/movimento.md) "
                 "vale al fantacalcio, non solo il ruolo ufficiale — quinti/terzini "
                 "offensivi, trequartisti, seconde punte segnano alto; mediani, "
                 "centrali puri, registi bassi segnano basso.",
        )
```

Add `"profilo tattico"` reasoning to `METRIC_HELP` only if that dict is referenced elsewhere for consistency — otherwise the inline `help=` string above is sufficient and matches the file's existing ad-hoc `help=` usage.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_components.py -v`
Expected: PASS (all tests in the file)

Also verify manually with `streamlit run dashboard/app.py`: open a Centrocampisti/Difensori player detail and confirm "Profilo tattico" renders without error for both a player with and one without `role_mantra` set.

- [ ] **Step 5: Commit**

```bash
git add dashboard/components.py tests/test_components.py
git commit -m "feat: show profilo tattico on player detail page"
```

---

## Explicitly out of scope for this plan

- New scraping of xG/xA/shots/key passes/touches-in-area (`movimento.md` sez. 15/17's full stat list). No source for these exists in the codebase today; adding one (e.g. FBref) is a separate, much larger project (new scraper, new matching, rate-limit/reliability risk on an external site) and should get its own spec/plan if wanted later.
- `tactical_profile` as a stored, versioned classification per movimento.md sez. 24 (`tactical_profile = WINGER`, `offensive_profile_score = 87`, ...) — `role_mantra` already stored on `players` plus the computed `tactical_profile_score` cover the same need without a schema migration; revisit only if a future spec needs the profile itself queryable/filterable independent of the score.
- Wiring `tactical_profile_score` into `ranking/ideal_squad.py`/`ranking/lp_optimizer.py` beyond the implicit effect of Task 5's `score` nudge (LP optimizer already maximizes `score`, which now carries the nudge) — a dedicated extra weight there would double-count the same signal.
