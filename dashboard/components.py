import base64
import os
import streamlit as st
from dashboard.data_access import get_ranked_role, search_and_sort

PLACEHOLDER_COLORS = {"P": "#f4c542", "D": "#4caf50", "C": "#2196f3", "A": "#e53935"}


def _photo_data_uri(photo_path: str) -> str | None:
    if not photo_path or not os.path.exists(photo_path):
        return None
    with open(photo_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def render_player_card(row: dict, rank: int) -> None:
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
    card_html = (
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
    st.markdown(card_html, unsafe_allow_html=True)


def _inject_card_css() -> None:
    st.markdown(
        """
        <style>
        .fc-card {
            width: 190px;
            aspect-ratio: 5 / 7;
            border: 3px solid #999;
            border-radius: 14px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            background: #ffffff;
            color: #1a1a1a;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            position: relative;
        }
        .fc-card-photo {
            width: 100%;
            height: 55%;
            object-fit: cover;
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


def render_role_page(conn, role_classic: str, role_label: str) -> None:
    st.title(role_label)
    _inject_card_css()

    query = st.text_input("Cerca giocatore per nome")
    sort_by = st.selectbox("Ordina per", ["rank", "team", "price"], format_func=lambda v: {
        "rank": "Ranking", "team": "Squadra", "price": "Quotazione",
    }[v])

    rows = get_ranked_role(conn, role_classic)
    rows = search_and_sort(rows, query=query, sort_by=sort_by)

    if any(r.get("is_promoted") for r in rows):
        st.caption("* Squadra neopromossa")

    cards_per_row = 4
    for start in range(0, len(rows), cards_per_row):
        chunk = list(enumerate(rows[start:start + cards_per_row], start=start + 1))
        cols = st.columns(cards_per_row)
        for col, (rank, row) in zip(cols, chunk):
            with col:
                render_player_card(row, rank=rank)
