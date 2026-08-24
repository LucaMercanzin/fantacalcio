import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import streamlit as st
from dashboard.app import get_db_connection
from dashboard.data_access import find_player_by_name, normalize_team_name, get_squad_suggestions
from db import repository
from ranking.budget import compute_budget_summary

conn = get_db_connection()

st.title("La Mia Rosa")

with st.form("add_player_form"):
    name = st.text_input("Nome giocatore (esatto)")
    price = st.number_input("Prezzo pagato", min_value=1, step=1)
    submitted = st.form_submit_button("Aggiungi alla rosa")

    if submitted:
        player = find_player_by_name(conn, name)
        if not player:
            st.error(f"Giocatore '{name}' non trovato nel database.")
        else:
            repository.add_roster_entry(
                conn, player["id"], float(price), date.today().isoformat()
            )
            st.success(f"{player['canonical_name']} aggiunto alla rosa.")

roster = repository.get_roster(conn)
summary = compute_budget_summary(roster)

st.subheader("Crediti")
col1, col2, col3 = st.columns(3)
col1.metric("Totali", summary["total_credits"])
col2.metric("Spesi", summary["spent"])
col3.metric("Rimanenti", summary["remaining"])

st.subheader("Slot per ruolo")
role_labels = {"P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"}
cols = st.columns(4)
for col, (role, label) in zip(cols, role_labels.items()):
    slot = summary["slots"][role]
    col.metric(label, f"{slot['filled']}/{slot['total']}")

st.subheader("Giocatori acquistati")
if roster:
    st.table([
        {"Nome": r["canonical_name"], "Ruolo": r["role_classic"],
         "Squadra": normalize_team_name(r["team"]),
         "Prezzo": r["price_paid"], "Data": r["date_added"]}
        for r in roster
    ])
else:
    st.write("Nessun giocatore ancora aggiunto.")

st.divider()
st.subheader("Chi comprare adesso")
st.caption(
    "Migliori candidati per ogni ruolo ancora scoperto, non già in rosa e "
    "acquistabili col budget residuo, ordinati per Decision Score (combina "
    "Fantasy Value, Value for Money e Risk). Si aggiorna da solo ad ogni acquisto."
)

squad_data = get_squad_suggestions(conn)
for role, label in role_labels.items():
    slot = squad_data["summary"]["slots"][role]
    candidates = squad_data["suggestions"].get(role, [])
    with st.expander(f"{label} — {slot['filled']}/{slot['total']} coperti", expanded=False):
        if slot["remaining"] <= 0:
            st.caption("Ruolo già al completo.")
        elif not candidates:
            st.caption("Nessun candidato acquistabile col budget residuo trovato.")
        else:
            st.table([
                {
                    "Nome": c["canonical_name"],
                    "Squadra": normalize_team_name(c["team"]),
                    "Quotazione": c["price_current"],
                    "Decision Score": c.get("decision_score", "-"),
                    "Value for Money": c.get("value_for_money", "-"),
                    "Risk": c.get("risk", "-"),
                }
                for c in candidates
            ])
