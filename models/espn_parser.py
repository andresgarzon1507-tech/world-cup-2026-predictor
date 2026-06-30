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

from difflib import SequenceMatcher
import re
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
    "cura ao":               "curacao",
    "curaa ao":              "curacao",
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
    # Códigos FIFA y abreviaturas habituales de ESPN.
    "por":                    "portugal",
    "col":                    "colombia",
    "bra":                    "brazil",
    "jpn":                    "japan",
    "ger":                    "germany",
    "deu":                    "germany",
    "par":                    "paraguay",
}


def normalize_team_name(name: str) -> str:
    """Quita acentos, uniforma espacios/signos y resuelve alias."""
    s = unicodedata.normalize("NFD", str(name or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    s = " ".join(s.split())
    return TEAM_NAME_ALIASES.get(s, s)


def teams_match(name_a: str, name_b: str) -> bool:
    """Compara dos nombres de equipo de forma tolerante."""
    a, b = normalize_team_name(name_a), normalize_team_name(name_b)
    return a == b or a in b or b in a


# ── Parseo del scoreboard (lista de partidos) ─────────────────────────────────

# Mapeo de estados ESPN -> estados que ya maneja el resto de tu app
NOT_FINISHED_STATES = {"STATUS_SCHEDULED", "STATUS_POSTPONED", "STATUS_CANCELED"}


def _competitor_team_names(competitor: dict) -> list[str]:
    """Nombres largo/corto, slug y código FIFA informados por ESPN."""
    team = competitor.get("team", {})
    values = [
        team.get("displayName"),
        team.get("shortDisplayName"),
        team.get("name"),
        team.get("location"),
        team.get("abbreviation"),
        team.get("slug"),
    ]
    return list(dict.fromkeys(value for value in values if value))


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

            home_names = _competitor_team_names(home)
            away_names = _competitor_team_names(away)
            notes = comp.get("notes") or []
            competition_type = comp.get("type") or {}
            type_text = (
                competition_type.get("text", "")
                if isinstance(competition_type, dict)
                else str(competition_type)
            )
            note_text = (
                notes[0].get("headline", "")
                if notes and isinstance(notes[0], dict)
                else ""
            )
            phase = (
                type_text
                or note_text
                or comp.get("altGameNote", "")
                or ev.get("season", {}).get("slug", "")
            )

            fixtures.append({
                "fixture_id":  ev.get("id"),
                "date":        ev.get("date"),
                "status":      "FT" if completed else ("NS" if status_name in NOT_FINISHED_STATES else "LIVE"),
                "round":       phase,
                "home_team":   home_names[0] if home_names else "",
                "away_team":   away_names[0] if away_names else "",
                "home_aliases": home_names,
                "away_aliases": away_names,
                "home_goals":  int(home["score"]) if home.get("score") not in (None, "") else None,
                "away_goals":  int(away["score"]) if away.get("score") not in (None, "") else None,
            })
        except (KeyError, IndexError, ValueError, TypeError):
            # Si un evento individual viene con estructura inesperada,
            # lo saltamos en vez de romper todo el parseo.
            continue

    return fixtures


def find_fixture(home_team: str, away_team: str, fixtures: list[dict]) -> Optional[dict]:
    """Busca el fixture usando nombres largos, cortos y códigos FIFA."""
    for fixture in fixtures:
        home_names = fixture.get("home_aliases") or [fixture.get("home_team", "")]
        away_names = fixture.get("away_aliases") or [fixture.get("away_team", "")]
        direct = (
            any(teams_match(home_team, name) for name in home_names)
            and any(teams_match(away_team, name) for name in away_names)
        )
        reverse = (
            any(teams_match(home_team, name) for name in away_names)
            and any(teams_match(away_team, name) for name in home_names)
        )
        if direct or reverse:
            return fixture
    return None


def fixture_similarity(home_team: str, away_team: str, fixture: dict) -> float:
    """Puntúa de 0 a 1 qué tan parecido es un evento al partido buscado."""
    def best(local_name, candidates):
        local = normalize_team_name(local_name)
        return max(
            (
                SequenceMatcher(None, local, normalize_team_name(name)).ratio()
                for name in candidates if name
            ),
            default=0.0,
        )

    home_names = fixture.get("home_aliases") or [fixture.get("home_team", "")]
    away_names = fixture.get("away_aliases") or [fixture.get("away_team", "")]
    direct = (best(home_team, home_names) + best(away_team, away_names)) / 2
    reverse = (best(home_team, away_names) + best(away_team, home_names)) / 2
    return max(direct, reverse)


def closest_fixtures(
    home_team: str,
    away_team: str,
    fixtures: list[dict],
    limit: int = 5,
) -> list[dict]:
    """Devuelve los candidatos más cercanos con score de similitud."""
    ranked = []
    for fixture in fixtures:
        candidate = dict(fixture)
        candidate["similarity"] = fixture_similarity(
            home_team, away_team, fixture
        )
        ranked.append(candidate)
    return sorted(
        ranked,
        key=lambda item: item["similarity"],
        reverse=True,
    )[:limit]


# ── Parseo de estadísticas (boxscore) ─────────────────────────────────────────

# Mapeo de nombres de estadística de ESPN -> campos que usa tu app.
# Se intentan varias claves posibles porque la nomenclatura de ESPN
# puede variar entre "name", "label" o "abbreviation" según el deporte.
STAT_FIELD_MAP = {
    "totalShots":      "shots",
    "shotsTotal":      "shots",
    "shotsOnTarget":   "shots_on",
    "possessionPct":   "possession",
    "possession":      "possession",
    "wonCorners":      "corners",
    "corners":         "corners",
    "foulsCommitted":  "fouls",
    "fouls":           "fouls",
    "yellowCards":     "yellows",
    "redCards":        "reds",
    "offsides":        "offsides",
    "totalPasses":     "passes",
    "passes":          "passes",
    "passPct":         "pass_acc",
    "passAccuracy":    "pass_acc",
}


def _extract_team_stats(team_block: dict) -> tuple[dict, bool]:
    """Extrae estadísticas y señala si ESPN informó alguna conocida."""
    result = {value: 0 for value in STAT_FIELD_MAP.values()}
    found_known = False

    stats_list = team_block.get("statistics", team_block.get("stats", []))
    for stat in stats_list:
        name = (
            stat.get("name")
            or stat.get("label")
            or stat.get("abbreviation")
            or ""
        )
        if name not in STAT_FIELD_MAP:
            continue

        found_known = True
        field = STAT_FIELD_MAP[name]
        raw_value = stat.get("displayValue", stat.get("value", 0))
        try:
            cleaned = str(raw_value).replace("%", "").replace(",", "").strip()
            result[field] = float(cleaned)
        except (ValueError, TypeError):
            result[field] = 0
    return result, found_known


def parse_statistics(summary_raw: dict, home_team_name: str) -> Optional[dict]:
    """
    Convierte el boxscore del /summary al formato de save_match_stats()
    de tu app. Devuelve None si no hay boxscore disponible (partido
    todavía no jugado, o ESPN no lo publicó).
    """
    if not summary_raw:
        return None

    # ESPN alterna entre boxscore.teams y header.competitions.competitors.
    boxscore = summary_raw.get("boxscore") or {}
    teams_block = boxscore.get("teams", [])
    if len(teams_block) < 2:
        competitions = summary_raw.get("header", {}).get("competitions", [])
        teams_block = (
            competitions[0].get("competitors", [])
            if competitions
            else []
        )
    if len(teams_block) < 2:
        return None

    # Determinar cuál bloque es local y cuál visitante comparando nombres
    def block_team_name(block):
        return block.get("team", {}).get("displayName", "")

    if teams_match(home_team_name, block_team_name(teams_block[0])):
        home_block, away_block = teams_block[0], teams_block[1]
    else:
        home_block, away_block = teams_block[1], teams_block[0]

    home_stats, home_has_stats = _extract_team_stats(home_block)
    away_stats, away_has_stats = _extract_team_stats(away_block)
    if not home_has_stats and not away_has_stats:
        return None

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
