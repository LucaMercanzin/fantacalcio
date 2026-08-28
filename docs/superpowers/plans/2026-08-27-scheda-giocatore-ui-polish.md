# Scheda Giocatore UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the UI-only gaps between `statistiche giocatore` (the player-detail-page spec) and the current `render_player_detail` — an explicit tier badge, a value-for-money 🟢/🟡/🔴 semaforo, a role-percentile comparison section, and a rules-generated "verdetto" summary — using only data the scoring pipeline already computes.

**Architecture:** `render_player_detail` (`dashboard/components.py:941`) and `get_player_detail` (`dashboard/data_access.py:421`) already carry almost every number these features need (`score`, `risk`, `value_for_money_percentile`, `tactical_profile_score`, and — via `get_ranked_role` — the whole role's ranked rows). `get_player_detail` already computes `role_rows` (the player's whole role, ranked) purely to derive `rank_in_role`; this plan reuses that same `role_rows` list — no second query — to also derive a tier (`ranking/tiers.classify_role`) and a per-metric role comparison (a new pure module, `ranking/role_comparison.py`, mirroring `ranking/tiers.py`'s and `ranking/goalkeepers.py`'s existing shape: a plain function over already-fetched rows, no Streamlit/DB coupling). The verdetto (`ranking/verdict.py`) is the same pattern one layer up: a pure rules table over already-computed scores, not a new score.

**Tech Stack:** Python 3.11, Streamlit, sqlite3, pytest.

## Global Constraints

- No new scraper, no new schema, no new computed score — every feature in this plan reads fields `get_ranked_role`/`enrich_scores` already produce (`score`, `risk`, `value_for_money_percentile`, `tactical_profile_score`, `appearances`, `status`, `fantamedia`, `season_goals_scored`, `season_assists`) or a value already merged onto the ranked row.
- `statistiche giocatore` sez. 23/26/27: verdetto, semaforo and price ranges "must be calculated by the engine, not hardcoded per player" — every output here is a pure function of a row dict, never a per-player special case.
- `grafica/grafica.md` sez. 29 (proprietary UI, no copying Fantanalisi's layout/CSS/naming) applies to every new UI element added here too — use `st.markdown`/`st.progress`/`st.caption`, the existing card/section conventions, and Italian section labels already used elsewhere in `render_player_detail` (`"Storico stagioni"`, `"Squadra"`, ...), not a Fantanalisi-styled widget.
- Minimum necessary change: do not touch `1_Portieri.py`/`2_Difensori.py`/`3_Centrocampisti.py`/`4_Attaccanti.py`, `render_role_page`, or any scraper — every change in this plan is scoped to `get_player_detail`, `render_player_detail`, and the new `ranking/` modules.
- Task 1 must land before Task 5: `ranking/verdict.compute_verdict` reads `row["tier"]`, which only exists on the merged row after Task 1 wires `classify_role` into `get_player_detail`.

## File Structure

- `ranking/role_comparison.py` — new. Pure function: given a role's ranked rows and a `player_id`, returns per-metric player-value/role-average/percentile.
- `ranking/verdict.py` — new. Pure function: given a merged player row (with `tier` already set) and that player's set-piece summary, returns a stars/headline/strengths/risks dict.
- `dashboard/data_access.py` — modify `get_player_detail` (currently `dashboard/data_access.py:421-461`) to also set `merged["tier"]` and `merged["role_comparison"]`, reusing the `role_rows` it already computes.
- `dashboard/components.py` — modify `render_player_detail` (currently `dashboard/components.py:941-1223`) to render the tier badge, the value-for-money semaforo, a new "Confronto con il ruolo" section, and a new "Verdetto" section.
- `tests/test_data_access.py`, `tests/test_components.py` — extend with the new assertions.
- `tests/test_role_comparison.py`, `tests/test_verdict.py` — new, pure-function tests for the two new `ranking/` modules.

---

### Task 1: Tier badge on the player detail page

**Files:**
- Modify: `dashboard/data_access.py:421-461` (`get_player_detail`)
- Modify: `dashboard/components.py:941-975` (`render_player_detail` header)
- Test: `tests/test_data_access.py`

**Interfaces:**
- Consumes: `ranking.tiers.classify_role(rows: list) -> dict` (`{tier_key: [rows]}`, already imported into `dashboard/components.py` — not yet into `dashboard/data_access.py`), `ranking.tiers.TIER_LABELS`/`TIER_DESCRIPTIONS` (already imported into `dashboard/components.py:34`).
- Produces: `get_player_detail(conn, player_id)`'s returned dict gains a `"tier"` key — one of `ranking.tiers.TOP/SEMI_TOP/TITOLARE_FISSO/BASSO_PREZZO/SCOMMESSA/DA_EVITARE`, or `None` when the player isn't classified into any tier (this includes every player already in the roster or already taken by an opponent — `classify_role` only classifies "available" players, by design, since a tier exists to guide the *next* pick).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_data_access.py`:

```python
def test_get_player_detail_includes_tier(tmp_path):
    from ranking.tiers import TOP

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    star = repository.upsert_player(conn, "Star Player", "Inter", "A", None, None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, star, source, "2026-08-22", 30, 30, "ok", 8.0, 8.0, 35)
    for i in range(15):
        filler = repository.upsert_player(conn, f"Filler{i}", "Inter", "A", None, None)
        for source in ("fantacalcio_it", "fantapazz"):
            repository.insert_quotation(conn, filler, source, "2026-08-22", 10, 10, "ok", 5.5, 5.5, 25)

    detail = get_player_detail(conn, star)

    assert detail["tier"] == TOP
    conn.close()


def test_get_player_detail_tier_is_none_for_player_already_in_roster(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Owned Player", "Inter", "A", None, None)
    for source in ("fantacalcio_it", "fantapazz"):
        repository.insert_quotation(conn, p1, source, "2026-08-22", 30, 30, "ok", 8.0, 8.0, 35)
    repository.add_roster_entry(conn, p1, 30, "2026-08-22")

    detail = get_player_detail(conn, p1)

    assert detail["tier"] is None
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_access.py -k test_get_player_detail_includes_tier -v`
Expected: FAIL with `KeyError: 'tier'`

- [ ] **Step 3: Implement**

In `dashboard/data_access.py`, add the import near the top (with the other `ranking.*` imports):

```python
from ranking.tiers import classify_role
```

In `get_player_detail`, right after the existing block that copies `decision_score`/`value_for_money_percentile` from `role_match` (currently ending at `dashboard/data_access.py:459`), add:

```python
    tiers = classify_role(role_rows)
    merged["tier"] = next(
        (tier for tier, players in tiers.items()
         if any(p["player_id"] == player_id for p in players)),
        None,
    )
```

In `dashboard/components.py`, inside `render_player_detail`, right after the existing:

```python
        if row.get("is_in_roster"):
            st.success("In rosa")
        elif row.get("taken_by"):
            st.warning(f"🔒 Preso da {row['taken_by']}")
```

add:

```python
        tier = row.get("tier")
        if tier:
            st.caption(f"{TIER_LABELS[tier]} — {TIER_DESCRIPTIONS[tier]}")
```

(`TIER_LABELS`/`TIER_DESCRIPTIONS` are already imported at the top of `dashboard/components.py` — no new import needed there.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_access.py -k test_get_player_detail -v`
Expected: PASS (both new tests)

- [ ] **Step 5: Commit**

```bash
git add dashboard/data_access.py dashboard/components.py tests/test_data_access.py
git commit -m "feat: show tier badge on player detail page"
```

---

### Task 2: Value-for-money 🟢/🟡/🔴 semaforo

**Files:**
- Modify: `dashboard/components.py` (`render_player_detail`, the `score_cols` block currently at `dashboard/components.py:1024-1041`)
- Test: `tests/test_components.py`

**Interfaces:**
- Consumes: `row["value_for_money_percentile"]` (already set by `get_player_detail`, see Task 1's `Interfaces`/existing `dashboard/data_access.py:459` — population-relative 0-100, `None` when there's no role population to compare against yet).
- Produces: a private `_value_for_money_semaforo(vfm_percentile) -> str` helper in `dashboard/components.py`, and a caption rendered next to the existing "Value for Money" metric.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_components.py`:

```python
def test_render_player_detail_shows_green_semaforo_for_high_vfm_percentile(tmp_path):
    conn, row = _base_player_row(tmp_path, value_for_money_percentile=80.0)

    at = _run_player_detail(conn, row)

    assert any("🟢" in c.value for c in at.caption)
    conn.close()


def test_render_player_detail_shows_red_semaforo_for_low_vfm_percentile(tmp_path):
    conn, row = _base_player_row(tmp_path, value_for_money_percentile=10.0)

    at = _run_player_detail(conn, row)

    assert any("🔴" in c.value for c in at.caption)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_components.py -k semaforo -v`
Expected: FAIL — no caption contains "🟢"/"🔴"

- [ ] **Step 3: Implement**

In `dashboard/components.py`, add near `_rank_badge_class` (same private-helper style):

```python
def _value_for_money_semaforo(vfm_percentile) -> str:
    """🟢/🟡/🔴 read on value_for_money_percentile (statistiche giocatore
    sez. 26) — the same population-relative percentile ranking.tiers already
    uses to gate BASSO_PREZZO, not the raw value_for_money ratio (unbounded,
    not comparable across players — see compute_decision_score's docstring
    in ranking/scorer.py)."""
    if vfm_percentile is None:
        return ""
    if vfm_percentile >= 66.0:
        return "🟢 Sottovalutato"
    if vfm_percentile >= 33.0:
        return "🟡 Prezzo corretto"
    return "🔴 Sopravvalutato"
```

In `render_player_detail`, right after the existing:

```python
    vfm = row.get("value_for_money")
    score_cols[2].metric(
        "Value for Money", f"{vfm:.1f}" if vfm is not None else "-",
        help=METRIC_HELP["value_for_money"],
    )
```

add:

```python
    semaforo = _value_for_money_semaforo(row.get("value_for_money_percentile"))
    if semaforo:
        st.caption(semaforo)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_components.py -k semaforo -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/components.py tests/test_components.py
git commit -m "feat: value-for-money semaforo on player detail page"
```

---

### Task 3: `ranking/role_comparison.py` — role-percentile comparison engine

**Files:**
- Create: `ranking/role_comparison.py`
- Test: `tests/test_role_comparison.py`

**Interfaces:**
- Produces: `compute_role_comparison(role_rows: list, player_id) -> dict`. `role_rows`: `get_ranked_role`'s output for the player's own role (same shape Task 1 already has as `role_rows` inside `get_player_detail`). Returns `{}` when `player_id` isn't found in `role_rows`. Otherwise `{metric_key: {"label": str, "player": value, "role_avg": float, "percentile": float}}` for each of `fantamedia`, `score`, `season_goals_scored`, `season_assists`, `appearances` — skipping a metric entirely when the player's own value for it is `None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_role_comparison.py`:

```python
from ranking.role_comparison import compute_role_comparison


def _row(player_id, fantamedia, score, goals, assists, appearances):
    return {
        "player_id": player_id, "fantamedia": fantamedia, "score": score,
        "season_goals_scored": goals, "season_assists": assists,
        "appearances": appearances,
    }


def test_computes_percentile_and_role_average_for_each_metric():
    rows = [
        _row(1, 8.0, 90.0, 20, 5, 35),
        _row(2, 6.0, 50.0, 5, 2, 25),
        _row(3, 6.5, 55.0, 8, 3, 30),
    ]

    comparison = compute_role_comparison(rows, player_id=1)

    assert comparison["fantamedia"]["player"] == 8.0
    assert comparison["fantamedia"]["role_avg"] == round((8.0 + 6.0 + 6.5) / 3, 1)
    assert comparison["fantamedia"]["percentile"] == 100.0
    assert comparison["fantamedia"]["label"] == "Fantamedia"


def test_returns_empty_dict_when_player_not_in_role_rows():
    rows = [_row(2, 6.0, 50.0, 5, 2, 25)]

    assert compute_role_comparison(rows, player_id=999) == {}


def test_skips_metric_when_players_own_value_is_none():
    rows = [
        {"player_id": 1, "fantamedia": None, "score": 90.0, "appearances": 35,
         "season_goals_scored": None, "season_assists": None},
        {"player_id": 2, "fantamedia": 6.0, "score": 50.0, "appearances": 25,
         "season_goals_scored": 5, "season_assists": 2},
    ]

    comparison = compute_role_comparison(rows, player_id=1)

    assert "fantamedia" not in comparison
    assert "score" in comparison
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_comparison.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ranking.role_comparison'`

- [ ] **Step 3: Implement**

Create `ranking/role_comparison.py`:

```python
"""Compares one player's core Fantacalcio metrics against the rest of his
role (statistiche giocatore sez. 24: "Confronto con il ruolo"). Pure
function over get_ranked_role's already-scored output — same bisect-based
percentile approach as ranking.tiers._percentile_rank, so a player is
always compared against role-mates only (a difensore never against
attaccanti)."""

import bisect

METRICS = {
    "fantamedia": "Fantamedia",
    "score": "Fantasy Value",
    "season_goals_scored": "Gol",
    "season_assists": "Assist",
    "appearances": "Presenze",
}


def _percentile_rank(value, sorted_values: list) -> float:
    if not sorted_values:
        return 50.0
    idx = bisect.bisect_left(sorted_values, value)
    return round(idx / len(sorted_values) * 100, 1)


def compute_role_comparison(role_rows: list, player_id) -> dict:
    player_row = next((r for r in role_rows if r["player_id"] == player_id), None)
    if player_row is None:
        return {}

    comparison = {}
    for key, label in METRICS.items():
        player_value = player_row.get(key)
        if player_value is None:
            continue
        values = [r[key] for r in role_rows if r.get(key) is not None]
        role_avg = round(sum(values) / len(values), 1) if values else None
        comparison[key] = {
            "label": label,
            "player": player_value,
            "role_avg": role_avg,
            "percentile": _percentile_rank(player_value, sorted(values)),
        }
    return comparison
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_comparison.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ranking/role_comparison.py tests/test_role_comparison.py
git commit -m "feat: role_comparison engine for player-vs-role percentiles"
```

---

### Task 4: Render "Confronto con il ruolo" on the player detail page

**Files:**
- Modify: `dashboard/data_access.py:421-461` (`get_player_detail`)
- Modify: `dashboard/components.py` (`render_player_detail`, right before the existing `set_pieces = get_set_piece_summary(...)` call currently at `dashboard/components.py:1066`)
- Test: `tests/test_data_access.py`, `tests/test_components.py`

**Interfaces:**
- Consumes: `ranking.role_comparison.compute_role_comparison` (Task 3).
- Produces: `get_player_detail(conn, player_id)`'s returned dict gains a `"role_comparison"` key (Task 3's return shape, possibly `{}`). A new private `_render_role_comparison(row: dict) -> None` in `dashboard/components.py`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_data_access.py`:

```python
def test_get_player_detail_includes_role_comparison(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    p1 = repository.upsert_player(conn, "Player One", "Inter", "A", None, None)
    p2 = repository.upsert_player(conn, "Player Two", "Inter", "A", None, None)
    for pid, fm in ((p1, 8.0), (p2, 6.0)):
        for source in ("fantacalcio_it", "fantapazz"):
            repository.insert_quotation(conn, pid, source, "2026-08-22", 20, 20, "ok", fm, fm, 30)

    detail = get_player_detail(conn, p1)

    assert detail["role_comparison"]["fantamedia"]["player"] == 8.0
    conn.close()
```

Add to `tests/test_components.py`:

```python
def test_render_player_detail_shows_role_comparison_section(tmp_path):
    conn, row = _base_player_row(tmp_path, role_comparison={
        "fantamedia": {"label": "Fantamedia", "player": 8.0, "role_avg": 6.5, "percentile": 92.0},
    })

    at = _run_player_detail(conn, row)

    assert any("Confronto con il ruolo" in m.value for m in at.markdown)
    conn.close()


def test_render_player_detail_omits_role_comparison_section_when_empty(tmp_path):
    conn, row = _base_player_row(tmp_path, role_comparison={})

    at = _run_player_detail(conn, row)

    assert not any("Confronto con il ruolo" in m.value for m in at.markdown)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_access.py -k role_comparison -v tests/test_components.py -k role_comparison -v`
Expected: FAIL — `KeyError: 'role_comparison'` / section not found

- [ ] **Step 3: Implement**

In `dashboard/data_access.py`, add the import near the other `ranking.*` imports:

```python
from ranking.role_comparison import compute_role_comparison
```

In `get_player_detail`, right after the `merged["tier"] = ...` block added in Task 1, add:

```python
    merged["role_comparison"] = compute_role_comparison(role_rows, player_id)
```

In `dashboard/components.py`, add a new function near `_render_profile_radar`:

```python
def _render_role_comparison(row: dict) -> None:
    comparison = row.get("role_comparison")
    if not comparison:
        return
    st.markdown("**Confronto con il ruolo**")
    for metric in comparison.values():
        st.caption(f"{metric['label']}: {metric['player']} (media ruolo {metric['role_avg']})")
        st.progress(
            min(max(int(metric["percentile"]), 0), 100),
            text=f"{metric['percentile']:.0f}° percentile",
        )
```

In `render_player_detail`, right before the existing:

```python
    set_pieces = get_set_piece_summary(conn, row["player_id"])
```

add:

```python
    _render_role_comparison(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_access.py -k role_comparison -v && pytest tests/test_components.py -k role_comparison -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/data_access.py dashboard/components.py tests/test_data_access.py tests/test_components.py
git commit -m "feat: render role-percentile comparison on player detail page"
```

---

### Task 5: `ranking/verdict.py` — rules-based verdetto, rendered as the page's closing section

**Files:**
- Create: `ranking/verdict.py`
- Modify: `dashboard/components.py` (`render_player_detail`, right before the final `render_purchase_evaluator(conn, row)` call currently at `dashboard/components.py:1223`)
- Test: `tests/test_verdict.py`, `tests/test_components.py`

**Interfaces:**
- Consumes: `row["tier"]` (Task 1 — must be present; this task depends on Task 1), `row["risk"]`, `row["appearances"]`, `row["status"]`, `row["value_for_money_percentile"]`, `row["tactical_profile_score"]`, `ranking.tiers.{TOP, SEMI_TOP, TITOLARE_FISSO, BASSO_PREZZO, SCOMMESSA, DA_EVITARE, PROVEN_MIN_APPEARANCES, NAILED_ON_MIN_APPEARANCES, UNPROVEN_MAX_APPEARANCES}` (all already defined in `ranking/tiers.py`). The existing `get_set_piece_summary(conn, row["player_id"])` call already in `render_player_detail` (`dashboard/components.py:1066`, result stored in the local `set_pieces` variable) — reused, not re-queried.
- Produces: `compute_verdict(row: dict, set_pieces: list) -> dict` returning `{"stars": int (1-5), "headline": str, "strengths": [str], "risks": [str]}`. A new private `_render_verdict(row: dict, set_pieces: list) -> None` in `dashboard/components.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_verdict.py`:

```python
from ranking.verdict import compute_verdict
from ranking.tiers import TOP, SCOMMESSA


def test_top_tier_gets_five_stars_and_matching_strengths():
    row = {
        "tier": TOP, "appearances": 35, "risk": 20.0,
        "value_for_money_percentile": 70.0, "tactical_profile_score": 50.0,
        "status": "ok",
    }

    verdict = compute_verdict(row, set_pieces=[])

    assert verdict["stars"] == 5
    assert "Titolare quasi certo" in verdict["strengths"]
    assert "Buon rapporto qualità/prezzo" in verdict["strengths"]


def test_injured_player_gets_a_risk_flag():
    row = {
        "tier": SCOMMESSA, "appearances": 5, "risk": 70.0,
        "value_for_money_percentile": None, "tactical_profile_score": None,
        "status": "infortunato",
    }

    verdict = compute_verdict(row, set_pieces=[])

    assert any("infortunato" in r for r in verdict["risks"])
    assert verdict["stars"] == 2


def test_penalty_taker_is_a_strength():
    row = {
        "tier": None, "appearances": 20, "risk": 40.0,
        "value_for_money_percentile": 50.0, "tactical_profile_score": None,
        "status": "ok",
    }
    set_pieces = [{"category": "Rigori", "rank": 1, "label": "Principale", "updated_at": "2026-08-01"}]

    verdict = compute_verdict(row, set_pieces=set_pieces)

    assert any("Rigorista" in s for s in verdict["strengths"])
```

Add to `tests/test_components.py`:

```python
def test_render_player_detail_shows_verdetto_section(tmp_path):
    conn, row = _base_player_row(tmp_path, tier=None, risk=20.0,
                                  value_for_money_percentile=70.0)

    at = _run_player_detail(conn, row)

    assert any("Verdetto" in m.value for m in at.markdown)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_verdict.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ranking.verdict'`

- [ ] **Step 3: Implement**

Create `ranking/verdict.py`:

```python
"""Rules-based verdetto (statistiche giocatore sez. 23): turns the
already-computed separated scores (tier, risk, value_for_money_percentile,
tactical_profile_score) into a short, generated-not-hand-written summary. No
new data, no new score — a fixed decision table over numbers the scoring
pipeline already produces."""

from ranking.tiers import (
    TOP, SEMI_TOP, TITOLARE_FISSO, BASSO_PREZZO, SCOMMESSA, DA_EVITARE,
    PROVEN_MIN_APPEARANCES, NAILED_ON_MIN_APPEARANCES, UNPROVEN_MAX_APPEARANCES,
)

TIER_STARS = {
    TOP: 5, SEMI_TOP: 4, TITOLARE_FISSO: 3, BASSO_PREZZO: 3, SCOMMESSA: 2, DA_EVITARE: 1,
}

TIER_HEADLINES = {
    5: "Top player del ruolo.",
    4: "Semi-top, scelta solida.",
    3: "Titolare affidabile.",
    2: "Scommessa: potenziale incerto.",
    1: "Da evitare o da monitorare con cautela.",
}

RISK_LOW = 35.0
RISK_HIGH = 60.0
VFM_PCT_GOOD = 66.0
VFM_PCT_BAD = 20.0
TACTICAL_PROFILE_GOOD = 60.0
PENALIZED_STATUSES = {"infortunato", "squalificato"}


def compute_verdict(row: dict, set_pieces: list) -> dict:
    tier = row.get("tier")
    stars = TIER_STARS.get(tier, 3)

    strengths = []
    risks = []

    appearances = row.get("appearances")
    if appearances is not None and appearances >= NAILED_ON_MIN_APPEARANCES:
        strengths.append("Titolare quasi certo")
    elif appearances is not None and appearances >= PROVEN_MIN_APPEARANCES:
        strengths.append("Buona continuità di impiego")
    elif appearances is not None and appearances < UNPROVEN_MAX_APPEARANCES:
        risks.append("Poche presenze: rendimento ancora da confermare")

    for sp in set_pieces or []:
        if sp["rank"] == 1:
            strengths.append(f"Rigorista/battitore principale ({sp['category']})")

    risk = row.get("risk")
    if risk is not None and risk < RISK_LOW:
        strengths.append("Alta affidabilità")
    elif risk is not None and risk >= RISK_HIGH:
        risks.append("Rischio elevato (affidabilità bassa)")

    vfm_pct = row.get("value_for_money_percentile")
    if vfm_pct is not None and vfm_pct >= VFM_PCT_GOOD:
        strengths.append("Buon rapporto qualità/prezzo")
    elif vfm_pct is not None and vfm_pct < VFM_PCT_BAD:
        risks.append("Prezzo d'asta elevato rispetto al rendimento atteso")

    tactical = row.get("tactical_profile_score")
    if tactical is not None and tactical >= TACTICAL_PROFILE_GOOD:
        strengths.append("Profilo tattico offensivo favorevole")

    if row.get("status") in PENALIZED_STATUSES:
        risks.append(f"Attualmente {row['status']}")

    if not strengths:
        strengths.append("Nessun punto di forza particolare rilevato dai dati disponibili")
    if not risks:
        risks.append("Nessun rischio particolare rilevato dai dati disponibili")

    return {
        "stars": stars,
        "headline": TIER_HEADLINES[stars],
        "strengths": strengths,
        "risks": risks,
    }
```

In `dashboard/components.py`, add a new function near `render_player_detail`:

```python
def _render_verdict(row: dict, set_pieces: list) -> None:
    verdict = compute_verdict(row, set_pieces)
    stars = "★" * verdict["stars"] + "☆" * (5 - verdict["stars"])
    st.markdown(f"**Verdetto**  \n{stars}  \n{verdict['headline']}")
    st.markdown("**Punti forti**\n" + "\n".join(f"- {s}" for s in verdict["strengths"]))
    st.markdown("**Rischi**\n" + "\n".join(f"- {r}" for r in verdict["risks"]))
```

Add the import at the top of `dashboard/components.py` (with the other `ranking.*` imports):

```python
from ranking.verdict import compute_verdict
```

In `render_player_detail`, right before the existing final line:

```python
    render_purchase_evaluator(conn, row)
```

add:

```python
    _render_verdict(row, set_pieces)

```

(so the file reads `_render_verdict(row, set_pieces)` followed by `render_purchase_evaluator(conn, row)`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_verdict.py -v && pytest tests/test_components.py -k verdetto -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ranking/verdict.py dashboard/components.py tests/test_verdict.py tests/test_components.py
git commit -m "feat: rules-based verdetto section on player detail page"
```
