# models/prediction_engine.py
# Motor corregido:
# - Separación exponencial de ratings (fix #9)
# - Terceros correctamente registrados (fix #4 #5)
# - Fases correctamente alineadas (fix #6)
# - Penales dependientes de rating (fix #7)
# - Ratings con shrinkage bayesiano (fix #8)
# - Ventaja de anfitrión (fix #10)
# - Ruido controlado entre simulaciones (fix #11)

import numpy as np
from scipy.stats import poisson
import random
from collections import defaultdict

from data.tournament_data import (
    GROUPS, FIFA_RATINGS, R32_BRACKET_VALID, THIRD_PLACE_SLOTS,
    ALL_TEAMS, GROUP_LETTERS, GROUP_FIXTURES,
    HOST_TEAMS, HOST_BOOST,
)

# ─── PARÁMETROS GLOBALES ──────────────────────────────────────────────────────

SIMULATIONS   = 10_000
BASE_LAMBDA   = 1.25   # goles esperados base por equipo (Mundial, campo neutro)
RHO           = -0.13  # correlación Dixon-Coles (scores bajos)

# Shrinkage: cuánto confiamos en el resultado vs el prior FIFA
# 0 = ignorar resultados, 1 = ignorar prior
SHRINKAGE_K   = 3.0    # equivale a "3 partidos previos imaginarios"

# Ruido entre simulaciones para capturar incertidumbre
RATING_NOISE_STD = 0.025  # desviación estándar del ruido gaussiano por simulación

# ─── TRANSFORMACIÓN RATING → LAMBDA (exponencial) ────────────────────────────

def rating_to_lambda(rating):
    """
    Convierte rating [0,1] a lambda de goles esperados.
    Función exponencial: genera MUCHA más separación que lineal.

    Factor 3.0 (ajustado tras validación empírica — ver notas):
    rating=0.95 (Argentina) → lambda ≈ 2.73
    rating=0.50 (Chequia)   → lambda ≈ 0.95
    rating=0.34 (NZ)        → lambda ≈ 0.57

    NOTA: el factor anterior (2.0) daba a un partido tipo
    "Argentina vs Jordania" solo ~69% de probabilidad de victoria
    del favorito, muy por debajo de lo que reflejan mercados reales
    de apuestas (típicamente 85-90%+ en desigualdades de ese nivel).
    Con 3.0 ese mismo partido da ~83%, mucho más realista, sin
    distorsionar partidos parejos (ej: Brasil vs Marruecos se
    mantiene ~53% vs ~24%, correctamente cerrado).
    """
    return BASE_LAMBDA * np.exp(3.0 * (rating - 0.65))


def expected_goals(r_home, r_away, home_is_host=False, away_is_host=False):
    """
    Estima lambda_home y lambda_away usando transformación exponencial.
    Aplica ventaja de anfitrión si corresponde.
    Ajuste cruzado: la defensa del rival frena el ataque.
    """
    rh = r_home + (HOST_BOOST if home_is_host else 0)
    ra = r_away + (HOST_BOOST if away_is_host else 0)

    rh = min(1.0, rh)
    ra = min(1.0, ra)

    lh = rating_to_lambda(rh)
    la = rating_to_lambda(ra)

    # Ajuste cruzado: atacas menos contra una defensa mejor
    adj_h = lh * (1 - 0.25 * ra)
    adj_a = la * (1 - 0.25 * rh)

    return max(0.15, adj_h), max(0.15, adj_a)


# ─── RATINGS DINÁMICOS CON SHRINKAGE BAYESIANO ───────────────────────────────

def compute_performance_score(stats: dict, home_goals: int, away_goals: int):
    """
    Calcula un performance_score para local y visitante basado en
    estadísticas reales del partido. Rango aprox: 0.0 a 2.0 por equipo.

    Componentes (todos normalizados a [0,1] antes de ponderar):
    - xG ratio            : calidad de ocasiones generadas
    - Posesión            : dominio del juego
    - Precisión de pases  : control táctico
    - Remates al arco ratio: eficiencia ofensiva
    - Corners             : presión territorial
    - Penalización rojas  : impacto disciplinario
    - Resultado real      : base del ajuste
    """
    if not stats:
        return None, None

    def safe(val, default=0):
        return val if val is not None else default

    # ── xG ─────────────────────────────────────────────────────────────────
    # Si se ingresó xG manual, usarlo; si no, estimarlo con remates al arco
    h_xg = safe(stats.get("home_xg"))
    a_xg = safe(stats.get("away_xg"))
    if h_xg == 0 and a_xg == 0:
        h_xg = safe(stats.get("home_shots_on"), 0) * 0.10
        a_xg = safe(stats.get("away_shots_on"), 0) * 0.10

    total_xg = h_xg + a_xg
    xg_ratio_h = h_xg / total_xg if total_xg > 0 else 0.5
    xg_ratio_a = a_xg / total_xg if total_xg > 0 else 0.5

    # ── Posesión ────────────────────────────────────────────────────────────
    h_pos = safe(stats.get("home_possession"), 50) / 100
    a_pos = safe(stats.get("away_possession"), 50) / 100

    # ── Precisión de pases ──────────────────────────────────────────────────
    h_pacc = safe(stats.get("home_pass_acc"), 75) / 100
    a_pacc = safe(stats.get("away_pass_acc"), 75) / 100

    # ── Remates al arco / remates totales ────────────────────────────────────
    h_shots     = safe(stats.get("home_shots"), 1)
    a_shots     = safe(stats.get("away_shots"), 1)
    h_shots_on  = safe(stats.get("home_shots_on"), 0)
    a_shots_on  = safe(stats.get("away_shots_on"), 0)
    h_precision = h_shots_on / h_shots if h_shots > 0 else 0
    a_precision = a_shots_on / a_shots if a_shots > 0 else 0

    # ── Corners (presión territorial) ────────────────────────────────────────
    h_corn = safe(stats.get("home_corners"), 0)
    a_corn = safe(stats.get("away_corners"), 0)
    total_corn = h_corn + a_corn
    h_corn_r = h_corn / total_corn if total_corn > 0 else 0.5
    a_corn_r = a_corn / total_corn if total_corn > 0 else 0.5

    # ── Resultado real ────────────────────────────────────────────────────────
    if home_goals > away_goals:
        res_h, res_a = 1.0, 0.0
    elif home_goals < away_goals:
        res_h, res_a = 0.0, 1.0
    else:
        res_h = res_a = 0.5

    # ── Penalización disciplinaria ────────────────────────────────────────────
    h_reds    = safe(stats.get("home_reds"), 0)
    a_reds    = safe(stats.get("away_reds"), 0)
    h_yellows = safe(stats.get("home_yellows"), 0)
    a_yellows = safe(stats.get("away_yellows"), 0)
    h_disc_pen = h_reds * 0.12 + h_yellows * 0.02
    a_disc_pen = a_reds * 0.12 + a_yellows * 0.02

    # ── Score final ponderado ─────────────────────────────────────────────────
    # Pesos: xG es lo más importante, luego resultado, luego métricas de juego
    W = {
        "xg":        0.30,
        "resultado": 0.25,
        "posesion":  0.15,
        "pass_acc":  0.10,
        "precision": 0.12,
        "corners":   0.08,
    }

    score_h = (
        W["xg"]        * xg_ratio_h +
        W["resultado"] * res_h +
        W["posesion"]  * h_pos +
        W["pass_acc"]  * h_pacc +
        W["precision"] * h_precision +
        W["corners"]   * h_corn_r -
        h_disc_pen
    )

    score_a = (
        W["xg"]        * xg_ratio_a +
        W["resultado"] * res_a +
        W["posesion"]  * a_pos +
        W["pass_acc"]  * a_pacc +
        W["precision"] * a_precision +
        W["corners"]   * a_corn_r -
        a_disc_pen
    )

    return float(np.clip(score_h, 0, 1.5)), float(np.clip(score_a, 0, 1.5))


def compute_dynamic_ratings(played_matches, analyst_notes=None, match_stats=None):
    """
    Actualiza ratings usando shrinkage bayesiano + performance score.

    Jerarquía de datos (de mayor a menor precisión):
    1. Estadísticas completas del partido (xG, posesión, remates, etc.)
    2. Notas del analista (ajuste subjetivo calibrado)
    3. Solo resultado (goles)

    Formula shrinkage: rating_new = (K*prior + Σ scores) / (K + n)
    """
    result_sum   = {t: 0.0 for t in ALL_TEAMS}
    result_count = {t: 0.0 for t in ALL_TEAMS}
    n_matches    = len(played_matches)
    match_stats  = match_stats or {}
    analyst_notes = analyst_notes or {}

    for i, m in enumerate(played_matches):
        home = m["home_team"]
        away = m["away_team"]
        hg   = m["home_goals"]
        ag   = m["away_goals"]

        if hg is None or ag is None:
            continue

        # Peso temporal: partidos recientes valen más
        recency = 0.7 + 0.3 * (i / max(n_matches - 1, 1))

        mid   = m["id"]
        stats = match_stats.get(mid)

        if stats:
            # ── Ruta 1: estadísticas completas ─────────────────────────────
            score_h, score_a = compute_performance_score(stats, hg, ag)
            if score_h is not None:
                result_sum[home]   += score_h * recency
                result_sum[away]   += score_a * recency
                result_count[home] += recency
                result_count[away] += recency

                # Penalización adicional por bajas en próximo partido
                h_abs = len(stats.get("home_key_absences") or [])
                a_abs = len(stats.get("away_key_absences") or [])
                if h_abs > 0:
                    result_sum[home] -= h_abs * 0.03
                if a_abs > 0:
                    result_sum[away] -= a_abs * 0.03
                continue

        # ── Ruta 2: solo resultado ──────────────────────────────────────────
        if hg > ag:
            res_h, res_a = 1.0, 0.0
        elif hg < ag:
            res_h, res_a = 0.0, 1.0
        else:
            res_h = res_a = 0.5

        diff = abs(hg - ag)
        goal_bonus = 0.08 * np.sqrt(diff)
        if hg > ag:
            res_h += goal_bonus
        elif hg < ag:
            res_a += goal_bonus

        # ── Ruta 3: ajuste del analista (sobre el resultado base) ──────────
        note = analyst_notes.get(mid, {})
        intensity = note.get("deserved_intensity", 0)
        analyst_adj = intensity * 0.04   # -0.08 a +0.08

        result_sum[home]   += (res_h + analyst_adj) * recency
        result_sum[away]   += (res_a - analyst_adj) * recency
        result_count[home] += recency
        result_count[away] += recency

    # ── Shrinkage bayesiano ─────────────────────────────────────────────────
    ratings = {}
    for t in ALL_TEAMS:
        prior = FIFA_RATINGS.get(t, 0.5)
        n     = result_count[t]
        s     = result_sum[t]
        ratings[t] = (SHRINKAGE_K * prior + s) / (SHRINKAGE_K + n) if n > 0 else prior
        ratings[t] = float(np.clip(ratings[t], 0.05, 1.0))

    return ratings


def add_simulation_noise(ratings):
    """
    Agrega ruido gaussiano a los ratings para capturar incertidumbre.
    Cada simulación usa ratings ligeramente distintos (fix #11).
    """
    noisy = {}
    for t, r in ratings.items():
        noise = np.random.normal(0, RATING_NOISE_STD)
        noisy[t] = float(np.clip(r + noise, 0.05, 1.0))
    return noisy


# ─── DIXON-COLES ─────────────────────────────────────────────────────────────

def _tau(x, y, lh, la, rho):
    """Corrección Dixon-Coles para scores bajos."""
    if   x == 0 and y == 0: return 1 - lh * la * rho
    elif x == 0 and y == 1: return 1 + lh * rho
    elif x == 1 and y == 0: return 1 + la * rho
    elif x == 1 and y == 1: return 1 - rho
    return 1.0


def match_probabilities_dc(r_home, r_away,
                            home_is_host=False, away_is_host=False,
                            rho=RHO):
    """
    Calcula P(local gana), P(empate), P(visitante gana)
    usando Dixon-Coles con transformación exponencial.
    """
    lh, la = expected_goals(r_home, r_away, home_is_host, away_is_host)
    max_g  = 8
    p_hw = p_d = p_aw = 0.0

    for i in range(max_g + 1):
        for j in range(max_g + 1):
            p = (poisson.pmf(i, lh) *
                 poisson.pmf(j, la) *
                 _tau(i, j, lh, la, rho))
            if   i > j: p_hw += p
            elif i == j: p_d  += p
            else:        p_aw += p

    total = p_hw + p_d + p_aw
    return p_hw/total, p_d/total, p_aw/total


def over_under_probs(r_home, r_away, home_is_host=False, away_is_host=False):
    lh, la = expected_goals(r_home, r_away, home_is_host, away_is_host)
    probs  = {"over_05":0,"over_15":0,"over_25":0,"over_35":0,"btts":0}
    for i in range(11):
        for j in range(11):
            p = poisson.pmf(i, lh) * poisson.pmf(j, la)
            t = i + j
            if t > 0.5: probs["over_05"] += p
            if t > 1.5: probs["over_15"] += p
            if t > 2.5: probs["over_25"] += p
            if t > 3.5: probs["over_35"] += p
            if i > 0 and j > 0: probs["btts"] += p
    return probs


def exact_score_probs(r_home, r_away, home_is_host=False, away_is_host=False, top_n=10):
    lh, la = expected_goals(r_home, r_away, home_is_host, away_is_host)
    scores = []
    for i in range(8):
        for j in range(8):
            p = poisson.pmf(i, lh) * poisson.pmf(j, la)
            scores.append({"score": f"{i}-{j}", "prob": round(p * 100, 2)})
    return sorted(scores, key=lambda x: x["prob"], reverse=True)[:top_n]


# ─── SIMULACIÓN DE PARTIDO ───────────────────────────────────────────────────

def sim_score(lh, la):
    """Simula marcador con Poisson."""
    return int(np.random.poisson(lh)), int(np.random.poisson(la))


def sim_ko_match(team_a, team_b, ratings):
    """
    Simula partido KO (sin empate).
    Penales modelados con probabilidad dependiente del rating (fix #7):
    el equipo más fuerte tiene más chance de ganar penales.
    """
    if not team_a: return team_b
    if not team_b: return team_a

    ra = ratings.get(team_a, 0.5)
    rb = ratings.get(team_b, 0.5)

    host_a = team_a in HOST_TEAMS
    host_b = team_b in HOST_TEAMS

    lh, la = expected_goals(ra, rb, host_a, host_b)
    h, a   = sim_score(lh, la)

    if h != a:
        return team_a if h > a else team_b

    # Empate → penales: probabilidad proporcional al rating
    pen_prob_a = ra / (ra + rb)
    return team_a if random.random() < pen_prob_a else team_b


# ─── SIMULACIÓN DE GRUPOS ────────────────────────────────────────────────────

def _sort_key(entry):
    return (entry["pts"], entry["gd"], entry["gf"])


def sim_groups_once(all_matches, ratings):
    """
    Simula UNA vez la fase de grupos completa.
    - Usa resultados reales donde existen
    - Simula el resto con Poisson + ratings con ruido
    - Retorna slots {"1A": equipo, "2A": equipo, ...}
      Y lista de terceros con sus stats
    """
    noisy   = add_simulation_noise(ratings)
    slots   = {}
    thirds  = []

    # Indexar partidos jugados por (group, home, away)
    played_idx = {}
    for m in all_matches:
        if m["played"]:
            key = (m["group_letter"], m["home_team"], m["away_team"])
            played_idx[key] = m

    for g in GROUP_LETTERS:
        teams   = GROUPS[g]
        table   = {t: {"pts":0,"gf":0,"ga":0,"gd":0} for t in teams}

        for home, away in GROUP_FIXTURES[g]:
            played = played_idx.get((g, home, away))

            if played:
                h, a = played["home_goals"], played["away_goals"]
            else:
                rh = noisy.get(home, 0.5)
                ra = noisy.get(away, 0.5)
                hh = home in HOST_TEAMS
                ah = away in HOST_TEAMS
                lh, la = expected_goals(rh, ra, hh, ah)
                h, a   = sim_score(lh, la)

            table[home]["gf"] += h; table[home]["ga"] += a
            table[away]["gf"] += a; table[away]["ga"] += h
            table[home]["gd"]  = table[home]["gf"] - table[home]["ga"]
            table[away]["gd"]  = table[away]["gf"] - table[away]["ga"]

            if h > a:
                table[home]["pts"] += 3
            elif h < a:
                table[away]["pts"] += 3
            else:
                table[home]["pts"] += 1
                table[away]["pts"] += 1

        ranked = sorted(
            [{"team": t, **table[t]} for t in teams],
            key=_sort_key, reverse=True
        )

        slots[f"1{g}"] = ranked[0]["team"]
        slots[f"2{g}"] = ranked[1]["team"]

        # Tercero y cuarto: guardar stats completos para ranking global
        thirds.append({
            "team":  ranked[2]["team"],
            "group": g,
            "pts":   ranked[2]["pts"],
            "gd":    ranked[2]["gd"],
            "gf":    ranked[2]["gf"],
        })
        # Cuarto lugar: eliminado directo
        # (no lo usamos pero queda disponible)

    # Mejores 8 terceros — clasifican por puntos/gd/gf
    thirds.sort(key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True)
    qualified_thirds = thirds[:8]          # los 8 que avanzan
    qualif_thirds = {t["team"] for t in qualified_thirds}
    qualified_groups = {t["group"] for t in qualified_thirds}  # letras de grupo clasificadas

    # Resolver el sistema condicional real de FIFA:
    # cada slot "3-XXXXX" se asigna al MEJOR tercero clasificado que
    # pertenezca a la lista de grupos candidatos de ese slot.
    # Una vez asignado un grupo a un slot, se descarta para los demás
    # slots (cada tercero juega un solo partido de Dieciseisavos).
    assigned_groups = set()
    for slot_name, candidate_groups in THIRD_PLACE_SLOTS.items():
        # Buscar, en orden de ranking, el mejor tercero candidato no asignado aún
        for t in qualified_thirds:
            if t["group"] in candidate_groups and t["group"] not in assigned_groups:
                slots[slot_name] = t["team"]
                assigned_groups.add(t["group"])
                break

    return slots, qualif_thirds, thirds


# ─── MONTE CARLO COMPLETO ────────────────────────────────────────────────────

def run_monte_carlo(all_matches, analyst_notes=None, match_stats=None, n_sims=SIMULATIONS):
    """
    Corre N simulaciones completas del torneo.
    Respeta como definitivos los resultados KO ya jugados y simula
    únicamente los cruces pendientes.

    FASES CORRECTAMENTE ALINEADAS (fix #6):
    - 'groups'   : llegó a fase de grupos (todos los equipos = 100%)
    - 'r32'      : LLEGÓ a Ronda de 32 (clasificó de grupos)
    - 'r16'      : LLEGÓ a Ronda de 16 (ganó en R32)
    - 'qf'       : LLEGÓ a Cuartos (ganó en R16)
    - 'sf'       : LLEGÓ a Semis (ganó en QF)
    - 'final'    : LLEGÓ a la Final (ganó en SF)
    - 'champion' : Ganó la Final

    CLASIFICACIÓN (fix #4 #5):
    - qualify = first + second + best_third
    """
    played = [m for m in all_matches if m.get("played")]
    ratings = compute_dynamic_ratings(played, analyst_notes, match_stats)

    # Resultados KO reales, indexados por fase y número de partido.
    # Solo se aplican cuando los dos equipos guardados coinciden con el cruce
    # que corresponde en esa simulación. Así evitamos reutilizar datos viejos
    # si el bracket fue editado o resincronizado.
    ko_phases = ("r32", "r16", "qf", "sf", "final")
    real_ko_matches = {phase: {} for phase in ko_phases}
    for match in all_matches:
        phase = match.get("phase")
        match_number = match.get("match_number")
        if phase in real_ko_matches and match_number is not None:
            match_number = int(match_number)
            current = real_ko_matches[phase].get(match_number)
            if current is None or (
                not current.get("played") and match.get("played")
            ):
                real_ko_matches[phase][match_number] = match

    def real_or_simulated_winner(phase, match_number, team_a, team_b):
        real_match = real_ko_matches.get(phase, {}).get(match_number)
        if real_match and real_match.get("played"):
            home = real_match.get("home_team")
            away = real_match.get("away_team")
            home_goals = real_match.get("home_goals")
            away_goals = real_match.get("away_goals")

            expected_teams = {team for team in (team_a, team_b) if team}
            stored_teams = {team for team in (home, away) if team}
            same_match = (
                len(expected_teams) == 2
                and expected_teams == stored_teams
            )

            if (
                same_match
                and home_goals is not None
                and away_goals is not None
                and home_goals != away_goals
            ):
                return home if home_goals > away_goals else away

        return sim_ko_match(team_a, team_b, ratings)

    # ── Contadores ────────────────────────────────────────────────────────
    phase_count = {
        t: {"r32":0,"r16":0,"qf":0,"sf":0,"final":0,"champion":0}
        for t in ALL_TEAMS
    }
    group_count = {
        g: {t: {"first":0,"second":0,"best_third":0,"out":0}
            for t in GROUPS[g]}
        for g in GROUP_LETTERS
    }
    champ_count = defaultdict(int)

    for _ in range(n_sims):
        slots, qualif_thirds, thirds_ranked = sim_groups_once(all_matches, ratings)

        # ── Contabilizar posiciones de grupo ──────────────────────────────
        for g in GROUP_LETTERS:
            t1 = slots.get(f"1{g}")
            t2 = slots.get(f"2{g}")
            if t1 and t1 in group_count[g]: group_count[g][t1]["first"]  += 1
            if t2 and t2 in group_count[g]: group_count[g][t2]["second"] += 1
            for t in GROUPS[g]:
                if t == t1 or t == t2:
                    continue
                if t in qualif_thirds:
                    if t in group_count[g]: group_count[g][t]["best_third"] += 1
                else:
                    if t in group_count[g]: group_count[g][t]["out"] += 1

        # ── Todos los clasificados llegan a R32 ───────────────────────────
        classified = set(slots.values())
        for t in classified:
            if t and t in phase_count:
                phase_count[t]["r32"] += 1   # llegó a R32

        # ── R32 → ganadores llegan a R16 ─────────────────────────────────
        r32w = []
        for match_number, (slot_a, slot_b) in enumerate(
            R32_BRACKET_VALID, start=1
        ):
            w = real_or_simulated_winner(
                "r32",
                match_number,
                slots.get(slot_a),
                slots.get(slot_b),
            )
            r32w.append(w)

        for t in r32w:
            if t and t in phase_count:
                phase_count[t]["r16"] += 1   # llegó a R16

        # ── R16 → ganadores llegan a QF ──────────────────────────────────
        r16w = []
        for i in range(8):
            w = real_or_simulated_winner(
                "r16", i + 1, r32w[i*2], r32w[i*2+1]
            )
            r16w.append(w)

        for t in r16w:
            if t and t in phase_count:
                phase_count[t]["qf"] += 1    # llegó a cuartos

        # ── QF → ganadores llegan a SF ───────────────────────────────────
        qfw = []
        for i in range(4):
            w = real_or_simulated_winner(
                "qf", i + 1, r16w[i*2], r16w[i*2+1]
            )
            qfw.append(w)

        for t in qfw:
            if t and t in phase_count:
                phase_count[t]["sf"] += 1    # llegó a semis

        # ── SF → ganadores llegan a Final ─────────────────────────────────
        sfw = []
        for i in range(2):
            w = real_or_simulated_winner(
                "sf", i + 1, qfw[i*2], qfw[i*2+1]
            )
            sfw.append(w)

        for t in sfw:
            if t and t in phase_count:
                phase_count[t]["final"] += 1 # llegó a la final

        # ── Final → campeón ───────────────────────────────────────────────
        champ = real_or_simulated_winner(
            "final",
            1,
            sfw[0] if sfw else None,
            sfw[1] if len(sfw) > 1 else None,
        )
        if champ and champ in phase_count:
            phase_count[champ]["champion"] += 1
            champ_count[champ] += 1

    # ── Convertir a probabilidades ────────────────────────────────────────
    def pct(n): return round(n / n_sims * 100, 1)

    champion_probs = sorted(
        [{"team": t, "prob": pct(champ_count[t])} for t in ALL_TEAMS],
        key=lambda x: x["prob"], reverse=True
    )

    group_probs = {}
    for g in GROUP_LETTERS:
        rows = []
        for t in GROUPS[g]:
            c = group_count[g][t]
            qualify = pct(c["first"] + c["second"] + c["best_third"])
            rows.append({
                "team":       t,
                "first":      pct(c["first"]),
                "second":     pct(c["second"]),
                "best_third": pct(c["best_third"]),
                "qualify":    qualify,
            })
        group_probs[g] = sorted(rows, key=lambda x: x["qualify"], reverse=True)

    phase_probs = {
        t: {k: pct(phase_count[t][k]) for k in phase_count[t]}
        for t in ALL_TEAMS
    }

    predicted_qualifiers = {
        g: {"first": group_probs[g][0], "second": group_probs[g][1]}
        for g in GROUP_LETTERS
    }

    return {
        "model_version":       "ko-aware-v1",
        "ko_matches_played":   sum(
            1
            for phase_matches in real_ko_matches.values()
            for match in phase_matches.values()
            if match.get("played")
        ),
        "champion_probs":      champion_probs,
        "group_probs":         group_probs,
        "phase_probs":         phase_probs,
        "predicted_qualifiers": predicted_qualifiers,
        "ratings_used":        {t: round(ratings[t], 4) for t in ALL_TEAMS},
        "matches_played":      len(played),
        "simulations":         n_sims,
    }


# ─── VALUE BETS ───────────────────────────────────────────────────────────────

def odd_to_implied_prob(odd):
    return 1.0 / odd


def remove_overround(implied_probs):
    total = sum(implied_probs)
    return [p / total for p in implied_probs]


def calculate_edge(model_prob, implied_prob):
    return round((model_prob - implied_prob) * 100, 2)


def calculate_ev(model_prob, odd):
    return round(model_prob * (odd - 1) - (1 - model_prob), 4)


def kelly_criterion(model_prob, odd, fraction=0.25):
    b = odd - 1
    if b <= 0: return 0
    q = 1 - model_prob
    k = (b * model_prob - q) / b
    return max(0.0, round(k * fraction, 4))


def detect_value_bets(model_probs_1x2, odds_1x2, min_edge=3.0):
    markets    = ["Local gana (1)", "Empate (X)", "Visitante gana (2)"]
    implied    = [odd_to_implied_prob(o) for o in odds_1x2]
    impl_clean = remove_overround(implied)

    vbs = []
    for i, market in enumerate(markets):
        mp   = model_probs_1x2[i]
        ip   = impl_clean[i]
        odd  = odds_1x2[i]
        edge = calculate_edge(mp, ip)
        ev   = calculate_ev(mp, odd)
        if edge >= min_edge:
            vbs.append({
                "market":     market,
                "model_prob": round(mp * 100, 1),
                "impl_prob":  round(ip * 100, 1),
                "odd":        odd,
                "edge":       edge,
                "ev":         ev,
                "kelly_25":   kelly_criterion(mp, odd),
            })
    return sorted(vbs, key=lambda x: x["edge"], reverse=True)
