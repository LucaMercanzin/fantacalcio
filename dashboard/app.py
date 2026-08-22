import os
import streamlit as st
from db.connection import get_connection, init_db

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fantacalcio.db")


def get_db_connection():
    if "db_conn" not in st.session_state:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        init_db(DB_PATH)
        st.session_state.db_conn = get_connection(DB_PATH)
    return st.session_state.db_conn


st.set_page_config(page_title="Fantacalcio Dashboard", layout="wide")
st.title("Fantacalcio Dashboard")
st.write("Seleziona una pagina dal menu a sinistra: Portieri, Difensori, Centrocampisti, Attaccanti, La Mia Rosa.")
