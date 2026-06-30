# models/espn_integration.py
# Módulo de alto nivel: orquesta espn_api + espn_cache + espn_parser
# y expone EXACTAMENTE la misma interfaz pública que tenía
# models/api_football.py, para no romper nada en app.py.
#
# No requiere API key. Streamlit nunca debe importar espn_api ni
# espn_parser directamente — solo este módulo.

from typing import Optional
from models import espn_cache, espn_parser


def api_football_configured() -> bool:
    """
    Se mantiene el mismo nombre de función que usaba app.py para no
    tener que tocar el resto del código. ESPN no requiere key, así
    que esta función siempre devuelve True — la integración está
    'configurada' por definición, no hay nada que el usuario deba
    completar en .env para esta fuente de datos.
    """
    return True


def get_world_cup_fixtures() -> tuple[list[dict], str]:
    """
    Trae todos los partidos del Mundial 2026 (formato ya parseado,
    listo para usar). Cacheado para no golpear ESPN repetidamente.
    """
    raw, msg = espn_cache.get_cached_scoreboard()
    if not raw:
        return [], msg
    fixtures = espn_parser.parse_scoreboard(raw)
    return fixtures, f"✅ {len(fixtures)} partidos obtenidos de ESPN"


def find_fixture_id(home_team: str, away_team: str, fixtures: Optional[list] = None) -> Optional[str]:
    """Busca el fixture_id de un partido por nombre de equipos."""
    if fixtures is None:
        fixtures, _ = get_world_cup_fixtures()
    match = espn_parser.find_fixture(home_team, away_team, fixtures)
    return match["fixture_id"] if match else None


def get_fixture_statistics(fixture_id: str, home_team_name: str = "") -> tuple[Optional[dict], str]:
    """
    Trae estadísticas completas de un partido (remates, posesión,
    tarjetas, etc.) ya mapeadas a los campos de tu base de datos.
    """
    raw, msg = espn_cache.get_cached_summary(fixture_id)
    if not raw:
        return None, msg
    stats = espn_parser.parse_statistics(raw, home_team_name)
    if not stats:
        return None, "ℹ️ Sin boxscore disponible para este partido todavía"
    return stats, "✅ Estadísticas obtenidas"


def get_fixture_lineups(fixture_id: str, home_team_name: str = "") -> tuple[Optional[dict], str]:
    """Trae formación de ambos equipos."""
    raw, msg = espn_cache.get_cached_summary(fixture_id)
    if not raw:
        return None, msg
    lineups = espn_parser.parse_lineups(raw, home_team_name)
    if not lineups:
        return None, "ℹ️ Sin alineaciones disponibles para este partido todavía"
    return lineups, "✅ Alineaciones obtenidas"


def get_full_match_data(home_team: str, away_team: str, fixtures: Optional[list] = None) -> tuple[Optional[dict], str]:
    """
    Función de alto nivel: dado el nombre de dos equipos, busca el
    partido en ESPN y trae estadísticas + formación en un único dict
    listo para pasarle directo a save_match_stats().

    Mantiene la misma firma e interfaz que tenía la versión de
    API-Football para no romper app.py.
    """
    if fixtures is None:
        fixtures, fetch_msg = get_world_cup_fixtures()
        if not fixtures:
            return None, fetch_msg

    match = espn_parser.find_fixture(home_team, away_team, fixtures)
    if not match:
        return None, (
            f"❌ No se encontró el partido {home_team} vs {away_team} en ESPN. "
            f"Puede ser una diferencia de nombre (revisá TEAM_NAME_ALIASES "
            f"en espn_parser.py) o que el partido todavía no esté en el calendario."
        )

    fixture_id = match["fixture_id"]
    status     = match["status"]

    if status == "NS":
        return None, (
            f"ℹ️ El partido {home_team} vs {away_team} todavía no se jugó. "
            f"Las estadísticas estarán disponibles cuando termine."
        )

    stats, stats_msg = get_fixture_statistics(fixture_id, home_team)
    if not stats:
        return None, f"⚠️ Partido encontrado pero sin estadísticas todavía. {stats_msg}"

    lineups, _ = get_fixture_lineups(fixture_id, home_team)
    if lineups:
        stats.update(lineups)

    return stats, f"✅ Datos completos de {home_team} vs {away_team} obtenidos de ESPN"


def get_remaining_requests() -> str:
    """
    ESPN no tiene límite de requests documentado ni key, así que esta
    función solo existe para mantener compatibilidad con el código que
    ya mostraba este mensaje en el sidebar/UI.
    """
    return "✅ ESPN (sin límite de requests, no requiere key)"
