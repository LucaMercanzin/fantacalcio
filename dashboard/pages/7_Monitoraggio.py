import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import streamlit as st
from dashboard.common import get_db_connection
from dashboard.data_access import get_monitoring_data, get_match_review_queue, normalize_team_name
from db import repository


@st.cache_data(ttl=60, show_spinner="Ricalcolo statistiche fonti...")
def _cached_monitoring_data(_conn) -> dict:
    """get_monitoring_data ricalcola il consensus su ~800 giocatori: pesante,
    ma non cambia quando l'utente conferma/rifiuta un match sotto — quella
    parte (get_match_review_queue) resta sempre fuori dalla cache e viene
    letta fresca a ogni rerun, così i pulsanti 🟢🟡🔴 restano istantanei."""
    return get_monitoring_data(_conn)


conn = get_db_connection()

st.title("Monitoraggio Dati")
st.caption(
    "Stato delle fonti, affidabilità del consensus e giocatori con quotazioni "
    "discordanti tra fonti."
)

data = _cached_monitoring_data(conn)

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
st.subheader("Salute delle tabelle dati")
st.caption(
    "Una tabella vuota non è mostrata come assenza di problemi: è mostrata "
    "come pipeline mai eseguita (🔴). 🟡 = ha dati ma non aggiornati di "
    "recente, o senza una colonna data affidabile. 🟢 = popolata e fresca."
)
STATUS_ICONS = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
health_header = st.columns([3, 1, 2, 3])
health_header[0].markdown("**Tabella**")
health_header[1].markdown("**Stato**")
health_header[2].markdown("**Righe / ultimo agg.**")
health_header[3].markdown("**Pipeline**")
for h in data["table_health"]:
    cols = st.columns([3, 1, 2, 3])
    cols[0].write(h["label"])
    cols[1].write(STATUS_ICONS[h["status"]])
    cols[2].write(f"{h['row_count']} / {h['last_update'] or 'mai'}")
    cols[3].code(h["pipeline"], language=None)

st.divider()
st.subheader("Stato delle fonti")

source_rows = {s["source"]: s for s in data["source_stats"]}
all_sources = sorted(set(data["weights"]) | set(source_rows))

if not all_sources:
    st.caption("Nessuna fonte configurata ancora.")
else:
    header = st.columns([3, 2, 2, 2, 2, 2, 2])
    header[0].markdown("**Fonte**")
    header[1].markdown("**Ultimo aggiornamento**")
    header[2].markdown("**Record**")
    header[3].markdown("**Peso crediti**")
    header[4].markdown("**Salva**")
    header[5].markdown("**Peso resto**")
    header[6].markdown("**Salva**")

    for source in all_sources:
        stats = source_rows.get(source, {})
        cols = st.columns([3, 2, 2, 2, 2, 2, 2])
        cols[0].write(source)
        cols[1].write(stats.get("last_update") or "mai")
        cols[2].write(stats.get("record_count", 0))
        new_weight = cols[3].number_input(
            "peso crediti", min_value=0.0, step=0.5,
            value=float(data["weights"].get(source, 1)),
            key=f"weight-{source}", label_visibility="collapsed",
        )
        if cols[4].button("Salva", key=f"save-{source}"):
            repository.set_source_weight(conn, source, new_weight)
            _cached_monitoring_data.clear()
            st.success(f"Peso crediti di {source} aggiornato a {new_weight}.")
            st.rerun()
        new_stats_weight = cols[5].number_input(
            "peso resto", min_value=0.0, step=0.5,
            value=float(data["stats_weights"].get(source, 1)),
            key=f"stats-weight-{source}", label_visibility="collapsed",
        )
        if cols[6].button("Salva", key=f"save-stats-{source}"):
            repository.set_source_stats_weight(conn, source, new_stats_weight)
            _cached_monitoring_data.clear()
            st.success(f"Peso resto di {source} aggiornato a {new_stats_weight}.")
            st.rerun()

    st.caption(
        "**Peso crediti**: quanto conta questa fonte per la quotazione/prezzo "
        "d'asta. **Peso resto**: quanto conta per fantamedia, media voto, "
        "presenze — separati apposta, perché una fonte affidabile sui crediti "
        "reali non è per forza la più affidabile sulle statistiche di voto."
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
STATUS_LABELS = {"confirmed": "🟢 Stessa persona", "unsure": "🟡 Non so", "rejected": "🔴 Non è la stessa persona"}

match_review_queue = get_match_review_queue(conn)

if match_review_queue:
    header = st.columns([2.5, 1.5, 1.5, 2, 2, 1, 1, 1, 2])
    for col, label in zip(header, [
        "Giocatore", "Squadra", "Fonte", "Nome nella fonte", "Squadra nella fonte",
        "🟢", "🟡", "🔴", "Stato",
    ]):
        col.markdown(f"**{label}**")

    for m in match_review_queue:
        cols = st.columns([2.5, 1.5, 1.5, 2, 2, 1, 1, 1, 2])
        cols[0].write(m["canonical_name"])
        cols[1].write(normalize_team_name(m["team"]))
        cols[2].write(m["source"])
        cols[3].write(m["source_name"])
        cols[4].write(m["source_team"])
        if cols[5].button("🟢", key=f"confirm-{m['player_id']}-{m['source']}", help="Stessa persona"):
            repository.set_match_review_status(conn, m["player_id"], m["source"], "confirmed")
            st.rerun()
        if cols[6].button("🟡", key=f"unsure-{m['player_id']}-{m['source']}", help="Non so"):
            repository.set_match_review_status(conn, m["player_id"], m["source"], "unsure")
            st.rerun()
        if cols[7].button("🔴", key=f"reject-{m['player_id']}-{m['source']}", help="Non è la stessa persona"):
            repository.set_match_review_status(conn, m["player_id"], m["source"], "rejected")
            st.rerun()
        cols[8].write(STATUS_LABELS.get(m.get("review_status"), "In attesa"))

    st.caption(
        "🟢 conferma il match. 🟡 segna come incerto (nessun effetto sui dati). "
        "🔴 esclude la quotazione di quella fonte dal consensus di questo "
        "giocatore, perché non è la stessa persona."
    )
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
