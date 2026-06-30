# app.py — Dashboard principal World Cup 2026 Predictor v2
# Ejecutar con: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import json, sys, os

sys.path.insert(0, os.path.dirname(__file__))

from data.database import (
    get_all_matches, get_played_matches, save_match_result, clear_match_result,
    save_analyst_note, get_analyst_note, get_all_analyst_notes,
    save_prediction, get_latest_prediction, save_value_bet,
    get_value_bets_history,
    init_ko_matches, get_ko_matches, update_ko_teams,
    save_ko_result, clear_ko_result, get_ko_winner, clean_ko_duplicates,
    save_match_stats, get_match_stats, get_all_match_stats,
)
from data.tournament_data import GROUPS, FLAGS, ALL_TEAMS, GROUP_LETTERS, HOST_TEAMS, R32_BRACKET_VALID, THIRD_PLACE_SLOTS
from models.prediction_engine import (
    run_monte_carlo, match_probabilities_dc, over_under_probs,
    exact_score_probs, detect_value_bets, compute_dynamic_ratings,
)
from models.odds_api import (
    get_live_odds, get_best_odds, get_remaining_requests, api_configured,
)
from models.espn_integration import (
    api_football_configured, get_full_match_data, get_world_cup_fixtures,
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

# ── AUTO-MIGRACIÓN: crea tablas nuevas si no existen ─────────────────────────
import sqlite3 as _sqlite3
_DB_PATH = os.path.join(os.path.dirname(__file__), "worldcup2026.db")
if os.path.exists(_DB_PATH):
    _conn = _sqlite3.connect(_DB_PATH)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS match_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER UNIQUE REFERENCES matches(id),
            home_shots INTEGER, away_shots INTEGER,
            home_shots_on INTEGER, away_shots_on INTEGER,
            home_possession REAL, away_possession REAL,
            home_passes INTEGER, away_passes INTEGER,
            home_pass_acc REAL, away_pass_acc REAL,
            home_fouls INTEGER, away_fouls INTEGER,
            home_yellows INTEGER, away_yellows INTEGER,
            home_reds INTEGER, away_reds INTEGER,
            home_offsides INTEGER, away_offsides INTEGER,
            home_corners INTEGER, away_corners INTEGER,
            home_xg REAL, away_xg REAL,
            home_formation TEXT, away_formation TEXT,
            home_lineup TEXT DEFAULT '[]',
            away_lineup TEXT DEFAULT '[]',
            home_key_absences TEXT DEFAULT '[]',
            away_key_absences TEXT DEFAULT '[]',
            extra_notes TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_stats_match ON match_stats(match_id)")
    _conn.commit()
    _conn.close()

st.set_page_config(
    page_title="World Cup 2026 — Predictor",
    page_icon="⚽", layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ─── PALETA MUNDIAL 2026: verde césped, dorado trofeo, azul cielo ─── */
.stApp {
    background: linear-gradient(180deg, #0d3d24 0%, #0f4a2c 35%, #11532f 100%);
}
h1,h2,h3,h4 { color: #ffd84d !important; }
.stTabs [data-baseweb="tab"] { color: #cfe8d8; font-weight:600; font-size:13px; }
.stTabs [aria-selected="true"] { color:#ffd84d !important; border-bottom:3px solid #ffd84d; }
.stTabs [data-baseweb="tab-list"] { background-color: rgba(0,0,0,0.18); border-radius:10px; padding:4px; }
div[data-testid="stMetricValue"] { color:#ffd84d; font-size:1.6rem; font-weight:700; }
div[data-testid="stMetricLabel"] { color:#cfe8d8 !important; }
.stButton>button {
    background: linear-gradient(135deg, #ffd84d, #f5b800);
    color:#0d3d24; font-weight:800; border:none; border-radius:8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
.stButton>button:hover { background: linear-gradient(135deg, #fff0a8, #ffd84d); }
.block-container { padding-top:0.8rem; }
.stDataFrame { border:1px solid #1c6b3f; border-radius:8px; }
.stExpander { background-color: rgba(255,255,255,0.04); border:1px solid #1c6b3f; border-radius:10px; }
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #08291a 0%, #0a3320 100%);
    border-right: 2px solid #1c6b3f;
}
.stCaption, .stMarkdown p, .stMarkdown li { color: #e3f3e8; }
.stRadio label, .stSelectbox label, .stSlider label, .stNumberInput label { color: #cfe8d8 !important; }
div[data-baseweb="select"] { background-color: rgba(255,255,255,0.06); }
.stAlert { border-radius:10px; }
hr { border-color: #1c6b3f !important; }
/* Inputs numéricos con acento azul cielo, como balón sobre césped */
input[type="number"] {
    background-color: #ffffff !important;
    color: #0d3d24 !important;
    font-weight:700 !important;
    border: 2px solid #3aa6ff !important;
    border-radius: 6px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────

if "predictions" not in st.session_state:
    # Intentar cargar última predicción de la DB
    latest = get_latest_prediction()
    st.session_state.predictions = latest["results_json"] if latest else None

# Las predicciones anteriores no fijaban los resultados KO ya jugados.
# Se descartan para evitar mostrar como candidato a un equipo eliminado.
if (
    st.session_state.predictions
    and st.session_state.predictions.get("model_version") != "ko-aware-v1"
):
    st.session_state.predictions = None

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def flag(t):   return FLAGS.get(t, "🏳️")
def fp(t):     return f"{flag(t)} {t}"

def color_prob(p):
    if p >= 65: return "🟢"
    if p >= 35: return "🟡"
    if p >= 10: return "🔵"
    return "🔴"

# ─── CAPA DE CACHÉ ────────────────────────────────────────────────────────────
if "data_version" not in st.session_state:
    st.session_state.data_version = 0

def bump_data_version():
    st.session_state.data_version += 1

@st.cache_data(show_spinner=False)
def cached_all_matches(version):
    return get_all_matches()

@st.cache_data(show_spinner=False)
def cached_played_matches(version):
    return get_played_matches()

@st.cache_data(show_spinner=False)
def cached_all_analyst_notes(version):
    return get_all_analyst_notes()

@st.cache_data(show_spinner=False)
def cached_all_match_stats(version):
    return get_all_match_stats()

@st.cache_data(show_spinner=False)
def cached_group_table(g, version):
    matches = cached_all_matches(version)
    teams = GROUPS[g]
    tbl   = {t: {"PJ":0,"G":0,"E":0,"P":0,"GF":0,"GC":0,"DG":0,"Pts":0} for t in teams}
    for m in matches:
        if m["group_letter"] != g or not m["played"]: continue
        h,a   = m["home_goals"], m["away_goals"]
        ht,at = m["home_team"], m["away_team"]
        tbl[ht]["PJ"]+=1; tbl[at]["PJ"]+=1
        tbl[ht]["GF"]+=h;  tbl[ht]["GC"]+=a
        tbl[at]["GF"]+=a;  tbl[at]["GC"]+=h
        tbl[ht]["DG"] = tbl[ht]["GF"]-tbl[ht]["GC"]
        tbl[at]["DG"] = tbl[at]["GF"]-tbl[at]["GC"]
        if h>a:   tbl[ht]["G"]+=1; tbl[ht]["Pts"]+=3; tbl[at]["P"]+=1
        elif h<a: tbl[at]["G"]+=1; tbl[at]["Pts"]+=3; tbl[ht]["P"]+=1
        else:     tbl[ht]["E"]+=1; tbl[ht]["Pts"]+=1; tbl[at]["E"]+=1; tbl[at]["Pts"]+=1
    rows = [{"team": t, **tbl[t]} for t in teams]
    return sorted(rows, key=lambda x:(x["Pts"],x["DG"],x["GF"]), reverse=True)

def get_group_table(g, matches=None):
    rows = cached_group_table(g, st.session_state.data_version)
    return [{"Equipo": fp(r["team"]), **{k:v for k,v in r.items() if k!="team"}} for r in rows]

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚽ World Cup 2026")
    st.markdown("*Predictor · Value Bets · Monte Carlo*")
    st.divider()

    st.markdown("### 🔐 Acceso")
    admin_password = st.text_input("Clave admin", type="password")
    try:
        expected_password = st.secrets.get("ADMIN_PASSWORD", "")
    except Exception:
        expected_password = ""

    IS_ADMIN = bool(expected_password) and admin_password == expected_password

    if IS_ADMIN:
        st.success("Modo administrador activo")
    else:
        st.info("Modo público")

    st.divider()

    all_matches = cached_all_matches(st.session_state.data_version)
    played      = [m for m in all_matches if m["played"]]
    total_matches = len(all_matches)

    st.metric("Partidos jugados", f"{len(played)} / {total_matches}")
    st.metric("Partidos restantes", f"{total_matches - len(played)}")

    st.divider()

    n_sims = st.select_slider(
        "Simulaciones",
        options=[1_000, 5_000, 10_000, 25_000],
        value=10_000,
        help="Más simulaciones = más preciso pero más lento"
    )

    if st.button("▶ SIMULAR AHORA", use_container_width=True):
        analyst_notes = get_all_analyst_notes()
        with st.spinner(f"Ejecutando {n_sims:,} simulaciones..."):
            all_stats = get_all_match_stats()
            preds = run_monte_carlo(all_matches, analyst_notes, all_stats, n_sims)
            st.session_state.predictions = preds
            save_prediction(len(played), n_sims, preds)
        st.success("✅ Completado")
        st.rerun()

    st.divider()
    st.markdown("### 🏆 Top 5 favoritos")
    preds = st.session_state.predictions
    if preds:
        for i,d in enumerate(preds["champion_probs"][:5]):
            st.markdown(f"`{i+1}.` {fp(d['team'])} — **{d['prob']}%**")
    else:
        st.caption("Ejecutá la simulación primero")

    if IS_ADMIN:
        st.divider()
        with st.expander("🛠️ Mantenimiento"):
            st.caption("Si ves partidos duplicados en eliminatorias, presioná:")
            if st.button("🧹 Limpiar duplicados KO", use_container_width=True):
                deleted = clean_ko_duplicates()
                if deleted > 0:
                    st.success(f"✅ {deleted} duplicado(s) eliminado(s)")
                else:
                    st.info("No había duplicados")
                st.rerun()


# ─── TÍTULO ──────────────────────────────────────────────────────────────────

st.markdown("# ⚽ WORLD CUP 2026 — PREDICTOR v2")
col_a, col_b, col_c = st.columns(3)
col_a.metric("Partidos jugados",   len(played))
col_b.metric("Equipos",           48)
col_c.metric("Simulaciones",      f"{n_sims:,}")
st.divider()

# ─── TABS ────────────────────────────────────────────────────────────────────

if IS_ADMIN:
    tabs = st.tabs([
        "📊 Grupos",
        "🏟️ Eliminatorias",
        "🎯 Clasificados",
        "🗺️ Bracket",
        "📝 Analista",
        "💰 Value Bets",
    ])
    tab_grupos, tab_elim, tab_pred, tab_bracket, tab_analista, tab_value = tabs
else:
    tabs = st.tabs([
        "🎯 Clasificados",
        "🗺️ Bracket",
        "💰 Value Bets",
    ])
    tab_pred, tab_bracket, tab_value = tabs
    tab_grupos = None
    tab_elim = None
    tab_analista = None

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — GRUPOS
# ══════════════════════════════════════════════════════════════════════════════

if IS_ADMIN:
    with tab_grupos:
        st.markdown("### Cargá los resultados de cada partido")
        st.caption(
            "Con 1 solo partido jugado por equipo el modelo ya actualiza las probabilidades. "
            "Cuantos más resultados, más preciso."
        )
        preds = st.session_state.predictions
        all_matches = cached_all_matches(st.session_state.data_version)

        for row_i in range(0, 12, 3):
            cols = st.columns(3)
            for ci, g in enumerate(GROUP_LETTERS[row_i:row_i+3]):
                with cols[ci]:
                    host_badge = " 🏠" if any(t in HOST_TEAMS for t in GROUPS[g]) else ""
                    st.markdown(f"#### Grupo {g}{host_badge}")

                    table = get_group_table(g, all_matches)
                    df    = pd.DataFrame(table)

                    def style_row(row):
                        idx = df.index.get_loc(row.name)
                        if idx == 0: return ["background-color:#0a3d24;color:#ffd84d"]*len(row)
                        if idx == 1: return ["background-color:#0a1a30;color:#7ab0e8"]*len(row)
                        if idx == 2: return ["background-color:#0a1a0a;color:#7ab07a"]*len(row)
                        return [""]*len(row)

                    st.dataframe(df.style.apply(style_row, axis=1),
                                hide_index=True, use_container_width=True, height=155)

                    if preds:
                        gp = preds["group_probs"].get(g, [])
                        st.caption("**% de clasificar (simulado):**")
                        for d in gp:
                            c = "🟢" if d["qualify"]>=60 else "🟡" if d["qualify"]>=30 else "🔴"
                            bt = f"*(1°:{d['first']}% 2°:{d['second']}% T3:{d['best_third']}%)*"
                            st.markdown(f"{c} {fp(d['team'])} — **{d['qualify']}%** {bt}")

                    gmatches = [m for m in all_matches if m["group_letter"]==g]
                    played_count = sum(1 for m in gmatches if m["played"])
                    with st.expander(f"Partidos Grupo {g} ({played_count}/6 jugados)"):
                        match_options = {
                            f"{'✅' if mm['played'] else '⬜'} {mm['home_team']} vs {mm['away_team']}"
                            + (f" ({mm['home_goals']}-{mm['away_goals']})" if mm["played"] else ""): mm["id"]
                            for mm in gmatches
                        }
                        sel_label = st.selectbox(
                            "Elegí el partido a cargar/editar",
                            list(match_options.keys()),
                            key=f"sel_match_{g}"
                        )
                        selected_id = match_options[sel_label]
                        m = next(mm for mm in gmatches if mm["id"] == selected_id)

                        with st.form(key=f"form_match_{g}_{selected_id}", border=False):
                            st.markdown(f"**{fp(m['home_team'])} vs {fp(m['away_team'])}**")
                            c1, c2 = st.columns(2)
                            with c1:
                                st.caption(f"{flag(m['home_team'])} {m['home_team'][:3].upper()}")
                                hg = st.number_input("Local",
                                        min_value=0, max_value=20,
                                        value=int(m["home_goals"]) if m["played"] else 0,
                                        key=f"hg_{selected_id}", label_visibility="collapsed")
                            with c2:
                                st.caption(f"{flag(m['away_team'])} {m['away_team'][:3].upper()}")
                                ag = st.number_input("Visitante",
                                        min_value=0, max_value=20,
                                        value=int(m["away_goals"]) if m["played"] else 0,
                                        key=f"ag_{selected_id}", label_visibility="collapsed")

                            bcol1, bcol2 = st.columns(2)
                            with bcol1:
                                submitted = st.form_submit_button("💾 Guardar este partido", use_container_width=True)
                            with bcol2:
                                deleted = st.form_submit_button("🗑️ Borrar resultado", use_container_width=True)

                            if submitted:
                                save_match_result(m["id"], hg, ag)
                                bump_data_version()
                                st.success(f"✅ {m['home_team']} {hg}-{ag} {m['away_team']} guardado")
                                st.rerun()
                            if deleted:
                                clear_match_result(m["id"])
                                bump_data_version()
                                st.warning(f"🗑️ Resultado de {m['home_team']} vs {m['away_team']} borrado. Volvé a simular para actualizar.")
                                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB ELIMINATORIAS
# ══════════════════════════════════════════════════════════════════════════════
if IS_ADMIN:
    with tab_elim:
        st.markdown("### 🏟️ Fases Eliminatorias")
        st.caption(
            "Los cruces se arman automáticamente con los clasificados reales. "
            "Cargá los goles de cada partido y la siguiente ronda se actualiza sola."
        )

        init_ko_matches()

        all_m = cached_all_matches(st.session_state.data_version)
        preds = st.session_state.predictions

        def get_real_standings(g, matches):
            teams = GROUPS[g]
            tbl   = {t: {"pts":0,"gf":0,"ga":0,"gd":0} for t in teams}
            for m in matches:
                if m["group_letter"] != g or not m["played"]: continue
                h,a   = m["home_goals"], m["away_goals"]
                ht,at = m["home_team"], m["away_team"]
                tbl[ht]["gf"]+=h; tbl[ht]["ga"]+=a
                tbl[at]["gf"]+=a; tbl[at]["ga"]+=h
                tbl[ht]["gd"] = tbl[ht]["gf"]-tbl[ht]["ga"]
                tbl[at]["gd"] = tbl[at]["gf"]-tbl[at]["ga"]
                if h>a:   tbl[ht]["pts"]+=3
                elif h<a: tbl[at]["pts"]+=3
                else:     tbl[ht]["pts"]+=1; tbl[at]["pts"]+=1
            return sorted(teams, key=lambda t:(tbl[t]["pts"],tbl[t]["gd"],tbl[t]["gf"]), reverse=True)

        real_qualifiers = {}
        thirds_list = []
        for g in GROUP_LETTERS:
            ranked = get_real_standings(g, all_m)
            gmatches = [m for m in all_m if m["group_letter"]==g and m["played"]]
            group_complete = len(gmatches) == 6

            if group_complete:
                real_qualifiers[f"1{g}"] = {"team": ranked[0], "confirmed": True}
                real_qualifiers[f"2{g}"] = {"team": ranked[1], "confirmed": True}
            elif preds:
                q = preds["predicted_qualifiers"].get(g, {})
                real_qualifiers[f"1{g}"] = {"team": q.get("first",{}).get("team","?"), "confirmed": False, "predicted": True}
                real_qualifiers[f"2{g}"] = {"team": q.get("second",{}).get("team","?"), "confirmed": False, "predicted": True}
            elif len(gmatches) > 0:
                real_qualifiers[f"1{g}"] = {"team": ranked[0], "confirmed": False, "predicted": False}
                real_qualifiers[f"2{g}"] = {"team": ranked[1], "confirmed": False, "predicted": False}
            else:
                real_qualifiers[f"1{g}"] = {"team": f"1° Grupo {g}", "confirmed": False, "predicted": False}
                real_qualifiers[f"2{g}"] = {"team": f"2° Grupo {g}", "confirmed": False, "predicted": False}

            if group_complete:
                group_matches_g = [m for m in all_m if m["group_letter"]==g and m["played"]]
                tbl2 = {t: {"pts":0,"gf":0,"ga":0,"gd":0} for t in GROUPS[g]}
                for m in group_matches_g:
                    h,a=m["home_goals"],m["away_goals"]
                    ht,at=m["home_team"],m["away_team"]
                    tbl2[ht]["gf"]+=h; tbl2[ht]["ga"]+=a
                    tbl2[at]["gf"]+=a; tbl2[at]["ga"]+=h
                    tbl2[ht]["gd"]=tbl2[ht]["gf"]-tbl2[ht]["ga"]
                    tbl2[at]["gd"]=tbl2[at]["gf"]-tbl2[at]["ga"]
                    if h>a: tbl2[ht]["pts"]+=3
                    elif h<a: tbl2[at]["pts"]+=3
                    else: tbl2[ht]["pts"]+=1; tbl2[at]["pts"]+=1
                thirds_list.append({"team":ranked[2],"group":g,"pts":tbl2[ranked[2]]["pts"],
                                    "gd":tbl2[ranked[2]]["gd"],"gf":tbl2[ranked[2]]["gf"]})
            elif preds:
                gp = preds["group_probs"].get(g, [])
                if gp:
                    # Para completar grupos no terminados usamos la probabilidad de
                    # entrar como MEJOR TERCERO, no la probabilidad total de clasificar.
                    # Antes se elegía el 3.er equipo por "qualify", lo que podía poner
                    # un segundo probable en un slot de tercero y desordenar los VS.
                    third_pred = max(gp, key=lambda r: r.get("best_third", 0))
                    thirds_list.append({
                        "team": third_pred["team"], "group": g,
                        "pts": 0, "gd": 0, "gf": 0,
                        "predicted_prob": third_pred.get("best_third", 0),
                    })

        real_thirds      = [t for t in thirds_list if "predicted_prob" not in t]
        predicted_thirds = [t for t in thirds_list if "predicted_prob" in t]
        real_thirds.sort(key=lambda x:(x["pts"],x["gd"],x["gf"]), reverse=True)
        predicted_thirds.sort(key=lambda x: x["predicted_prob"], reverse=True)
        thirds_list = real_thirds + predicted_thirds

        qualified_thirds = thirds_list[:8]
        assigned_groups = set()
        for slot_name, candidate_groups in THIRD_PLACE_SLOTS.items():
            for t in qualified_thirds:
                if t["group"] in candidate_groups and t["group"] not in assigned_groups:
                    all_candidates_done = all(
                        sum(1 for m in all_m if m["group_letter"]==cg and m["played"]) == 6
                        for cg in candidate_groups
                    )
                    real_qualifiers[slot_name] = {
                        "team": t["team"],
                        "confirmed": all_candidates_done,
                        "predicted": "predicted_prob" in t,
                    }
                    assigned_groups.add(t["group"])
                    break

        def resolve(slot):
            d = real_qualifiers.get(slot, {})
            t = d.get("team", slot)
            confirmed = d.get("confirmed", False)
            predicted = d.get("predicted", False)
            badge = "✅" if confirmed else ("🔮" if predicted else "❓")
            return t, badge

        # ── Función para renderizar una fase KO ──────────────────────────────────
        def render_ko_phase(phase_key, phase_name, n_matches, bracket_pairs=None,
                            prev_phase=None, prev_n=None):
            st.markdown(f"---")
            st.markdown(f"#### {phase_name}")

            ko_matches = get_ko_matches(phase_key)
            if not ko_matches:
                init_ko_matches()
                ko_matches = get_ko_matches(phase_key)

            for i, pair in enumerate(bracket_pairs or []):
                m = ko_matches[i] if i < len(ko_matches) else None
                if m is None: continue

                if phase_key == "r32" and bracket_pairs:
                    slot_a, slot_b = pair
                    ta, _ = resolve(slot_a)
                    tb, _ = resolve(slot_b)
                elif prev_phase:
                    ta = get_ko_winner(prev_phase, i*2+1) or ""
                    tb = get_ko_winner(prev_phase, i*2+2) or ""
                else:
                    ta, tb = m["home_team"], m["away_team"]

                if ta and tb and (m["home_team"] != ta or m["away_team"] != tb):
                    update_ko_teams(phase_key, i+1, ta, tb)

            ko_matches = get_ko_matches(phase_key)

            cols = st.columns(2)
            for i, m in enumerate(ko_matches):
                home_t = m["home_team"] or "Por definir"
                away_t = m["away_team"] or "Por definir"
                played  = m["played"]
                hg = m["home_goals"] if played else 0
                ag = m["away_goals"] if played else 0

                winner = None
                if played and m["home_goals"] is not None:
                    winner = home_t if m["home_goals"] > m["away_goals"] else away_t

                with cols[i % 2]:
                    label = f"{'✅' if played else '⬜'} Partido {i+1}"
                    if winner:
                        label += f" — 🏆 {winner}"

                    with st.expander(
                        f"{label}: {fp(home_t) if home_t != 'Por definir' else home_t} "
                        f"vs {fp(away_t) if away_t != 'Por definir' else away_t}"
                        + (f" ({hg}-{ag})" if played else ""),
                        expanded=not played and home_t != "Por definir"
                    ):
                        if home_t == "Por definir" or away_t == "Por definir":
                            st.caption("⏳ Esperando resultados de la ronda anterior")
                        else:
                            with st.form(key=f"form_{phase_key}_{i+1}", border=False):
                                c1, c2, c3 = st.columns([3,2,3])
                                with c1:
                                    st.markdown(f"**{fp(home_t)}**")
                                    st.caption(f"🏠 Local — {home_t}")
                                with c2:
                                    st.caption(f"Goles {home_t.split()[0] if home_t else ''}")
                                    new_hg = st.number_input(f"Goles {home_t}", min_value=0, max_value=20,
                                        value=int(hg), key=f"{phase_key}_hg_{i+1}",
                                        label_visibility="collapsed")
                                    st.caption(f"Goles {away_t.split()[0] if away_t else ''}")
                                    new_ag = st.number_input(f"Goles {away_t}", min_value=0, max_value=20,
                                        value=int(ag), key=f"{phase_key}_ag_{i+1}",
                                        label_visibility="collapsed")
                                with c3:
                                    st.markdown(f"**{fp(away_t)}**")
                                    st.caption(f"✈️ Visitante — {away_t}")

                                if new_hg == new_ag:
                                    st.caption("⚠️ Empate no válido en KO — el ganador se define por penales. Poné el marcador final incluyendo el resultado de penales si es necesario.")

                                bcol1, bcol2 = st.columns(2)
                                with bcol1:
                                    submitted = st.form_submit_button("💾 Guardar", use_container_width=True)
                                with bcol2:
                                    deleted = st.form_submit_button("🗑️ Borrar", use_container_width=True)

                                if submitted:
                                    save_ko_result(phase_key, i+1, new_hg, new_ag)
                                    bump_data_version()
                                    st.success(f"✅ {home_t} {new_hg}-{new_ag} {away_t}")
                                    st.rerun()
                                if deleted:
                                    clear_ko_result(phase_key, i+1)
                                    bump_data_version()
                                    st.warning(f"🗑️ Resultado de {home_t} vs {away_t} borrado. Volvé a simular para actualizar.")
                                    st.rerun()

                        if preds and home_t not in ["Por definir",""] and away_t not in ["Por definir",""]:
                            ph_t = preds["phase_probs"].get(home_t,{}).get("champion",0)
                            pa_t = preds["phase_probs"].get(away_t,{}).get("champion",0)
                            total = ph_t + pa_t
                            if total > 0:
                                prob_h = ph_t/total*100
                                prob_a = pa_t/total*100
                                st.caption(f"Modelo: {fp(home_t)} **{prob_h:.0f}%** vs {fp(away_t)} **{prob_a:.0f}%** *(basado en prob. de campeón)*")

        # ── RENDERIZAR TODAS LAS FASES ────────────────────────────────────────────
        # ─── UN SOLO BOTÓN SEGURO ARRIBA DE LAS ELIMINATORIAS ──────────────────
        if st.button("🔄 Sincronizar Nuevos Cruces Lógicos", use_container_width=True, key="sync_final_btn"):
            with st.spinner("Reorganizando las llaves en la base de datos..."):
                
                # 1. Limpiamos la base de datos con tus funciones seguras
                for phase_name, total_matches in [("r32", 16), ("r16", 8), ("qf", 4), ("sf", 2), ("final", 1)]:
                    for match_idx in range(1, total_matches + 1):
                        clear_ko_result(phase_name, match_idx)
                
                # 2. Volvemos a inicializar los partidos limpios
                init_ko_matches()
                bump_data_version()
                
                # 3. ¡EL TRUCO! Borramos el estado de la pantalla en Streamlit 
                # para obligarlo a leer los nuevos 'vs' desde cero
                keys_to_clear = [k for k in st.session_state.keys() if "r32" in k or "ko_" in k]
                for key in keys_to_clear:
                    del st.session_state[key]
                
                st.success("¡Estructura de llaves corregida con éxito! Tus grupos siguen guardados.")
                st.rerun()
        # ───────────────────────────────────────────────────────────────────────

        render_ko_phase("r32",  "RONDA DE 32 — Dieciseisavos de Final", 16,
                        bracket_pairs=R32_BRACKET_VALID)

        render_ko_phase("r16",  "RONDA DE 16 — Octavos de Final",  8,
                        prev_phase="r32", prev_n=16)

        render_ko_phase("qf",   "CUARTOS DE FINAL",              4,
                        prev_phase="r16", prev_n=8)

        render_ko_phase("sf",   "SEMIFINALES",                   2,
                        prev_phase="qf", prev_n=4)

        render_ko_phase("final","GRAN FINAL — 19 Jul · MetLife", 1,
                        prev_phase="sf", prev_n=2)

        # ── CAMPEÓN ──────────────────────────────────────────────────────────────
        champ = get_ko_winner("final", 1)
        if champ:
            st.divider()
            st.markdown(f"""
    <div style="text-align:center;padding:32px;background:linear-gradient(135deg,#0f4a2c,#11532f);
    border:1px solid #ffd84d44;border-radius:14px;margin-top:16px;">
    <div style="font-size:14px;letter-spacing:4px;color:#ffd84d;margin-bottom:8px;">
    🏆 CAMPEÓN DEL MUNDO 2026</div>
    <div style="font-size:60px;">{flag(champ)}</div>
    <div style="font-family:sans-serif;font-size:42px;font-weight:900;color:#fff;letter-spacing:2px;">
    {champ.upper()}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CLASIFICADOS
# ══════════════════════════════════════════════════════════════════════════════

with tab_pred:
    preds = st.session_state.predictions
    if not preds:
        st.info("Ejecutá la simulación para ver probabilidades completas.")
    else:
        meta_parts = []
        matches_played = preds.get("matches_played")
        simulations = preds.get("simulations")
        if matches_played is not None:
            meta_parts.append(f"{matches_played} partidos jugados")
        if simulations is not None:
            meta_parts.append(f"{simulations:,} simulaciones")
        ko_matches_played = preds.get("ko_matches_played")
        if ko_matches_played is not None:
            meta_parts.append(f"{ko_matches_played} eliminatorias fijadas")
        if meta_parts:
            st.caption(" · ".join(meta_parts))

        group_probs = preds.get("group_probs") or {}
        predicted_qualifiers = preds.get("predicted_qualifiers") or {}

        st.markdown("### 🎯 Clasificados más probables por grupo")
        cols = st.columns(4)
        for i, g in enumerate(GROUP_LETTERS):
            rows = group_probs.get(g) or []
            q = predicted_qualifiers.get(g) or {}

            first = q.get("first") or max(
                rows, key=lambda row: row.get("first", 0), default={}
            )
            second = q.get("second") or max(
                rows, key=lambda row: row.get("second", 0), default={}
            )

            with cols[i % 4]:
                host = "🏠" if any(t in HOST_TEAMS for t in GROUPS[g]) else ""
                st.markdown(f"**Grupo {g}** {host}")

                if first.get("team"):
                    first_prob = first.get("qualify", first.get("first", 0))
                    st.markdown(f"🥇 {fp(first['team'])} `{first_prob}%`")
                if second.get("team"):
                    second_prob = second.get("qualify", second.get("second", 0))
                    st.markdown(f"🥈 {fp(second['team'])} `{second_prob}%`")
                if not first.get("team") and not second.get("team"):
                    st.caption("Sin proyección disponible")
                st.divider()

        if group_probs:
            st.markdown("### 📊 Probabilidades de clasificación por grupo")
            group_rows = []
            group_metrics = [
                ("first", "1.º (%)"),
                ("second", "2.º (%)"),
                ("best_third", "Mejor 3.º (%)"),
                ("qualify", "Clasifica (%)"),
            ]
            available_group_metrics = [
                (key, label)
                for key, label in group_metrics
                if any(
                    isinstance(row, dict) and row.get(key) is not None
                    for rows in group_probs.values()
                    for row in (rows or [])
                )
            ]

            for g in GROUP_LETTERS:
                for row in group_probs.get(g) or []:
                    if not isinstance(row, dict) or not row.get("team"):
                        continue
                    display_row = {
                        "Grupo": g,
                        "Equipo": fp(row["team"]),
                    }
                    for key, label in available_group_metrics:
                        display_row[label] = row.get(key)
                    group_rows.append(display_row)

            if group_rows:
                st.dataframe(
                    pd.DataFrame(group_rows),
                    hide_index=True,
                    use_container_width=True,
                )

            third_candidates = []
            for g in GROUP_LETTERS:
                rows = [
                    row for row in (group_probs.get(g) or [])
                    if isinstance(row, dict) and row.get("team")
                ]
                if not rows:
                    continue
                candidate = max(rows, key=lambda row: row.get("best_third", 0) or 0)
                third_prob = candidate.get("best_third")
                if third_prob is not None and third_prob > 0:
                    third_candidates.append({
                        "Grupo": g,
                        "Equipo": fp(candidate["team"]),
                        "Mejor 3.º (%)": third_prob,
                        "Clasifica (%)": candidate.get("qualify"),
                    })

            if third_candidates:
                third_candidates.sort(
                    key=lambda row: row.get("Mejor 3.º (%)", 0),
                    reverse=True,
                )
                third_slots = len(THIRD_PLACE_SLOTS)
                st.markdown("### 🥉 Mejores terceros proyectados")
                st.caption(
                    "Ordenados por la probabilidad existente de clasificar como mejor tercero."
                )
                st.dataframe(
                    pd.DataFrame(third_candidates[:third_slots]),
                    hide_index=True,
                    use_container_width=True,
                )

        phase_probs = preds.get("phase_probs") or {}
        phase_metrics = [
            ("r32", "R32 / Dieciseisavos (%)"),
            ("r16", "Octavos (%)"),
            ("qf", "Cuartos (%)"),
            ("sf", "Semifinales (%)"),
            ("final", "Final (%)"),
            ("champion", "Campeón (%)"),
        ]
        available_phase_metrics = [
            (key, label)
            for key, label in phase_metrics
            if any(
                isinstance(metrics, dict) and metrics.get(key) is not None
                for metrics in phase_probs.values()
            )
        ]

        st.markdown("### 🏟️ Probabilidades de avance por fase")
        if available_phase_metrics:
            team_groups = {
                team: group
                for group, teams in GROUPS.items()
                for team in teams
            }
            phase_rows = []
            for team, metrics in phase_probs.items():
                if not isinstance(metrics, dict):
                    continue
                display_row = {
                    "Equipo": fp(team),
                    "Grupo": team_groups.get(team, "—"),
                }
                for key, label in available_phase_metrics:
                    display_row[label] = metrics.get(key)
                phase_rows.append(display_row)

            deepest_label = available_phase_metrics[-1][1]
            phase_rows.sort(
                key=lambda row: (
                    row.get(deepest_label) is not None,
                    row.get(deepest_label) or 0,
                ),
                reverse=True,
            )
            st.dataframe(
                pd.DataFrame(phase_rows),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info(
                "El modelo actual solo está guardando probabilidades de "
                "clasificación de grupos. Para mostrar campeón, final y "
                "semifinales hay que extender la salida del motor de simulación."
            )

        champion_probs = [
            row for row in (preds.get("champion_probs") or [])
            if isinstance(row, dict)
            and row.get("team")
            and row.get("prob") is not None
        ]
        if champion_probs:
            st.markdown("### 🏆 Probabilidad de ser campeón")
            df_champ = pd.DataFrame(champion_probs[:15])
            df_champ["Equipo"] = df_champ["team"].apply(fp)

            fig = px.bar(
                df_champ.head(12),
                x="Equipo",
                y="prob",
                color="prob",
                color_continuous_scale=[
                    [0, "#0a3320"],
                    [0.5, "#3aa6ff"],
                    [1, "#ffd84d"],
                ],
                template="plotly_dark",
                labels={"prob": "Probabilidad (%)"},
                title="Top 12 — Probabilidad de ganar el Mundial 2026",
            )
            fig.update_layout(
                plot_bgcolor="#0d3d24",
                paper_bgcolor="#0d3d24",
                font_color="#e3f3e8",
                coloraxis_showscale=False,
                xaxis_tickangle=-35,
                title_font_color="#ffd84d",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                df_champ[["Equipo", "prob"]].rename(
                    columns={"prob": "Prob (%)"}
                ),
                hide_index=True,
                use_container_width=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — BRACKET
# ══════════════════════════════════════════════════════════════════════════════

with tab_bracket:
    preds = st.session_state.predictions
    if not preds:
        st.info("Ejecutá la simulación primero.")
    else:
        st.markdown("### 🗺️ Bracket proyectado — Clasificados más probables")
        st.caption("Basado en el clasificado con mayor probabilidad de cada slot")

        q = preds["predicted_qualifiers"]
        
        st.markdown("#### Dieciseisavos de Final — Cruces proyectados")

        def resolve_predicted_thirds(preds):
            group_probs = preds.get("group_probs", {})
            assigned = set()
            resolved = {}
            for slot_name, candidate_groups in THIRD_PLACE_SLOTS.items():
                best_team, best_prob, best_group = None, -1, None
                for cg in candidate_groups:
                    if cg in assigned:
                        continue
                    rows = group_probs.get(cg, [])
                    if len(rows) < 3:
                        continue
                    # El candidato correcto para un slot 3-XXXXX es el equipo
                    # con mayor probabilidad de clasificar como MEJOR TERCERO.
                    # No se debe usar "qualify", porque mezcla 1°, 2° y 3°.
                    third = max(rows, key=lambda r: r.get("best_third", 0))
                    prob = third.get("best_third", 0)
                    if prob > best_prob:
                        best_prob, best_team, best_group = prob, third["team"], cg
                if best_team:
                    resolved[slot_name] = best_team
                    assigned.add(best_group)
            return resolved

        predicted_thirds = resolve_predicted_thirds(preds)

        def resolve_slot(slot, q):
            if slot.startswith("1") and len(slot) == 2:
                g = slot[1]
                return q.get(g,{}).get("first",{}).get("team","?")
            elif slot.startswith("2") and len(slot) == 2:
                g = slot[1]
                return q.get(g,{}).get("second",{}).get("team","?")
            elif slot.startswith("3-"):
                return predicted_thirds.get(slot, "Mejor 3°")
            else:
                return "?"

        cols = st.columns(2)
        for i, (sa, sb) in enumerate(R32_BRACKET_VALID):
            ta = resolve_slot(sa, q)
            tb = resolve_slot(sb, q)
            ph = preds["phase_probs"]
            prob_a = ph.get(ta,{}).get("champion",0) if ta not in ("?","Mejor 3°") else 0
            prob_b = ph.get(tb,{}).get("champion",0) if tb not in ("?","Mejor 3°") else 0
            fav    = ta if prob_a >= prob_b else tb

            with cols[i%2]:
                st.markdown(
                    f"**Partido {i+1}** `{sa} vs {sb}`\n\n"
                    f"{fp(ta) if ta!='?' else ta} vs {fp(tb) if tb!='?' else tb} "
                    f"— Favorito: **{fp(fav) if fav!='?' else '?'}**"
                )

        st.divider()
        st.markdown("#### Camino proyectado por selección")
        selected = st.selectbox(
            "Seleccioná un equipo",
            sorted(ALL_TEAMS, key=lambda t: preds["phase_probs"][t]["champion"], reverse=True)
        )
        if selected:
            ph = preds["phase_probs"][selected]
            gp = next(
                (v for g,teams in GROUPS.items() if selected in teams
                 for v in [preds["group_probs"][g]] ),
                None
            )
            team_gp = next((d for d in (gp or []) if d["team"]==selected), {})

            st.markdown(f"### {fp(selected)} — Probabilidades de avance")
            r1,r2,r3 = st.columns(3)
            r1.metric("Clasificar del grupo", f"{team_gp.get('qualify',0)}%")
            r2.metric("Llegar a R16",         f"{ph['r16']}%")
            r3.metric("Llegar a Cuartos",     f"{ph['qf']}%")
            r4,r5,r6 = st.columns(3)
            r4.metric("Llegar a Semis",       f"{ph['sf']}%")
            r5.metric("Llegar a la Final",    f"{ph['final']}%")
            r6.metric("🏆 Ser campeón",       f"{ph['champion']}%")

            fig_team = go.Figure(go.Bar(
                x=["Grupos","R32","R16","Cuartos","Semis","Final","Campeón"],
                y=[team_gp.get("qualify",0), ph["r32"], ph["r16"],
                   ph["qf"], ph["sf"], ph["final"], ph["champion"]],
                marker_color=["#3aa6ff","#3aa6ff","#6aab4e","#6aab4e",
                              "#ffd84d","#ffd84d","#fff0a8"],
                text=[f"{v}%" for v in [
                    team_gp.get("qualify",0), ph["r32"], ph["r16"],
                    ph["qf"], ph["sf"], ph["final"], ph["champion"]
                ]],
                textposition="outside",
            ))
            fig_team.update_layout(
                plot_bgcolor="#0d3d24", paper_bgcolor="#0d3d24",
                font_color="#e3f3e8", yaxis_range=[0,105],
                title=f"Camino proyectado — {selected}",
                title_font_color="#ffd84d",
            )
            st.plotly_chart(fig_team, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — ANALISTA
# ══════════════════════════════════════════════════════════════════════════════

def render_match_stats_card(m, phase_lbl):
    ex = get_match_stats(m["id"])
    has_stats = ex is not None

    with st.expander(
        f"{'📊' if has_stats else '📋'} "
        f"{fp(m['home_team'])} **{m['home_goals']}-{m['away_goals']}** "
        f"{fp(m['away_team'])} · {phase_lbl}"
        + (" ✅" if has_stats else ""),
        expanded=False
    ):
        api_prefix = f"api_{m['id']}"
        if st.button("📡 Traer datos de ESPN", key=f"apifetch_{m['id']}"):
            with st.spinner("Consultando ESPN..."):
                data, msg = get_full_match_data(m["home_team"], m["away_team"])
            if data:
                st.session_state[f"{api_prefix}_data"] = data
                st.success(msg)
                st.rerun()
            else:
                st.info(msg)

        api_data = st.session_state.get(f"{api_prefix}_data", {})

        def sv(field, default=0):
            if field in api_data and api_data[field] is not None:
                return api_data[field]
            if ex and ex.get(field) is not None:
                return ex[field]
            return default

        st.markdown(
            f"#### {fp(m['home_team'])} {m['home_goals']} — "
            f"{m['away_goals']} {fp(m['away_team'])}"
        )
        st.divider()

        st.markdown("**🗒️ Formación**")
        fc1, fc2 = st.columns(2)
        with fc1:
            h_formation = st.text_input(
                f"Formación {m['home_team']}",
                value=sv("home_formation",""),
                placeholder="ej: 4-3-3",
                key=f"hform_{m['id']}"
            )
        with fc2:
            a_formation = st.text_input(
                f"Formación {m['away_team']}",
                value=sv("away_formation",""),
                placeholder="ej: 4-4-2",
                key=f"aform_{m['id']}"
            )

        st.divider()
        st.markdown("**📊 Estadísticas del partido**")

        h1, h2, h3 = st.columns([2,3,2])
        h1.markdown(f"**{flag(m['home_team'])} {m['home_team']}**")
        h2.markdown("<div style='text-align:center;color:#6b7a8d'>Métrica</div>", unsafe_allow_html=True)
        h3.markdown(f"**{flag(m['away_team'])} {m['away_team']}**")

        def stat_row(label, key_h, key_a, dh=0, da=0,
                     mn=0, mx=100, is_float=False, step=1):
            c1, c2, c3 = st.columns([2,3,2])
            kw = dict(min_value=float(mn) if is_float else mn,
                      max_value=float(mx) if is_float else mx,
                      step=float(step) if is_float else step,
                      label_visibility="collapsed")
            with c1:
                vh = st.number_input(f"{label} local",
                    value=float(sv(key_h,dh)) if is_float else int(sv(key_h,dh)),
                    key=f"{key_h}_{m['id']}", **kw)
            with c2:
                st.markdown(
                    f"<div style='text-align:center;padding-top:8px;"
                    f"color:#9aa3b0;font-size:13px'>{label}</div>",
                    unsafe_allow_html=True)
            with c3:
                va = st.number_input(f"{label} visit.",
                    value=float(sv(key_a,da)) if is_float else int(sv(key_a,da)),
                    key=f"{key_a}_{m['id']}", **kw)
            return vh, va

        h_shots,    a_shots    = stat_row("Remates totales",    "home_shots",      "away_shots",      0,  0,  0, 50)
        h_shots_on, a_shots_on = stat_row("Remates al arco",    "home_shots_on",   "away_shots_on",   0,  0,  0, 30)
        h_pos,      a_pos      = stat_row("Posesión (%)",        "home_possession", "away_possession", 50, 50, 0,100, True, 0.5)
        h_passes,   a_passes   = stat_row("Pases",               "home_passes",     "away_passes",     0,  0,  0,1000)
        h_pacc,     a_pacc     = stat_row("Precisión pases (%)","home_pass_acc",   "away_pass_acc",   75, 75, 0,100, True, 0.5)
        h_fouls,    a_fouls    = stat_row("Faltas",               "home_fouls",      "away_fouls",      0,  0,  0, 50)
        h_yellows,  a_yellows  = stat_row("Amarillas",           "home_yellows",    "away_yellows",    0,  0,  0, 10)
        h_reds,     a_reds     = stat_row("Rojas",               "home_reds",       "away_reds",       0,  0,  0,  5)
        h_off,      a_off      = stat_row("Fuera de juego",      "home_offsides",   "away_offsides",   0,  0,  0, 20)
        h_corn,     a_corn     = stat_row("Córners",             "home_corners",    "away_corners",    0,  0,  0, 20)

        st.divider()
        st.markdown("**⚽ Goles esperados (xG)**")

        auto_h = round(h_shots_on * 0.10, 2)
        auto_a = round(a_shots_on * 0.10, 2)

        xc1, xc2, xc3 = st.columns([2,3,2])
        with xc1:
            h_xg = st.number_input(
                f"xG {m['home_team']}", min_value=0.0, max_value=10.0,
                value=float(sv("home_xg", auto_h)), step=0.01,
                key=f"hxg_{m['id']}", label_visibility="collapsed"
            )
        with xc2:
            st.markdown(
                f"<div style='text-align:center;padding-top:6px;"
                f"color:#9aa3b0;font-size:12px'>"
                f"xG estimado desde remates: "
                f"<b style='color:#ffd84d'>{auto_h}</b> — "
                f"<b style='color:#ffd84d'>{auto_a}</b>"
                f"</div>",
                unsafe_allow_html=True
            )
        with xc3:
            a_xg = st.number_input(
                f"xG {m['away_team']}", min_value=0.0, max_value=10.0,
                value=float(sv("away_xg", auto_a)), step=0.01,
                key=f"axg_{m['id']}", label_visibility="collapsed"
            )

        if h_xg > 0 or a_xg > 0:
            hg_r, ag_r = m["home_goals"], m["away_goals"]
            ia1, ia2 = st.columns(2)
            with ia1:
                dh = hg_r - h_xg
                col = "#6aab4e" if dh >= 0 else "#e05c5c"
                st.markdown(
                    f"{flag(m['home_team'])} xG **{h_xg:.2f}** → Goles **{hg_r}** "
                    f"<span style='color:{col}'>({'+' if dh>=0 else ''}{dh:.2f})</span>",
                    unsafe_allow_html=True)
            with ia2:
                da = ag_r - a_xg
                col = "#6aab4e" if da >= 0 else "#e05c5c"
                st.markdown(
                    f"{flag(m['away_team'])} xG **{a_xg:.2f}** → Goles **{ag_r}** "
                    f"<span style='color:{col}'>({'+' if da>=0 else ''}{da:.2f})</span>",
                    unsafe_allow_html=True)

            if h_xg > a_xg and hg_r < ag_r:
                st.warning(
                    f"⚠️ {m['home_team']} generó más xG pero perdió — "
                    f"posible valor apostando a este equipo en el próximo partido.")
            elif a_xg > h_xg and ag_r < hg_r:
                st.warning(
                    f"⚠️ {m['away_team']} generó más xG pero perdió — "
                    f"posible valor apostando a este equipo en el próximo partido.")

        st.divider()

        from models.prediction_engine import compute_performance_score
        preview = {
            "home_shots": h_shots, "away_shots": a_shots,
            "home_shots_on": h_shots_on, "away_shots_on": a_shots_on,
            "home_possession": h_pos, "away_possession": a_pos,
            "home_pass_acc": h_pacc, "away_pass_acc": a_pacc,
            "home_corners": h_corn, "away_corners": a_corn,
            "home_yellows": h_yellows, "away_yellows": a_yellows,
            "home_reds": h_reds, "away_reds": a_reds,
            "home_xg": h_xg, "away_xg": a_xg,
        }
        ps_h, ps_a = compute_performance_score(preview, m["home_goals"], m["away_goals"])

        if ps_h is not None:
            st.markdown("**🔬 Performance Score** *(impacto en el modelo)*")
            pc1, pc2 = st.columns(2)
            with pc1:
                col = "#6aab4e" if ps_h > ps_a else "#e05c5c"
                st.markdown(
                    f"{flag(m['home_team'])} **{m['home_team']}** "
                    f"<span style='color:{col};font-size:20px;font-weight:700'>"
                    f"{ps_h:.3f}</span>",
                    unsafe_allow_html=True)
            with pc2:
                col = "#6aab4e" if ps_a > ps_h else "#e05c5c"
                st.markdown(
                    f"{flag(m['away_team'])} **{m['away_team']}** "
                    f"<span style='color:{col};font-size:20px;font-weight:700'>"
                    f"{ps_a:.3f}</span>",
                    unsafe_allow_html=True)
            st.caption(
                "Score > 0.5 = buen rendimiento · "
                "Score alto con derrota = equipo subestimado por el mercado"
            )

        st.divider()
        if st.button(
            "💾 Guardar estadísticas",
            key=f"save_stats_{m['id']}",
            use_container_width=True
        ):
            save_match_stats(m["id"], {
                "home_shots": h_shots,       "away_shots": a_shots,
                "home_shots_on": h_shots_on, "away_shots_on": a_shots_on,
                "home_possession": h_pos,    "away_possession": a_pos,
                "home_passes": h_passes,     "away_passes": a_passes,
                "home_pass_acc": h_pacc,     "away_pass_acc": a_pacc,
                "home_fouls": h_fouls,       "away_fouls": a_fouls,
                "home_yellows": h_yellows,   "away_yellows": a_yellows,
                "home_reds": h_reds,         "away_reds": a_reds,
                "home_offsides": h_off,      "away_offsides": a_off,
                "home_corners": h_corn,      "away_corners": a_corn,
                "home_xg": h_xg,             "away_xg": a_xg,
                "home_formation": h_formation,
                "away_formation": a_formation,
                "home_lineup": [],
                "away_lineup": [],
                "home_key_absences": [],
                "away_key_absences": [],
                "extra_notes": "",
            })
            bump_data_version()
            st.success(
                "✅ Estadísticas guardadas. "
                "Presioná **SIMULAR AHORA** para actualizar las predicciones."
            )
            st.rerun()


if IS_ADMIN:
    with tab_analista:
        st.markdown("### 📝 Estadísticas de Partidos")
        st.caption(
            "Completá las estadísticas de cada partido jugado. "
            "Cada fase tiene su propia sub-pestaña para no mezclar partidos."
        )

        group_played = cached_played_matches(st.session_state.data_version)

        ko_played_by_phase = {}
        for phase, phase_name in [("r32","R32"),("r16","R16"),("qf","Cuartos"),("sf","Semis"),("final","Final")]:
            matches = [m for m in get_ko_matches(phase) if m["played"]]
            ko_played_by_phase[phase] = (phase_name, matches)

        sub_tabs = st.tabs([
            f"Grupos ({len(group_played)})",
            f"R32 ({len(ko_played_by_phase['r32'][1])})",
            f"R16 ({len(ko_played_by_phase['r16'][1])})",
            f"Cuartos ({len(ko_played_by_phase['qf'][1])})",
            f"Semis ({len(ko_played_by_phase['sf'][1])})",
            f"Final ({len(ko_played_by_phase['final'][1])})",
        ])

        with sub_tabs[0]:
            if not group_played:
                st.info("No hay partidos de grupos jugados todavía.")
            else:
                for m in group_played:
                    render_match_stats_card(m, f"Grupo {m['group_letter']}")

        for idx, phase in enumerate(["r32","r16","qf","sf","final"], start=1):
            phase_name, matches = ko_played_by_phase[phase]
            with sub_tabs[idx]:
                if not matches:
                    st.info(f"No hay partidos de {phase_name} jugados todavía.")
                else:
                    for m in matches:
                        render_match_stats_card(m, phase_name)


# TAB 6 — VALUE BETS
# ══════════════════════════════════════════════════════════════════════════════

with tab_value:
    st.markdown("### 💰 Detector de Value Bets")
    st.caption(
        "Seleccioná cualquier partido pendiente de cualquier fase. "
        "El sistema calcula las probabilidades del modelo y detecta value bets."
    )

    preds = st.session_state.predictions
    if not preds:
        st.warning("⚠️ Ejecutá la simulación primero desde el panel izquierdo.")
    else:
        played_m = cached_played_matches(st.session_state.data_version)
        ratings  = compute_dynamic_ratings(played_m, cached_all_analyst_notes(st.session_state.data_version))

        all_m    = get_all_matches()

        group_pending = [
            m for m in all_m
            if m["phase"] == "groups"
            and not m["played"]
            and m["home_team"] and m["away_team"]
        ]

        ko_phases = ["r32","r16","qf","sf","final"]
        ko_phase_names = {
            "r32":"Ronda de 32 (Dieciseisavos)","r16":"Ronda de 16 (Octavos)",
            "qf":"Cuartos de Final","sf":"Semifinales","final":"Final"
        }
        ko_pending = []
        for phase in ko_phases:
            for m in get_ko_matches(phase):
                if (not m["played"]
                    and m.get("home_team") and m.get("away_team")
                    and m["home_team"] not in ["","Por definir"]
                    and m["away_team"] not in ["","Por definir"]):
                    m["phase_display"] = ko_phase_names.get(phase, phase)
                    ko_pending.append(m)

        available_bet_phases = []
        if group_pending:
            available_bet_phases.append("Fase de Grupos")
        if ko_pending:
            available_bet_phases.append("Eliminatorias")

        if len(available_bet_phases) > 1:
            fase_sel = st.radio(
                "Fase",
                available_bet_phases,
                horizontal=True,
                key="vb_phase_selector",
            )
        elif available_bet_phases:
            fase_sel = available_bet_phases[0]
            st.caption(f"Fase disponible: **{fase_sel}**")
        else:
            fase_sel = None

        if fase_sel == "Fase de Grupos":
            pending = group_pending
            def match_label(m):
                return f"{fp(m['home_team'])} vs {fp(m['away_team'])} · Grupo {m['group_letter']}"
            is_ko = False
        elif fase_sel == "Eliminatorias":
            pending = ko_pending
            def match_label(m):
                return f"{fp(m['home_team'])} vs {fp(m['away_team'])} · {m.get('phase_display','KO')}"
            is_ko = True
        else:
            pending = []
            is_ko = False

        if not pending:
            if fase_sel == "Eliminatorias":
                st.info(
                    "No hay partidos eliminatorios pendientes con equipos definidos. "
                    "Cargá los resultados de grupos en la pestaña **🏟️ Eliminatorias** "
                    "para que se armen los cruces."
                )
            elif fase_sel == "Fase de Grupos":
                st.info("No hay partidos de grupos pendientes.")
            else:
                st.info("No hay partidos pendientes con equipos definidos.")
        else:
            options = {match_label(m): m["id"] for m in pending}
            sel_lbl = st.selectbox("Partido a analizar", list(options.keys()), key="vb_match_selector")
            selected_match_id = options[sel_lbl]
            sel_m   = next(m for m in pending if m["id"] == selected_match_id)
            home    = sel_m["home_team"]
            away    = sel_m["away_team"]

            rh = ratings.get(home, 0.5)
            ra = ratings.get(away, 0.5)
            hh = home in HOST_TEAMS
            ah = away in HOST_TEAMS

            ph, pd_, pa = match_probabilities_dc(rh, ra, hh, ah)
            ou          = over_under_probs(rh, ra, hh, ah)
            scores      = exact_score_probs(rh, ra, hh, ah)

            if is_ko:
                total_ko = ph + pa
                if total_ko > 0:
                    ph_ko = ph / total_ko
                    pa_ko = pa / total_ko
                else:
                    ph_ko = pa_ko = 0.5
            else:
                ph_ko = ph
                pa_ko = pa

            ph_champ = preds["phase_probs"].get(home,{}).get("champion",0)
            pa_champ = preds["phase_probs"].get(away,{}).get("champion",0)

            c1, c2 = st.columns(2)

            with c1:
                st.markdown("**📊 Modelo — Probabilidades del partido**")
                if is_ko:
                    st.table({
                        "Resultado": [f"🏠 {home} gana", f"✈️ {away} gana"],
                        "Probabilidad": [f"{ph_ko*100:.1f}%", f"{pa_ko*100:.1f}%"],
                    })
                    st.caption("*Fase KO: no hay empate. Probabilidad incluye posibles penales.*")
                else:
                    st.table({
                        "Resultado":    [f"🏠 {home} gana", "🤝 Empate", f"✈️ {away} gana"],
                        "Probabilidad": [f"{ph*100:.1f}%", f"{pd_*100:.1f}%", f"{pa*100:.1f}%"],
                    })

                st.markdown("**🏆 Contexto — Prob. de ser campeón:**")
                st.caption(f"{fp(home)}: **{ph_champ}%** | {fp(away)}: **{pa_champ}%**")

                st.markdown("**Over/Under:**")
                st.dataframe(pd.DataFrame([
                    {"Mercado":"Over 0.5","Prob":f"{ou['over_05']*100:.1f}%"},
                    {"Mercado":"Over 1.5","Prob":f"{ou['over_15']*100:.1f}%"},
                    {"Mercado":"Over 2.5","Prob":f"{ou['over_25']*100:.1f}%"},
                    {"Mercado":"Over 3.5","Prob":f"{ou['over_35']*100:.1f}%"},
                    {"Mercado":"Ambos anotan","Prob":f"{ou['btts']*100:.1f}%"},
                ]), hide_index=True, use_container_width=True)

                st.markdown("**Marcadores más probables:**")
                st.dataframe(pd.DataFrame(scores[:8]), hide_index=True, use_container_width=True)

            with c2:
                st.markdown("**🏦 Cuotas de la casa**")

                if api_configured():
                    if st.button("🔄 Cargar cuotas automáticamente"):
                        best, commence, msg = get_best_odds(home, away)
                        if best:
                            st.session_state[f"oh_{home}_{away}"] = best["odd_home"]
                            st.session_state[f"od_{home}_{away}"] = best["odd_draw"]
                            st.session_state[f"oa_{home}_{away}"] = best["odd_away"]
                            st.success(f"✅ {msg}")
                        else:
                            st.warning(msg)

                oh = st.number_input(f"Cuota {home} gana",
                    min_value=1.01, max_value=50.0,
                    value=st.session_state.get(f"oh_{home}_{away}", 2.10),
                    step=0.05, key=f"oh_{home}_{away}")

                if not is_ko:
                    od = st.number_input("Cuota empate",
                        min_value=1.01, max_value=50.0,
                        value=st.session_state.get(f"od_{home}_{away}", 3.40),
                        step=0.05, key=f"od_{home}_{away}")
                else:
                    od = None

                oa = st.number_input(f"Cuota {away} gana",
                    min_value=1.01, max_value=50.0,
                    value=st.session_state.get(f"oa_{home}_{away}", 3.20),
                    step=0.05, key=f"oa_{home}_{away}")

                edge_min = st.slider("Edge mínimo (%)", 1, 10, 3,
                                     key=f"edge_{home}_{away}")

                if st.button("🔍 DETECTAR VALUE BETS", use_container_width=True):
                    if is_ko:
                        from models.prediction_engine import (
                            odd_to_implied_prob, remove_overround,
                            calculate_edge, calculate_ev, kelly_criterion
                        )
                        impl = remove_overround([odd_to_implied_prob(oh), odd_to_implied_prob(oa)])
                        vbs  = []
                        for mp, ip, odd, label in [
                            (ph_ko, impl[0], oh, f"🏠 {home} gana"),
                            (pa_ko, impl[1], oa, f"✈️ {away} gana"),
                        ]:
                            edge = calculate_edge(mp, ip)
                            ev   = calculate_ev(mp, odd)
                            if edge >= edge_min:
                                vbs.append({
                                    "market":     label,
                                    "model_prob": round(mp*100,1),
                                    "impl_prob":  round(ip*100,1),
                                    "odd":        odd,
                                    "edge":       edge,
                                    "ev":         ev,
                                    "kelly_25":   kelly_criterion(mp, odd),
                                })
                    else:
                        vbs = detect_value_bets((ph, pd_, pa), (oh, od, oa), edge_min)

                    if vbs:
                        st.success(f"✅ {len(vbs)} value bet(s) encontrado(s)")
                        for vb in vbs:
                            color = "🟢" if vb["edge"] >= 6 else "🟡"
                            st.markdown(f"""
{color} **{vb['market']}** — Cuota `{vb['odd']}`
- Modelo: `{vb['model_prob']}%` | Casa: `{vb['impl_prob']}%`
- Edge: `+{vb['edge']}%` | EV: `{vb['ev']:+.4f}`
- Kelly 25%: apostar `{vb['kelly_25']*100:.2f}%` del bankroll
""")
                            save_value_bet(
                                sel_m["id"], vb["market"], vb["market"],
                                vb["model_prob"]/100, vb["impl_prob"]/100,
                                vb["odd"], vb["edge"], vb["ev"], vb["kelly_25"]
                            )
                        st.caption("✅ Guardado en historial")
                    else:
                        st.warning(f"Sin value bets con edge ≥ {edge_min}%")
                        st.caption("Las cuotas de la casa reflejan bien el modelo, o son desfavorables.")

        st.divider()
        st.markdown("### 📋 Historial de value bets detectados")
        hist = get_value_bets_history()
        if hist:
            st.dataframe(pd.DataFrame(hist)[[
                "home_team","away_team","market","odd",
                "model_prob","implied_prob","edge","ev","kelly_fraction","detected_at"
            ]], hide_index=True, use_container_width=True)
        else:
            st.caption("Sin historial todavía.")

# ─── FOOTER ──────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "⚠️ Herramienta de análisis estadístico. Las probabilidades son estimaciones matemáticas. "
    "Las apuestas deportivas conllevan riesgo económico real. Apostá con responsabilidad."
)
