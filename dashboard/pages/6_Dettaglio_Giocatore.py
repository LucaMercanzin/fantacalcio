import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
from dashboard.common import get_db_connection
from dashboard.data_access import get_player_detail
from dashboard.components import render_player_detail

st.title("Scheda giocatore")

player_id = st.session_state.get("detail_player_id")

if not player_id:
    st.info("Nessun giocatore selezionato. Clicca su una figurina in una delle pagine di ruolo per aprire la scheda.")
else:
    conn = get_db_connection()
    row = get_player_detail(conn, player_id)
    if not row:
        st.warning("Giocatore non trovato.")
    else:
        render_player_detail(conn, row)
