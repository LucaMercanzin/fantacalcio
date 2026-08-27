# Portieri Depth Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Portieri dashboard page shows exactly the titolare + riserva for each of the 20 Serie A teams (40 players), grouped by team, instead of a flat list of every scraped goalkeeper — per `giocatori/portieri.md`.

**Architecture:** Almost everything `portieri.md` asks for already exists: `get_ranked_role` already filters to `is_current_serie_a_team` (sez. 3/12 "rosa reale alla data dello scraping", "current_team non storico"), already excludes third-string keepers below `RELIABLE_APPEARANCES_MIN`, and `PROMOTED_TEAMS`/`is_promoted` already exist and are used to sort promoted teams last elsewhere (sez. 17 "neopromosse per ultime"). What's missing is purely the **grouping**: turning that flat, already-correct list into a per-team titolare/riserva structure. This plan adds one small ranking module (mirroring the existing `ranking/tiers.py` shape: takes `get_ranked_role`'s output for one role, returns a grouped structure) and a dedicated rendering path on the Portieri page only (it already has its own page file, `dashboard/pages/1_Portieri.py`, so this doesn't touch the shared `render_role_page` used by Difensori/Centrocampisti/Attaccanti).

**Tech Stack:** Python 3.11, Streamlit, sqlite3, pytest.

## Global Constraints

- No new scraper: the starter/backup hierarchy is derived from existing consensus data (`score`, itself driven by `fantamedia`/`avg_rating`/`appearances`/`status`) — `portieri.md` sez. 7's "priorità 1: gerarchia esplicita della fonte" data (an explicit 1./2./3. ordered list per team) isn't scraped by anything in this codebase today, so `score`-ranking within team is the best available proxy. Note this limitation in the module's docstring rather than silently pretending it's the spec's Priorità 1.
- Never invent a second goalkeeper for a team that only has one identifiable (sez. 13: "non inventare il secondo giocatore") — surface a warning instead.
- Reuse `PROMOTED_TEAMS`/`is_promoted` (already correct for 2026/27: Venezia, Frosinone, Monza — verified against the current Serie A standings) rather than adding a second, possibly-diverging team list.

---

## File Structure

- `ranking/goalkeepers.py` — **new**: `build_goalkeeper_depth_chart(rows)`, mirrors `ranking/tiers.py`'s shape.
- `dashboard/components.py` — **new** `render_goalkeeper_depth_chart(conn)` function.
- `dashboard/pages/1_Portieri.py` — modify to call the new renderer instead of the generic `render_role_page`.
- Tests: `tests/test_goalkeepers.py` (new), `tests/test_components.py`.

---

### Task 1: `ranking/goalkeepers.py` — group ranked portieri into a per-team depth chart

**Files:**
- Create: `ranking/goalkeepers.py`
- Test: `tests/test_goalkeepers.py`

**Interfaces:**
- Consumes: `get_ranked_role(conn, "P")`'s output — each row already has `player_id`, `team`, `score`, `is_promoted` (set by `dashboard.data_access.get_ranked_role`).
- Produces: `build_goalkeeper_depth_chart(rows: list) -> dict` with keys:
  - `"teams"`: list of `{"team": str, "is_promoted": bool, "starter": dict | None, "backup": dict | None}`, ordered non-promoted teams first (alphabetical), promoted teams last (alphabetical) — same ordering convention as `dashboard.data_access.search_and_sort`.
  - `"warnings"`: list of team names with fewer than 2 identifiable portieri.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_goalkeepers.py`:

```python
from ranking.goalkeepers import build_goalkeeper_depth_chart


def _row(player_id, team, score, is_promoted=False):
    return {
        "player_id": player_id, "canonical_name": f"Player{player_id}",
        "team": team, "score": score, "is_promoted": is_promoted,
    }


def test_groups_by_team_starter_and_backup():
    rows = [
        _row(1, "Napoli", 70.0),
        _row(2, "Napoli", 50.0),
        _row(3, "Inter", 65.0),
        _row(4, "Inter", 60.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    assert napoli["starter"]["player_id"] == 1
    assert napoli["backup"]["player_id"] == 2
    assert chart["warnings"] == []


def test_third_choice_keeper_excluded_from_depth_chart():
    rows = [
        _row(1, "Napoli", 70.0),
        _row(2, "Napoli", 50.0),
        _row(3, "Napoli", 30.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    napoli = next(t for t in chart["teams"] if t["team"] == "Napoli")
    ids = {napoli["starter"]["player_id"], napoli["backup"]["player_id"]}
    assert ids == {1, 2}


def test_warns_when_team_has_only_one_identifiable_keeper():
    rows = [_row(1, "Como", 55.0)]

    chart = build_goalkeeper_depth_chart(rows)

    como = next(t for t in chart["teams"] if t["team"] == "Como")
    assert como["starter"]["player_id"] == 1
    assert como["backup"] is None
    assert chart["warnings"] == ["Como"]


def test_promoted_teams_sorted_last():
    rows = [
        _row(1, "Venezia", 60.0, is_promoted=True),
        _row(2, "Venezia", 50.0, is_promoted=True),
        _row(3, "Atalanta", 60.0),
        _row(4, "Atalanta", 50.0),
    ]

    chart = build_goalkeeper_depth_chart(rows)

    team_order = [t["team"] for t in chart["teams"]]
    assert team_order == ["Atalanta", "Venezia"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_goalkeepers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ranking.goalkeepers'`

- [ ] **Step 3: Implement**

Create `ranking/goalkeepers.py`:

```python
"""Groups get_ranked_role(conn, "P")'s already-filtered, already-ranked
portieri into a per-team titolare/riserva depth chart (giocatori/
portieri.md): exactly 1st + 2nd choice per team, teams ordered with
neopromosse last.

Note on gerarchia (portieri.md sez. 7): "Priorità 1 — gerarchia esplicita
della fonte" would mean an explicitly scraped 1./2./3. ordering per team;
nothing in this codebase scrapes that today, so this ranks by `score`
(itself driven by fantamedia/avg_rating/appearances/status) within team as
the best available proxy — a genuinely-explicit-hierarchy source would be a
separate scraper addition, not something this module can source on its own.
"""

import bisect


def build_goalkeeper_depth_chart(rows: list) -> dict:
    """rows: get_ranked_role(conn, "P") output (already filtered to current
    Serie A teams and reliable appearances — see dashboard.data_access.
    _compute_ranked_role)."""
    by_team: dict = {}
    for row in rows:
        by_team.setdefault(row["team"], []).append(row)

    teams = []
    warnings = []
    for team, keepers in by_team.items():
        ranked = sorted(keepers, key=lambda r: r["score"], reverse=True)
        starter = ranked[0] if len(ranked) >= 1 else None
        backup = ranked[1] if len(ranked) >= 2 else None
        if backup is None:
            warnings.append(team)
        teams.append({
            "team": team,
            "is_promoted": bool(keepers[0].get("is_promoted")),
            "starter": starter,
            "backup": backup,
        })

    non_promoted = sorted(
        (t for t in teams if not t["is_promoted"]), key=lambda t: t["team"],
    )
    promoted = sorted(
        (t for t in teams if t["is_promoted"]), key=lambda t: t["team"],
    )
    warnings.sort()

    return {"teams": non_promoted + promoted, "warnings": warnings}
```

(The `bisect` import is unused — remove it; it was a leftover from mirroring `ranking/tiers.py`'s header. Final file should not import `bisect`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_goalkeepers.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add ranking/goalkeepers.py tests/test_goalkeepers.py
git commit -m "feat: per-team titolare/riserva depth chart for portieri"
```

---

### Task 2: Render the depth chart on the Portieri page

**Files:**
- Modify: `dashboard/components.py`
- Modify: `dashboard/pages/1_Portieri.py`
- Test: `tests/test_components.py`

**Interfaces:**
- Consumes: `ranking.goalkeepers.build_goalkeeper_depth_chart` (Task 1), `dashboard.data_access.get_ranked_role`, the existing `render_player_card(row, rank)`.
- Produces: `render_goalkeeper_depth_chart(conn) -> None`.

**Note on testing Streamlit UI functions:** check how the existing `tests/test_components.py` tests functions that call `st.*` (likely via `streamlit.testing.v1.AppTest` or by monkeypatching `st` — read a couple of its existing tests before writing this one and match its exact approach; do not introduce a second testing style for the same file).

- [ ] **Step 1: Write the failing test**

First read `tests/test_components.py` to copy its existing Streamlit-testing setup exactly, then add a test asserting: given a conn seeded with 2 teams' worth of goalkeeper quotations (one team with 2 keepers, one with only 1), `render_goalkeeper_depth_chart(conn)` runs without raising, and a warning is shown for the single-keeper team. Match the file's existing assertion style (e.g. if it uses `AppTest.from_function(...).run()` and inspects `.markdown`/`.warning` elements, do the same here) rather than inventing a new pattern — write the concrete test only after reading that file, since guessing the harness here risks testing the wrong thing.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_components.py -k goalkeeper_depth_chart -v`
Expected: FAIL — `AttributeError: module 'dashboard.components' has no attribute 'render_goalkeeper_depth_chart'`

- [ ] **Step 3: Implement**

In `dashboard/components.py`, add (near `render_role_page`, using the same `_inject_card_css`/pagination-free simpler layout since a depth chart of 40 players grouped in 20 small sections doesn't need the generic role page's search/sort/pagination controls):

```python
def render_goalkeeper_depth_chart(conn) -> None:
    """Vista dedicata Portieri (giocatori/portieri.md): titolare + riserva
    per ciascuna delle 20 squadre di Serie A, neopromosse per ultime,
    invece della lista piatta generica di render_role_page."""
    _inject_card_css()
    st.markdown('<div class="fc-page-title">Portieri</div>', unsafe_allow_html=True)

    all_rows = get_ranked_role(conn, "P")
    chart = build_goalkeeper_depth_chart(all_rows)

    if chart["warnings"]:
        st.warning(
            "Solo un portiere identificabile (dati insufficienti per la riserva) "
            "per: " + ", ".join(chart["warnings"])
        )

    for team_entry in chart["teams"]:
        st.markdown(f"### {team_entry['team']}" + (" *" if team_entry["is_promoted"] else ""))
        cols = st.columns(2)
        with cols[0]:
            if team_entry["starter"]:
                render_player_card(team_entry["starter"], rank=1)
        with cols[1]:
            if team_entry["backup"]:
                render_player_card(team_entry["backup"], rank=2)

    if any(t["is_promoted"] for t in chart["teams"]):
        st.caption("* Squadra neopromossa")
```

Add the import at the top of `dashboard/components.py`:

```python
from ranking.goalkeepers import build_goalkeeper_depth_chart
```

(Check `render_player_card`'s `rank` parameter usage first — confirm passing a fixed `1`/`2` per card, rather than a running page-wide counter, renders sensibly; e.g. if `rank` drives a "#N" badge on the card, `1`/`2` reading as "titolare"/"riserva" position within the team is exactly the intended meaning here, not a global leaderboard position — adjust the card's rank label copy if it currently assumes global ranking.)

Update `dashboard/pages/1_Portieri.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.common import get_db_connection
from dashboard.components import render_goalkeeper_depth_chart

render_goalkeeper_depth_chart(get_db_connection())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_components.py tests/test_goalkeepers.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification**

Run: `streamlit run dashboard/app.py`, open Portieri page, confirm:
- Teams render grouped, each with up to 2 cards.
- Promoted teams (Venezia, Frosinone, Monza) appear last.
- If any team in the current dataset has fewer than 2 reliable portieri, the warning banner lists it.

- [ ] **Step 6: Commit**

```bash
git add dashboard/components.py dashboard/pages/1_Portieri.py tests/test_components.py
git commit -m "feat: grouped titolare/riserva view for Portieri page"
```

---

## Explicitly out of scope for this plan

- ADDED/REMOVED/TRANSFERRED change tracking across the 1 September market-close re-scrape (`portieri.md` sez. 14). This needs a "previous roster snapshot" comparison with no existing precedent anywhere in this codebase (every current view is computed fresh from the latest quotations, nothing diffs against a prior snapshot) — a real, separate feature, not a small addition. Revisit as its own plan if wanted; for now the depth chart in this plan will always show the correct up-to-date hierarchy on 1 September, it just won't narrate what changed to get there.
- Explicit source-hierarchy scraping (portieri.md sez. 7 "Priorità 1") — see the module docstring note in Task 1; would need a new scraper for a source that publishes an explicit 1./2./3. goalkeeper depth chart (fantacalcio.it's probabile formazione pages might have this, but that's a new scraper, out of scope here).
