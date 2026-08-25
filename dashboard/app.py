import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from db.connection import get_connection, init_db
from dashboard.components import inject_global_css

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fantacalcio.db")


def get_db_connection():
    if "db_conn" not in st.session_state:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        init_db(DB_PATH)
        st.session_state.db_conn = get_connection(DB_PATH)
    inject_global_css()
    return st.session_state.db_conn


st.set_page_config(page_title="Fantacalcio Dashboard", layout="wide")
inject_global_css()
st.title("Fantacalcio Dashboard")
st.write("Seleziona una pagina dal menu a sinistra: Portieri, Difensori, Centrocampisti, Attaccanti, La Mia Rosa.")
