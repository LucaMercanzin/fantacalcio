"""Dettaglio giocatore: rendering della scheda completa (header, metriche,
radar, storico, infortuni, verdetto). Estratto da components.py perché era
la sezione più grande e coesa del monolite (CRITICA_SPIETATA_2026-09-01 #5)."""

import pandas as pd
import streamlit as st

from dashboard import components
from dashboard.data_access import (
    format_count,
    get_injury_summary,
    get_player_season_stats,
    get_price_history_by_date,
    get_recent_form,
    get_set_piece_summary,
    get_team_strength,
)
from dashboard.team_info import get_role_fit, get_team_info
from ranking.tiers import TIER_DESCRIPTIONS, TIER_LABELS
from ranking.verdict import compute_verdict


def _render_role_comparison(row: dict) -> None:
    comparison = row.get("role_comparison")
    if not comparison:
        st.caption("Confronto con il ruolo: dato non ancora raccolto per questo giocatore.")
        return
    st.markdown("**Confronto con il ruolo**")
    for metric in comparison.values():
        st.caption(f"{metric['label']}: {metric['player']} (media ruolo {metric['role_avg']})")
        st.progress(
            min(max(int(metric["percentile"]), 0), 100),
            text=f"{metric['percentile']:.0f}° percentile",
        )


def _render_advanced_stats(row: dict) -> None:
    stats = row.get("advanced_stats")
    if not stats:
        st.caption("Percentili avanzati (xG/xA): dato non ancora raccolto per questo giocatore.")
        return
    st.markdown("**Percentili per-90 (xG/xA, Understat)**")
    labels = {
        "xg90_percentile": "xG/90", "xa90_percentile": "xA/90",
        "shots90_percentile": "Tiri/90", "key_passes90_percentile": "Rifiniture/90",
        "involvement_percentile": "Coinvolgimento", "minutes_percentile": "Minuti",
    }
    for key, label in labels.items():
        value = stats.get(key)
        if value is None:
            continue
        st.progress(min(max(int(value), 0), 100), text=f"{label}: {value}° percentile")


def _render_fantanalisi_valuation(row: dict) -> None:
    valuation = row.get("fantanalisi_valuation")
    if not valuation:
        return
    parts = []
    if valuation.get("fair_price_range"):
        parts.append(f"Fasce affare {valuation['fair_price_range']}")
    if valuation.get("max_bid"):
        parts.append(f"Max {valuation['max_bid']}")
    if valuation.get("tier"):
        parts.append(f"Tier {valuation['tier']}")
    if valuation.get("risk"):
        parts.append(f"Risk {valuation['risk']}")
    if not parts:
        return
    st.caption("Valutazioni Fantanalisi: " + " · ".join(parts))
    st.caption(
        "Valutazioni proprietarie del sito terzo, informative: non incidono "
        "su Fantasy Value/Player Quality/Tier di questo progetto."
    )


def _render_profile_radar(row: dict) -> None:
    """Radar/esagono sintetico del giocatore (Player Quality, Fantasy Value,
    Value for Money, Safety=100-Risk, ALG FCP), normalizzati 0-100 e disegnati
    come SVG inline — nessuna libreria di plotting aggiuntiva necessaria."""
    import math

    def _clip(value, default=0.0):
        if value is None:
            return default
        return max(0.0, min(100.0, float(value)))

    axes = {
        "Player Quality": _clip(row.get("player_quality")),
        "Fantasy Value": _clip(row.get("score")),
        "Value for Money": _clip(row.get("value_for_money")),
        "Safety": _clip(100 - row["risk"] if row.get("risk") is not None else None),
        "ALG FCP": _clip(row.get("alg_fcp")),
    }
    if not any(axes.values()):
        return

    center, max_radius = 110, 85
    n = len(axes)
    angle_step = 2 * math.pi / n
    start_angle = -math.pi / 2

    def _point(i, radius):
        angle = start_angle + i * angle_step
        return center + radius * math.cos(angle), center + radius * math.sin(angle)

    grid_polygons = ""
    for frac in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (_point(i, max_radius * frac) for i in range(n)))
        grid_polygons += f'<polygon points="{pts}" fill="none" stroke="#e5e5ea" stroke-width="1"/>'

    axis_lines = ""
    labels = ""
    for i in range(n):
        x, y = _point(i, max_radius)
        axis_lines += f'<line x1="{center}" y1="{center}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e5e5ea" stroke-width="1"/>'
        lx, ly = _point(i, max_radius + 18)
        anchor = "middle"
        if lx < center - 5:
            anchor = "end"
        elif lx > center + 5:
            anchor = "start"
        labels += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" fill="#1d1d1f" '
            f'text-anchor="{anchor}" dominant-baseline="middle">{list(axes)[i]}</text>'
        )

    values_pts = " ".join(
        f"{x:.1f},{y:.1f}" for x, y in (_point(i, max_radius * v / 100) for i, v in enumerate(axes.values()))
    )

    svg = f"""
    <svg viewBox="0 0 220 220" width="280" height="280" style="overflow: visible;">
        {grid_polygons}
        {axis_lines}
        <polygon points="{values_pts}" fill="rgba(0,113,227,0.25)" stroke="#0071e3" stroke-width="2"/>
        {labels}
    </svg>
    """
    st.markdown("**Profilo sintetico**")
    st.markdown(f'<div style="padding: 0 70px 0 70px;">{svg}</div>', unsafe_allow_html=True)


def _render_verdict(row: dict, set_pieces: list) -> None:
    verdict = compute_verdict(row, set_pieces)
    if verdict["stars"] is None:
        stars = "—"  # not "☆☆☆☆☆": that would read as "0 stars", a verdict, not an absence of one
    else:
        stars = "★" * verdict["stars"] + "☆" * (5 - verdict["stars"])
    st.markdown(f"**Verdetto**  \n{stars}  \n{verdict['headline']}")
    st.markdown("**Punti forti**\n" + "\n".join(f"- {s}" for s in verdict["strengths"]))
    st.markdown("**Rischi**\n" + "\n".join(f"- {r}" for r in verdict["risks"]))


def render_player_detail(conn, row: dict) -> None:
    photo_uri = components._photo_data_uri(row.get("photo_path"))
    header_col1, header_col2 = st.columns([1, 3])
    with header_col1:
        if photo_uri:
            st.image(photo_uri, width=180)
        else:
            color = components.PLACEHOLDER_COLORS.get(row["role_classic"], "#999999")
            st.markdown(
                f"<div style='width:180px;height:180px;border-radius:12px;background:{color};"
                f"display:flex;align-items:center;justify-content:center;color:white;"
                f"font-size:64px;font-weight:bold;'>{row['canonical_name'][0]}</div>",
                unsafe_allow_html=True,
            )
    with header_col2:
        title = row["canonical_name"]
        if row.get("is_promoted"):
            title += " *"
        if row.get("is_in_roster"):
            title += " ⭐"
        st.subheader(title)
        role_label = components.ROLE_LABELS.get(row.get("role_classic"), row.get("role_classic", "-"))
        mantra = row.get("role_mantra")
        role_caption = f"{role_label}" + (f" ({mantra})" if mantra else "")
        st.caption(f"{role_caption} · {row.get('team', '-')}")
        fixture = components.get_fixture_difficulty(conn, row.get("team"))
        if fixture and fixture.get("difficulty_attack") is not None:
            st.caption(
                f"Calendario prime 5 giornate: {fixture['difficulty_attack']}/100 "
                "(più alto = più morbido)"
            )
        if row.get("rank_in_role"):
            st.caption(
                f"#{row['rank_in_role']} su {row['role_total']} nel ruolo {role_label}"
            )
        if row.get("is_in_roster"):
            st.success("In rosa")
        elif row.get("taken_by"):
            st.warning(f"🔒 Preso da {row['taken_by']}")

        tier = row.get("tier")
        if tier:
            st.caption(f"{TIER_LABELS[tier]} — {TIER_DESCRIPTIONS[tier]}")

    st.divider()

    info_cols = st.columns(4)
    info_cols[0].metric(
        "Rating", f"{row['score']:.1f}" if row.get("score") is not None else "-",
        help=components.METRIC_HELP["rating"],
    )
    price_current = row.get("price_current")
    price_initial = row.get("price_initial")
    delta = None
    if price_current is not None and price_initial is not None:
        delta = round(price_current - price_initial, 2)
    # DA6/TASK-029: a price from real auction credits and one converted
    # from the listino (no real-auction source for this player) must not
    # look identical — the difference is real, now that P0-001 separated
    # the two scales, and hiding it invites overpaying on a guess.
    price_is_estimated = row.get("price_basis") == "listino_converted"
    info_cols[1].metric(
        "Quotazione ~" if price_is_estimated else "Quotazione",
        price_current if price_current is not None else "-",
        delta=delta if delta else None,
        help=components.METRIC_HELP["quotazione_stimata"] if price_is_estimated else components.METRIC_HELP["quotazione"],
    )
    info_cols[2].metric(
        "Quot. iniziale", price_initial if price_initial is not None else "-",
        help=components.METRIC_HELP["quot_iniziale"],
    )
    info_cols[3].metric("Fantamedia", row.get("fantamedia", "-"), help=components.METRIC_HELP["fantamedia"])

    info_cols2 = st.columns(4)
    info_cols2[0].metric("Media voto", row.get("avg_rating", "-"), help=components.METRIC_HELP["media_voto"])
    appearances_discordi = row.get("appearances_disagreement")
    info_cols2[1].metric(
        "Presenze ⚠️" if appearances_discordi else "Presenze",
        row.get("appearances", "-"),
        help=components.METRIC_HELP["presenze_discordi"] if appearances_discordi else components.METRIC_HELP["presenze"],
    )
    status = row.get("status")
    info_cols2[2].metric(
        "Stato", status if status and status != "ok" else "Regolare",
        help=components.METRIC_HELP["stato"],
    )
    info_cols2[3].metric("Fonti dati", row.get("source", "-"), help=components.METRIC_HELP["fonti_dati"])

    tactical_score = row.get("tactical_profile_score")
    if tactical_score is not None:
        info_cols3 = st.columns(4)
        info_cols3[0].metric(
            "Profilo tattico", f"{tactical_score:.0f}/100",
            help="Quanto il ruolo REALE del giocatore (giocatori/movimento.md) "
                 "vale al fantacalcio, non solo il ruolo ufficiale — quinti/terzini "
                 "offensivi, trequartisti, seconde punte segnano alto; mediani, "
                 "centrali puri, registi bassi segnano basso.",
        )

    st.caption(
        "Player Quality misura la forza calcistica del giocatore; Fantasy Value quanto "
        "rende al fantacalcio; Value for Money il rendimento per credito speso; Risk "
        "l'affidabilità. Sono quattro cose diverse: un buon giocatore non è per forza "
        "un buon acquisto. Passa il mouse su ciascuna per i dettagli."
    )
    score_cols = st.columns(4)
    score_cols[0].metric(
        "Player Quality", f"{row['player_quality']:.0f}" if row.get("player_quality") is not None else "-",
        help=components.METRIC_HELP["player_quality"],
    )
    fantasy_value_is_estimated = row.get("estimated") is True
    score_cols[1].metric(
        "Fantasy Value ~" if fantasy_value_is_estimated else "Fantasy Value",
        f"{row['score']:.1f}" if row.get("score") is not None else "-",
        help=components.METRIC_HELP["fantasy_value_stimato"] if fantasy_value_is_estimated else components.METRIC_HELP["fantasy_value"],
    )
    vfm = row.get("value_for_money")
    score_cols[2].metric(
        "Value for Money", f"{vfm:.1f}" if vfm is not None else "-",
        help=components.METRIC_HELP["value_for_money"],
    )
    semaforo = components._value_for_money_semaforo(row.get("value_for_money_percentile"))
    if semaforo:
        st.caption(semaforo)
    score_cols[3].metric(
        "Risk", f"{row['risk']:.0f}" if row.get("risk") is not None else "-",
        help=components.METRIC_HELP["risk"],
    )

    _render_profile_radar(row)

    price_agreement = row.get("price_agreement")
    if price_agreement is not None:
        st.caption(
            f"Confidence quotazione (accordo tra le fonti): {price_agreement:.0f}% — "
            f"{components.METRIC_HELP['price_agreement']}"
        )
    if row.get("price_outlier_sources"):
        outliers = ", ".join(row["price_outlier_sources"])
        st.caption(f"⚠️ Quotazione anomala segnalata da: {outliers} (peso ridotto nel calcolo)")

    alg_fcp = row.get("alg_fcp")
    punteggio_fcp = row.get("punteggio_fcp")
    fcp_skills = row.get("fcp_skills")
    if alg_fcp is not None or punteggio_fcp is not None or fcp_skills:
        parts = []
        if alg_fcp is not None:
            parts.append(f"ALG FCP: {alg_fcp:.0f}/100")
        if punteggio_fcp is not None:
            parts.append(f"Punteggio FCP: {punteggio_fcp:.0f}/100")
        if fcp_skills:
            parts.append(" · ".join(fcp_skills))
        st.caption(" — ".join(parts))
        st.caption(
            "Segnali da Fantacalciopedia (algoritmo, punteggio e tag skill), "
            "informativi: non incidono su Fantasy Value/Player Quality."
        )

    _render_role_comparison(row)
    _render_advanced_stats(row)
    _render_fantanalisi_valuation(row)

    set_pieces = get_set_piece_summary(conn, row["player_id"])
    if set_pieces:
        rank_icon = {"Principale": "🟢", "Secondario": "🟡"}
        badges = " · ".join(
            f"{rank_icon.get(sp['label'], '⚪')} {sp['category']}: {sp['label']}"
            for sp in set_pieces
        )
        st.markdown(badges)
        st.caption(
            "Gerarchia calci piazzati da fantacalcio.it/rigoristi-serie-a. "
            "🟢 Principale, 🟡 Secondario, ⚪ Riserva."
        )
    else:
        st.caption("Gerarchia calci piazzati: dato non ancora raccolto per questo giocatore.")

    if row.get("notes"):
        st.markdown(f"**Note:** {row['notes']}")

    extra = components.get_player_extra(conn, row["player_id"])
    if extra.get("transfermarkt_id"):
        st.markdown(
            f"[Profilo Transfermarkt](https://www.transfermarkt.com/-/profil/spieler/{extra['transfermarkt_id']})"
        )

    anagrafica = extra.get("anagrafica")
    if anagrafica:
        parts = []
        if anagrafica.get("birth_date"):
            from datetime import date as _date
            born = _date.fromisoformat(anagrafica["birth_date"])
            age = (_date.today() - born).days // 365
            parts.append(f"{age} anni")
        if anagrafica.get("height_cm"):
            parts.append(f"{anagrafica['height_cm']} cm")
        if anagrafica.get("foot"):
            parts.append(f"piede {anagrafica['foot']}")
        if anagrafica.get("nationality"):
            parts.append(anagrafica["nationality"])
        if anagrafica.get("shirt_number"):
            parts.append(f"#{anagrafica['shirt_number']}")
        if parts:
            st.caption(" · ".join(parts))

    st.divider()
    st.markdown("**Squadra**")
    team_info = get_team_info(row.get("team"))
    if team_info:
        tcol1, tcol2 = st.columns(2)
        tcol1.markdown(f"**Città:** {team_info['citta']}")
        tcol1.markdown(f"**Stadio:** {team_info['stadio']}")
        rivali_text = ', '.join(team_info['rivali']) if team_info['rivali'] else "Nessuno di rilievo"
        tcol2.markdown(f"**Rivali storici:** {rivali_text}")
        tcol2.markdown(f"**Stile di gioco:** {team_info['stile']}")
        st.caption("Informazioni generali sul club, non legate alla stagione in corso.")

        role_fit = get_role_fit(row.get("team"), row.get("role_classic"), row.get("role_mantra"))
        if role_fit:
            st.markdown(f"**Il suo compito:** {role_fit['compito']}")
            fit_cols = st.columns(2)
            if role_fit["pro"]:
                fit_cols[0].markdown(
                    "**Pro per lui:**\n" + "\n".join(f"- {p}" for p in role_fit["pro"])
                )
            if role_fit["contro"]:
                fit_cols[1].markdown(
                    "**Contro per lui:**\n" + "\n".join(f"- {c}" for c in role_fit["contro"])
                )
            st.caption(
                "Valutazione generale basata sullo stile della squadra, non una previsione statistica."
            )
    else:
        st.caption("Nessuna informazione aggiuntiva disponibile su questa squadra.")

    team_strength = get_team_strength(conn, row.get("team"))
    if team_strength and team_strength.get("xg") is not None:
        st.markdown("**Forza squadra (Understat)**")
        scol1, scol2, scol3 = st.columns(3)
        scol1.metric("xG a partita", format_count(team_strength["xg"]))
        scol2.metric("xGA a partita", format_count(team_strength["xga"]))
        scol3.metric("PPDA", format_count(team_strength.get("ppda")))
        st.caption(
            "Gol attesi fatti/concessi a partita e intensità del pressing "
            "(PPDA, più basso = pressing più alto) — dati Understat via "
            "fantanalisi.it, non entrano nel calcolo del Fantasy Value."
        )

    st.divider()
    st.markdown("**Forma recente**")
    form = get_recent_form(conn, row["player_id"])
    if not form["ratings"]:
        st.caption(
            "Nessuna giornata disputata ancora registrata: la forma recente si "
            "popola man mano che vengono giocate le partite."
        )
    else:
        st.metric(
            f"Fantavoto medio (ultime {len(form['ratings'])} giornate)",
            form["avg_fantavoto"] if form["avg_fantavoto"] is not None else "-",
            help="Media del fantavoto (Redazione Fantacalcio) sulle giornate più "
                 "recenti disputate, separata dalla fantamedia stagionale.",
        )
        st.table([
            {"Giornata": r["giornata"], "Stagione": r["season"],
             "Voto": format_count(r["voto"]), "Fantavoto": format_count(r["fantavoto"])}
            for r in form["ratings"]
        ])

    st.divider()
    st.markdown("**Andamento quotazione**")
    history_by_date = get_price_history_by_date(conn, row["player_id"])
    if len(history_by_date) < 2:
        st.caption(
            "Storico non ancora sufficiente: servono più giorni di aggiornamenti "
            "per mostrare un grafico dell'andamento."
        )
    else:
        history_df = pd.DataFrame.from_dict(history_by_date, orient="index").sort_index()
        components.static_line_chart(history_df, index_label="Data")

    st.divider()
    st.markdown("**Storico stagioni**")
    st.caption(
        "Presenze/gol/assist/media voto reali per stagione (Fantacalciopedia) — "
        "gol subiti al posto di gol fatti per i portieri."
    )
    season_stats = get_player_season_stats(conn, row["player_id"])
    if not season_stats:
        st.caption("Nessuno storico stagionale disponibile per questo giocatore.")
    else:
        is_goalkeeper = row.get("role_classic") == "P"
        goals_label = "Gol subiti" if is_goalkeeper else "Gol fatti"
        chart_df = pd.DataFrame([
            {
                "Stagione": s["season"],
                goals_label: s["goals_conceded"] if is_goalkeeper else s["goals_scored"],
                "Assist": s["assists"],
            }
            for s in reversed(season_stats)  # oldest first, so the chart reads left-to-right chronologically
        ]).set_index("Stagione")
        components.static_bar_chart(chart_df, index_label="Stagione")
        st.table([
            {
                "Stagione": s["season"],
                "Presenze": format_count(s["appearances"]),
                goals_label: format_count(s["goals_conceded"] if is_goalkeeper else s["goals_scored"]),
                "Assist": format_count(s["assists"]),
                "Media voto": format_count(s["avg_rating"]),
                "Ammonizioni": format_count(s["yellow_cards"]),
                "Espulsioni": format_count(s["red_cards"]),
            }
            for s in season_stats
        ])

    st.divider()
    st.markdown("**Storico infortuni**")

    summary = get_injury_summary(conn, row["player_id"])
    injuries = summary["injuries"]

    if not injuries:
        st.caption("Nessuno storico infortuni disponibile per questo giocatore.")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Giorni totali fermo (storico)", format_count(summary["total_days_out"]))
        col2.metric("Partite saltate (storico)", format_count(summary["total_matches_missed"]))

        st.table([
            {
                "Stagione": i["season"],
                "Infortunio": i["injury_type"],
                "Dal": i["date_from"],
                "Al": i["date_to"],
                "Giorni": format_count(i["days_out"]),
                "Partite saltate": format_count(i["matches_missed"]),
            }
            for i in injuries
        ])

    _render_verdict(row, set_pieces)

    components.render_purchase_evaluator(conn, row)
