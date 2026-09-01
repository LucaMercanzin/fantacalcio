import base64
import io
import logging
import os
import re
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st
from PIL import Image, UnidentifiedImageError

from dashboard.styles import _inject_card_css
from dashboard.data_access import (
    DECISION_BUCKET_LABELS,
    DECISION_BUCKETS,
    PROMOTED_TEAM_CODES,
    TEAM_ABBREV_TO_FULL,
    evaluate_player_purchase,
    format_count,
    get_auction_intelligence,
    get_data_freshness_summary,
    get_decision_center,
    get_fixture_difficulty,
    get_goalkeeper_pool,
    get_ideal_formation,
    get_injury_summary,
    get_insufficient_data_players,
    get_player_extra,
    get_player_season_stats,
    get_price_history_by_date,
    get_purchase_history,
    get_ranked_role,
    get_recent_form,
    get_roster_with_profile,
    get_set_piece_summary,
    get_team_strength,
    get_value_index,
    normalize_team_name,
    search_and_sort,
)
from dashboard.team_info import get_role_fit, get_team_info
from db import repository
from matching.player_matcher import normalize_team
from ranking.auction_checklist import build_checklist, current_phase
from ranking.budget import compute_budget_summary, compute_role_budget_plan
from ranking.correlation import find_correlations
from ranking.goalkeepers import build_goalkeeper_depth_chart
from ranking.tiers import TIER_DESCRIPTIONS, TIER_LABELS, TIER_ORDER, classify_role
from ranking.verdict import compute_verdict

logger = logging.getLogger(__name__)

PURCHASE_VERDICT_STYLE = {
    "affare": "success", "prezzo_giusto": "success",
    "caro": "warning", "troppo_caro": "error",
    "ruolo_pieno": "error", "inutile_hai_di_meglio": "error",
    "sconosciuto": "info",
}

PLACEHOLDER_COLORS = {"P": "#f4c542", "D": "#4caf50", "C": "#2196f3", "A": "#e53935"}

CHART_SERIES_COLOR = "#4C78A8"


def _melt_for_chart(df: pd.DataFrame, index_label: str) -> pd.DataFrame:
    long_df = df.reset_index()
    long_df = long_df.rename(columns={long_df.columns[0]: index_label})
    return long_df.melt(index_label, var_name="Serie", value_name="Valore")


def static_line_chart(df: pd.DataFrame, index_label: str = "x") -> None:
    """Come st.line_chart, ma senza lo zoom/pan a rotella del mouse che
    Streamlit accende di default sui grafici nativi (line_chart, bar_chart,
    scatter_chart) e per cui non espone un parametro di disattivazione: lo
    spec Vega-Lite che genera aggiunge da sé una selection interattiva.
    Stesso disegno, costruito a mano con Altair senza `.interactive()` —
    che è il pezzo che inietta quella selection — quindi resta fermo."""
    long_df = _melt_for_chart(df, index_label)
    encode_kwargs = {
        "x": alt.X(f"{index_label}:N", sort=None, title=None),
        "y": alt.Y("Valore:Q"),
    }
    if long_df["Serie"].nunique() > 1:
        encode_kwargs["color"] = alt.Color("Serie:N", title=None)
    else:
        encode_kwargs["color"] = alt.value(CHART_SERIES_COLOR)
    chart = alt.Chart(long_df).mark_line(point=True).encode(**encode_kwargs)
    st.altair_chart(chart, use_container_width=True)


def static_bar_chart(df: pd.DataFrame, index_label: str = "x") -> None:
    """Come static_line_chart ma a barre — vedi lì per il perché."""
    long_df = _melt_for_chart(df, index_label)
    multi_series = long_df["Serie"].nunique() > 1
    encode_kwargs = {
        "x": alt.X(f"{index_label}:N", sort=None, title=None),
        "y": alt.Y("Valore:Q"),
    }
    if multi_series:
        encode_kwargs["color"] = alt.Color("Serie:N", title=None)
        encode_kwargs["xOffset"] = alt.XOffset("Serie:N")
    else:
        encode_kwargs["color"] = alt.value(CHART_SERIES_COLOR)
    chart = alt.Chart(long_df).mark_bar().encode(**encode_kwargs)
    st.altair_chart(chart, use_container_width=True)


def static_scatter_chart(df: pd.DataFrame, x: str, y: str) -> None:
    """Come static_line_chart ma a dispersione — vedi lì per il perché."""
    chart = alt.Chart(df).mark_circle(size=80).encode(
        x=alt.X(f"{x}:Q"), y=alt.Y(f"{y}:Q"),
    )
    st.altair_chart(chart, use_container_width=True)

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "photos")

ROLE_LABELS = {"P": "Portiere", "D": "Difensore", "C": "Centrocampista", "A": "Attaccante"}

# Spiegazioni contestuali per ogni metrica (spec sez. 106-127): l'utente non
# deve dover ricordare cosa significa ogni sigla. Streamlit le mostra al
# passaggio del mouse tramite l'argomento `help` di st.metric.
METRIC_HELP = {
    "rating": "Alias di Fantasy Value: quanto rende questo giocatore al fantacalcio, "
              "tenendo conto di bonus attesi e affidabilità.",
    "quotazione": "Prezzo consensus: media pesata delle quotazioni delle fonti configurate "
                  "in Monitoraggio, corretta per outlier e recenza.",
    "quotazione_stimata": "Prezzo consensus stimato dal listino (~40) e convertito in crediti "
                           "d'asta: nessuna fonte con crediti reali per questo giocatore, non "
                           "il prezzo di un'asta vera (DA6/TASK-029).",
    "quot_iniziale": "Prezzo di partenza a inizio stagione, prima delle variazioni di mercato.",
    "fantamedia": "Media dei voti fantacalcio (voto + bonus - malus) sulle partite giocate. "
                  "Nessun valore stimato: se manca, non è mostrato un numero fittizio (P0-002).",
    "media_voto": "Media dei voti puri in pagella, senza bonus/malus fantacalcio.",
    "presenze": "Numero di partite giocate nella stagione.",
    "presenze_discordi": "Le fonti riportano un numero di presenze diverso di più di 3 partite: "
                          "mostrata la media pesata, non il valore di una singola fonte "
                          "(DA6/TASK-029).",
    "stato": "Disponibilità attuale del giocatore (infortunato, squalificato, regolare).",
    "fonti_dati": "Fonti che hanno contribuito alla quotazione consensus di questo giocatore.",
    "player_quality": "Forza calcistica pura (basata sulla media voto), indipendente da "
                       "prezzo e convenienza fantasy. Un difensore forte ma che non fa bonus "
                       "può avere Player Quality alta.",
    "fantasy_value": "Quanto rende questo giocatore al fantacalcio: bonus attesi più "
                      "affidabilità, penalizzato se attualmente indisponibile.",
    "fantasy_value_stimato": "Nessuna fantamedia da nessuna fonte per questo giocatore "
                              "(tipico per un nuovo arrivo/giovane senza storico Serie A): "
                              "Fantasy Value stimato dal prezzo consensus, non da rendimento "
                              "reale (movimento.md §22/TASK-011b). Value for Money non "
                              "mostrato per questa riga per evitare circolarità.",
    "value_for_money": "Fantasy Value diviso per il prezzo attuale: quanto rendimento ottieni "
                        "per ogni credito speso. Più alto = affare migliore.",
    "risk": "0-100, più alto è più rischioso: dipende da quante partite ha giocato "
            "(affidabilità) e se è attualmente indisponibile.",
    "price_agreement": "Quanto le fonti sono d'accordo sulla quotazione di questo giocatore. "
                        "Basso = poche fonti o fonti molto discordanti.",
}


# Transfermarkt's og:image (our only photo source, scrapers/transfermarkt.py
# fetch_photo_url) falls back to the club crest for players with no profile
# photo on file, and the pipeline saves that indistinguishably from a real
# headshot — no separate "is this a crest" field exists anywhere upstream.
# Crests are flat vector graphics (a handful of solid colors); real photos
# are photographic (tens of thousands of distinct colors from skin tones,
# lighting, JPEG noise). Measured on this repo's actual crest vs. photo
# files: crests sit at 0.3-0.6% unique colors per pixel, real photos at
# 29-53% — a ~50x gap, so a generous 5% cutoff has wide margin either way.
CREST_COLOR_RATIO_THRESHOLD = 0.05


def _looks_like_crest(raw_bytes: bytes) -> bool | None:
    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            im = im.convert("RGB")
            width, height = im.size
            colors = im.getcolors(maxcolors=width * height)
    except (OSError, UnidentifiedImageError) as exc:
        logger.warning("Immagine giocatore illeggibile: %s", exc)
        return None
    if not colors:
        return True
    return (len(colors) / (width * height)) < CREST_COLOR_RATIO_THRESHOLD


@st.cache_data(ttl=3600, show_spinner=False)
def _photo_data_uri(photo_path: str) -> str | None:
    """Resolve a photo by filename against the repo's data/photos dir.

    Old rows may have an absolute path from whatever machine scraped them
    (e.g. a local Windows path); only the filename is portable across
    machines/deployments, so we always re-resolve against PHOTOS_DIR.

    Every role page renders one of these per player (100+ per role, no
    pagination) with zero caching previously: a full disk read + base64
    re-encode of every photo, on every single script rerun (i.e. every click
    anywhere on the page, since Streamlit reruns top-to-bottom). Cached here
    since photo files essentially never change in place once downloaded.
    """
    if not photo_path:
        return None
    # Old rows can hold a Windows path (backslash-separated). os.path.basename
    # only splits on the host OS's separator, so on Linux (Streamlit Cloud)
    # a Windows path comes back unsplit and the file is never found — split
    # on both separators explicitly instead of relying on the OS default.
    filename = re.split(r"[\\/]", photo_path)[-1]
    resolved = os.path.join(PHOTOS_DIR, filename)
    if not os.path.exists(resolved):
        return None
    with open(resolved, "rb") as f:
        raw = f.read()
    crest_result = _looks_like_crest(raw)
    if crest_result is not False:
        return None
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _value_for_money_semaforo(vfm_percentile) -> str:
    """🟢/🟡/🔴 read on value_for_money_percentile (docs/scheda-giocatore.md
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


def _rank_badge_class(rank: int) -> str:
    """Top-3 get a very tenuous gold tint (grafica.md sez. 7); everyone else
    stays neutral. Kept as a single hook so the CSS only needs one modifier
    class, not per-rank inline colors."""
    return "fc-card-rank fc-card-rank-gold" if rank <= 3 else "fc-card-rank"


def render_player_card(row: dict, rank: int, badge_text: str | None = None) -> None:
    """One player card: a native st.container(border=True) restyled into an
    Apple-like surface, a photo that opens the player detail page on click,
    name/team, a Rating stack, a structured Quot./FM/Iniz. stat grid, a
    "Vedi scheda →" text link, and a unified +/- pill control.

    The photo click target is a real st.button, but with an empty label and
    overlaid on the photo via CSS — the one place in this file that still
    depends on Streamlit's internal data-testid structure (:has() + negative
    margin, same technique the old whole-card overlay used), because
    Streamlit has no native "clickable image" widget. Scoped to just the
    photo now (not the whole card) to keep that dependency's blast radius
    small: if a future Streamlit version changes this internal structure,
    only the photo stops being clickable — name, stats and the +/- buttons
    (plain st.button, no overlay trick) keep working regardless.
    """
    color = PLACEHOLDER_COLORS.get(row["role_classic"], "#999999")
    photo_uri = _photo_data_uri(row.get("photo_path"))

    if photo_uri:
        photo_html = f"<img src='{photo_uri}' class='fc-card-photo' />"
    else:
        photo_html = (
            f"<div class='fc-card-photo fc-card-placeholder' style='background:{color};'>"
            f"{row['canonical_name'][0]}</div>"
        )

    # NOT st.container(height=N): that makes the box internally scrollable,
    # and a mouse wheel over a card scrolls *inside* it instead of scrolling
    # the page — worse than the original misalignment complaint. Uniform
    # height instead comes from every piece of variable-length content being
    # capped to a fixed number of lines below (name, and the two optional
    # info lines render an empty-but-same-height div when there's nothing to
    # show), so every card's natural height is already identical — nothing
    # needs to be force-clipped or made scrollable.
    # badge_text overrides both the label and the gold-top-3 styling: it's
    # used by the Portieri depth chart, where rank is always 1 or 2 (titolare/
    # riserva) and would otherwise gold-tint every single card, destroying
    # the "top 3 of the role" signal the badge carries everywhere else.
    badge_class = "fc-card-rank" if badge_text else _rank_badge_class(rank)
    badge_label = badge_text or f"#{rank}"
    with st.container(border=True):
        st.markdown(
            f"<div class='fc-photo-wrap'>{photo_html}"
            f"<span class='{badge_class}'>{badge_label}</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("", key=f"open-{row['player_id']}", use_container_width=True):
            _open_player_detail(row["player_id"])

        roster_tag = " ⭐" if row["is_in_roster"] else ""
        promoted_tag = " *" if row.get("is_promoted") else ""
        st.markdown(
            f"<div class='fc-card-name'>{row['canonical_name']}{promoted_tag}{roster_tag}</div>"
            f"<div class='fc-card-team'>{row['team']}</div>",
            unsafe_allow_html=True,
        )

        alert_line = ""
        if row.get("taken_by"):
            alert_line = f"🔒 Preso da {row['taken_by']}"
        elif row.get("status") and row["status"] not in ("ok", None):
            alert_line = f"⚠️ Stato: {row['status']}"
        notes_line = f"📝 {row['notes']}" if row["notes"] else ""
        if alert_line or notes_line:
            st.markdown(
                f"<div class='fc-card-extra'>{alert_line}</div>"
                f"<div class='fc-card-extra'>{notes_line}</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            "<div class='fc-rating'>"
            "<div class='fc-rating-label'>Rating</div>"
            f"<div class='fc-rating-value'>{row['score']:.1f}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        # DA6/TASK-029: "~" marks a price converted from the listino (no
        # real-auction source for this player) instead of read from actual
        # auction credits — the two used to render identically.
        quot_label = "Quot. ~" if row.get("price_basis") == "listino_converted" else "Quot."
        st.markdown(
            "<div class='fc-stat-grid'>"
            f"<div class='fc-stat-cell'><div class='fc-stat-label'>{quot_label}</div>"
            f"<div class='fc-stat-value'>{format_count(row.get('price_current'))}</div></div>"
            f"<div class='fc-stat-cell'><div class='fc-stat-label'>FM</div>"
            f"<div class='fc-stat-value'>{row.get('fantamedia', '-') or '-'}</div></div>"
            f"<div class='fc-stat-cell'><div class='fc-stat-label'>Iniz.</div>"
            f"<div class='fc-stat-value'>{format_count(row.get('price_initial'))}</div></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown('<span class="fc-link-marker"></span>', unsafe_allow_html=True)
        if st.button("Vedi scheda →", key=f"link-{row['player_id']}", use_container_width=True):
            _open_player_detail(row["player_id"])

        st.markdown('<div class="fc-qty-marker"></div>', unsafe_allow_html=True)
        qty_cols = st.columns(2)
        with qty_cols[0]:
            if st.button(
                "**−**", key=f"minus-{row['player_id']}",
                help="Preso da un avversario", use_container_width=True,
            ):
                st.session_state["quick_action_buyer"] = "avversario"
                if "purchase_buyer_choice" in st.session_state:
                    del st.session_state["purchase_buyer_choice"]
                _open_player_detail(row["player_id"])
        with qty_cols[1]:
            if st.button(
                "**+**", key=f"plus-{row['player_id']}",
                help="Prendo io", use_container_width=True,
            ):
                st.session_state["quick_action_buyer"] = "io"
                if "purchase_buyer_choice" in st.session_state:
                    del st.session_state["purchase_buyer_choice"]
                _open_player_detail(row["player_id"])


def render_data_freshness_banner(conn) -> None:
    """DA5/TASK-028: "dati al 26/08, 6 fonti su 6, 407 giocatori valutati,
    396 esclusi per dati insufficienti" at the top of every page — a user
    mid-auction reads a role page, not the separate Monitoraggio page, and
    has no way to know the data is 3 days old or that 2 of 6 sources
    failed unless it's right there."""
    summary = get_data_freshness_summary(conn)
    if summary["reference_date"] is None:
        return  # no scrape has ever run — nothing to report a freshness on
    sources_ok = summary["sources_fresh"] == summary["sources_total"]
    st.caption(
        f"{'🟢' if sources_ok else '🟡'} Dati al {summary['reference_date']} — "
        f"{summary['sources_fresh']}/{summary['sources_total']} fonti aggiornate — "
        f"{summary['players_valutati']} giocatori valutati, "
        f"{summary['players_esclusi']} esclusi per dati insufficienti"
    )


ROLE_BUDGET_LABELS = {"P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"}


def render_top_budget_bar(conn) -> None:
    """Persistent top-of-page strip: total credits left, plus a per-role
    budget target (ranking.budget.ROLE_BUDGET_PCT — the studied 6/16/32/46
    split) live-adjusted for what's already been spent in each role, so it
    "evolves" with the squad rather than staying a static plan. Shown on
    every page (called from get_db_connection, same as the sidebar Rosa
    Ideale) since budget awareness matters everywhere during an auction, not
    just on La Mia Rosa."""
    roster = repository.get_roster(conn)
    if not roster and not repository.get_opponent_picks(conn):
        return  # nothing bought yet anywhere in the league — the plan is just the static split, not worth a bar yet
    summary = compute_budget_summary(roster)
    plan = compute_role_budget_plan(summary)

    cols = st.columns(5)
    cols[0].metric("Crediti rimasti", format_count(summary["remaining"]))
    for col, role in zip(cols[1:], ("P", "D", "C", "A")):
        role_plan = plan[role]
        remaining_slots = role_plan["remaining_slots"]
        if remaining_slots <= 0:
            col.metric(ROLE_BUDGET_LABELS[role], "completo")
            continue
        # delta = avg budget left per still-empty slot in this role. Its own
        # sign already carries the right meaning: positive (green, "on
        # track") when the role's studied share hasn't been exceeded yet,
        # negative (red, Streamlit's default for a negative delta) once
        # remaining_target has gone below zero — no special-casing needed.
        avg = role_plan["avg_per_remaining_slot"]
        col.metric(
            ROLE_BUDGET_LABELS[role],
            format_count(role_plan["remaining_target"]),
            delta=f"{format_count(avg)}/slot",
        )
    st.caption(
        "Budget per ruolo: quota studiata (6% P / 16% D / 32% C / 46% A) "
        "meno quanto già speso in quel ruolo — non un tetto rigido, un riferimento."
    )
    st.divider()


def render_sidebar_ideal_squad(conn) -> None:
    """Voce 'Rosa Ideale' nel menu laterale: si espande al passaggio del
    mouse (puro CSS, tecnica dropdown a max-height) e mostra scorciatoie
    dirette alla scheda di ciascun titolare, senza passare dalla pagina
    completa 'La Mia Rosa'."""
    formation = get_ideal_formation(conn)  # default formation, config.DEFAULT_FORMATION (TASK-019)
    starters = formation["starters"]
    role_order = [("P", "🥅"), ("D", "🛡️"), ("C", "⚙️"), ("A", "⚔️")]
    all_starters = [
        (icon, player)
        for role, icon in role_order
        for player in starters.get(role, [])
    ]
    if not all_starters:
        return

    with st.sidebar:
        st.markdown('<div class="fc-ideal-menu-marker">⚽ Rosa Ideale ▸</div>', unsafe_allow_html=True)
        with st.container():
            for icon, player in all_starters:
                if st.button(
                    f"{icon} {player['canonical_name']}",
                    key=f"sidebar-ideal-{player['player_id']}",
                    use_container_width=True,
                ):
                    _open_player_detail(player["player_id"])


def _render_role_comparison(row: dict) -> None:
    comparison = row.get("role_comparison")
    if not comparison:
        st.caption("Confronto con il ruolo: dato non ancora raccolto per questo giocatore.")
        return
    st.markdown("**Confronto con il ruolo**")
    for metric in comparison.values():
        st.caption(f"{metric['label']}: {metric['player']} (media ruolo {metric['role_avg']})")
        st.progress(
            min(max(int(metric["percentile"]), 0), 100),
            text=f"{metric['percentile']:.0f}° percentile",
        )


def _render_advanced_stats(row: dict) -> None:
    stats = row.get("advanced_stats")
    if not stats:
        st.caption("Percentili avanzati (xG/xA): dato non ancora raccolto per questo giocatore.")
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


def _render_fantanalisi_valuation(row: dict) -> None:
    valuation = row.get("fantanalisi_valuation")
    if not valuation:
        return
    parts = []
    if valuation.get("fair_price_range"):
        parts.append(f"Fasce affare {valuation['fair_price_range']}")
    if valuation.get("max_bid"):
        parts.append(f"Max {valuation['max_bid']}")
    if valuation.get("tier"):
        parts.append(f"Tier {valuation['tier']}")
    if valuation.get("risk"):
        parts.append(f"Risk {valuation['risk']}")
    if not parts:
        return
    st.caption("Valutazioni Fantanalisi: " + " · ".join(parts))
    st.caption(
        "Valutazioni proprietarie del sito terzo, informative: non incidono "
        "su Fantasy Value/Player Quality/Tier di questo progetto."
    )


def _render_profile_radar(row: dict) -> None:
    """Radar/esagono sintetico del giocatore (Player Quality, Fantasy Value,
    Value for Money, Safety=100-Risk, ALG FCP), normalizzati 0-100 e disegnati
    come SVG inline — nessuna libreria di plotting aggiuntiva necessaria."""
    import math

    def _clip(value, default=0.0):
        if value is None:
            return default
        return max(0.0, min(100.0, float(value)))

    axes = {
        "Player Quality": _clip(row.get("player_quality")),
        "Fantasy Value": _clip(row.get("score")),
        "Value for Money": _clip(row.get("value_for_money")),
        "Safety": _clip(100 - row["risk"] if row.get("risk") is not None else None),
        "ALG FCP": _clip(row.get("alg_fcp")),
    }
    if not any(axes.values()):
        return

    center, max_radius = 110, 85
    n = len(axes)
    angle_step = 2 * math.pi / n
    start_angle = -math.pi / 2

    def _point(i, radius):
        angle = start_angle + i * angle_step
        return center + radius * math.cos(angle), center + radius * math.sin(angle)

    grid_polygons = ""
    for frac in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (_point(i, max_radius * frac) for i in range(n)))
        grid_polygons += f'<polygon points="{pts}" fill="none" stroke="#e5e5ea" stroke-width="1"/>'

    axis_lines = ""
    labels = ""
    for i in range(n):
        x, y = _point(i, max_radius)
        axis_lines += f'<line x1="{center}" y1="{center}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e5e5ea" stroke-width="1"/>'
        lx, ly = _point(i, max_radius + 18)
        anchor = "middle"
        if lx < center - 5:
            anchor = "end"
        elif lx > center + 5:
            anchor = "start"
        labels += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" fill="#1d1d1f" '
            f'text-anchor="{anchor}" dominant-baseline="middle">{list(axes)[i]}</text>'
        )

    values_pts = " ".join(
        f"{x:.1f},{y:.1f}" for x, y in (_point(i, max_radius * v / 100) for i, v in enumerate(axes.values()))
    )

    svg = f"""
    <svg viewBox="0 0 220 220" width="280" height="280" style="overflow: visible;">
        {grid_polygons}
        {axis_lines}
        <polygon points="{values_pts}" fill="rgba(0,113,227,0.25)" stroke="#0071e3" stroke-width="2"/>
        {labels}
    </svg>
    """
    st.markdown("**Profilo sintetico**")
    st.markdown(f'<div style="padding: 0 70px 0 70px;">{svg}</div>', unsafe_allow_html=True)


def _render_verdict(row: dict, set_pieces: list) -> None:
    verdict = compute_verdict(row, set_pieces)
    if verdict["stars"] is None:
        stars = "—"  # not "☆☆☆☆☆": that would read as "0 stars", a verdict, not an absence of one
    else:
        stars = "★" * verdict["stars"] + "☆" * (5 - verdict["stars"])
    st.markdown(f"**Verdetto**  \n{stars}  \n{verdict['headline']}")
    st.markdown("**Punti forti**\n" + "\n".join(f"- {s}" for s in verdict["strengths"]))
    st.markdown("**Rischi**\n" + "\n".join(f"- {r}" for r in verdict["risks"]))


def render_player_detail(conn, row: dict) -> None:
    photo_uri = _photo_data_uri(row.get("photo_path"))
    header_col1, header_col2 = st.columns([1, 3])
    with header_col1:
        if photo_uri:
            st.image(photo_uri, width=180)
        else:
            color = PLACEHOLDER_COLORS.get(row["role_classic"], "#999999")
            st.markdown(
                f"<div style='width:180px;height:180px;border-radius:12px;background:{color};"
                f"display:flex;align-items:center;justify-content:center;color:white;"
                f"font-size:64px;font-weight:bold;'>{row['canonical_name'][0]}</div>",
                unsafe_allow_html=True,
            )
    with header_col2:
        title = row["canonical_name"]
        if row.get("is_promoted"):
            title += " *"
        if row.get("is_in_roster"):
            title += " ⭐"
        st.subheader(title)
        role_label = ROLE_LABELS.get(row.get("role_classic"), row.get("role_classic", "-"))
        mantra = row.get("role_mantra")
        role_caption = f"{role_label}" + (f" ({mantra})" if mantra else "")
        st.caption(f"{role_caption} · {row.get('team', '-')}")
        fixture = get_fixture_difficulty(conn, row.get("team"))
        if fixture and fixture.get("difficulty_attack") is not None:
            st.caption(
                f"Calendario prime 5 giornate: {fixture['difficulty_attack']}/100 "
                "(più alto = più morbido)"
            )
        if row.get("rank_in_role"):
            st.caption(
                f"#{row['rank_in_role']} su {row['role_total']} nel ruolo {role_label}"
            )
        if row.get("is_in_roster"):
            st.success("In rosa")
        elif row.get("taken_by"):
            st.warning(f"🔒 Preso da {row['taken_by']}")

        tier = row.get("tier")
        if tier:
            st.caption(f"{TIER_LABELS[tier]} — {TIER_DESCRIPTIONS[tier]}")

    st.divider()

    info_cols = st.columns(4)
    info_cols[0].metric(
        "Rating", f"{row['score']:.1f}" if row.get("score") is not None else "-",
        help=METRIC_HELP["rating"],
    )
    price_current = row.get("price_current")
    price_initial = row.get("price_initial")
    delta = None
    if price_current is not None and price_initial is not None:
        delta = round(price_current - price_initial, 2)
    # DA6/TASK-029: a price from real auction credits and one converted
    # from the listino (no real-auction source for this player) must not
    # look identical — the difference is real, now that P0-001 separated
    # the two scales, and hiding it invites overpaying on a guess.
    price_is_estimated = row.get("price_basis") == "listino_converted"
    info_cols[1].metric(
        "Quotazione ~" if price_is_estimated else "Quotazione",
        price_current if price_current is not None else "-",
        delta=delta if delta else None,
        help=METRIC_HELP["quotazione_stimata"] if price_is_estimated else METRIC_HELP["quotazione"],
    )
    info_cols[2].metric(
        "Quot. iniziale", price_initial if price_initial is not None else "-",
        help=METRIC_HELP["quot_iniziale"],
    )
    info_cols[3].metric("Fantamedia", row.get("fantamedia", "-"), help=METRIC_HELP["fantamedia"])

    info_cols2 = st.columns(4)
    info_cols2[0].metric("Media voto", row.get("avg_rating", "-"), help=METRIC_HELP["media_voto"])
    appearances_discordi = row.get("appearances_disagreement")
    info_cols2[1].metric(
        "Presenze ⚠️" if appearances_discordi else "Presenze",
        row.get("appearances", "-"),
        help=METRIC_HELP["presenze_discordi"] if appearances_discordi else METRIC_HELP["presenze"],
    )
    status = row.get("status")
    info_cols2[2].metric(
        "Stato", status if status and status != "ok" else "Regolare",
        help=METRIC_HELP["stato"],
    )
    info_cols2[3].metric("Fonti dati", row.get("source", "-"), help=METRIC_HELP["fonti_dati"])

    tactical_score = row.get("tactical_profile_score")
    if tactical_score is not None:
        info_cols3 = st.columns(4)
        info_cols3[0].metric(
            "Profilo tattico", f"{tactical_score:.0f}/100",
            help="Quanto il ruolo REALE del giocatore (giocatori/movimento.md) "
                 "vale al fantacalcio, non solo il ruolo ufficiale — quinti/terzini "
                 "offensivi, trequartisti, seconde punte segnano alto; mediani, "
                 "centrali puri, registi bassi segnano basso.",
        )

    st.caption(
        "Player Quality misura la forza calcistica del giocatore; Fantasy Value quanto "
        "rende al fantacalcio; Value for Money il rendimento per credito speso; Risk "
        "l'affidabilità. Sono quattro cose diverse: un buon giocatore non è per forza "
        "un buon acquisto. Passa il mouse su ciascuna per i dettagli."
    )
    score_cols = st.columns(4)
    score_cols[0].metric(
        "Player Quality", f"{row['player_quality']:.0f}" if row.get("player_quality") is not None else "-",
        help=METRIC_HELP["player_quality"],
    )
    fantasy_value_is_estimated = row.get("estimated") is True
    score_cols[1].metric(
        "Fantasy Value ~" if fantasy_value_is_estimated else "Fantasy Value",
        f"{row['score']:.1f}" if row.get("score") is not None else "-",
        help=METRIC_HELP["fantasy_value_stimato"] if fantasy_value_is_estimated else METRIC_HELP["fantasy_value"],
    )
    vfm = row.get("value_for_money")
    score_cols[2].metric(
        "Value for Money", f"{vfm:.1f}" if vfm is not None else "-",
        help=METRIC_HELP["value_for_money"],
    )
    semaforo = _value_for_money_semaforo(row.get("value_for_money_percentile"))
    if semaforo:
        st.caption(semaforo)
    score_cols[3].metric(
        "Risk", f"{row['risk']:.0f}" if row.get("risk") is not None else "-",
        help=METRIC_HELP["risk"],
    )

    _render_profile_radar(row)

    price_agreement = row.get("price_agreement")
    if price_agreement is not None:
        st.caption(
            f"Confidence quotazione (accordo tra le fonti): {price_agreement:.0f}% — "
            f"{METRIC_HELP['price_agreement']}"
        )
    if row.get("price_outlier_sources"):
        outliers = ", ".join(row["price_outlier_sources"])
        st.caption(f"⚠️ Quotazione anomala segnalata da: {outliers} (peso ridotto nel calcolo)")

    alg_fcp = row.get("alg_fcp")
    punteggio_fcp = row.get("punteggio_fcp")
    fcp_skills = row.get("fcp_skills")
    if alg_fcp is not None or punteggio_fcp is not None or fcp_skills:
        parts = []
        if alg_fcp is not None:
            parts.append(f"ALG FCP: {alg_fcp:.0f}/100")
        if punteggio_fcp is not None:
            parts.append(f"Punteggio FCP: {punteggio_fcp:.0f}/100")
        if fcp_skills:
            parts.append(" · ".join(fcp_skills))
        st.caption(" — ".join(parts))
        st.caption(
            "Segnali da Fantacalciopedia (algoritmo, punteggio e tag skill), "
            "informativi: non incidono su Fantasy Value/Player Quality."
        )

    _render_role_comparison(row)
    _render_advanced_stats(row)
    _render_fantanalisi_valuation(row)

    set_pieces = get_set_piece_summary(conn, row["player_id"])
    if set_pieces:
        rank_icon = {"Principale": "🟢", "Secondario": "🟡"}
        badges = " · ".join(
            f"{rank_icon.get(sp['label'], '⚪')} {sp['category']}: {sp['label']}"
            for sp in set_pieces
        )
        st.markdown(badges)
        st.caption(
            "Gerarchia calci piazzati da fantacalcio.it/rigoristi-serie-a. "
            "🟢 Principale, 🟡 Secondario, ⚪ Riserva."
        )
    else:
        st.caption("Gerarchia calci piazzati: dato non ancora raccolto per questo giocatore.")

    if row.get("notes"):
        st.markdown(f"**Note:** {row['notes']}")

    extra = get_player_extra(conn, row["player_id"])
    if extra.get("transfermarkt_id"):
        st.markdown(
            f"[Profilo Transfermarkt](https://www.transfermarkt.com/-/profil/spieler/{extra['transfermarkt_id']})"
        )

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

    st.divider()
    st.markdown("**Squadra**")
    team_info = get_team_info(row.get("team"))
    if team_info:
        tcol1, tcol2 = st.columns(2)
        tcol1.markdown(f"**Città:** {team_info['citta']}")
        tcol1.markdown(f"**Stadio:** {team_info['stadio']}")
        rivali_text = ', '.join(team_info['rivali']) if team_info['rivali'] else "Nessuno di rilievo"
        tcol2.markdown(f"**Rivali storici:** {rivali_text}")
        tcol2.markdown(f"**Stile di gioco:** {team_info['stile']}")
        st.caption("Informazioni generali sul club, non legate alla stagione in corso.")

        role_fit = get_role_fit(row.get("team"), row.get("role_classic"), row.get("role_mantra"))
        if role_fit:
            st.markdown(f"**Il suo compito:** {role_fit['compito']}")
            fit_cols = st.columns(2)
            if role_fit["pro"]:
                fit_cols[0].markdown(
                    "**Pro per lui:**\n" + "\n".join(f"- {p}" for p in role_fit["pro"])
                )
            if role_fit["contro"]:
                fit_cols[1].markdown(
                    "**Contro per lui:**\n" + "\n".join(f"- {c}" for c in role_fit["contro"])
                )
            st.caption(
                "Valutazione generale basata sullo stile della squadra, non una previsione statistica."
            )
    else:
        st.caption("Nessuna informazione aggiuntiva disponibile su questa squadra.")

    team_strength = get_team_strength(conn, row.get("team"))
    if team_strength and team_strength.get("xg") is not None:
        st.markdown("**Forza squadra (Understat)**")
        scol1, scol2, scol3 = st.columns(3)
        scol1.metric("xG a partita", format_count(team_strength["xg"]))
        scol2.metric("xGA a partita", format_count(team_strength["xga"]))
        scol3.metric("PPDA", format_count(team_strength.get("ppda")))
        st.caption(
            "Gol attesi fatti/concessi a partita e intensità del pressing "
            "(PPDA, più basso = pressing più alto) — dati Understat via "
            "fantanalisi.it, non entrano nel calcolo del Fantasy Value."
        )

    st.divider()
    st.markdown("**Forma recente**")
    form = get_recent_form(conn, row["player_id"])
    if not form["ratings"]:
        st.caption(
            "Nessuna giornata disputata ancora registrata: la forma recente si "
            "popola man mano che vengono giocate le partite."
        )
    else:
        st.metric(
            f"Fantavoto medio (ultime {len(form['ratings'])} giornate)",
            form["avg_fantavoto"] if form["avg_fantavoto"] is not None else "-",
            help="Media del fantavoto (Redazione Fantacalcio) sulle giornate più "
                 "recenti disputate, separata dalla fantamedia stagionale.",
        )
        st.table([
            {"Giornata": r["giornata"], "Stagione": r["season"],
             "Voto": format_count(r["voto"]), "Fantavoto": format_count(r["fantavoto"])}
            for r in form["ratings"]
        ])

    st.divider()
    st.markdown("**Andamento quotazione**")
    history_by_date = get_price_history_by_date(conn, row["player_id"])
    if len(history_by_date) < 2:
        st.caption(
            "Storico non ancora sufficiente: servono più giorni di aggiornamenti "
            "per mostrare un grafico dell'andamento."
        )
    else:
        history_df = pd.DataFrame.from_dict(history_by_date, orient="index").sort_index()
        static_line_chart(history_df, index_label="Data")

    st.divider()
    st.markdown("**Storico stagioni**")
    st.caption(
        "Presenze/gol/assist/media voto reali per stagione (Fantacalciopedia) — "
        "gol subiti al posto di gol fatti per i portieri."
    )
    season_stats = get_player_season_stats(conn, row["player_id"])
    if not season_stats:
        st.caption("Nessuno storico stagionale disponibile per questo giocatore.")
    else:
        is_goalkeeper = row.get("role_classic") == "P"
        goals_label = "Gol subiti" if is_goalkeeper else "Gol fatti"
        chart_df = pd.DataFrame([
            {
                "Stagione": s["season"],
                goals_label: s["goals_conceded"] if is_goalkeeper else s["goals_scored"],
                "Assist": s["assists"],
            }
            for s in reversed(season_stats)  # oldest first, so the chart reads left-to-right chronologically
        ]).set_index("Stagione")
        static_bar_chart(chart_df, index_label="Stagione")
        st.table([
            {
                "Stagione": s["season"],
                "Presenze": format_count(s["appearances"]),
                goals_label: format_count(s["goals_conceded"] if is_goalkeeper else s["goals_scored"]),
                "Assist": format_count(s["assists"]),
                "Media voto": format_count(s["avg_rating"]),
                "Ammonizioni": format_count(s["yellow_cards"]),
                "Espulsioni": format_count(s["red_cards"]),
            }
            for s in season_stats
        ])

    st.divider()
    st.markdown("**Storico infortuni**")

    summary = get_injury_summary(conn, row["player_id"])
    injuries = summary["injuries"]

    if not injuries:
        st.caption("Nessuno storico infortuni disponibile per questo giocatore.")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Giorni totali fermo (storico)", format_count(summary["total_days_out"]))
        col2.metric("Partite saltate (storico)", format_count(summary["total_matches_missed"]))

        st.table([
            {
                "Stagione": i["season"],
                "Infortunio": i["injury_type"],
                "Dal": i["date_from"],
                "Al": i["date_to"],
                "Giorni": format_count(i["days_out"]),
                "Partite saltate": format_count(i["matches_missed"]),
            }
            for i in injuries
        ])

    _render_verdict(row, set_pieces)

    render_purchase_evaluator(conn, row)


TIMING_DECISION_STYLE = {
    "buy_now": "success", "wait": "info", "pass": "error", "save_budget": "warning",
}


@st.cache_data(ttl=3600, show_spinner="Calcolo Auction Intelligence...")
def _cached_auction_intelligence(_conn, player_id: int, current_bid: float, data_version: tuple) -> dict:
    """get_auction_intelligence ricalcola il consensus prezzo su ~700
    giocatori (per l'inflazione) più il ranking dell'intero ruolo (per la
    scarsità): troppo pesante per essere rifatto da zero a ogni rerun della
    pagina (ogni digit nel campo prezzo, ogni click). Tenuta fresca da
    data_version (repository.get_auction_data_version), non da un ttl breve
    (DA9/TASK-026): budget_remaining dipende da my_roster/opponent_picks,
    che un ttl=30 poteva servire stale fino a 30s dopo un acquisto
    registrato durante l'asta. ttl=3600 resta solo come backstop contro una
    cache che cresce senza limite in un processo di lunga durata, non è più
    il meccanismo di invalidazione primario — stesso pattern di
    dashboard.data_access._compute_ranked_role."""
    return get_auction_intelligence(_conn, player_id, current_bid=current_bid)


def render_auction_intelligence(conn, player_id: int, current_bid: float) -> None:
    """Auction Intelligence Engine (spec sez. 84-99): la versione 'cockpit'
    compatta pensata per essere letta in pochi secondi durante un'asta vocale
    — Fair Price, quanto probabilmente costerà, quanto puoi realisticamente
    offrire, e la decisione in un colpo d'occhio. Il dettaglio (perché) resta
    sotto, non nascosto, come richiesto dalla spec sez. 104."""
    data_version = repository.get_auction_data_version(conn)
    info = _cached_auction_intelligence(conn, player_id, current_bid, data_version)
    if not info or not info.get("fair_price"):
        return

    st.markdown("**🎯 Auction Intelligence**")

    cols = st.columns(4)
    cols[0].metric("Fair Price", format_count(info["fair_price"]))
    cols[1].metric(
        "Expected Price", format_count(info["expected_auction_price"]),
        help="Quanto probabilmente verrà pagato, in base all'inflazione osservata "
             "finora in questa asta (miei acquisti + presi dagli avversari).",
    )
    max_bid_info = info.get("max_bid") or {}
    max_bid = max_bid_info.get("max_bid")
    # P1-010/TASK-018: max_bid can now come in below fair_price when the
    # budget/slot reservation doesn't stretch that far — "affordable" makes
    # that visible instead of implying the fair price is still reachable.
    affordable_label = "" if max_bid_info.get("affordable", True) else " ⚠️ non ti puoi permettere il fair price"
    cols[2].metric(
        "Maximum Bid", format_count(max_bid) + affordable_label,
        help="Il tetto oltre il quale non conviene più spingersi: già tiene conto "
             "di budget residuo, slot rimanenti, inflazione e scarsità.",
    )
    cols[3].metric(
        "Scarcity", info["scarcity"]["label"],
        help=f"{info['scarcity']['alternatives_remaining']} alternative di livello "
             "comparabile ancora libere per questo ruolo.",
    )

    timing = info["timing"]
    style = getattr(st, TIMING_DECISION_STYLE.get(timing["action"], "info"))
    style(f"{timing['label']} — {timing['reason']}")

    if info.get("overbid") and info["overbid"]["alert"]:
        st.error(
            f"🚨 OVERBID: il prezzo che stai valutando è "
            f"+{info['overbid']['overbid_pct']:.0f}% sopra l'Expected Price."
        )

    inflation = info["inflation"]
    if inflation.get("inflation_pct") is not None:
        direction = "Inflazione" if inflation["inflation_pct"] >= 0 else "Deflazione"
        st.caption(
            f"{direction} d'asta: {inflation['inflation_pct']:+.1f}% "
            f"(prezzo medio pagato {format_count(inflation['avg_price_paid'])} vs "
            f"fair price medio {format_count(inflation['avg_fair_price'])}, "
            f"su {inflation['sample_size']} acquisti registrati)."
        )
    else:
        st.caption(
            "Inflazione d'asta non ancora stimabile: servono almeno "
            "3 acquisti registrati (miei o degli avversari)."
        )

    dist = info.get("distribution")
    if dist:
        st.caption(
            f"Range di prezzo atteso: {format_count(dist['p25'])}–{format_count(dist['p90'])} "
            f"(mediana {format_count(dist['median'])}, su {dist['sample_size']} acquisti)."
        )

    opponents = info.get("opponents")
    if opponents:
        with st.expander("Avversari (budget e minaccia stimati)", expanded=False):
            st.caption(
                "Stima basata sui soli acquisti registrati manualmente e sull'assunzione "
                "che tutte le squadre seguano le tue stesse regole di lega (budget e slot)."
            )
            st.table([
                {
                    "Avversario": o["opponent_name"],
                    "Speso": format_count(o["spent"]),
                    "Budget residuo": format_count(o["budget_remaining"]),
                    "Giocatori presi": o["players_bought"],
                    "Threat Score": f"{o['threat_score']:.0f}/100",
                }
                for o in opponents
            ])


def render_purchase_evaluator(conn, row: dict) -> None:
    """Sezione 'ne vale la pena?': prezzo ipotetico -> giudizio d'acquisto,
    con possibilità di confermare l'acquisto (mio o di un avversario) e
    storico di tutti gli acquisti registrati finora."""
    st.divider()
    st.markdown("**Valuta acquisto**")

    already_gone = row.get("is_in_roster") or row.get("taken_by")
    if already_gone:
        st.caption(
            "In rosa" if row.get("is_in_roster") else f"Già preso da {row['taken_by']}."
        )
        return

    # TASK-015/P1-004: era un secondo "prezzo massimo" (Price Engine),
    # sistematicamente diverso da quello dell'Auction Intelligence qui
    # sotto — stessa unità, stesso nome operativo, ~3x di scarto su un
    # giocatore reale. Auction Intelligence resta l'unica fonte per
    # "quanto posso offrire"; questo resta un indice di efficienza
    # (100 = mediana del ruolo disponibile), mai un prezzo.
    value_index = get_value_index(conn, row["player_id"])
    if value_index is not None:
        st.caption(
            f"📊 Value Index: {value_index} (100 = mediana di value-for-money del ruolo "
            "ancora disponibile — non un prezzo, un indice di efficienza)."
        )

    # Il preset (+/- cliccato in una pagina ruolo) vale solo per il primo
    # render di questa scheda: dopo va lasciato libero di cambiarlo.
    if "purchase_buyer_choice" not in st.session_state:
        st.session_state["purchase_buyer_choice"] = st.session_state.pop(
            "quick_action_buyer", "io"
        )

    buyer = st.radio(
        "Chi lo prende?", ["io", "avversario"],
        format_func=lambda v: "Io (+)" if v == "io" else "Un avversario (-)",
        key="purchase_buyer_choice", horizontal=True,
    )

    opponent_name = None
    if buyer == "avversario":
        opponent_name = st.text_input("Nome avversario", key="purchase_opponent_name")

    price = st.number_input(
        "Prezzo da valutare", min_value=1,
        value=int(row.get("price_current") or 1), step=1,
        key="purchase_price_input",
    )

    render_auction_intelligence(conn, row["player_id"], price)

    if buyer == "io":
        evaluation = evaluate_player_purchase(conn, row["player_id"], price)
        if evaluation:
            style = getattr(st, PURCHASE_VERDICT_STYLE.get(evaluation["verdict"], "info"))
            style(evaluation["headline"])
            for reason in evaluation["reasons"]:
                st.caption(reason)
            if evaluation.get("all_in_recommended"):
                st.warning(
                    "💡 O lo prendi al prezzo giusto, o rinunci del tutto: non ha senso "
                    "spendere poco su questo slot."
                )
            vfm_price = evaluation.get("value_for_money_at_price")
            if vfm_price is not None:
                st.caption(
                    f"Value for Money a questo prezzo: {vfm_price:.1f} "
                    f"(a quotazione: {format_count(evaluation.get('value_for_money_at_listed'))})"
                )
    else:
        st.caption("Registra solo il prezzo pagato dall'avversario, per tracciare il mercato.")

    if st.button("Conferma", key="purchase_confirm_btn"):
        if buyer == "avversario" and not (opponent_name or "").strip():
            st.error("Indica il nome dell'avversario.")
        else:
            if buyer == "io":
                repository.add_roster_entry(
                    conn, row["player_id"], float(price), date.today().isoformat()
                )
                st.success(f"{row['canonical_name']} aggiunto alla tua rosa a {price} crediti.")
            else:
                repository.add_opponent_pick(
                    conn, row["player_id"], opponent_name.strip(), float(price),
                    date.today().isoformat(),
                )
                st.success(f"{row['canonical_name']} segnato come preso da {opponent_name}.")
            del st.session_state["purchase_buyer_choice"]
            st.rerun()

    st.divider()
    st.markdown("**Storico giocatori e prezzi**")
    mine_only = st.checkbox(
        "Mostra solo i giocatori presi da me", key="purchase_history_mine_only"
    )
    history = get_purchase_history(conn, mine_only=mine_only)
    if not history:
        st.caption("Nessun acquisto registrato ancora.")
    else:
        st.table([
            {
                "Nome": h["canonical_name"], "Ruolo": h["role_classic"],
                "Squadra": normalize_team_name(h["team"]),
                "Prezzo": format_count(h["price_paid"]),
                "Chi": "Io" if h["source"] == "me" else (h.get("opponent_name") or "Avversario"),
                "Data": h["date_added"],
            }
            for h in history
        ])


def _open_player_detail(player_id: int) -> None:
    st.session_state["detail_player_id"] = player_id
    st.switch_page("pages/6_Dettaglio_Giocatore.py")


def _render_role_charts(rows: list) -> None:
    """Scatter ALG FCP vs prezzo (sottovalutati in alto a sinistra) +
    istogramma prezzi per ruolo, dentro un expander per non appesantire
    la pagina di default."""
    with st.expander("Grafici", expanded=False):
        fcp_rows = [
            {"Prezzo": r["price_current"], "ALG FCP": r["alg_fcp"], "Nome": r["canonical_name"]}
            for r in rows
            if r.get("price_current") is not None and r.get("alg_fcp") is not None
        ]
        if fcp_rows:
            st.caption(
                "Sottovalutati: ALG FCP alto (Fantacalciopedia) a fronte di un "
                "prezzo basso — punti in alto a sinistra."
            )
            static_scatter_chart(pd.DataFrame(fcp_rows), x="Prezzo", y="ALG FCP")
        else:
            st.caption(
                "Nessun dato ALG FCP disponibile ancora per questo ruolo "
                "(serve uno scrape delle pagine dettaglio Fantacalciopedia)."
            )

        prices = [r["price_current"] for r in rows if r.get("price_current") is not None]
        if prices:
            st.caption("Distribuzione dei prezzi (inflazione asta per ruolo).")
            bins = pd.cut(prices, bins=min(10, len(set(prices))) or 1)
            counts = bins.value_counts().sort_index()
            hist_df = pd.DataFrame({
                "Fascia prezzo": [f"{int(i.left)}-{int(i.right)}" for i in counts.index],
                "Giocatori": counts.values,
            }).set_index("Fascia prezzo")
            static_bar_chart(hist_df, index_label="Fascia prezzo")


TIER_TABLE_LIMIT = 12  # a curated shortlist, not the whole role dumped into a table


def render_tier_sections(rows: list, insufficient_data_rows: list | None = None) -> None:
    """Fasce (ranking.tiers.classify_role) for one role: Top / Semi-top /
    Titolari fissi / A basso prezzo / Scommesse / Da evitare, each an
    expander with a compact table — a quick-scan study aid layered on top
    of the full card grid below, not a replacement for it. `rows` must be
    the *unfiltered* role ranking (before the search box/sort selector),
    so tiers always reflect the whole role regardless of what the user is
    currently searching for.

    insufficient_data_rows (dashboard.data_access.get_insufficient_data_
    players): players with no real fantamedia, so no score at all — not a
    tier (they'd otherwise land nowhere, or worse, get grouped into "Da
    evitare" as if the numbers had judged them, P0-002/TASK-002)."""
    tiers = classify_role(rows)
    insufficient_data_rows = [
        p for p in (insufficient_data_rows or [])
        if not p.get("is_in_roster") and not p.get("taken_by")
    ]
    if not tiers and not insufficient_data_rows:
        return

    with st.expander("📊 Fasce del ruolo", expanded=False):
        for tier in TIER_ORDER:
            players = tiers.get(tier)
            if not players:
                continue
            st.markdown(f"**{TIER_LABELS[tier]}** ({len(players)})")
            st.caption(TIER_DESCRIPTIONS[tier])
            st.table([
                {
                    "Nome": p["canonical_name"],
                    "Squadra": normalize_team_name(p["team"]),
                    "Quot.": format_count(p.get("price_current")),
                    "Fantasy Value": format_count(p.get("score")),
                    "Risk": format_count(p.get("risk")),
                }
                for p in players[:TIER_TABLE_LIMIT]
            ])
            if len(players) > TIER_TABLE_LIMIT:
                st.caption(f"+ altri {len(players) - TIER_TABLE_LIMIT} in questa fascia.")

        if insufficient_data_rows:
            st.markdown(f"**❓ Dati insufficienti** ({len(insufficient_data_rows)})")
            st.caption(
                "Nessuna fantamedia Serie A disponibile (spesso neo-arrivati senza "
                "storico) — non classificabili in una fascia, e non 'da evitare'."
            )
            st.table([
                {
                    "Nome": p["canonical_name"],
                    "Squadra": normalize_team_name(p["team"]),
                    "Quot.": format_count(p.get("price_current")),
                }
                for p in insufficient_data_rows[:TIER_TABLE_LIMIT]
            ])
            if len(insufficient_data_rows) > TIER_TABLE_LIMIT:
                st.caption(f"+ altri {len(insufficient_data_rows) - TIER_TABLE_LIMIT} con dati insufficienti.")


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


def render_decision_center(conn) -> None:
    """Decision Center (dashboard.data_access.get_decision_center): i
    migliori candidati su tutti i ruoli, classificati Compra/Differenziale/
    Attendi/Evita da Auction Intelligence (scarsità + inflazione + max bid
    dinamico, TASK-015) + Marginal Squad Value, ognuno con una motivazione
    breve."""
    result = get_decision_center(conn)
    if not any(result.values()):
        return

    with st.expander("🧭 Decision Center", expanded=False):
        st.caption(
            "I migliori candidati sui ruoli ancora aperti, valutati su prezzo "
            "equo, scarsità di alternative e quanto migliorerebbero davvero "
            "la tua rosa — non solo il Fantasy Value assoluto."
        )
        for bucket in DECISION_BUCKETS:
            entries = result[bucket]
            if not entries:
                continue
            st.markdown(f"**{DECISION_BUCKET_LABELS[bucket]}**")
            for r in entries:
                cols = st.columns([3, 2, 2, 4])
                cols[0].write(f"{r['canonical_name']} ({r['role_classic']})")
                cols[1].write(f"Quot. {format_count(r.get('price_current'))}")
                max_bid = r.get("auction_max_bid")
                cols[2].write(f"Max {format_count(max_bid)}" if max_bid is not None else "")
                cols[3].caption(r.get("reason", ""))
            st.divider()


# Rendering 100+ cards at once (some roles have 150+ players and this page
# has no filter applied by default) meant 100+ image decodes and 300+ button
# widgets built on every rerun even before the missing-cache issue. Paginate
# so a role page only ever builds one page's worth of cards; searching still
# searches the *entire* role, only the results are paginated.
# Must be a multiple of the 4-cards-per-row grid: a page total that isn't
# (30 wasn't) leaves a short last page/row, which used to both stretch that
# row's cards wider than every other row's and make the header's total
# ("N giocatori") not match what's actually visible on page 1 for any role
# whose size is close to one page (e.g. Portieri, 32 players).
CARDS_PER_PAGE = 32


# Due squadre per riga nella pagina Portieri, quindi **quattro card per riga**
# come nelle pagine degli altri ruoli (render_role_page, cols_per_row = 4).
# Le due squadre restano coppie distinte: le intestazioni vanno su una riga da
# 2 colonne e le card su una da 4, così ogni titolo copre esattamente la sua
# coppia titolare/riserva e non si perde di vista a chi appartiene una card.
GOALKEEPER_TEAMS_PER_ROW = 2


def goalkeeper_team_rows(teams: list, per_row: int = GOALKEEPER_TEAMS_PER_ROW) -> list:
    """Spezza l'elenco squadre nelle righe della griglia. Funzione a sé, e
    non un `range` dentro il rendering, perché "quante card per riga" è la
    cosa che si vuole poter verificare senza montare una pagina Streamlit."""
    return [teams[i:i + per_row] for i in range(0, len(teams), per_row)]


def render_goalkeeper_depth_chart(conn) -> None:
    """Vista dedicata Portieri (giocatori/portieri.md): titolare + riserva
    per ciascuna delle 20 squadre di Serie A, neopromosse per ultime,
    invece della lista piatta generica di render_role_page."""
    _inject_card_css()
    st.markdown('<div class="fc-page-title">Portieri</div>', unsafe_allow_html=True)

    all_rows = get_goalkeeper_pool(conn)
    expected_teams = {
        full: normalize_team(full) in PROMOTED_TEAM_CODES
        for full in TEAM_ABBREV_TO_FULL.values()
    }
    chart = build_goalkeeper_depth_chart(all_rows, expected_teams=expected_teams)

    st.caption(
        f"{chart['n_teams']} squadre, {chart['n_goalkeepers']} portieri titolari/riserva "
        "identificati (controllo anti-errore portieri.md §13)."
    )
    if chart["duplicates"]:
        st.warning(
            "Stesso giocatore selezionato per più squadre (probabile errore di "
            f"matching): player_id {', '.join(str(pid) for pid in chart['duplicates'])}"
        )
    if chart["warnings"]:
        st.warning(
            "Solo un portiere identificabile (dati insufficienti per la riserva) "
            "per: " + ", ".join(chart["warnings"])
        )
    if chart["missing"]:
        st.warning(
            "Nessun portiere identificabile (dati insufficienti) per: "
            + ", ".join(chart["missing"])
        )

    for row_teams in goalkeeper_team_rows(chart["teams"]):
        header_cols = st.columns(GOALKEEPER_TEAMS_PER_ROW)
        for col, team_entry in zip(header_cols, row_teams):
            with col:
                st.markdown(f"### {team_entry['team']}")
                # Perché quel portiere è dato titolare. Con "presenze" la
                # scelta viene dalla stagione scorsa e va guardata con più
                # sospetto che con "prezzo" (ranking/goalkeepers.py).
                if team_entry.get("starter_basis"):
                    st.caption(f"gerarchia da: {team_entry['starter_basis']}")

        card_cols = st.columns(GOALKEEPER_TEAMS_PER_ROW * 2)
        for i, team_entry in enumerate(row_teams):
            with card_cols[i * 2]:
                if team_entry["starter"]:
                    render_player_card(team_entry["starter"], rank=1, badge_text="T")
            with card_cols[i * 2 + 1]:
                if team_entry["backup"]:
                    render_player_card(team_entry["backup"], rank=2, badge_text="R")

    if any(t["is_promoted"] for t in chart["teams"]):
        st.caption("* Squadra neopromossa")

    render_tier_sections(all_rows, get_insufficient_data_players(conn, "P"))


def render_role_page(conn, role_classic: str, role_label: str) -> None:
    _inject_card_css()
    st.markdown(
        f'<div class="fc-page-title">{role_label}</div>', unsafe_allow_html=True,
    )

    query = st.text_input("Cerca giocatore per nome", key=f"role-search-{role_classic}")
    sort_by = st.selectbox(
        "Ordina per", ["rank", "team", "price"], key=f"role-sort-{role_classic}",
        index=2,  # default "price" (quotazione), on request
        format_func=lambda v: {"rank": "Ranking", "team": "Squadra", "price": "Quotazione"}[v],
    )

    all_rows = get_ranked_role(conn, role_classic)
    rows = search_and_sort(all_rows, query=query, sort_by=sort_by)

    render_tier_sections(all_rows, get_insufficient_data_players(conn, role_classic))

    _render_role_charts(rows)

    if any(r.get("is_promoted") for r in rows):
        st.caption("* Squadra neopromossa")

    page_key = f"role-page-{role_classic}"
    total_pages = max(1, -(-len(rows) // CARDS_PER_PAGE))  # ceiling division
    current_page = min(st.session_state.get(page_key, 1), total_pages)
    page_start = (current_page - 1) * CARDS_PER_PAGE
    page_rows = rows[page_start:page_start + CARDS_PER_PAGE]

    meta_right = f"{current_page} / {total_pages}" if total_pages > 1 else ""
    st.markdown(
        '<div class="fc-page-meta">'
        f'<span>{len(rows)} giocatori</span><span>{meta_right}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    cols_per_row = 4
    for start in range(0, len(page_rows), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = list(enumerate(
            page_rows[start:start + cols_per_row], start=page_start + start + 1,
        ))
        for col, (rank, row) in zip(cols, chunk):
            with col:
                render_player_card(row, rank)

    if total_pages > 1:
        st.markdown('<div class="fc-pager-marker"></div>', unsafe_allow_html=True)
        nav_cols = st.columns([1, 1, 10])
        with nav_cols[0]:
            if st.button("‹", disabled=current_page <= 1, key=f"{page_key}-prev"):
                st.session_state[page_key] = current_page - 1
                st.rerun()
        with nav_cols[1]:
            if st.button("›", disabled=current_page >= total_pages, key=f"{page_key}-next"):
                st.session_state[page_key] = current_page + 1
                st.rerun()
