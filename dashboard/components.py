import base64
import os
import streamlit as st
from dashboard.data_access import (
    get_ranked_role,
    search_and_sort,
    get_injury_summary,
    get_player_extra,
)
from dashboard.team_info import get_team_info

PLACEHOLDER_COLORS = {"P": "#f4c542", "D": "#4caf50", "C": "#2196f3", "A": "#e53935"}

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "photos")

ROLE_LABELS = {"P": "Portiere", "D": "Difensore", "C": "Centrocampista", "A": "Attaccante"}


def _photo_data_uri(photo_path: str) -> str | None:
    """Resolve a photo by filename against the repo's data/photos dir.

    Old rows may have an absolute path from whatever machine scraped them
    (e.g. a local Windows path); only the filename is portable across
    machines/deployments, so we always re-resolve against PHOTOS_DIR.
    """
    if not photo_path:
        return None
    resolved = os.path.join(PHOTOS_DIR, os.path.basename(photo_path))
    if not os.path.exists(resolved):
        return None
    with open(resolved, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def render_player_card(row: dict, rank: int) -> str:
    color = PLACEHOLDER_COLORS.get(row["role_classic"], "#999999")
    photo_uri = _photo_data_uri(row.get("photo_path"))

    if photo_uri:
        photo_html = f"<img src='{photo_uri}' class='fc-card-photo' />"
    else:
        photo_html = (
            f"<div class='fc-card-photo fc-card-placeholder' style='background:{color};'>"
            f"{row['canonical_name'][0]}</div>"
        )

    roster_tag = " ⭐" if row["is_in_roster"] else ""
    promoted_tag = " *" if row.get("is_promoted") else ""
    notes_html = f"<div class='fc-card-notes'>{row['notes']}</div>" if row["notes"] else ""
    status_html = (
        f"<div class='fc-card-status'>Stato: {row['status']}</div>"
        if row.get("status") and row["status"] not in ("ok", None)
        else ""
    )
    fantamedia_html = (
        f"<div class='fc-card-line'>Fantamedia: {row['fantamedia']}</div>"
        if row.get("fantamedia")
        else ""
    )

    price_line = (
        f"<div class='fc-card-line'>Quot. {row.get('price_current', '-')} "
        f"(in. {row.get('price_initial', '-')})</div>"
    )
    return (
        f"<div class='fc-card' style='border-color:{color};'>"
        f"{photo_html}"
        f"<div class='fc-card-rank' style='background:{color};'>#{rank}</div>"
        f"<div class='fc-card-body'>"
        f"<div class='fc-card-name'>{row['canonical_name']}{promoted_tag}{roster_tag}</div>"
        f"<div class='fc-card-team'>{row['team']} · Rating {row['score']:.1f}</div>"
        f"{price_line}"
        f"{fantamedia_html}"
        f"{status_html}"
        f"{notes_html}"
        f"</div>"
        f"</div>"
    )


def _inject_card_css() -> None:
    st.markdown(
        """
        <style>
        .fc-card-wrap {
            position: relative;
        }
        .fc-card {
            width: 100%;
            max-width: 190px;
            height: 280px;
            margin: 0 auto;
            border: 3px solid #999;
            border-radius: 14px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            background: #ffffff;
            color: #1a1a1a;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            position: relative;
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }
        .fc-card-wrap:hover .fc-card {
            transform: translateY(-3px);
            box-shadow: 0 6px 14px rgba(0,0,0,0.25);
        }
        div[data-testid="stElementContainer"][class*="st-key-card-btn-"] {
            margin-top: -284px;
            width: 100% !important;
            position: relative;
            z-index: 10;
        }
        div[data-testid="stElementContainer"][class*="st-key-card-btn-"] div[data-testid="stButton"] {
            width: 100%;
        }
        div[data-testid="stElementContainer"][class*="st-key-card-btn-"] button {
            height: 280px;
            width: 100% !important;
            opacity: 0;
            cursor: pointer;
            border: none;
            padding: 0;
            background: transparent;
        }
        .fc-card-photo {
            width: 100%;
            height: 154px;
            flex-shrink: 0;
            object-fit: cover;
            display: block;
        }
        @media (max-width: 480px) {
            .fc-card {
                max-width: 260px;
                height: 320px;
            }
            .fc-card-photo {
                height: 180px;
            }
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
        .fc-card-body {
            padding: 8px 10px;
            display: flex;
            flex-direction: column;
            gap: 2px;
            overflow-y: auto;
        }
        .fc-card-name {
            font-weight: bold;
            font-size: 14px;
            line-height: 1.2;
        }
        .fc-card-team {
            font-size: 12px;
            color: #444;
        }
        .fc-card-line {
            font-size: 11px;
            color: #1a1a1a;
        }
        .fc-card-status {
            font-size: 11px;
            color: #b45309;
        }
        .fc-card-notes {
            font-size: 11px;
            font-style: italic;
            opacity: 0.85;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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

    st.divider()

    info_cols = st.columns(4)
    info_cols[0].metric("Rating", f"{row['score']:.1f}" if row.get("score") is not None else "-")
    price_current = row.get("price_current")
    price_initial = row.get("price_initial")
    delta = None
    if price_current is not None and price_initial is not None:
        delta = round(price_current - price_initial, 2)
    info_cols[1].metric(
        "Quotazione", price_current if price_current is not None else "-",
        delta=delta if delta else None,
    )
    info_cols[2].metric("Quot. iniziale", price_initial if price_initial is not None else "-")
    info_cols[3].metric("Fantamedia", row.get("fantamedia", "-"))

    info_cols2 = st.columns(4)
    info_cols2[0].metric("Media voto", row.get("avg_rating", "-"))
    info_cols2[1].metric("Presenze", row.get("appearances", "-"))
    status = row.get("status")
    info_cols2[2].metric("Stato", status if status and status != "ok" else "Regolare")
    info_cols2[3].metric("Fonti dati", row.get("source", "-"))

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
        tcol2.markdown(f"**Rivali storici:** {', '.join(team_info['rivali'])}")
        tcol2.markdown(f"**Stile di gioco:** {team_info['stile']}")
        st.caption("Informazioni generali sul club, non legate alla stagione in corso.")
    else:
        st.caption("Nessuna informazione aggiuntiva disponibile su questa squadra.")

    st.divider()
    st.markdown("**Storico infortuni**")

    summary = get_injury_summary(conn, row["player_id"])
    injuries = summary["injuries"]

    if not injuries:
        st.caption("Nessuno storico infortuni disponibile per questo giocatore.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Giorni totali fermo (storico)", summary["total_days_out"])
    col2.metric("Partite saltate (storico)", summary["total_matches_missed"])

    st.table([
        {
            "Stagione": i["season"],
            "Infortunio": i["injury_type"],
            "Dal": i["date_from"],
            "Al": i["date_to"],
            "Giorni": i["days_out"],
            "Partite saltate": i["matches_missed"],
        }
        for i in injuries
    ])


def _open_player_detail(player_id: int) -> None:
    st.session_state["detail_player_id"] = player_id
    st.switch_page("pages/6_Dettaglio_Giocatore.py")


def render_role_page(conn, role_classic: str, role_label: str) -> None:
    st.title(role_label)
    _inject_card_css()

    query = st.text_input("Cerca giocatore per nome")
    sort_by = st.selectbox("Ordina per", ["rank", "team", "price"], format_func=lambda v: {
        "rank": "Ranking", "team": "Squadra", "price": "Quotazione",
    }[v])

    rows = get_ranked_role(conn, role_classic)
    rows = search_and_sort(rows, query=query, sort_by=sort_by)

    st.caption(f"{len(rows)} giocatori · Clicca su una figurina per aprire la scheda completa.")

    if any(r.get("is_promoted") for r in rows):
        st.caption("* Squadra neopromossa")

    cols_per_row = 5
    for start in range(0, len(rows), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = list(enumerate(rows[start:start + cols_per_row], start=start + 1))
        for col, (rank, row) in zip(cols, chunk):
            with col:
                st.markdown(
                    f"<div class='fc-card-wrap'>{render_player_card(row, rank)}</div>",
                    unsafe_allow_html=True,
                )
                if st.button("", key=f"card-btn-{role_classic}-{row['player_id']}"):
                    _open_player_detail(row["player_id"])
