import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from dashboard.components import (
    inject_global_css,
    render_sidebar_ideal_squad,
    render_top_budget_bar,
)
from db.connection import get_connection, init_db

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fantacalcio.db")


def get_db_connection():
    if "db_conn" not in st.session_state:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        init_db(DB_PATH)
        st.session_state.db_conn = get_connection(DB_PATH)
    inject_global_css()
    render_top_budget_bar(st.session_state.db_conn)
    render_sidebar_ideal_squad(st.session_state.db_conn)
    return st.session_state.db_conn
