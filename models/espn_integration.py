# models/espn_integration.py
# Orquesta transporte, caché y parseo de ESPN sin alterar la base de datos.

from datetime import datetime, timedelta
from typing import Optional

from models import espn_api, espn_cache, espn_parser


TOURNAMENT_START = "20260611"
TOURNAMENT_END = "20260719"


def api_football_configured() -> bool:
    """ESPN no requiere API key."""
    return True


def get_world_cup_fixtures() -> tuple[list[dict], str]:
    """Trae y parsea el calendario cacheado del Mundial 2026."""
    raw, msg = espn_cache.get_cached_scoreboard()
    if not raw:
        return [], msg
    fixtures = espn_parser.parse_scoreboard(raw)
    return fixtures, f"{len(fixtures)} partidos obtenidos de ESPN"


def find_fixture_id(
    home_team: str,
    away_team: str,
    fixtures: Optional[list] = None,
) -> Optional[str]:
    """Busca el fixture_id por nombres de equipos."""
    if fixtures is None:
        fixtures, _ = get_world_cup_fixtures()
    match = espn_parser.find_fixture(home_team, away_team, fixtures)
    return match["fixture_id"] if match else None


def get_fixture_statistics(
    fixture_id: str,
    home_team_name: str = "",
) -> tuple[Optional[dict], str]:
    """Trae las estadísticas mapeadas al formato de la app."""
    raw, msg = espn_cache.get_cached_summary(fixture_id)
    if not raw:
        return None, msg
    stats = espn_parser.parse_statistics(raw, home_team_name)
    if not stats:
        return None, "Sin boxscore disponible para este partido todavía"
    return stats, "Estadísticas obtenidas"


def get_fixture_lineups(
    fixture_id: str,
    home_team_name: str = "",
) -> tuple[Optional[dict], str]:
    """Trae las formaciones de ambos equipos."""
    raw, msg = espn_cache.get_cached_summary(fixture_id)
    if not raw:
        return None, msg
    lineups = espn_parser.parse_lineups(raw, home_team_name)
    if not lineups:
        return None, "Sin alineaciones disponibles para este partido todavía"
    return lineups, "Alineaciones obtenidas"


def _search_range(match_date=None) -> tuple[str, str]:
    """Usa ±3 días con fecha local o todo el torneo cuando no existe."""
    if match_date:
        raw_date = str(match_date).strip()
        for value, fmt in (
            (raw_date[:10], "%Y-%m-%d"),
            (raw_date[:8], "%Y%m%d"),
        ):
            try:
                parsed = datetime.strptime(value, fmt)
                return (
                    (parsed - timedelta(days=3)).strftime("%Y%m%d"),
                    (parsed + timedelta(days=3)).strftime("%Y%m%d"),
                )
            except ValueError:
                continue
    return TOURNAMENT_START, TOURNAMENT_END


def _candidate_summary(candidate: dict) -> str:
    score = ""
    if candidate.get("home_goals") is not None:
        score = f" {candidate['home_goals']}-{candidate['away_goals']}"
    date = str(candidate.get("date") or "sin fecha")[:10]
    return (
        f"ID {candidate.get('fixture_id')} | {date} | "
        f"{candidate.get('home_team')} vs {candidate.get('away_team')}{score} | "
        f"{candidate.get('round') or 'fase sin informar'} | "
        f"{candidate.get('status')} | similitud "
        f"{candidate.get('similarity', 0):.0%}"
    )


def find_espn_event_for_match(
    home_team: str,
    away_team: str,
    match_date=None,
    phase: Optional[str] = None,
    fixtures: Optional[list] = None,
) -> dict:
    """Busca el evento y devuelve diagnóstico y candidatos si no coincide."""
    if fixtures is None:
        initial_fixtures, _ = get_world_cup_fixtures()
    else:
        initial_fixtures = list(fixtures)

    date_from, date_to = _search_range(match_date)
    match = espn_parser.find_fixture(
        home_team, away_team, initial_fixtures
    )
    if match:
        return {
            "event": match,
            "candidates": [],
            "range": (date_from, date_to),
            "events_found": len(initial_fixtures),
            "phase": phase,
        }

    # El rango largo puede ser parcial en ESPN. El respaldo por día recorre
    # grupos y todas las fases KO sin depender de la jornada actual.
    raw, fetch_message = espn_api.fetch_scoreboards_by_day(
        date_from, date_to
    )
    dated_fixtures = espn_parser.parse_scoreboard(raw or {})

    combined = {}
    for fixture in initial_fixtures + dated_fixtures:
        key = fixture.get("fixture_id") or (
            fixture.get("date"),
            fixture.get("home_team"),
            fixture.get("away_team"),
        )
        combined[key] = fixture
    all_fixtures = list(combined.values())

    match = espn_parser.find_fixture(home_team, away_team, all_fixtures)
    candidates = espn_parser.closest_fixtures(
        home_team, away_team, all_fixtures
    )
    return {
        "event": match,
        "candidates": candidates,
        "range": (date_from, date_to),
        "events_found": len(all_fixtures),
        "phase": phase,
        "fetch_message": fetch_message,
    }


def get_full_match_data(
    home_team: str,
    away_team: str,
    fixtures: Optional[list] = None,
    match_date=None,
    phase: Optional[str] = None,
) -> tuple[Optional[dict], str]:
    """Busca el evento y obtiene estadísticas y formaciones."""
    search = find_espn_event_for_match(
        home_team,
        away_team,
        match_date=match_date,
        phase=phase,
        fixtures=fixtures,
    )
    match = search["event"]

    if not match:
        date_from, date_to = search["range"]
        candidates = search.get("candidates") or []
        candidate_text = ""
        if candidates:
            candidate_text = "\n\nCandidatos cercanos:\n" + "\n".join(
                f"- {_candidate_summary(candidate)}"
                for candidate in candidates
            )
        return None, (
            f"No se encontró el partido {home_team} vs {away_team} en ESPN. "
            f"Rango consultado: {date_from}–{date_to}. "
            f"Eventos encontrados: {search['events_found']}."
            f"{candidate_text}"
        )

    fixture_id = match["fixture_id"]
    status = match["status"]
    date_from, date_to = search["range"]
    diagnostic = (
        f"Rango consultado: {date_from}–{date_to}. "
        f"Eventos encontrados: {search['events_found']}."
    )

    if status == "NS":
        return None, (
            f"El partido {home_team} vs {away_team} fue encontrado en ESPN "
            f"(ID {fixture_id}), pero todavía está pendiente y no tiene "
            f"estadísticas disponibles. {diagnostic}"
        )

    stats, stats_msg = get_fixture_statistics(fixture_id, home_team)
    if not stats:
        return None, (
            "El partido fue encontrado, pero ESPN no tiene "
            f"boxscore/statistics disponibles todavía. {stats_msg}. "
            f"{diagnostic}"
        )

    lineups, _ = get_fixture_lineups(fixture_id, home_team)
    if lineups:
        stats.update(lineups)

    return (
        stats,
        f"Datos completos de {home_team} vs {away_team} obtenidos de ESPN. "
        f"{diagnostic}",
    )


def get_remaining_requests() -> str:
    """Compatibilidad con la interfaz anterior."""
    return "ESPN (sin API key)"
