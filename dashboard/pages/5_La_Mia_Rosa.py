import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pandas as pd
import streamlit as st

from dashboard.common import get_db_connection
from dashboard.components import (
    render_auction_checklist_section,
    render_correlation_section,
    render_decision_center,
)
from dashboard.data_access import (
    find_player_by_name,
    format_count,
    get_auction_price_trend,
    get_ideal_formation,
    get_optimal_squad_lp,
    get_roster_fcp_chart_data,
    get_squad_suggestions,
    normalize_team_name,
)
from config import DEFAULT_FORMATION
from db import repository
from ranking.budget import compute_budget_summary
from ranking.ideal_squad import FORMATIONS, compare_starters_to_lp

conn = get_db_connection()

st.title("La Mia Rosa")

render_decision_center(conn)

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

with st.form("add_opponent_pick_form"):
    st.caption(
        "Registra un giocatore preso da un avversario in asta: verrà escluso "
        "dai suggerimenti di 'Chi comprare adesso' (sez. 84-105 della spec)."
    )
    opp_name = st.text_input("Nome giocatore (esatto)", key="opp_player_name")
    opponent = st.text_input("Preso da (nome avversario)")
    opp_price = st.number_input("Prezzo pagato", min_value=1, step=1, key="opp_price")
    opp_submitted = st.form_submit_button("Segna come preso")

    if opp_submitted:
        player = find_player_by_name(conn, opp_name)
        if not player:
            st.error(f"Giocatore '{opp_name}' non trovato nel database.")
        elif not opponent.strip():
            st.error("Indica il nome dell'avversario.")
        else:
            # Upsert (P1-017/TASK-020): registrarlo di nuovo aggiorna
            # avversario/prezzo invece di fallire — correggere un errore di
            # battitura non richiede più rimuovere e ri-aggiungere.
            repository.add_opponent_pick(
                conn, player["id"], opponent.strip(), float(opp_price),
                date.today().isoformat(),
            )
            st.success(f"{player['canonical_name']} segnato come preso da {opponent}.")

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
    for r in roster:
        rcol1, rcol2 = st.columns([5, 1])
        rcol1.write(
            f"{r['canonical_name']} ({normalize_team_name(r['team'])}, "
            f"{r['role_classic']}) — {r['price_paid']} crediti, {r['date_added']}"
        )
        if rcol2.button("Rimuovi", key=f"remove-roster-{r['player_id']}"):
            repository.remove_roster_entry(conn, r["player_id"])
            st.rerun()
else:
    st.write("Nessun giocatore ancora aggiunto.")

st.divider()
render_correlation_section(conn)

st.divider()
render_auction_checklist_section(conn)

st.subheader("Presi dagli avversari")
opponent_picks = repository.get_opponent_picks(conn)
if opponent_picks:
    for pick in opponent_picks:
        pcol1, pcol2 = st.columns([5, 1])
        pcol1.write(
            f"{pick['canonical_name']} ({normalize_team_name(pick['team'])}, "
            f"{pick['role_classic']}) — {pick['opponent_name']}, {pick['price_paid']} crediti"
        )
        if pcol2.button("Rimuovi", key=f"remove-opp-{pick['player_id']}"):
            repository.remove_opponent_pick(conn, pick["player_id"])
            st.rerun()
else:
    st.caption("Nessun giocatore ancora segnato come preso da un avversario.")

st.divider()
st.subheader("Andamento prezzo medio asta")
st.caption(
    "Prezzo medio pagato finora nell'asta (i tuoi acquisti + quelli segnati "
    "come presi dagli avversari), nell'ordine in cui sono stati registrati: "
    "una lettura di massima dell'inflazione dell'asta, non un dato di mercato ufficiale."
)
trend = get_auction_price_trend(conn)
if len(trend["running"]) < 2:
    st.caption("Servono almeno due acquisti registrati (tuoi o avversari) per un andamento.")
else:
    trend_df = pd.DataFrame(trend["running"]).set_index("Acquisto")
    st.line_chart(trend_df)

st.divider()
st.subheader("Rosa Ideale — Formazione 3-4-3")
st.caption(
    "L'undici titolare ideale in campo: i giocatori già in rosa restano "
    "titolari, gli altri sono i migliori liberi per Fantasy Value. Se un "
    "titolare viene preso da un avversario, sparisce automaticamente e viene "
    "sostituito dal prossimo migliore libero per quel ruolo (il suo 'secondo')."
)

formation_result = get_ideal_formation(conn, DEFAULT_FORMATION)
starters = formation_result["starters"]
bench = formation_result["bench"]
roster_ids = {r["player_id"] for r in roster}

PITCH_ROWS = [
    ("A", [20, 50, 80]),
    ("C", [12, 37, 63, 88]),
    ("D", [20, 50, 80]),
    ("P", [50]),
]
ROW_BOTTOM_PCT = {"A": 80, "C": 56, "D": 32, "P": 8}


def _chip(player: dict) -> str:
    surname = player["canonical_name"].split()[-1]
    owned = player["player_id"] in roster_ids
    badge = "✅" if owned else format_count(player.get("price_current"))
    color = "#1f8a3b" if owned else "#0d3b66"
    return (
        f'<div style="background:{color};color:#fff;border-radius:10px;'
        f'padding:6px 12px;font-size:16px;font-weight:600;text-align:center;'
        f'white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.45);">{surname}<br>'
        f'<span style="font-size:13px;font-weight:400;opacity:.9;">{badge}</span></div>'
    )


chips_html = ""
for role, xs in PITCH_ROWS:
    players = starters.get(role, [])
    bottom = ROW_BOTTOM_PCT[role]
    for i, player in enumerate(players):
        if i >= len(xs):
            break
        left = xs[i]
        chips_html += (
            f'<div style="position:absolute;bottom:{bottom}%;left:{left}%;'
            f'transform:translate(-50%, 50%);">{_chip(player)}</div>'
        )

pitch_html = f"""
<div style="position:relative;width:100%;max-width:900px;margin:0 auto;
            aspect-ratio:16/10;background:#2e7d32;
            border:3px solid #fff;border-radius:12px;
            box-shadow:0 4px 16px rgba(0,0,0,.35);overflow:hidden;">
  <div style="position:absolute;top:50%;left:0;right:0;border-top:2px solid rgba(255,255,255,.5);"></div>
  <div style="position:absolute;top:50%;left:50%;width:120px;height:120px;
              border:2px solid rgba(255,255,255,.5);border-radius:50%;
              transform:translate(-50%,-50%);"></div>
  <div style="position:absolute;bottom:0;left:50%;width:220px;height:70px;
              border:2px solid rgba(255,255,255,.5);border-top:none;
              transform:translateX(-50%);"></div>
  {chips_html}
</div>
"""
st.markdown(pitch_html, unsafe_allow_html=True)
st.caption(
    "✅ = già in rosa, altrimenti quotazione stimata."
)

if any(bench.get(role) for role in bench):
    with st.expander("Panchina (rincalzi per ruolo)", expanded=False):
        for role, label in role_labels.items():
            players = bench.get(role, [])
            if not players:
                continue
            st.markdown(f"**{label}**")
            st.table([
                {
                    "Nome": p["canonical_name"],
                    "Squadra": normalize_team_name(p["team"]),
                    "Quotazione": format_count(p.get("price_current")),
                    "Fantasy Value": format_count(p["score"]),
                    "Fantamedia": format_count(p.get("fantamedia")),
                    "Presenze": p.get("appearances", "-"),
                }
                for p in players
            ])

st.divider()
st.subheader("Rosa Ottimale (LP)")
st.caption(
    "Rosa a 25 (3-8-8-6) che massimizza matematicamente la somma di Fantasy "
    "Value dato il budget — un solver a programmazione lineare, non "
    "un'euristica: garantisce l'ottimo per i vincoli dati, a differenza della "
    "Rosa Ideale sopra."
)
lp_mode_label = st.radio(
    "Modalità", ["Vincolata alla rosa attuale", "Da zero (budget pieno)"],
    horizontal=True, key="lp_mode",
)
lp_mode = "constrained" if lp_mode_label.startswith("Vincolata") else "from_scratch"
lp_result = get_optimal_squad_lp(conn, mode=lp_mode)

if lp_result["status"] == "infeasible":
    st.error(f"Nessuna rosa valida trovata: {lp_result.get('reason') or 'vincoli attuali non soddisfacibili.'}")
else:
    st.caption(
        f"Costo totale: {format_count(lp_result['total_cost'])} crediti — "
        f"Fantasy Value totale: {format_count(lp_result['total_score'])}"
    )
    if lp_result.get("roster_not_in_pool"):
        st.warning(
            "In rosa ma non nelle liste ranked (dati insufficienti — poche "
            "presenze, una sola fonte, squadra non più in Serie A...): "
            f"{len(lp_result['roster_not_in_pool'])} giocatori. Restano "
            "fissi e contano sul budget con il prezzo pagato, ma senza "
            "Fantasy Value/quotazione aggiornati (P1-013/TASK-017)."
        )
    for role, label in role_labels.items():
        players = lp_result["squad"].get(role, [])
        with st.expander(f"{label} ({len(players)})", expanded=False):
            st.table([
                {
                    "Nome": p["canonical_name"],
                    "Squadra": normalize_team_name(p["team"]) or "-",
                    "Quotazione": format_count(p.get("price_current")),
                    "Fantasy Value": format_count(p.get("score")),
                    "In rosa": "✅" if p["player_id"] in roster_ids else "",
                }
                for p in players
            ])

    if lp_result["status"] != "infeasible":
        # Confronto sui soli 11 titolari per entrambi (stessa formazione),
        # con il costo totale accanto — sommare 18 (11+7 panchina) contro i
        # 25 dell'LP faceva vincere il solver per costruzione, non per
        # qualità delle scelte (P1-015/TASK-030).
        comparison = compare_starters_to_lp(starters, lp_result["squad"], FORMATIONS[DEFAULT_FORMATION])
        st.caption(
            "Confronto sui soli 11 titolari (stessa formazione 3-4-3) — "
            "Rosa Ideale (euristica, sopra) vs Rosa Ottimale (LP), col costo "
            "totale accanto: un punteggio più alto non è una scelta migliore "
            "se costa molto di più."
        )
        comparison_df = pd.DataFrame(
            {
                "Fantasy Value (11 titolari)": [comparison["ideal"]["score"], comparison["lp"]["score"]],
                "Costo (11 titolari)": [comparison["ideal"]["cost"], comparison["lp"]["cost"]],
            },
            index=["Rosa Ideale (euristica)", "Rosa Ottimale (LP)"],
        )
        st.bar_chart(comparison_df[["Fantasy Value (11 titolari)"]])
        st.table(comparison_df)

st.divider()
st.subheader("Affidabilità della rosa (Fantacalciopedia)")
st.caption(
    "Solidità fantainvestimento e resistenza infortuni dei tuoi giocatori, "
    "dalle pagine dettaglio di Fantacalciopedia — solo chi ha già questo dato scrappato."
)
roster_fcp_data = get_roster_fcp_chart_data(conn)
if roster_fcp_data:
    fcp_chart_df = pd.DataFrame(roster_fcp_data).set_index("Nome")
    st.bar_chart(fcp_chart_df)
else:
    st.caption("Nessun dato ancora disponibile per i giocatori in rosa.")

st.divider()
st.subheader("Chi comprare adesso")
st.caption(
    "Migliori candidati **realistici**: solo quelli acquistabili col budget "
    "residuo, per i ruoli ancora scoperti, non già in rosa. Ordinati per "
    "Fantasy Value — i più forti su una stagione intera, non i più economici. "
    "Filtra automaticamente le riserve con poche presenze."
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
                    "Quotazione": format_count(c["price_current"]),
                    "Fantasy Value": format_count(c["score"]),
                    "Fantamedia": format_count(c.get("fantamedia")),
                    "Presenze": c.get("appearances", "-"),
                    "Risk": format_count(c.get("risk")),
                }
                for c in candidates
            ])
