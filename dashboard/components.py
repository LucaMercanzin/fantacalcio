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
