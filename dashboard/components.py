import base64
import os
import re
from datetime import date
import pandas as pd
import streamlit as st
from db import repository
from dashboard.data_access import (
    get_ranked_role,
    search_and_sort,
    get_injury_summary,
    get_player_extra,
    get_price_history_by_date,
    get_set_piece_summary,
    get_recent_form,
    get_purchase_history,
    evaluate_player_purchase,
    normalize_team_name,
    format_count,
    get_ideal_formation,
    get_auction_intelligence,
)
from dashboard.team_info import get_team_info, get_role_fit

PURCHASE_VERDICT_STYLE = {
    "affare": "success", "prezzo_giusto": "success",
    "caro": "warning", "troppo_caro": "error",
    "ruolo_pieno": "error", "inutile_hai_di_meglio": "error",
    "sconosciuto": "info",
}

PLACEHOLDER_COLORS = {"P": "#f4c542", "D": "#4caf50", "C": "#2196f3", "A": "#e53935"}

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
    "quot_iniziale": "Prezzo di partenza a inizio stagione, prima delle variazioni di mercato.",
    "fantamedia": "Media dei voti fantacalcio (voto + bonus - malus) sulle partite giocate.",
    "media_voto": "Media dei voti puri in pagella, senza bonus/malus fantacalcio.",
    "presenze": "Numero di partite giocate nella stagione.",
    "stato": "Disponibilità attuale del giocatore (infortunato, squalificato, regolare).",
    "fonti_dati": "Fonti che hanno contribuito alla quotazione consensus di questo giocatore.",
    "player_quality": "Forza calcistica pura (basata sulla media voto), indipendente da "
                       "prezzo e convenienza fantasy. Un difensore forte ma che non fa bonus "
                       "può avere Player Quality alta.",
    "fantasy_value": "Quanto rende questo giocatore al fantacalcio: bonus attesi più "
                      "affidabilità, penalizzato se attualmente indisponibile.",
    "value_for_money": "Fantasy Value diviso per il prezzo attuale: quanto rendimento ottieni "
                        "per ogni credito speso. Più alto = affare migliore.",
    "risk": "0-100, più alto è più rischioso: dipende da quante partite ha giocato "
            "(affidabilità) e se è attualmente indisponibile.",
    "confidence": "Quanto le fonti sono d'accordo sulla quotazione di questo giocatore. "
                  "Bassa confidence = poche fonti o fonti molto discordanti.",
}


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
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def render_player_card(row: dict, rank: int) -> None:
    """One player card: a native st.container(border=True) with a photo
    (still a small HTML snippet for the rounded frame + rank badge, but
    self-contained — position:relative/absolute inside a div this function
    itself renders, not anchored to Streamlit's internal DOM structure) and
    native st.markdown/st.caption text, a real "Apri scheda" button, and the
    two quick-action buttons.

    Previously the whole card was one HTML blob plus an invisible full-card
    button made clickable via CSS :has() selectors targeting Streamlit's
    internal data-testid attributes and negative margins to overlay it —
    functional, but liable to silently stop intercepting clicks (or misalign
    over the wrong element) on any Streamlit DOM change, since it depended on
    undocumented internal structure rather than a public API. A visible
    button is less "magic" but keeps working regardless of Streamlit's
    internal markup.
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

    with st.container(border=True):
        st.markdown(
            f"<div class='fc-photo-wrap'>{photo_html}"
            f"<span class='fc-card-rank' style='background:{color};'>#{rank}</span></div>",
            unsafe_allow_html=True,
        )

        roster_tag = " ⭐" if row["is_in_roster"] else ""
        promoted_tag = " *" if row.get("is_promoted") else ""
        st.markdown(f"**{row['canonical_name']}{promoted_tag}{roster_tag}**")
        st.caption(f"{row['team']} · Rating {row['score']:.1f}")

        price_line = f"Quot. {row.get('price_current', '-')} (in. {row.get('price_initial', '-')})"
        if row.get("fantamedia"):
            price_line += f" · FM {row['fantamedia']}"
        st.caption(price_line)

        if row.get("taken_by"):
            st.caption(f"🔒 Preso da {row['taken_by']}")
        elif row.get("status") and row["status"] not in ("ok", None):
            st.caption(f"⚠️ Stato: {row['status']}")
        if row["notes"]:
            st.caption(f"📝 {row['notes']}")

        if st.button("Apri scheda →", key=f"open-{row['player_id']}", use_container_width=True):
            _open_player_detail(row["player_id"])

        action_cols = st.columns(2)
        with action_cols[0]:
            if st.button(
                "➕", key=f"plus-{row['player_id']}",
                help="Prendo io", use_container_width=True,
            ):
                st.session_state["quick_action_buyer"] = "io"
                if "purchase_buyer_choice" in st.session_state:
                    del st.session_state["purchase_buyer_choice"]
                _open_player_detail(row["player_id"])
        with action_cols[1]:
            if st.button(
                "➖", key=f"minus-{row['player_id']}",
                help="Preso da un avversario", use_container_width=True,
            ):
                st.session_state["quick_action_buyer"] = "avversario"
                if "purchase_buyer_choice" in st.session_state:
                    del st.session_state["purchase_buyer_choice"]
                _open_player_detail(row["player_id"])


# Apple-style palette: system-blue accent, off-white surfaces, near-black
# text — same tokens the global CSS and the player-card CSS both draw from.
APPLE_BLUE = "#6e6e73"
APPLE_BLUE_DARK = "#525256"
APPLE_INK = "#1d1d1f"
APPLE_GRAY = "#6e6e73"
APPLE_SURFACE = "#f5f5f7"
APPLE_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', "
    "'Helvetica Neue', Helvetica, Arial, sans-serif"
)


def inject_global_css() -> None:
    """Apple-like visual theme applied across every page: SF-style font
    stack, neutral surfaces, system-blue accent, rounded corners and soft
    shadows on Streamlit's native widgets (buttons, metrics, inputs,
    tables). Safe to call multiple times per run (st.markdown just appends
    another <style> block)."""
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: {APPLE_FONT_STACK};
        }}
        [data-testid="stAppViewContainer"] {{
            background: #ffffff;
        }}
        [data-testid="stHeader"] {{
            background: rgba(255,255,255,0.8);
            backdrop-filter: saturate(180%) blur(12px);
        }}
        [data-testid="stSidebar"] {{
            background: {APPLE_SURFACE};
            border-right: 1px solid #e5e5ea;
        }}
        h1, h2, h3 {{
            color: {APPLE_INK};
            font-weight: 600;
            letter-spacing: -0.01em;
        }}
        p, span, label, div {{
            color: {APPLE_INK};
        }}
        [data-testid="stCaptionContainer"], .stCaption {{
            color: {APPLE_GRAY} !important;
        }}
        button[kind], .stButton > button, .stDownloadButton > button {{
            border-radius: 980px;
            border: 1px solid {APPLE_BLUE};
            background: {APPLE_BLUE};
            color: #ffffff;
            font-weight: 500;
            transition: background 0.15s ease, transform 0.1s ease;
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            background: {APPLE_BLUE_DARK};
            border-color: {APPLE_BLUE_DARK};
            transform: translateY(-1px);
        }}
        [data-testid="stMetric"] {{
            background: {APPLE_SURFACE};
            border-radius: 18px;
            padding: 14px 16px;
            border: 1px solid #e5e5ea;
        }}
        [data-testid="stMetricValue"] {{
            color: {APPLE_INK};
            font-weight: 600;
        }}
        [data-testid="stMetricLabel"] {{
            color: {APPLE_GRAY};
        }}
        div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="base-input"] {{
            border-radius: 12px !important;
        }}
        [data-testid="stExpander"] {{
            border-radius: 14px;
            border: 1px solid #e5e5ea;
        }}
        [data-testid="stTable"], .stTable {{
            border-radius: 14px;
            overflow: hidden;
        }}
        hr, [data-testid="stDivider"] {{
            border-color: #e5e5ea;
        }}
        [data-testid="stAlert"] {{
            border-radius: 14px;
            border: none;
        }}
        .fc-ideal-menu-marker {{
            font-weight: 600;
            padding: 8px 10px;
            border-radius: 10px;
            cursor: default;
            color: {APPLE_INK};
        }}
        .fc-ideal-menu-marker:hover {{
            background: #e5e5ea;
        }}
        [data-testid="stSidebar"] div[data-testid="element-container"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"] {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.2s ease-in;
            margin-top: -6px;
        }}
        [data-testid="stSidebar"] div[data-testid="element-container"]:has(.fc-ideal-menu-marker):hover + div[data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.fc-ideal-menu-marker):hover + div[data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.fc-ideal-menu-marker):hover,
        [data-testid="stSidebar"] div[data-testid="element-container"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"]:hover,
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.fc-ideal-menu-marker) + div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
            max-height: 900px;
        }}
        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button {{
            background: transparent;
            border: none;
            color: {APPLE_INK};
            font-weight: 400;
            text-align: left;
            justify-content: flex-start;
            padding: 4px 10px 4px 22px;
            border-radius: 8px;
        }}
        [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button:hover {{
            background: #e5e5ea;
            transform: none;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_ideal_squad(conn) -> None:
    """Voce 'Rosa Ideale' nel menu laterale: si espande al passaggio del
    mouse (puro CSS, tecnica dropdown a max-height) e mostra scorciatoie
    dirette alla scheda di ciascun titolare, senza passare dalla pagina
    completa 'La Mia Rosa'."""
    formation = get_ideal_formation(conn, "3-4-3")
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


def _inject_card_css() -> None:
    """Styles only elements render_player_card renders and fully owns
    (.fc-photo-wrap and its children) — no selector here reaches into
    Streamlit's own generated markup (data-testid, container nesting), unlike
    the previous version. The card "box" itself is now a plain
    st.container(border=True): no custom width/height/shadow rules needed,
    Streamlit's own container styling provides it and keeps doing so across
    version upgrades."""
    inject_global_css()
    st.markdown(
        """
        <style>
        .fc-photo-wrap {
            position: relative;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 0.5rem;
        }
        .fc-card-photo {
            width: 100%;
            height: 140px;
            object-fit: cover;
            object-position: center 15%;
            display: block;
        }
        .fc-card-placeholder {
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 48px;
            font-weight: bold;
        }
        .fc-card-rank {
            position: absolute;
            top: 6px;
            left: 6px;
            color: white;
            font-size: 12px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
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
        if row.get("rank_in_role"):
            st.caption(
                f"#{row['rank_in_role']} su {row['role_total']} nel ruolo {role_label}"
            )
        if row.get("is_in_roster"):
            st.success("In rosa")
        elif row.get("taken_by"):
            st.warning(f"🔒 Preso da {row['taken_by']}")

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
    info_cols[1].metric(
        "Quotazione", price_current if price_current is not None else "-",
        delta=delta if delta else None, help=METRIC_HELP["quotazione"],
    )
    info_cols[2].metric(
        "Quot. iniziale", price_initial if price_initial is not None else "-",
        help=METRIC_HELP["quot_iniziale"],
    )
    info_cols[3].metric("Fantamedia", row.get("fantamedia", "-"), help=METRIC_HELP["fantamedia"])

    info_cols2 = st.columns(4)
    info_cols2[0].metric("Media voto", row.get("avg_rating", "-"), help=METRIC_HELP["media_voto"])
    info_cols2[1].metric("Presenze", row.get("appearances", "-"), help=METRIC_HELP["presenze"])
    status = row.get("status")
    info_cols2[2].metric(
        "Stato", status if status and status != "ok" else "Regolare",
        help=METRIC_HELP["stato"],
    )
    info_cols2[3].metric("Fonti dati", row.get("source", "-"), help=METRIC_HELP["fonti_dati"])

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
    score_cols[1].metric(
        "Fantasy Value", f"{row['score']:.1f}" if row.get("score") is not None else "-",
        help=METRIC_HELP["fantasy_value"],
    )
    vfm = row.get("value_for_money")
    score_cols[2].metric(
        "Value for Money", f"{vfm:.1f}" if vfm is not None else "-",
        help=METRIC_HELP["value_for_money"],
    )
    score_cols[3].metric(
        "Risk", f"{row['risk']:.0f}" if row.get("risk") is not None else "-",
        help=METRIC_HELP["risk"],
    )

    _render_profile_radar(row)

    confidence = row.get("confidence")
    if confidence is not None:
        st.caption(f"Confidence quotazione (accordo tra le fonti): {confidence:.0f}% — {METRIC_HELP['confidence']}")
    if row.get("price_outlier_sources"):
        outliers = ", ".join(row["price_outlier_sources"])
        st.caption(f"⚠️ Quotazione anomala segnalata da: {outliers} (peso ridotto nel calcolo)")

    alg_fcp = row.get("alg_fcp")
    fcp_skills = row.get("fcp_skills")
    if alg_fcp is not None or fcp_skills:
        parts = []
        if alg_fcp is not None:
            parts.append(f"ALG FCP: {alg_fcp:.0f}/100")
        if fcp_skills:
            parts.append(" · ".join(fcp_skills))
        st.caption(" — ".join(parts))
        st.caption(
            "Segnali da Fantacalciopedia (algoritmo e tag skill), informativi: "
            "non incidono su Fantasy Value/Player Quality."
        )

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

    if row.get("notes"):
        st.markdown(f"**Note:** {row['notes']}")

    extra = get_player_extra(conn, row["player_id"])
    if extra.get("transfermarkt_id"):
        st.markdown(
            f"[Profilo Transfermarkt](https://www.transfermarkt.com/-/profil/spieler/{extra['transfermarkt_id']})"
        )

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
        st.line_chart(history_df)

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

    render_purchase_evaluator(conn, row)


TIMING_DECISION_STYLE = {
    "buy_now": "success", "wait": "info", "pass": "error", "save_budget": "warning",
}


@st.cache_data(ttl=30, show_spinner="Calcolo Auction Intelligence...")
def _cached_auction_intelligence(_conn, player_id: int, current_bid: float) -> dict:
    """get_auction_intelligence ricalcola il consensus prezzo su ~700
    giocatori (per l'inflazione) più il ranking dell'intero ruolo (per la
    scarsità): troppo pesante per essere rifatto da zero a ogni rerun della
    pagina (ogni digit nel campo prezzo, ogni click). Cache breve (30s) così
    resta comunque aggiornata poco dopo il prossimo acquisto registrato."""
    return get_auction_intelligence(_conn, player_id, current_bid=current_bid)


def render_auction_intelligence(conn, player_id: int, current_bid: float) -> None:
    """Auction Intelligence Engine (spec sez. 84-99): la versione 'cockpit'
    compatta pensata per essere letta in pochi secondi durante un'asta vocale
    — Fair Price, quanto probabilmente costerà, quanto puoi realisticamente
    offrire, e la decisione in un colpo d'occhio. Il dettaglio (perché) resta
    sotto, non nascosto, come richiesto dalla spec sez. 104."""
    info = _cached_auction_intelligence(conn, player_id, current_bid)
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
    max_bid = info["max_bid"].get("max_bid") if info.get("max_bid") else None
    cols[2].metric(
        "Maximum Bid", format_count(max_bid),
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
            st.scatter_chart(pd.DataFrame(fcp_rows), x="Prezzo", y="ALG FCP")
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
            st.bar_chart(hist_df)


# Rendering 100+ cards at once (some roles have 150+ players and this page
# has no filter applied by default) meant 100+ image decodes and 300+ button
# widgets built on every rerun even before the missing-cache issue. Paginate
# so a role page only ever builds one page's worth of cards; searching still
# searches the *entire* role, only the results are paginated.
CARDS_PER_PAGE = 30


def render_role_page(conn, role_classic: str, role_label: str) -> None:
    st.title(role_label)
    _inject_card_css()

    query = st.text_input("Cerca giocatore per nome", key=f"role-search-{role_classic}")
    sort_by = st.selectbox(
        "Ordina per", ["rank", "team", "price"], key=f"role-sort-{role_classic}",
        format_func=lambda v: {"rank": "Ranking", "team": "Squadra", "price": "Quotazione"}[v],
    )

    rows = get_ranked_role(conn, role_classic)
    rows = search_and_sort(rows, query=query, sort_by=sort_by)

    _render_role_charts(rows)

    if any(r.get("is_promoted") for r in rows):
        st.caption("* Squadra neopromossa")

    page_key = f"role-page-{role_classic}"
    total_pages = max(1, -(-len(rows) // CARDS_PER_PAGE))  # ceiling division
    current_page = min(st.session_state.get(page_key, 1), total_pages)
    page_start = (current_page - 1) * CARDS_PER_PAGE
    page_rows = rows[page_start:page_start + CARDS_PER_PAGE]

    caption = f"{len(rows)} giocatori"
    if total_pages > 1:
        caption += f" · pagina {current_page}/{total_pages}"
    st.caption(caption + " · Clicca \"Apri scheda\" per i dettagli.")

    cols_per_row = 5
    for start in range(0, len(page_rows), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = list(enumerate(
            page_rows[start:start + cols_per_row], start=page_start + start + 1,
        ))
        for col, (rank, row) in zip(cols, chunk):
            with col:
                render_player_card(row, rank)

    if total_pages > 1:
        nav_cols = st.columns([1, 1, 3])
        with nav_cols[0]:
            if st.button("← Precedente", disabled=current_page <= 1, key=f"{page_key}-prev"):
                st.session_state[page_key] = current_page - 1
                st.rerun()
        with nav_cols[1]:
            if st.button("Successiva →", disabled=current_page >= total_pages, key=f"{page_key}-next"):
                st.session_state[page_key] = current_page + 1
                st.rerun()
