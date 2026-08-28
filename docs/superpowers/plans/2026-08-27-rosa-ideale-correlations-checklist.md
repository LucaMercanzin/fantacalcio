# Rosa Ideale — Correlations and Auction Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface two `giocatori/rosa-ideale.md` requirements that nothing in the codebase currently implements: player-correlation flagging for the owned roster (sez. 14-15 — positive combos like "assistman + goleador", negative ones like two players competing for the same bonus pool) and a guided auction checklist/phase tracker (sez. 26, 28).

**Architecture:** Both features are read-only views over data that already exists on `get_ranked_role`'s rows (`team`, `role_classic`, `role_mantra`, `season_goals_scored`, `season_assists`, `appearances`) plus `price_paid`/`date_added` from `repository.get_roster`. A single new `dashboard.data_access.get_roster_with_profile(conn)` helper joins those two (Task 1), then two small pure `ranking/` modules consume it: `ranking/correlation.py::find_correlations` (Task 1) and `ranking/auction_checklist.py::build_checklist`/`current_phase` (Task 3), each mirroring the existing `ranking/tiers.py`/`ranking/scarcity.py` shape (a pure function over already-computed rows, no new scraping, no new schema). Two new `render_*(conn)` functions in `dashboard/components.py` (Tasks 2, 4) display them on `dashboard/pages/5_La_Mia_Rosa.py`, matching the existing `render_decision_center(conn)`/`render_goalkeeper_depth_chart(conn)` pattern.

**Tech Stack:** Python 3.11, Streamlit, sqlite3, pytest.

## Global Constraints

- No new scraper and no new schema: every field these modules read already exists on `get_ranked_role`'s output or `repository.get_roster`'s output — verified against the current code in `dashboard/data_access.py` and `db/repository.py` before writing this plan.
- Portieri are excluded from negative-correlation flagging: rosa-ideale.md sez. 14 explicitly wants titolare+secondo of the same team as a goalkeeper pair (protection against a blank slot), which is the opposite of a negative correlation — and `ranking.goalkeepers.build_goalkeeper_depth_chart` already exists specifically to surface that pairing. Flagging it again here as "negative" would contradict that feature.
- Where the spec's checklist (sez. 28) asks something no data in the schema can answer (a pre-auction "planned max price" per player is never recorded anywhere), the checklist item must show up with an explicit "verifica manuale" status, never a guessed True/False — matches this project's `AGENTS.md` rule against inventing signals that don't exist.
- Reuse existing constants instead of redefining them: `ranking.tiers.UNPROVEN_MAX_APPEARANCES` for "scommessa", the existing `ranking.budget.compute_budget_summary`/`ROLE_SLOTS` shape for the phase tracker, `db.repository.get_roster` for `price_paid`.
- Match existing repo conventions: one test file per module (`tests/test_<module>.py`), constants as named module-level values with a comment explaining the choice (see `ranking/tactical_profile.py`, `ranking/scarcity.py` for house style).

---

## File Structure

- `dashboard/data_access.py` — **new** `get_roster_with_profile(conn) -> list`: every owned player enriched with role_mantra/score/season stats (from `get_ranked_role`) plus `price_paid` (from `repository.get_roster`).
- `ranking/correlation.py` — **new**: `find_correlations(roster_rows) -> dict`.
- `ranking/auction_checklist.py` — **new**: `build_checklist(roster_rows) -> list`, `current_phase(budget_summary) -> dict`.
- `dashboard/components.py` — **new** `render_correlation_section(conn)` and `render_auction_checklist_section(conn)`.
- `dashboard/pages/5_La_Mia_Rosa.py` — modify to call both new render functions.
- Tests: `tests/test_data_access.py`, `tests/test_correlation.py` (new), `tests/test_auction_checklist.py` (new), `tests/test_components.py`.

---

### Task 1: `get_roster_with_profile` + `ranking/correlation.py`

**Files:**
- Modify: `dashboard/data_access.py`
- Create: `ranking/correlation.py`
- Test: `tests/test_data_access.py`, `tests/test_correlation.py`

**Interfaces:**
- Consumes: `get_ranked_role(conn, role)` (existing — rows carry `player_id`, `team`, `role_classic`, `role_mantra`, `season_goals_scored`, `season_assists`, `is_in_roster`), `repository.get_roster(conn)` (existing — rows carry `player_id`, `price_paid`).
- Produces: `get_roster_with_profile(conn) -> list[dict]` — one dict per owned player, superset of `get_ranked_role`'s row keys plus `price_paid`. `find_correlations(roster_rows: list) -> dict` with keys `"positive"`/`"negative"`, each a list of `{"player_a": dict, "player_b": dict, "reason": str}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_data_access.py`:

```python
def test_get_roster_with_profile_merges_price_paid_and_role_mantra(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Owned Player", "Inter", "D", "E", None)
    repository.insert_quotation(conn, p1, "fantacalcio_it", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)
    repository.insert_quotation(conn, p1, "fantapazz", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)
    repository.add_roster_entry(conn, p1, 12.0, "2026-08-22")

    owned = get_roster_with_profile(conn)

    assert len(owned) == 1
    assert owned[0]["player_id"] == p1
    assert owned[0]["role_mantra"] == "E"
    assert owned[0]["price_paid"] == 12.0
    conn.close()


def test_get_roster_with_profile_excludes_players_not_owned(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    not_owned = repository.upsert_player(conn, "Free Player", "Milan", "A", "PC", None)
    repository.insert_quotation(conn, not_owned, "fantacalcio_it", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)
    repository.insert_quotation(conn, not_owned, "fantapazz", "2026-08-22", 10, 8, "ok", 6.0, 6.0, 30)

    owned = get_roster_with_profile(conn)

    assert owned == []
    conn.close()
```

Add the import to `tests/test_data_access.py`'s existing `from dashboard.data_access import (...)` block: `get_roster_with_profile`.

Create `tests/test_correlation.py`:

```python
from ranking.correlation import find_correlations


def _row(player_id, name, team, role_classic, role_mantra=None, goals=0, assists=0):
    return {
        "player_id": player_id, "canonical_name": name, "team": team,
        "role_classic": role_classic, "role_mantra": role_mantra,
        "season_goals_scored": goals, "season_assists": assists,
    }


def test_flags_positive_correlation_assistman_and_goleador_same_team():
    rows = [
        _row(1, "Assistman", "Inter", "C", "E", goals=1, assists=6),
        _row(2, "Goleador", "Inter", "A", "PC", goals=10, assists=0),
    ]

    result = find_correlations(rows)

    assert len(result["positive"]) == 1
    pair = result["positive"][0]
    assert pair["player_a"]["player_id"] == 1
    assert pair["player_b"]["player_id"] == 2


def test_no_positive_correlation_across_different_teams():
    rows = [
        _row(1, "Assistman", "Inter", "C", "E", goals=1, assists=6),
        _row(2, "Goleador", "Milan", "A", "PC", goals=10, assists=0),
    ]

    result = find_correlations(rows)

    assert result["positive"] == []


def test_flags_negative_correlation_same_contested_role_same_team():
    rows = [
        _row(1, "Punta A", "Napoli", "A", "PC", goals=8, assists=1),
        _row(2, "Punta B", "Napoli", "A", "PC", goals=5, assists=0),
    ]

    result = find_correlations(rows)

    assert len(result["negative"]) == 1
    ids = {result["negative"][0]["player_a"]["player_id"],
           result["negative"][0]["player_b"]["player_id"]}
    assert ids == {1, 2}


def test_no_negative_correlation_for_non_contested_role_mantra():
    rows = [
        _row(1, "Centrale A", "Napoli", "D", "DC"),
        _row(2, "Centrale B", "Napoli", "D", "DC"),
    ]

    result = find_correlations(rows)

    assert result["negative"] == []


def test_ignores_portieri():
    rows = [
        _row(1, "Titolare", "Roma", "P", "POR"),
        _row(2, "Riserva", "Roma", "P", "POR"),
    ]

    result = find_correlations(rows)

    assert result["positive"] == []
    assert result["negative"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_access.py -k get_roster_with_profile -v tests/test_correlation.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_roster_with_profile'` and `ModuleNotFoundError: No module named 'ranking.correlation'`

- [ ] **Step 3: Implement**

In `dashboard/data_access.py`, add near `get_ranked_role`:

```python
def get_roster_with_profile(conn) -> list:
    """Every owned player (repository.get_roster), enriched with the same
    profile fields get_ranked_role computes per role (team, role_mantra,
    score, tactical_profile_score, season_goals_scored, season_assists,
    appearances) plus price_paid from my_roster — the row shape
    ranking.correlation.find_correlations and ranking.auction_checklist.
    build_checklist both need. get_ranked_role's own is_in_roster flag is
    what identifies these rows; this just reuses it instead of a second
    query path against the players/quotations tables."""
    price_paid_by_player = {
        r["player_id"]: r["price_paid"] for r in repository.get_roster(conn)
    }
    owned = []
    for role in ("P", "D", "C", "A"):
        for row in get_ranked_role(conn, role):
            if row["is_in_roster"]:
                row = dict(row)
                row["price_paid"] = price_paid_by_player.get(row["player_id"])
                owned.append(row)
    return owned
```

Create `ranking/correlation.py`:

```python
"""Flags positive and negative player correlations within the owned roster
(giocatori/rosa-ideale.md sez. 14-15): pairs on the same team that either
combine to produce bonuses together (assistman + goleador) or compete for
the same bonus pool (two players in the same tactical slot).

Deliberately scoped to D/C/A only — portieri titolare+secondo of the same
team is the DESIRED pairing (rosa-ideale.md sez. 14 "Portieri"), already the
explicit goal of ranking.goalkeepers.build_goalkeeper_depth_chart; flagging
it again here as a negative correlation would contradict that feature.
"""

# A player counts as a real goal/assist threat for correlation purposes
# above this many season goals/assists — low enough to catch a genuine
# secondary scorer, high enough that a single set piece won't trigger it.
GOAL_THREAT_MIN = 3
ASSIST_THREAT_MIN = 3

# role_mantra codes that are "the same tactical slot" for negative-
# correlation purposes — two players sharing one of these on the same team
# are competing for the same minutes/bonus pool. Deliberately a subset of
# ranking.tactical_profile.ROLE_MANTRA_BASE's keys: only the attacking-
# facing ones, since two "DC" centrali on the same team aren't competing
# for the same fantacalcio bonus the way two "PC" attaccanti are.
CONTESTED_ROLE_MANTRA = {"T", "W", "A", "PC", "E"}


def find_correlations(roster_rows: list) -> dict:
    """roster_rows: dashboard.data_access.get_roster_with_profile(conn)
    output, or any list of rows with player_id/canonical_name/team/
    role_classic/role_mantra/season_goals_scored/season_assists.

    Returns {"positive": [...], "negative": [...]}, each entry:
    {"player_a": row, "player_b": row, "reason": str}."""
    dc_a_rows = [r for r in roster_rows if r.get("role_classic") != "P"]

    positive = []
    negative = []
    for i, a in enumerate(dc_a_rows):
        for b in dc_a_rows[i + 1:]:
            if a["team"] != b["team"]:
                continue

            a_assists = a.get("season_assists") or 0
            b_assists = b.get("season_assists") or 0
            a_goals = a.get("season_goals_scored") or 0
            b_goals = b.get("season_goals_scored") or 0

            # elif, not two independent ifs: a pair that qualifies both ways
            # (both good scorers and assisters) would otherwise show up as
            # two near-identical cards for the same two players.
            if a_assists >= ASSIST_THREAT_MIN and b_goals >= GOAL_THREAT_MIN:
                positive.append({
                    "player_a": a, "player_b": b,
                    "reason": (
                        f"{a['canonical_name']} assist ({a_assists}) + "
                        f"{b['canonical_name']} gol ({b_goals}), stessa squadra"
                    ),
                })
            elif b_assists >= ASSIST_THREAT_MIN and a_goals >= GOAL_THREAT_MIN:
                positive.append({
                    "player_a": b, "player_b": a,
                    "reason": (
                        f"{b['canonical_name']} assist ({b_assists}) + "
                        f"{a['canonical_name']} gol ({a_goals}), stessa squadra"
                    ),
                })

            same_role_classic = a["role_classic"] == b["role_classic"]
            same_contested_mantra = (
                a.get("role_mantra") in CONTESTED_ROLE_MANTRA
                and a.get("role_mantra") == b.get("role_mantra")
            )
            if same_role_classic and same_contested_mantra:
                negative.append({
                    "player_a": a, "player_b": b,
                    "reason": (
                        f"{a['canonical_name']} e {b['canonical_name']}: stesso "
                        f"ruolo tattico ({a['role_mantra']}) nella stessa squadra, "
                        "competono per gli stessi bonus"
                    ),
                })

    return {"positive": positive, "negative": negative}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_access.py tests/test_correlation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/data_access.py ranking/correlation.py tests/test_data_access.py tests/test_correlation.py
git commit -m "feat: get_roster_with_profile helper and player correlation flagging"
```

---

### Task 2: Render correlations on the La Mia Rosa page

**Files:**
- Modify: `dashboard/components.py`
- Modify: `dashboard/pages/5_La_Mia_Rosa.py`
- Test: `tests/test_components.py`

**Interfaces:**
- Consumes: `dashboard.data_access.get_roster_with_profile` (Task 1), `ranking.correlation.find_correlations` (Task 1).
- Produces: `render_correlation_section(conn) -> None`.

- [ ] **Step 1: Write the failing test**

First read the existing `_seed_goalkeeper`/`_run_goalkeeper_depth_chart_app` helpers in `tests/test_components.py` (added for the Portieri depth chart) to match their exact `AppTest.from_function` pattern. Add to `tests/test_components.py`:

```python
def _seed_owned_pair(conn, team, assistman_goals_assists, goleador_goals_assists):
    a_id = repository.upsert_player(conn, "Assistman", team, "C", "E", None)
    b_id = repository.upsert_player(conn, "Goleador", team, "A", "PC", None)
    for pid in (a_id, b_id):
        repository.insert_quotation(conn, pid, "fantacalcio_it", "2026-08-22", 20, 15, "ok", 6.5, 6.5, 30)
        repository.insert_quotation(conn, pid, "fantapazz", "2026-08-22", 20, 15, "ok", 6.5, 6.5, 30)
        repository.add_roster_entry(conn, pid, 15.0, "2026-08-22")
    repository.upsert_player_season_stats(conn, a_id, "fantacalciopedia", [{
        "season": "2025-26", "appearances": 30, "goals_scored": assistman_goals_assists[0],
        "assists": assistman_goals_assists[1], "yellow_cards": 0, "red_cards": 0,
    }], "2026-08-22")
    repository.upsert_player_season_stats(conn, b_id, "fantacalciopedia", [{
        "season": "2025-26", "appearances": 30, "goals_scored": goleador_goals_assists[0],
        "assists": goleador_goals_assists[1], "yellow_cards": 0, "red_cards": 0,
    }], "2026-08-22")


def test_render_correlation_section_shows_positive_pair(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    _seed_owned_pair(conn, "Inter", assistman_goals_assists=(1, 6), goleador_goals_assists=(10, 0))

    def script(conn):
        from dashboard.components import render_correlation_section
        render_correlation_section(conn)

    at = AppTest.from_function(script, kwargs={"conn": conn})
    at.run()

    assert not at.exception
    assert any("Assistman" in w.value and "Goleador" in w.value for w in at.markdown)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_components.py -k render_correlation_section -v`
Expected: FAIL — `AttributeError: module 'dashboard.components' has no attribute 'render_correlation_section'`

- [ ] **Step 3: Implement**

In `dashboard/components.py`, add the two new names to the existing `from dashboard.data_access import (...)` block: `get_roster_with_profile`. Add near `render_decision_center`:

```python
from ranking.correlation import find_correlations
```

```python
def render_correlation_section(conn) -> None:
    """Rosa-ideale.md sez. 14-15: coppie di giocatori in rosa che si
    completano (correlazione positiva) o competono per lo stesso bonus
    (correlazione negativa)."""
    st.subheader("Correlazioni tra i tuoi giocatori")
    st.caption(
        "Coppie nella stessa squadra che si completano (assist + gol) o "
        "competono per lo stesso ruolo/bonus — rosa-ideale.md sez. 14-15."
    )
    roster_rows = get_roster_with_profile(conn)
    correlations = find_correlations(roster_rows)

    if correlations["positive"]:
        st.markdown("**Positive** — puntano a generare bonus insieme")
        for pair in correlations["positive"]:
            st.write(f"✅ {pair['reason']}")
    if correlations["negative"]:
        st.markdown("**Negative** — competono per gli stessi bonus")
        for pair in correlations["negative"]:
            st.write(f"⚠️ {pair['reason']}")
    if not correlations["positive"] and not correlations["negative"]:
        st.caption("Nessuna correlazione rilevante trovata nella rosa attuale.")
```

In `dashboard/pages/5_La_Mia_Rosa.py`, add `render_correlation_section` to the `from dashboard.components import (...)` line, and call it right after the "Giocatori acquistati" table section (after the `st.write("Nessun giocatore ancora aggiunto.")` else-branch, before `st.subheader("Presi dagli avversari")`):

```python
st.divider()
render_correlation_section(conn)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_components.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification**

Run: `streamlit run dashboard/app.py`, open "La Mia Rosa", confirm the new "Correlazioni tra i tuoi giocatori" section renders without error for both an empty roster and a populated one.

- [ ] **Step 6: Commit**

```bash
git add dashboard/components.py dashboard/pages/5_La_Mia_Rosa.py tests/test_components.py
git commit -m "feat: surface player correlations on La Mia Rosa"
```

---

### Task 3: `ranking/auction_checklist.py`

**Files:**
- Create: `ranking/auction_checklist.py`
- Test: `tests/test_auction_checklist.py`

**Interfaces:**
- Consumes: `dashboard.data_access.get_roster_with_profile`'s row shape (Task 1), `ranking.budget.compute_budget_summary`'s output (existing — `{"slots": {role: {"filled", "total", "remaining", "spent"}}}`), `ranking.tiers.UNPROVEN_MAX_APPEARANCES` (existing, value `12`).
- Produces: `build_checklist(roster_rows: list) -> list[dict]`, each `{"text": str, "status": bool | None}` (`None` = not computable from the schema, "verifica manuale"), in the same order as `giocatori/rosa-ideale.md` sez. 28. `current_phase(budget_summary: dict) -> dict` with keys `"role"` (`"P"`/`"D"`/`"C"`/`"A"`/`None`), `"label"`, `"focus"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auction_checklist.py`:

```python
from ranking.auction_checklist import build_checklist, current_phase
from ranking.budget import compute_budget_summary


def _row(player_id, role_classic, role_mantra=None, appearances=None,
         goals=0, assists=0, price_paid=None, price_current=None):
    return {
        "player_id": player_id, "canonical_name": f"Player{player_id}",
        "role_classic": role_classic, "role_mantra": role_mantra,
        "appearances": appearances, "season_goals_scored": goals,
        "season_assists": assists, "price_paid": price_paid,
        "price_current": price_current,
    }


def test_checklist_all_false_or_manual_on_empty_roster():
    checklist = build_checklist([])

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho un portiere titolare affidabile?"] is False
    assert statuses["Ho stabilito un prezzo massimo per i giocatori?"] is None


def test_checklist_flags_reliable_starting_goalkeeper():
    rows = [_row(1, "P", "POR", appearances=30)]

    checklist = build_checklist(rows)

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho un portiere titolare affidabile?"] is True


def test_checklist_flags_overpay():
    rows = [_row(1, "D", "DC", appearances=20, price_paid=50, price_current=20)]

    checklist = build_checklist(rows)

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho evitato di pagare il nome?"] is False


def test_checklist_no_overpay_flag_when_within_ratio():
    rows = [_row(1, "D", "DC", appearances=20, price_paid=20, price_current=18)]

    checklist = build_checklist(rows)

    statuses = {item["text"]: item["status"] for item in checklist}
    assert statuses["Ho evitato di pagare il nome?"] is True


def test_current_phase_portieri_when_no_goalkeepers_owned():
    summary = compute_budget_summary([])

    phase = current_phase(summary)

    assert phase["role"] == "P"
    assert phase["label"] == "Fase 1 — Portieri"


def test_current_phase_completamento_when_all_slots_full():
    roster = (
        [{"role_classic": "P", "price_paid": 1}] * 3
        + [{"role_classic": "D", "price_paid": 1}] * 8
        + [{"role_classic": "C", "price_paid": 1}] * 8
        + [{"role_classic": "A", "price_paid": 1}] * 6
    )
    summary = compute_budget_summary(roster)

    phase = current_phase(summary)

    assert phase["role"] is None
    assert phase["label"] == "Fase 5 — Completamento"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auction_checklist.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ranking.auction_checklist'`

- [ ] **Step 3: Implement**

Create `ranking/auction_checklist.py`:

```python
"""Auction-progress checklist and phase tracker (giocatori/rosa-ideale.md
sez. 26 "Strategia durante l'asta", sez. 28 "Checklist finale"): turns
signals already computed elsewhere (ranking.budget's slot-fill counts,
season goals/assists already on get_ranked_role's rows) into the spec's own
18-item checklist and 5-phase auction guide, instead of leaving the user to
cross-reference budget/roster against the spec by hand."""

from ranking.tiers import UNPROVEN_MAX_APPEARANCES

# Thresholds below are deliberately modest season totals (giocatori/
# rosa-ideale.md gives no exact numbers for sez. 28's checklist items) —
# enough to distinguish "this role is contributing" from "this role is
# empty", not a claim about what counts as "good" for a specific player.
OFFENSIVE_DEFENDER_MANTRA = {"E", "DD", "DS", "B"}
MIDFIELD_OFFENSIVE_MANTRA = {"T", "W", "A"}
MIN_OFFENSIVE_DEFENDERS = 2
MIN_OFFENSIVE_MIDFIELDERS = 3
MIN_MIDFIELD_GOALS = 3
MIN_MIDFIELD_ASSISTS = 3
MIN_STRIKER_GOALS = 8
MIN_STRIKER_ASSISTS_FOR_CREATOR = 3
MIN_VOTE_TAKERS = 15
MIN_DEPTH_TOTAL = 20
RELIABLE_APPEARANCES = 15

# 3-4-3 starting shape (matches dashboard.pages.5_La_Mia_Rosa's PITCH_ROWS)
# — sez. 28's last item ("posso schierare un 3-4-3 competitivo anche con
# 2-3 assenze?") needs each outfield role to have this many starters plus a
# depth buffer.
FORMATION_STARTERS = {"P": 1, "D": 3, "C": 4, "A": 3}
DEPTH_BUFFER = 2

# A player paid more than this multiple of today's quotation is a candidate
# for sez. 28's "ho evitato di pagare il nome?" — a real overpay signal
# using only price_paid (my_roster) vs price_current (today's consensus
# quotation), not a claim about what was reasonable at auction time.
OVERPAY_RATIO = 1.3


def _owned(rows, role):
    return [r for r in rows if r["role_classic"] == role]


def _appearances_ok(row):
    return (row.get("appearances") or 0) >= RELIABLE_APPEARANCES


def build_checklist(roster_rows: list) -> list:
    """roster_rows: dashboard.data_access.get_roster_with_profile(conn)
    output. Returns a list of {"text": str, "status": bool | None} in the
    same order as rosa-ideale.md sez. 28 — status is None when nothing in
    the schema can answer the item (shown as "verifica manuale" in the UI),
    never a guessed True/False."""
    p_rows = _owned(roster_rows, "P")
    d_rows = _owned(roster_rows, "D")
    c_rows = _owned(roster_rows, "C")
    a_rows = _owned(roster_rows, "A")

    offensive_defenders = [r for r in d_rows if r.get("role_mantra") in OFFENSIVE_DEFENDER_MANTRA]
    quinto_or_terzino = [r for r in d_rows if r.get("role_mantra") in {"E", "DD", "DS"}]
    reliable_centrali = [
        r for r in d_rows if r.get("role_mantra") == "DC" and _appearances_ok(r)
    ]
    offensive_midfielders = [r for r in c_rows if r.get("role_mantra") in MIDFIELD_OFFENSIVE_MANTRA]
    midfield_goals = sum(r.get("season_goals_scored") or 0 for r in c_rows)
    midfield_assists = sum(r.get("season_assists") or 0 for r in c_rows)
    striker_scorers = [r for r in a_rows if (r.get("season_goals_scored") or 0) >= MIN_STRIKER_GOALS]
    striker_creators = [r for r in a_rows if (r.get("season_assists") or 0) >= MIN_STRIKER_ASSISTS_FOR_CREATOR]
    vote_takers = [r for r in roster_rows if _appearances_ok(r)]
    scommesse = [
        r for r in roster_rows
        if r.get("appearances") is None or r["appearances"] < UNPROVEN_MAX_APPEARANCES
    ]
    overpaid = [
        r for r in roster_rows
        if r.get("price_paid") is not None and r.get("price_current")
        and r["price_paid"] > r["price_current"] * OVERPAY_RATIO
    ]
    bonus_role_count = sum(
        1 for group in (d_rows, c_rows, a_rows)
        if sum((r.get("season_goals_scored") or 0) + (r.get("season_assists") or 0) for r in group) > 0
    )
    formation_ready = all(
        len(_owned(roster_rows, role)) >= need + (DEPTH_BUFFER if role != "P" else 0)
        for role, need in FORMATION_STARTERS.items()
    )

    return [
        {"text": "Ho un portiere titolare affidabile?",
         "status": any(_appearances_ok(r) for r in p_rows)},
        {"text": "Ho una copertura adeguata in porta?",
         "status": len(p_rows) >= 2},
        {"text": "Ho almeno 2-3 difensori offensivi?",
         "status": len(offensive_defenders) >= MIN_OFFENSIVE_DEFENDERS},
        {"text": "Ho almeno un quinto/terzino listato difensore?",
         "status": len(quinto_or_terzino) >= 1},
        {"text": "Ho centrali affidabili per la copertura?",
         "status": len(reliable_centrali) >= 1},
        {"text": "Ho almeno 3-4 centrocampisti con produzione offensiva?",
         "status": len(offensive_midfielders) >= MIN_OFFENSIVE_MIDFIELDERS},
        {"text": "Ho almeno un centrocampista che gioca quasi da attaccante?",
         "status": len(offensive_midfielders) >= 1},
        {"text": "Ho abbastanza gol a centrocampo?",
         "status": midfield_goals >= MIN_MIDFIELD_GOALS},
        {"text": "Ho abbastanza assist a centrocampo?",
         "status": midfield_assists >= MIN_MIDFIELD_ASSISTS},
        {"text": "Ho una punta realmente da gol?",
         "status": len(striker_scorers) >= 1},
        {"text": "Ho almeno un attaccante capace di creare assist?",
         "status": len(striker_creators) >= 1},
        {"text": "Ho abbastanza titolari per affrontare le assenze?",
         "status": len(roster_rows) >= MIN_DEPTH_TOTAL},
        {"text": "Ho stabilito un prezzo massimo per i giocatori?",
         "status": None},
        {"text": "Ho evitato di pagare il nome?",
         "status": len(overpaid) == 0},
        {"text": "Ho distribuito i bonus tra più reparti?",
         "status": bonus_role_count >= 2},
        {"text": "Ho abbastanza giocatori che prendono voto?",
         "status": len(vote_takers) >= MIN_VOTE_TAKERS},
        {"text": "Ho alcune scommesse con alto potenziale?",
         "status": len(scommesse) >= 1},
        {"text": "Posso schierare un 3-4-3 competitivo anche con 2-3 assenze?",
         "status": formation_ready},
    ]


PHASE_LABELS = {
    "P": "Fase 1 — Portieri",
    "D": "Fase 2 — Difensori",
    "C": "Fase 3 — Centrocampisti",
    "A": "Fase 4 — Attaccanti",
}
PHASE_FOCUS = {
    "P": "Stabilisci coppia preferita e budget massimo (sez. 26).",
    "D": "Concentrati su quinti, terzini e difensori da bonus; evita di "
         "spendere troppo sui centrali puri.",
    "C": "Cerca gol + assist + posizione offensiva: la fase più importante "
         "per un 3-4-3.",
    "A": "Compra almeno una punta da gol, un secondo giocatore da bonus e "
         "un esterno/seconda punta.",
}


def current_phase(budget_summary: dict) -> dict:
    """budget_summary: ranking.budget.compute_budget_summary(roster) output.
    The first role (in P/D/C/A order, matching sez. 26's own phase order)
    with unfilled slots is the current phase; once all four are full it's
    sez. 26's Fase 5 — completamento with the leftover budget."""
    for role in ("P", "D", "C", "A"):
        if budget_summary["slots"][role]["remaining"] > 0:
            return {"role": role, "label": PHASE_LABELS[role], "focus": PHASE_FOCUS[role]}
    return {
        "role": None, "label": "Fase 5 — Completamento",
        "focus": "Usa i crediti rimanenti per titolari, coperture e scommesse.",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auction_checklist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ranking/auction_checklist.py tests/test_auction_checklist.py
git commit -m "feat: auction phase tracker and rosa-ideale checklist"
```

---

### Task 4: Render the checklist and phase tracker on the La Mia Rosa page

**Files:**
- Modify: `dashboard/components.py`
- Modify: `dashboard/pages/5_La_Mia_Rosa.py`
- Test: `tests/test_components.py`

**Interfaces:**
- Consumes: `ranking.auction_checklist.build_checklist`/`current_phase` (Task 3), `dashboard.data_access.get_roster_with_profile` (Task 1), `ranking.budget.compute_budget_summary` (existing, already imported in `dashboard/components.py`), `repository.get_roster` (existing, `db.repository` already imported in `dashboard/components.py`).
- Produces: `render_auction_checklist_section(conn) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_components.py`:

```python
def test_render_auction_checklist_section_runs_without_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    def script(conn):
        from dashboard.components import render_auction_checklist_section
        render_auction_checklist_section(conn)

    at = AppTest.from_function(script, kwargs={"conn": conn})
    at.run()

    assert not at.exception
    assert any("Fase 1" in i.value for i in at.info)
    assert any("verifica manuale" in m.value for m in at.markdown)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_components.py -k render_auction_checklist_section -v`
Expected: FAIL — `AttributeError: module 'dashboard.components' has no attribute 'render_auction_checklist_section'`

- [ ] **Step 3: Implement**

In `dashboard/components.py`, add the import near the other `ranking.*` imports:

```python
from ranking.auction_checklist import build_checklist, current_phase
```

Add the render function near `render_correlation_section`:

```python
def render_auction_checklist_section(conn) -> None:
    """Rosa-ideale.md sez. 26 (fasi asta) e sez. 28 (checklist finale)."""
    st.subheader("Checklist asta")
    roster_rows = get_roster_with_profile(conn)
    budget_summary = compute_budget_summary(repository.get_roster(conn))

    phase = current_phase(budget_summary)
    st.info(f"**{phase['label']}** — {phase['focus']}")

    for item in build_checklist(roster_rows):
        if item["status"] is None:
            st.write(f"◻️ {item['text']} *(verifica manuale)*")
        elif item["status"]:
            st.write(f"✅ {item['text']}")
        else:
            st.write(f"❌ {item['text']}")
```

In `dashboard/pages/5_La_Mia_Rosa.py`, add `render_auction_checklist_section` to the `from dashboard.components import (...)` line, and call it after `render_correlation_section(conn)`:

```python
st.divider()
render_auction_checklist_section(conn)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_components.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification**

Run: `streamlit run dashboard/app.py`, open "La Mia Rosa", confirm the "Checklist asta" section shows a phase banner and 18 checklist rows, with "Ho stabilito un prezzo massimo per i giocatori?" marked "verifica manuale" rather than a checkmark/cross.

- [ ] **Step 6: Commit**

```bash
git add dashboard/components.py dashboard/pages/5_La_Mia_Rosa.py tests/test_components.py
git commit -m "feat: auction checklist and phase tracker on La Mia Rosa"
```

---

## Explicitly out of scope for this plan

- Bench "function" labeling (rosa-ideale.md sez. 20: copertura / bonus / scommessa / copertura-di-titolare) — the existing `ranking/tiers.py` tier system already serves most of the same purpose for available players, and mapping it 1:1 onto owned bench players would need tier classification to work over owned rows too (`classify_role` currently filters those out by design). A real but small, separate follow-up, not folded into this plan.
- A literal "planned max price per player" tracker for sez. 28's "ho stabilito un prezzo massimo?" item — would need a new table/UI to record a pre-auction plan and compare it against what was actually paid; `ranking/price_engine.py::compute_max_price` already computes a live recommendation for *candidates*, but nothing records what the user's own plan was before bidding. Out of scope here; the checklist item is left as an explicit manual check instead of inventing a shaky proxy.
