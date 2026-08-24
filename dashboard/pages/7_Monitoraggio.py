import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import streamlit as st
from dashboard.app import get_db_connection
from dashboard.data_access import get_monitoring_data, normalize_team_name
from db import repository

conn = get_db_connection()

st.title("Monitoraggio Dati")
st.caption(
    "Stato delle fonti, affidabilità del consensus e giocatori con quotazioni "
    "discordanti tra fonti."
)

data = get_monitoring_data(conn)

st.subheader("Panoramica")
col1, col2, col3 = st.columns(3)
col1.metric("Giocatori nel database", data["total_players"])
col2.metric(
    "Confidence media consensus",
    f"{data['avg_confidence']:.0f}%" if data["avg_confidence"] is not None else "-",
    help="Media della confidence di tutti i giocatori: quanto le fonti sono "
         "d'accordo tra loro sulla quotazione. Bassa non significa errore, spesso "
         "significa solo poche fonti disponibili per quel giocatore.",
)
col3.metric(
    "Giocatori con outlier di prezzo", len(data["outlier_players"]),
    help="Giocatori per cui almeno una fonte si discosta più del 40% dalla "
         "mediana delle altre: quella fonte pesa meno nel consensus finale.",
)

st.divider()
st.subheader("Stato delle fonti")

source_rows = {s["source"]: s for s in data["source_stats"]}
all_sources = sorted(set(data["weights"]) | set(source_rows))

if not all_sources:
    st.caption("Nessuna fonte configurata ancora.")
else:
    header = st.columns([3, 2, 2, 2, 2])
    header[0].markdown("**Fonte**")
    header[1].markdown("**Ultimo aggiornamento**")
    header[2].markdown("**Record**")
    header[3].markdown("**Peso**")
    header[4].markdown("**Salva**")

    for source in all_sources:
        stats = source_rows.get(source, {})
        cols = st.columns([3, 2, 2, 2, 2])
        cols[0].write(source)
        cols[1].write(stats.get("last_update") or "mai")
        cols[2].write(stats.get("record_count", 0))
        new_weight = cols[3].number_input(
            "peso", min_value=0.0, step=0.5,
            value=float(data["weights"].get(source, 1)),
            key=f"weight-{source}", label_visibility="collapsed",
        )
        if cols[4].button("Salva", key=f"save-{source}"):
            repository.set_source_weight(conn, source, new_weight)
            st.success(f"Peso di {source} aggiornato a {new_weight}.")
            st.rerun()

    st.caption(
        "Il peso determina quanto conta questa fonte nella media pesata del "
        "consensus (sezione 7 della spec). Modificalo qui: non è hard-coded nel codice."
    )

st.divider()
st.subheader("Giocatori con quotazione anomala (outlier)")
st.caption(
    "Una fonte il cui prezzo si discosta troppo dalla mediana delle altre "
    "riceve un peso ridotto nel consensus, ma il dato resta visibile qui."
)
if data["outlier_players"]:
    st.table([
        {
            "Nome": p["canonical_name"],
            "Squadra": normalize_team_name(p["team"]),
            "Quotazione consensus": p["price_current"],
            "Fonti outlier": ", ".join(p["price_outlier_sources"]),
            "Confidence": f"{p['confidence']:.0f}%",
        }
        for p in data["outlier_players"]
    ])
else:
    st.caption("Nessun outlier rilevato al momento.")

st.divider()
st.subheader("Match tra fonti da rivedere")
st.caption(
    "Giocatori collegati a una fonte con similarità del nome sotto il 95% "
    "(sezione 5 della spec): probabilmente corretti, ma vale la pena controllare."
)
if data["match_review_queue"]:
    st.table([
        {
            "Giocatore (canonico)": m["canonical_name"],
            "Squadra": normalize_team_name(m["team"]),
            "Fonte": m["source"],
            "Nome nella fonte": m["source_name"],
            "Squadra nella fonte": m["source_team"],
            "Similarità": f"{m['confidence']:.0f}%",
        }
        for m in data["match_review_queue"]
    ])
else:
    st.caption("Nessun match incerto al momento.")

st.divider()
st.subheader("Giocatori con bassa confidence (< 50%)")
st.caption(
    "Confidence bassa di solito significa una sola fonte disponibile o fonti "
    "molto in disaccordo tra loro."
)
if data["low_confidence_players"]:
    st.table([
        {
            "Nome": p["canonical_name"],
            "Squadra": normalize_team_name(p["team"]),
            "Quotazione consensus": p["price_current"],
            "Fonti": p["source"],
            "Confidence": f"{p['confidence']:.0f}%",
        }
        for p in data["low_confidence_players"]
    ])
else:
    st.caption("Nessun giocatore sotto la soglia di confidence.")
