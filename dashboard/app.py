import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

st.set_page_config(page_title="Fantacalcio Dashboard", layout="wide")

pages = [
    st.Page("pages/7_Monitoraggio.py", title="Monitoraggio", icon="📡", default=True),
    st.Page("pages/1_Portieri.py", title="Portieri", icon="🥅"),
    st.Page("pages/2_Difensori.py", title="Difensori", icon="🛡️"),
    st.Page("pages/3_Centrocampisti.py", title="Centrocampisti", icon="⚙️"),
    st.Page("pages/4_Attaccanti.py", title="Attaccanti", icon="⚔️"),
    st.Page("pages/5_La_Mia_Rosa.py", title="La Mia Rosa", icon="⚽"),
    st.Page("pages/6_Dettaglio_Giocatore.py", title="Dettaglio Giocatore", icon="🔍"),
]
st.navigation(pages).run()
