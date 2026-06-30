# models/espn_api.py
# Capa de transporte: SOLO hace peticiones HTTP a la API no oficial de ESPN.
# No conoce el formato de tu base de datos ni el de tu aplicación.
# No requiere API key.
#
# Endpoint base verificado para FIFA World Cup 2026:
#   https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world
#
# Si en el futuro ESPN cambia algo, este es el único archivo que debería
# necesitar ajustes de URLs/parámetros — el parseo vive en espn_parser.py.

from typing import Optional
import requests

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
TIMEOUT  = 12  # segundos


def _get(path: str, params: Optional[dict] = None) -> tuple[Optional[dict], str]:
    """
    Request genérico con manejo de errores. Nunca lanza excepciones hacia
    arriba: siempre devuelve (data, mensaje), donde data es None si falló.
    """
    url = f"{BASE_URL}{path}"
    try:
        r = requests.get(url, params=params or {}, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json(), "✅ OK"
        else:
            return None, f"❌ Error {r.status_code} en {url}"
    except requests.Timeout:
        return None, "❌ Timeout — ESPN no respondió a tiempo"
    except requests.RequestException as e:
        return None, f"❌ Error de conexión: {e}"
    except ValueError:
        # r.json() falló (respuesta no era JSON válido)
        return None, "❌ Respuesta inesperada (no es JSON)"


def fetch_scoreboard(date_from: str, date_to: str, limit: int = 200) -> tuple[Optional[dict], str]:
    """
    Trae el scoreboard completo del Mundial 2026 en un rango de fechas.
    Formato de fecha: YYYYMMDD (ej: "20260611").

    Retorna el JSON crudo de ESPN (sin parsear) y un mensaje de estado.
    """
    return _get("/scoreboard", {
        "dates": f"{date_from}-{date_to}",
        "limit": limit,
    })


def fetch_summary(event_id: str) -> tuple[Optional[dict], str]:
    """
    Trae el resumen completo de un partido específico: boxscore,
    rosters, eventos clave, comentarios, standings, odds, etc.

    event_id es el "id" que devuelve fetch_scoreboard para cada evento.
    """
    return _get("/summary", {"event": event_id})
