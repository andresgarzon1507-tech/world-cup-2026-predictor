# models/espn_parser.py
# Capa de parseo: convierte el JSON crudo de ESPN al formato que usa
# tu aplicación (los mismos campos que ya tenía api_football.py, para
# no romper nada del resto del proyecto).
#
# IMPORTANTE: este archivo es DEFENSIVO a propósito. La API de ESPN no
# es oficial ni está documentada formalmente, así que cada función
# intenta varias rutas posibles dentro del JSON y devuelve None/0 en
# vez de lanzar una excepción si algo no está donde se esperaba.
# Si ESPN cambia su formato, ajustá solo este archivo — el resto de
# la app nunca debería enterarse.

from typing import Optional
import unicodedata


# ── Normalización y alias de nombres de equipo ────────────────────────────────
# Tu base usa nombres en español; ESPN devuelve nombres en inglés.
# Tu base de datos usa nombres en español; ESPN devuelve nombres en inglés.
# Tabla completa para los 48 equipos del Mundial 2026 — solo se listan
# los que difieren significativamente del español (los que coinciden,
# como "Argentina" o "Brasil", no necesitan alias).
TEAM_NAME_ALIASES = {
    "alemania":              "germany",
    "arabia saudi":          "saudi arabia",
    "arabia saudita":        "saudi arabia",
    "argelia":               "algeria",
    "austria":               "austria",
    "belgica":               "belgium",
    "bosnia y herzegovina":  "bosnia-herzegovina",
    "brasil":                "brazil",
    "cabo verde":            "cape verde",
    "canada":                "canada",
    "chequia":               "czechia",
    "republica checa":       "czechia",
    "congo dr":              "dr congo",
    "corea del sur":         "south korea",
    "costa de marfil":       "ivory coast",
    "croacia":               "croatia",
    "curazao":               "curacao",
    "egipto":                "egypt",
    "escocia":               "scotland",
    "espana":                "spain",
    "estados unidos":        "united states",
    "francia":               "france",
    "haiti":                 "haiti",
    "ir iran":               "iran",
    "iran":                  "iran",
    "inglaterra":            "england",
    "japon":                 "japan",
    "jordania":              "jordan",
    "marruecos":             "morocco",
    "mexico":                "mexico",
    "noruega":               "norway",
    "nueva zelanda":         "new zealand",
    "panama":                "panama",
    "paraguay":              "paraguay",
    "paises bajos":          "netherlands",
    "portugal":              "portugal",
    "qatar":                 "qatar",
    "senegal":               "senegal",
    "sudafrica":             "south africa",
    "suecia":                "sweden",
    "suiza":                 "switzerland",
    "turquia":               "turkiye",
    "tunez":                 "tunisia",
    "uruguay":               "uruguay",
    "uzbekistan":            "uzbekistan",
}


def normalize_team_name(name: str) -> str:
    """Quita acentos, pasa a minúsculas y resuelve alias conocidos."""
    s = unicodedata.normalize("NFD", name)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().strip()
    return TEAM_NAME_ALIASES.get(s, s)


def teams_match(name_a: str, name_b: str) -> bool:
    """Compara dos nombres de equipo de forma tolerante."""
    a, b = normalize_team_name(name_a), normalize_team_name(name_b)
    return a == b or a in b or b in a


# ── Parseo del scoreboard (lista de partidos) ─────────────────────────────────

# Mapeo de estados ESPN -> estados que ya maneja el resto de tu app
NOT_FINISHED_STATES = {"STATUS_SCHEDULED", "STATUS_POSTPONED", "STATUS_CANCELED"}


def parse_scoreboard(raw: dict) -> list[dict]:
    """
    Convierte el JSON crudo de /scoreboard en una lista de partidos
    con el formato esperado por el resto de la app:
        fixture_id, date, status, round, home_team, away_team,
        home_goals, away_goals
    """
    if not raw:
        return []

    events = raw.get("events", [])
    fixtures = []

    for ev in events:
        try:
            comp = ev["competitions"][0]
            status_type = comp.get("status", {}).get("type", {})
            status_name = status_type.get("name", "")
            completed   = status_type.get("completed", False)

            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)

            if not home or not away:
                continue

            fixtures.append({
                "fixture_id":  ev.get("id"),
                "date":        ev.get("date"),
                "status":      "FT" if completed else ("NS" if status_name in NOT_FINISHED_STATES else "LIVE"),
                "round":       ev.get("season", {}).get("slug", comp.get("altGameNote", "")),
                "home_team":   home.get("team", {}).get("displayName", ""),
                "away_team":   away.get("team", {}).get("displayName", ""),
                "home_goals":  int(home["score"]) if home.get("score") not in (None, "") else None,
                "away_goals":  int(away["score"]) if away.get("score") not in (None, "") else None,
            })
        except (KeyError, IndexError, ValueError, TypeError):
            # Si un evento individual viene con estructura inesperada,
            # lo saltamos en vez de romper todo el parseo.
            continue

    return fixtures


def find_fixture(home_team: str, away_team: str, fixtures: list[dict]) -> Optional[dict]:
    """Busca el fixture que coincide con los dos equipos dados."""
    for f in fixtures:
        if teams_match(home_team, f["home_team"]) and teams_match(away_team, f["away_team"]):
            return f
    return None


# ── Parseo de estadísticas (boxscore) ─────────────────────────────────────────

# Mapeo de nombres de estadística de ESPN -> campos que usa tu app.
# Se intentan varias claves posibles porque la nomenclatura de ESPN
# puede variar entre "name", "label" o "abbreviation" según el deporte.
STAT_FIELD_MAP = {
    "totalShots":      "shots",
    "shotsOnTarget":   "shots_on",
    "possessionPct":   "possession",
    "wonCorners":      "corners",
    "foulsCommitted":  "fouls",
    "yellowCards":     "yellows",
    "redCards":        "reds",
    "offsides":        "offsides",
    "totalPasses":     "passes",
    "passPct":         "pass_acc",
}


def _extract_team_stats(team_block: dict) -> dict:
    """
    Extrae las estadísticas de un equipo desde un bloque del boxscore.
    Soporta tanto el formato 'statistics' (lista de {name, displayValue})
    visto en el scoreboard, como variantes con 'stats' o 'displayValue'.
    """
    result = {v: 0 for v in STAT_FIELD_MAP.values()}

    stats_list = team_block.get("statistics", team_block.get("stats", []))
    for stat in stats_list:
        name = stat.get("name") or stat.get("abbreviation") or ""
        if name in STAT_FIELD_MAP:
            field = STAT_FIELD_MAP[name]
            raw_val = stat.get("displayValue", stat.get("value", 0))
            try:
                result[field] = float(raw_val)
            except (ValueError, TypeError):
                result[field] = 0
    return result


def parse_statistics(summary_raw: dict, home_team_name: str) -> Optional[dict]:
    """
    Convierte el boxscore del /summary al formato de save_match_stats()
    de tu app. Devuelve None si no hay boxscore disponible (partido
    todavía no jugado, o ESPN no lo publicó).
    """
    if not summary_raw:
        return None

    # El boxscore puede venir directo, o anidado distinto según el deporte/liga.
    boxscore = summary_raw.get("boxscore")
    if not boxscore:
        return None

    teams_block = boxscore.get("teams", [])
    if len(teams_block) < 2:
        return None

    # Determinar cuál bloque es local y cuál visitante comparando nombres
    def block_team_name(block):
        return block.get("team", {}).get("displayName", "")

    if teams_match(home_team_name, block_team_name(teams_block[0])):
        home_block, away_block = teams_block[0], teams_block[1]
    else:
        home_block, away_block = teams_block[1], teams_block[0]

    home_stats = _extract_team_stats(home_block)
    away_stats = _extract_team_stats(away_block)

    return {
        "home_shots":      int(home_stats["shots"]),
        "away_shots":      int(away_stats["shots"]),
        "home_shots_on":   int(home_stats["shots_on"]),
        "away_shots_on":   int(away_stats["shots_on"]),
        "home_possession": home_stats["possession"],
        "away_possession": away_stats["possession"],
        "home_passes":     int(home_stats["passes"]),
        "away_passes":     int(away_stats["passes"]),
        "home_pass_acc":   home_stats["pass_acc"],
        "away_pass_acc":   away_stats["pass_acc"],
        "home_fouls":      int(home_stats["fouls"]),
        "away_fouls":      int(away_stats["fouls"]),
        "home_yellows":    int(home_stats["yellows"]),
        "away_yellows":    int(away_stats["yellows"]),
        "home_reds":       int(home_stats["reds"]),
        "away_reds":       int(away_stats["reds"]),
        "home_offsides":   int(home_stats["offsides"]),
        "away_offsides":   int(away_stats["offsides"]),
        "home_corners":    int(home_stats["corners"]),
        "away_corners":    int(away_stats["corners"]),
    }


# ── Parseo de alineaciones ─────────────────────────────────────────────────────

def parse_lineups(summary_raw: dict, home_team_name: str) -> Optional[dict]:
    """
    Extrae formación de ambos equipos desde 'rosters' del /summary.
    Devuelve None si no está disponible.
    """
    if not summary_raw:
        return None

    rosters = summary_raw.get("rosters")
    if not rosters or len(rosters) < 2:
        return None

    def team_name(block):
        return block.get("team", {}).get("displayName", "")

    if teams_match(home_team_name, team_name(rosters[0])):
        home_block, away_block = rosters[0], rosters[1]
    else:
        home_block, away_block = rosters[1], rosters[0]

    return {
        "home_formation": home_block.get("formation", ""),
        "away_formation": away_block.get("formation", ""),
    }


# ── Parseo de eventos clave (goles, tarjetas) ─────────────────────────────────

def parse_key_events(summary_raw: dict) -> list[dict]:
    """
    Extrae la lista de eventos clave (goles, tarjetas, etc.) con minuto,
    tipo, equipo y jugador. Devuelve lista vacía si no hay datos.
    """
    if not summary_raw:
        return []

    events_raw = summary_raw.get("keyEvents", [])
    events = []
    for e in events_raw:
        try:
            events.append({
                "minute":      e.get("clock", {}).get("displayValue", ""),
                "type":        e.get("type", {}).get("text", ""),
                "team_id":     e.get("team", {}).get("id", ""),
                "player":      (e.get("athletesInvolved") or [{}])[0].get("displayName", ""),
                "description": e.get("type", {}).get("text", ""),
            })
        except (KeyError, IndexError, TypeError):
            continue
    return events
