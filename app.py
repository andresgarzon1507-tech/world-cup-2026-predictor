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
    ensure_database_initialized,
)
from data.public_export import export_public_data, load_public_data
from data.tournament_data import GROUPS, FLAGS, ALL_TEAMS, GROUP_LETTERS, HOST_TEAMS, R32_BRACKET_VALID, THIRD_PLACE_SLOTS
from engine.bracket import source_local_matches
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

# En Cloud no se versiona SQLite: inicializar esquema y fixture antes de leer.
ensure_database_initialized()
PUBLIC_SNAPSHOT = load_public_data()

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
    color:#0d3d24 !important;
    font-weight:700 !important;
    border:2px solid #3aa6ff !important;
    border-radius:6px !important;
}
.hero-shell {
    padding:28px 30px 24px;
    border:1px solid rgba(255,216,77,.35);
    border-radius:18px;
    background:
      radial-gradient(circle at 92% 10%, rgba(58,166,255,.22), transparent 35%),
      linear-gradient(135deg, rgba(4,25,16,.98), rgba(15,74,44,.92));
    box-shadow:0 14px 40px rgba(0,0,0,.24);
    margin-bottom:18px;
}
.hero-kicker { color:#8dd8ff; text-transform:uppercase; letter-spacing:2.2px; font-size:12px; font-weight:800; }
.hero-title { color:#fff; font-size:clamp(28px,5vw,48px); line-height:1.05; font-weight:900; margin:8px 0; }
.hero-title span { color:#ffd84d; }
.hero-subtitle { color:#d9efe2; font-size:15px; max-width:760px; margin:0 0 20px; }
.hero-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
.hero-metric { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); border-radius:12px; padding:11px 13px; }
.hero-metric-label { color:#9fc8ae; font-size:11px; text-transform:uppercase; letter-spacing:.7px; }
.hero-metric-value { color:#fff; font-size:16px; font-weight:800; margin-top:3px; }
.public-intro { background:rgba(58,166,255,.08); border-left:3px solid #3aa6ff; border-radius:0 10px 10px 0; padding:12px 15px; margin:4px 0 18px; color:#e3f3e8; }
.bracket-card { background:rgba(5,30,19,.82); border:1px solid #1c6b3f; border-radius:14px; padding:15px 17px; margin:8px 0; min-height:150px; box-shadow:0 6px 18px rgba(0,0,0,.18); }
.bracket-card.finalizado { border-color:#58c77b; }
.bracket-card.pendiente { border-color:#d9b52f; }
.match-top { display:flex; justify-content:space-between; gap:8px; align-items:center; margin-bottom:12px; }
.match-number { color:#9fc8ae; font-size:12px; font-weight:700; }
.status-pill { border-radius:999px; padding:4px 9px; font-size:10px; font-weight:900; letter-spacing:.5px; }
.status-pill.finalizado { color:#baf4ca; background:rgba(88,199,123,.16); }
.status-pill.pendiente { color:#ffe98b; background:rgba(217,181,47,.16); }
.match-team { display:flex; justify-content:space-between; gap:12px; color:#fff; font-weight:750; padding:4px 0; }
.match-score { color:#ffd84d; font-weight:900; }
.match-foot { color:#a9cbb5; font-size:11px; margin-top:10px; border-top:1px solid rgba(255,255,255,.08); padding-top:9px; }
@media (max-width:760px) {
  .hero-shell { padding:22px 18px; }
  .hero-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────

if "local_predictions" not in st.session_state:
    # Copia local separada: el modo público puede usar el snapshot JSON sin
    # reemplazar la predicción de trabajo del administrador.
    latest = get_latest_prediction()
    local_predictions = latest["results_json"] if latest else None
    if (
        local_predictions
        and local_predictions.get("model_version") != "ko-aware-v1"
    ):
        local_predictions = None
    st.session_state.local_predictions = local_predictions

if "predictions" not in st.session_state:
    st.session_state.predictions = st.session_state.local_predictions
if "prediction_source" not in st.session_state:
    st.session_state.prediction_source = "local"

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

    public_data = PUBLIC_SNAPSHOT if not IS_ADMIN else {}
    public_predictions = public_data.get("predictions")
    if (
        not IS_ADMIN
        and isinstance(public_predictions, dict)
        and public_predictions.get("model_version") == "ko-aware-v1"
    ):
        st.session_state.predictions = public_predictions
        st.session_state.prediction_source = "public"
    elif IS_ADMIN and st.session_state.prediction_source == "public":
        st.session_state.predictions = st.session_state.local_predictions
        st.session_state.prediction_source = "local"

    st.divider()

    database_matches = cached_all_matches(st.session_state.data_version)
    snapshot_matches = public_data.get("matches")
    all_matches = (
        snapshot_matches
        if isinstance(snapshot_matches, list) and snapshot_matches
        else database_matches
    )
    played = [match for match in all_matches if match.get("played")]
    public_metadata = public_data.get("metadata") or {}
    played_count = int(
        public_metadata.get("played_matches", len(played))
    )
    total_matches = int(
        public_metadata.get("total_matches", len(all_matches))
    )
    remaining_matches = int(
        public_metadata.get(
            "remaining_matches",
            total_matches - played_count,
        )
    )

    st.metric(
        "Partidos jugados",
        f"{played_count} / {total_matches}",
    )
    st.metric("Partidos restantes", f"{remaining_matches}")

    st.divider()

    if IS_ADMIN:
        n_sims = st.select_slider(
            "Simulaciones",
            options=[1_000, 5_000, 10_000, 25_000],
            value=10_000,
            help="Más simulaciones = más preciso pero más lento",
        )

        if st.button("▶ SIMULAR AHORA", use_container_width=True):
            analyst_notes = get_all_analyst_notes()
            with st.spinner(f"Ejecutando {n_sims:,} simulaciones..."):
                all_stats = get_all_match_stats()
                preds = run_monte_carlo(
                    all_matches,
                    analyst_notes,
                    all_stats,
                    n_sims,
                )
                st.session_state.predictions = preds
                st.session_state.local_predictions = preds
                st.session_state.prediction_source = "local"
                save_prediction(len(played), n_sims, preds)
            st.success("✅ Completado")
            st.rerun()

        if st.button(
            "📤 Exportar datos públicos",
            use_container_width=True,
        ):
            try:
                generated_files = export_public_data(
                    st.session_state.predictions
                )
                st.success("Datos públicos exportados correctamente.")
                st.code("\n".join(generated_files))
            except Exception as exc:
                st.error(f"No se pudo exportar: {exc}")
    else:
        public_metadata = public_data.get("metadata") or {}
        n_sims = int(
            (st.session_state.predictions or {}).get("simulations")
            or public_metadata.get("simulations")
            or 0
        )

    st.divider()
    st.markdown("### 🏆 Top 5 favoritos")
    preds = st.session_state.predictions
    if preds:
        top_favorites = []
        seen_teams = set()
        for candidate in preds.get("champion_probs") or []:
            team = str(candidate.get("team") or "").strip()
            normalized_team = team.casefold()
            if not team or normalized_team in seen_teams:
                continue
            seen_teams.add(normalized_team)
            top_favorites.append(candidate)
            if len(top_favorites) == 5:
                break

        for i, candidate in enumerate(top_favorites, start=1):
            # Chrome estaba traduciendo nombres propios dentro del Markdown
            # (Francia -> México, Argentina -> España). translate="no" evita
            # que equipos distintos terminen viéndose como duplicados.
            st.markdown(
                f'<div class="notranslate" translate="no">'
                f'<code>{i}.</code> {fp(candidate["team"])} — '
                f'<strong>{candidate["prob"]}%</strong></div>',
                unsafe_allow_html=True,
            )
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


def get_visible_ko_matches(phase):
    """Fuente KO pública desde JSON; en admin conserva SQLite."""
    if not IS_ADMIN:
        public_bracket = public_data.get("bracket") or {}
        phase_matches = public_bracket.get(phase)
        if isinstance(phase_matches, list):
            return [dict(match) for match in phase_matches]
    return get_ko_matches(phase)


def get_visible_analyst_notes():
    """Normaliza las claves numéricas serializadas por JSON."""
    if not IS_ADMIN:
        notes = public_data.get("analyst_notes")
        if isinstance(notes, dict):
            normalized = {}
            for match_id, note in notes.items():
                try:
                    match_id = int(match_id)
                except (TypeError, ValueError):
                    pass
                normalized[match_id] = note
            return normalized
    return cached_all_analyst_notes(st.session_state.data_version)


# ─── PORTADA ─────────────────────────────────────────────────────────────────

phase_targets = [
    ("r32", 16, "Dieciseisavos / R32"),
    ("r16", 8, "Octavos de final"),
    ("qf", 4, "Cuartos de final"),
    ("sf", 2, "Semifinales"),
    ("final", 1, "Final"),
]
current_phase = "Dieciseisavos / R32"
for phase_key, expected_matches, phase_label in phase_targets:
    phase_matches = [m for m in all_matches if m.get("phase") == phase_key]
    phase_played = sum(1 for m in phase_matches if m.get("played"))
    current_phase = phase_label
    if phase_played < expected_matches:
        break
else:
    current_phase = "Torneo finalizado"

updated_values = [
    str(m.get("updated_at"))
    for m in all_matches
    if m.get("updated_at")
]
public_generated_at = (
    (public_data.get("metadata") or {}).get("generated_at")
    if not IS_ADMIN
    else None
)
if public_generated_at:
    last_update = str(public_generated_at)[:16].replace("T", " ")
else:
    last_update = (
        max(updated_values)[:16].replace("T", " ")
        if updated_values
        else "Sin registro"
    )

st.markdown(f"""
<div class="hero-shell">
  <div class="hero-kicker">Mundial FIFA 2026 · modelo actualizado</div>
  <div class="hero-title">World Cup 2026 <span>Predictor</span></div>
  <div class="hero-subtitle">
    Simulador probabilístico con Monte Carlo, bracket dinámico y detección de value bets.
  </div>
  <div class="hero-metrics">
    <div class="hero-metric"><div class="hero-metric-label">Fase actual</div><div class="hero-metric-value">{current_phase}</div></div>
    <div class="hero-metric"><div class="hero-metric-label">Partidos jugados</div><div class="hero-metric-value">{played_count} / {total_matches}</div></div>
    <div class="hero-metric"><div class="hero-metric-label">Simulaciones</div><div class="hero-metric-value">{n_sims:,}</div></div>
    <div class="hero-metric"><div class="hero-metric-label">Última actualización</div><div class="hero-metric-value">{last_update}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

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
            else:
                # Un fixture oficial no se completa con probabilidades.
                # Hasta que el grupo termine, el slot permanece sin resolver.
                real_qualifiers[f"1{g}"] = {
                    "team": f"1° Grupo {g}",
                    "confirmed": False,
                    "predicted": False,
                }
                real_qualifiers[f"2{g}"] = {
                    "team": f"2° Grupo {g}",
                    "confirmed": False,
                    "predicted": False,
                }

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

        # Solo los terceros definidos por resultados reales pueden ocupar
        # slots oficiales del fixture.
        thirds_list.sort(
            key=lambda x: (x["pts"], x["gd"], x["gf"]),
            reverse=True,
        )

        qualified_thirds = thirds_list[:8]
        assigned_groups = set()
        for slot_name, candidate_groups in THIRD_PLACE_SLOTS.items():
            for t in qualified_thirds:
                if t["group"] in candidate_groups and t["group"] not in assigned_groups:
                    real_qualifiers[slot_name] = {
                        "team": t["team"],
                        "confirmed": True,
                        "predicted": False,
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

            matches_by_number = {
                int(match["match_number"]): match
                for match in ko_matches
                if match.get("match_number") is not None
            }

            # Todas las fases deben recorrerse. Antes este ciclo dependía de
            # bracket_pairs, que solo existe para R32, por lo que octavos y
            # las rondas posteriores nunca recibían a sus clasificados.
            for i in range(n_matches):
                match_number = i + 1
                m = matches_by_number.get(match_number)
                if m is None:
                    continue

                if phase_key == "r32" and bracket_pairs:
                    slot_a, slot_b = bracket_pairs[i]
                    ta, _ = resolve(slot_a)
                    tb, _ = resolve(slot_b)
                elif prev_phase:
                    source_a, source_b = source_local_matches(
                        phase_key,
                        match_number,
                    )
                    ta = get_ko_winner(prev_phase, source_a) or ""
                    tb = get_ko_winner(prev_phase, source_b) or ""
                else:
                    ta, tb = m["home_team"], m["away_team"]

                fixture_is_empty = (
                    not m.get("home_team")
                    and not m.get("away_team")
                    and not m.get("played")
                )
                resolved_teams_are_real = (
                    ta
                    and tb
                    and "Grupo" not in ta
                    and "Grupo" not in tb
                    and not ta.startswith("3-")
                    and not tb.startswith("3-")
                )
                if phase_key == "r32" and fixture_is_empty and resolved_teams_are_real:
                    # La DB es la fuente de verdad. Solo completamos filas vacías;
                    # nunca reordenamos ni sobrescribimos un cruce ya guardado.
                    update_ko_teams(phase_key, match_number, ta, tb)
                elif prev_phase and not m.get("played"):
                    # En rondas posteriores, los equipos sí deben seguir a los
                    # ganadores de los partidos fuente oficiales. Nunca se toca
                    # un encuentro de la ronda siguiente que ya fue jugado.
                    stored_teams = (
                        m.get("home_team") or "",
                        m.get("away_team") or "",
                    )
                    resolved_teams = (ta, tb)
                    if stored_teams != resolved_teams:
                        update_ko_teams(
                            phase_key,
                            match_number,
                            ta,
                            tb,
                        )

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
        # Inicialización no destructiva: crea únicamente filas KO faltantes.
        if st.button(
            "🔄 Completar filas KO faltantes",
            use_container_width=True,
            key="init_missing_ko_btn",
        ):
            init_ko_matches()
            bump_data_version()
            st.success(
                "Estructura verificada sin borrar resultados ni modificar "
                "cruces ya guardados."
            )
            st.rerun()

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
    st.markdown(
        '<div class="public-intro"><b>Panorama del torneo.</b> '
        'Compará las probabilidades de cada selección para avanzar de ronda '
        'y conquistar el título. Los resultados ya jugados se consideran definitivos.</div>',
        unsafe_allow_html=True,
    )
    preds = st.session_state.predictions
    if not preds:
        st.info("Ejecutá la simulación para ver el panorama completo del torneo.")
    else:
        group_probs = preds.get("group_probs") or {}
        phase_probs = preds.get("phase_probs") or {}
        champion_probs = [
            row for row in (preds.get("champion_probs") or [])
            if isinstance(row, dict)
            and row.get("team")
            and row.get("prob") is not None
        ]

        meta_parts = []
        if preds.get("matches_played") is not None:
            meta_parts.append(f"{preds.get('matches_played')} partidos incorporados")
        if preds.get("simulations") is not None:
            meta_parts.append(f"{preds.get('simulations'):,} simulaciones")
        if preds.get("ko_matches_played") is not None:
            meta_parts.append(f"{preds.get('ko_matches_played')} resultados KO fijados")
        if meta_parts:
            st.caption(" · ".join(meta_parts))

        st.markdown("### 🏆 Top candidatos al título")
        top_rows = [
            {
                "Posición": index,
                "Equipo": fp(row["team"]),
                "Campeón (%)": float(row["prob"]),
                "Final (%)": float(
                    (phase_probs.get(row["team"]) or {}).get("final", 0)
                ),
            }
            for index, row in enumerate(champion_probs[:10], start=1)
        ]
        if top_rows:
            top_df = pd.DataFrame(top_rows)
            st.dataframe(
                top_df.style.format({
                    "Campeón (%)": "{:.1f}%",
                    "Final (%)": "{:.1f}%",
                }),
                hide_index=True,
                use_container_width=True,
            )

        phase_metrics = [
            ("r32", "R32 / Dieciseisavos (%)"),
            ("r16", "Octavos (%)"),
            ("qf", "Cuartos (%)"),
            ("sf", "Semis (%)"),
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

        st.markdown("### 📊 Probabilidades por fase")
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
                row = {
                    "Equipo": fp(team),
                    "Grupo": team_groups.get(team, "—"),
                }
                for key, label in available_phase_metrics:
                    value = metrics.get(key)
                    row[label] = float(value) if value is not None else None
                phase_rows.append(row)

            sort_key, sort_label = (
                next(
                    ((key, label) for key, label in reversed(available_phase_metrics)
                     if key == "champion"),
                    available_phase_metrics[-1],
                )
            )
            phase_rows.sort(
                key=lambda row: row.get(sort_label) or 0,
                reverse=True,
            )
            phase_df = pd.DataFrame(phase_rows)
            percent_formats = {
                label: "{:.1f}%"
                for _, label in available_phase_metrics
            }
            st.dataframe(
                phase_df.style.format(percent_formats, na_rep="—"),
                hide_index=True,
                use_container_width=True,
                height=620,
            )
        else:
            st.info(
                "La simulación disponible todavía no incluye probabilidades "
                "de fases avanzadas."
            )

        played_ko = [
            m for m in all_matches
            if m.get("phase") in {"r32", "r16", "qf", "sf", "final"}
            and m.get("played")
        ]
        eliminated = set()
        for match in played_ko:
            home = match.get("home_team")
            away = match.get("away_team")
            hg = match.get("home_goals")
            ag = match.get("away_goals")
            if home and away and hg is not None and ag is not None and hg != ag:
                eliminated.add(away if hg > ag else home)

        alive = [
            team for team, metrics in phase_probs.items()
            if isinstance(metrics, dict)
            and (metrics.get("r32") or 0) > 0
            and team not in eliminated
        ]
        alive.sort(
            key=lambda team: (phase_probs.get(team) or {}).get("champion", 0),
            reverse=True,
        )
        eliminated_sorted = sorted(
            eliminated,
            key=lambda team: (phase_probs.get(team) or {}).get("champion", 0),
            reverse=True,
        )

        status_left, status_right = st.columns(2)
        with status_left:
            st.markdown("### ✅ Equipos que siguen vivos")
            if alive:
                alive_rows = [{
                    "Equipo": fp(team),
                    "Campeón (%)": float(
                        (phase_probs.get(team) or {}).get("champion", 0)
                    ),
                } for team in alive]
                st.dataframe(
                    pd.DataFrame(alive_rows).style.format(
                        {"Campeón (%)": "{:.1f}%"}
                    ),
                    hide_index=True,
                    use_container_width=True,
                    height=360,
                )
            else:
                st.caption("Sin datos suficientes para determinarlo.")
        with status_right:
            st.markdown("### ⛔ Equipos eliminados")
            if eliminated_sorted:
                st.dataframe(
                    pd.DataFrame({
                        "Equipo": [fp(team) for team in eliminated_sorted]
                    }),
                    hide_index=True,
                    use_container_width=True,
                    height=360,
                )
            else:
                st.caption("Todavía no hay eliminados registrados en KO.")

        predicted_qualifiers = preds.get("predicted_qualifiers") or {}
        if group_probs or predicted_qualifiers:
            st.divider()
            st.markdown("### 🎯 Resumen de la fase de grupos")
            st.caption(
                "Primeros, segundos y mejores terceros calculados a partir "
                "de los resultados cargados."
            )
            cols = st.columns(4)
            for i, group in enumerate(GROUP_LETTERS):
                rows = group_probs.get(group) or []
                projection = predicted_qualifiers.get(group) or {}
                first = projection.get("first") or max(
                    rows, key=lambda row: row.get("first", 0), default={}
                )
                second = projection.get("second") or max(
                    rows, key=lambda row: row.get("second", 0), default={}
                )
                with cols[i % 4]:
                    st.markdown(f"**Grupo {group}**")
                    if first.get("team"):
                        st.caption(f"🥇 {fp(first['team'])}")
                    if second.get("team"):
                        st.caption(f"🥈 {fp(second['team'])}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — BRACKET
# ══════════════════════════════════════════════════════════════════════════════

with tab_bracket:
    st.markdown(
        '<div class="public-intro"><b>Camino al campeón.</b> '
        'Los partidos finalizados muestran su resultado real; los pendientes '
        'muestran la probabilidad del modelo. La proyección se actualiza con '
        'cada nueva simulación.</div>',
        unsafe_allow_html=True,
    )
    preds = st.session_state.predictions
    if not preds:
        st.info("Ejecutá la simulación para construir el bracket actualizado.")
    else:
        group_probs = preds.get("group_probs") or {}
        phase_probs = preds.get("phase_probs") or {}
        ratings_used = preds.get("ratings_used") or {}

        # Resolver slots exclusivamente con resultados reales de grupos.
        # Las probabilidades nunca determinan el orden del fixture.
        official_slots = {}
        real_thirds = []
        for group in GROUP_LETTERS:
            group_matches = [
                match for match in all_matches
                if match.get("group_letter") == group
                and match.get("played")
            ]
            if len(group_matches) != 6:
                continue

            table = {
                team: {"pts": 0, "gf": 0, "ga": 0, "gd": 0}
                for team in GROUPS[group]
            }
            for match in group_matches:
                home = match["home_team"]
                away = match["away_team"]
                home_goals = match["home_goals"]
                away_goals = match["away_goals"]
                table[home]["gf"] += home_goals
                table[home]["ga"] += away_goals
                table[away]["gf"] += away_goals
                table[away]["ga"] += home_goals
                table[home]["gd"] = table[home]["gf"] - table[home]["ga"]
                table[away]["gd"] = table[away]["gf"] - table[away]["ga"]
                if home_goals > away_goals:
                    table[home]["pts"] += 3
                elif home_goals < away_goals:
                    table[away]["pts"] += 3
                else:
                    table[home]["pts"] += 1
                    table[away]["pts"] += 1

            ranked = sorted(
                GROUPS[group],
                key=lambda team: (
                    table[team]["pts"],
                    table[team]["gd"],
                    table[team]["gf"],
                ),
                reverse=True,
            )
            official_slots[f"1{group}"] = ranked[0]
            official_slots[f"2{group}"] = ranked[1]
            third = ranked[2]
            real_thirds.append({
                "team": third,
                "group": group,
                **table[third],
            })

        real_thirds.sort(
            key=lambda row: (row["pts"], row["gd"], row["gf"]),
            reverse=True,
        )
        qualified_thirds = real_thirds[:8]
        assigned_third_groups = set()
        for slot_name, candidate_groups in THIRD_PLACE_SLOTS.items():
            for third in qualified_thirds:
                if (
                    third["group"] in candidate_groups
                    and third["group"] not in assigned_third_groups
                ):
                    official_slots[slot_name] = third["team"]
                    assigned_third_groups.add(third["group"])
                    break

        def resolve_slot(slot):
            return official_slots.get(slot, slot)

        r32_matches = {
            int(match.get("match_number")): match
            for match in get_visible_ko_matches("r32")
            if match.get("match_number") is not None
        }

        st.markdown("### Dieciseisavos / R32")
        st.caption(
            "Estado real del cuadro combinado con proyección probabilística "
            "para los cruces todavía pendientes."
        )
        card_columns = st.columns(2)
        for index, (slot_a, slot_b) in enumerate(R32_BRACKET_VALID, start=1):
            match = r32_matches.get(index) or {}
            stored_home = match.get("home_team")
            stored_away = match.get("away_team")
            has_real_teams = (
                stored_home not in (None, "", "Por definir")
                and stored_away not in (None, "", "Por definir")
            )
            home = stored_home if has_real_teams else resolve_slot(slot_a)
            away = stored_away if has_real_teams else resolve_slot(slot_b)
            played_match = bool(match.get("played") and has_real_teams)
            home_goals = match.get("home_goals")
            away_goals = match.get("away_goals")

            status = "Finalizado" if played_match else "Pendiente"
            status_class = "finalizado" if played_match else "pendiente"
            home_score = ""
            away_score = ""
            footer = f"Slots: {slot_a} vs {slot_b}"

            if (
                played_match
                and home_goals is not None
                and away_goals is not None
            ):
                home_score = str(home_goals)
                away_score = str(away_goals)
                if home_goals != away_goals:
                    winner = home if home_goals > away_goals else away
                    footer = f"Ganador definitivo: {fp(winner)}"
            elif home not in ("?", "Mejor 3.º") and away not in ("?", "Mejor 3.º"):
                home_rating = ratings_used.get(home, 0.5)
                away_rating = ratings_used.get(away, 0.5)
                p_home, _, p_away = match_probabilities_dc(
                    home_rating,
                    away_rating,
                    home in HOST_TEAMS,
                    away in HOST_TEAMS,
                )
                ko_total = p_home + p_away
                if ko_total > 0:
                    footer = (
                        f"Modelo: {home} {p_home / ko_total * 100:.1f}% · "
                        f"{away} {p_away / ko_total * 100:.1f}%"
                    )

            home_display = fp(home) if home not in ("?", "Mejor 3.º") else home
            away_display = fp(away) if away not in ("?", "Mejor 3.º") else away
            with card_columns[(index - 1) % 2]:
                st.markdown(f"""
<div class="bracket-card {status_class}">
  <div class="match-top">
    <span class="match-number">PARTIDO {index}</span>
    <span class="status-pill {status_class}">{status.upper()}</span>
  </div>
  <div class="match-team"><span>{home_display}</span><span class="match-score">{home_score}</span></div>
  <div class="match-team"><span>{away_display}</span><span class="match-score">{away_score}</span></div>
  <div class="match-foot">{footer}</div>
</div>
""", unsafe_allow_html=True)

        st.divider()
        st.markdown("### Camino probabilístico por selección")
        selectable_teams = sorted(
            phase_probs,
            key=lambda team: (phase_probs.get(team) or {}).get("champion", 0),
            reverse=True,
        )
        selected = st.selectbox(
            "Seleccioná una selección",
            selectable_teams,
            format_func=fp,
            key="public_bracket_team",
        )
        selected_probs = phase_probs.get(selected) or {}
        selected_group_rows = next(
            (
                group_probs.get(group) or []
                for group, teams in GROUPS.items()
                if selected in teams
            ),
            [],
        )
        team_group_prob = next(
            (row for row in selected_group_rows if row.get("team") == selected),
            {},
        )
        path_metrics = [
            ("Clasificó", team_group_prob.get("qualify")),
            ("R32", selected_probs.get("r32")),
            ("Octavos", selected_probs.get("r16")),
            ("Cuartos", selected_probs.get("qf")),
            ("Semis", selected_probs.get("sf")),
            ("Final", selected_probs.get("final")),
            ("Campeón", selected_probs.get("champion")),
        ]
        path_metrics = [
            (label, float(value))
            for label, value in path_metrics
            if value is not None
        ]
        if path_metrics:
            metric_columns = st.columns(min(3, len(path_metrics)))
            for index, (label, value) in enumerate(path_metrics):
                metric_columns[index % len(metric_columns)].metric(
                    label,
                    f"{value:.1f}%",
                )
            figure = go.Figure(go.Bar(
                x=[label for label, _ in path_metrics],
                y=[value for _, value in path_metrics],
                marker_color="#ffd84d",
                text=[f"{value:.1f}%" for _, value in path_metrics],
                textposition="outside",
            ))
            figure.update_layout(
                plot_bgcolor="#0d3d24",
                paper_bgcolor="#0d3d24",
                font_color="#e3f3e8",
                yaxis_range=[0, 105],
                title=f"Camino al título — {selected}",
                title_font_color="#ffd84d",
            )
            st.plotly_chart(figure, use_container_width=True)


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

        def load_espn_data_into_widgets(data):
            """Copia cada dato ESPN a la key real que usa su widget."""
            direct_widget_fields = [
                "home_shots", "away_shots",
                "home_shots_on", "away_shots_on",
                "home_possession", "away_possession",
                "home_passes", "away_passes",
                "home_pass_acc", "away_pass_acc",
                "home_fouls", "away_fouls",
                "home_yellows", "away_yellows",
                "home_reds", "away_reds",
                "home_offsides", "away_offsides",
                "home_corners", "away_corners",
            ]
            for field in direct_widget_fields:
                value = data.get(field)
                if value is not None:
                    st.session_state[f"{field}_{m['id']}"] = value

            widget_key_map = {
                "home_formation": f"hform_{m['id']}",
                "away_formation": f"aform_{m['id']}",
                "home_xg": f"hxg_{m['id']}",
                "away_xg": f"axg_{m['id']}",
            }
            for field, widget_key in widget_key_map.items():
                value = data.get(field)
                if value is not None:
                    st.session_state[widget_key] = value

        if st.button("📡 Traer datos de ESPN", key=f"apifetch_{m['id']}"):
            with st.spinner("Consultando ESPN..."):
                data, msg = get_full_match_data(
                    m["home_team"],
                    m["away_team"],
                    match_date=m.get("match_date"),
                    phase=m.get("phase"),
                )
            if data:
                st.session_state[f"{api_prefix}_data"] = data
                load_espn_data_into_widgets(data)
                st.session_state[f"{api_prefix}_message"] = msg
                st.rerun()
            else:
                st.info(msg)

        loaded_message = st.session_state.pop(
            f"{api_prefix}_message",
            None,
        )
        if loaded_message:
            st.success(loaded_message)

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

        group_played = [
            match
            for match in cached_played_matches(st.session_state.data_version)
            if match.get("phase") == "groups"
        ]

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
    st.markdown("### 💰 Value Bets")
    st.markdown(
        '<div class="public-intro"><b>¿Qué es una value bet?</b> '
        'Es una oportunidad en la que la probabilidad estimada por el modelo '
        'es mayor que la probabilidad implícita de la cuota ofrecida.</div>',
        unsafe_allow_html=True,
    )
    st.warning(
        "Juego responsable: esto no es asesoramiento financiero ni garantía "
        "de ganancia. Apostá únicamente dinero que puedas permitirte perder."
    )

    preds = st.session_state.predictions
    if not preds:
        st.warning("⚠️ Ejecutá la simulación primero desde el panel izquierdo.")
    else:
        played_m = played
        # Misma fuente que Monte Carlo: estos ratings ya incorporan
        # resultados, estadísticas completas y notas del Analista.
        ratings = preds.get("ratings_used") or compute_dynamic_ratings(
            played_m,
            get_visible_analyst_notes(),
            (
                cached_all_match_stats(st.session_state.data_version)
                if IS_ADMIN
                else None
            ),
        )

        if preds.get("matches_played") != len(played_m):
            st.warning(
                "Hay resultados posteriores a la última simulación. "
                "Ejecutá **SIMULAR AHORA** para actualizar ratings, "
                "probabilidades y marcadores."
            )

        all_m = all_matches

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
            for m in get_visible_ko_matches(phase):
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

                home_odd_key = f"vb_odd_home_{selected_match_id}"
                draw_odd_key = f"vb_odd_draw_{selected_match_id}"
                away_odd_key = f"vb_odd_away_{selected_match_id}"

                if api_configured():
                    if st.button(
                        "🔄 Cargar cuotas disponibles",
                        key=f"load_odds_{selected_match_id}",
                        use_container_width=True,
                    ):
                        best, commence, msg = get_best_odds(home, away)
                        if best:
                            st.session_state[home_odd_key] = best.get("odd_home")
                            st.session_state[draw_odd_key] = best.get("odd_draw")
                            st.session_state[away_odd_key] = best.get("odd_away")
                            st.success(f"✅ {msg}")
                        else:
                            st.warning(msg)
                else:
                    st.caption(
                        "Sin proveedor de cuotas configurado. Podés ingresar "
                        "cuotas reales manualmente para analizarlas."
                    )

                oh = st.number_input(
                    f"Cuota {home} gana",
                    min_value=1.01,
                    max_value=50.0,
                    value=None,
                    step=0.05,
                    placeholder="Ingresá la cuota",
                    key=home_odd_key,
                )

                if not is_ko:
                    od = st.number_input(
                        "Cuota empate",
                        min_value=1.01,
                        max_value=50.0,
                        value=None,
                        step=0.05,
                        placeholder="Ingresá la cuota",
                        key=draw_odd_key,
                    )
                else:
                    od = None

                oa = st.number_input(
                    f"Cuota {away} gana",
                    min_value=1.01,
                    max_value=50.0,
                    value=None,
                    step=0.05,
                    placeholder="Ingresá la cuota",
                    key=away_odd_key,
                )

                edge_min = st.slider(
                    "Edge mínimo (%)",
                    1,
                    10,
                    3,
                    key=f"edge_{selected_match_id}",
                )
                odds_ready = (
                    oh is not None
                    and oa is not None
                    and (is_ko or od is not None)
                )
                if not odds_ready:
                    st.caption(
                        "Ingresá todas las cuotas para calcular probabilidad "
                        "implícita, edge y valor esperado."
                    )

                if st.button(
                    "🔍 DETECTAR VALUE BETS",
                    use_container_width=True,
                    disabled=not odds_ready,
                    key=f"detect_vb_{selected_match_id}",
                ):
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

                    positive_vbs = [
                        vb for vb in vbs
                        if vb.get("edge", 0) > 0
                    ]
                    if positive_vbs:
                        positive_vbs.sort(
                            key=lambda vb: vb.get("edge", 0),
                            reverse=True,
                        )
                        st.success(
                            f"✅ {len(positive_vbs)} oportunidad(es) "
                            "con edge positivo"
                        )
                        opportunities = pd.DataFrame([{
                            "Mercado": vb.get("market"),
                            "Prob. modelo (%)": vb.get("model_prob"),
                            "Cuota": vb.get("odd"),
                            "Prob. implícita (%)": vb.get("impl_prob"),
                            "Edge (%)": vb.get("edge"),
                            "EV": vb.get("ev"),
                        } for vb in positive_vbs])
                        st.dataframe(
                            opportunities.style.format({
                                "Prob. modelo (%)": "{:.1f}%",
                                "Cuota": "{:.2f}",
                                "Prob. implícita (%)": "{:.1f}%",
                                "Edge (%)": "+{:.1f}%",
                                "EV": "{:+.4f}",
                            }),
                            hide_index=True,
                            use_container_width=True,
                        )
                        if IS_ADMIN:
                            for vb in positive_vbs:
                                save_value_bet(
                                    sel_m["id"], vb["market"], vb["market"],
                                    vb["model_prob"]/100,
                                    vb["impl_prob"]/100,
                                    vb["odd"], vb["edge"], vb["ev"],
                                    vb["kelly_25"],
                                )
                            st.caption(
                                "Resultado guardado en el historial local."
                            )
                        else:
                            st.caption(
                                "Cálculo público: no se guardaron cambios."
                            )
                    else:
                        st.info(
                            f"No hay oportunidades con edge positivo "
                            f"por encima del umbral de {edge_min}%."
                        )

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
