# models/odds_api.py
# Integración con The Odds API (theOddsAPI.com)
# Plan gratuito: 500 requests/mes — suficiente para el Mundial completo.
#
# Para obtener tu API key gratuita:
# 1. Ir a https://the-odds-api.com
# 2. Registrarse (gratis)
# 3. Copiar la API key
# 4. Crear archivo .env en la carpeta del proyecto con:
#    ODDS_API_KEY=tu_key_aqui

import os
from datetime import datetime

import requests
from dotenv import load_dotenv

from models.espn_parser import normalize_team_name

load_dotenv()

ODDS_API_KEY  = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Sport key para fútbol internacional / Copa del Mundo
SPORT_KEY     = "soccer_fifa_world_cup"

# Casas de apuestas soportadas (las más conocidas)
BOOKMAKERS    = ["bet365","betfair","unibet","pinnacle","williamhill","betway"]


def _get(endpoint, params=None):
    """Request a la API con manejo de errores."""
    if not ODDS_API_KEY:
        return None, "❌ API key no configurada. Creá el archivo .env con ODDS_API_KEY=tu_key"
    
    url = f"{ODDS_API_BASE}{endpoint}"
    params = params or {}
    params["apiKey"] = ODDS_API_KEY
    
    try:
        r = requests.get(url, params=params, timeout=10)
        remaining = r.headers.get("x-requests-remaining", "?")
        used      = r.headers.get("x-requests-used", "?")
        
        if r.status_code == 200:
            return r.json(), f"✅ OK — requests usados: {used} | restantes: {remaining}"
        elif r.status_code == 401:
            return None, "❌ API key inválida"
        elif r.status_code == 429:
            return None, "❌ Límite de requests alcanzado"
        else:
            return None, f"❌ Error {r.status_code}: {r.text}"
    except requests.Timeout:
        return None, "❌ Timeout — la API no respondió"
    except Exception as e:
        return None, f"❌ Error de conexión: {e}"


def get_live_odds(markets="h2h"):
    """
    Trae cuotas en tiempo real para Copa del Mundo.
    markets: "h2h" (1X2), "totals" (over/under), "spreads"
    
    Retorna lista de partidos con cuotas por casa.
    """
    data, msg = _get(
        f"/sports/{SPORT_KEY}/odds",
        params={
            "regions":    "eu",        # cuotas europeas (decimales)
            "markets":    markets,
            "oddsFormat": "decimal",
            "bookmakers": ",".join(BOOKMAKERS),
        }
    )
    if not data:
        return [], msg
    
    matches = []
    for event in data:
        match = {
            "id":        event["id"],
            "home_team": event["home_team"],
            "away_team": event["away_team"],
            "commence":  event["commence_time"],
            "bookmakers": [],
        }
        for bm in event.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt["key"] == "h2h":
                    outcomes = {o["name"]: o["price"] for o in mkt["outcomes"]}
                    match["bookmakers"].append({
                        "name":      bm["title"],
                        "odd_home":  outcomes.get(event["home_team"], None),
                        "odd_draw":  outcomes.get("Draw", None),
                        "odd_away":  outcomes.get(event["away_team"], None),
                        "updated":   mkt.get("last_update", ""),
                    })
        matches.append(match)
    
    return matches, msg


def _parse_event_date(value):
    """Convierte fechas ISO de la app/API a date; None si no es válida."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).date()
    except (TypeError, ValueError):
        return None


def get_best_odds(home_team, away_team, match_date=None):
    """
    Busca las mejores cuotas disponibles para un partido específico.
    Retorna el mercado 1X2 completo de una sola casa con menor overround.
    """
    matches, msg = get_live_odds()
    
    candidates = [
        m for m in matches
        if normalize_team_name(home_team)
        == normalize_team_name(m.get("home_team"))
        and normalize_team_name(away_team)
        == normalize_team_name(m.get("away_team"))
    ]

    if match_date:
        expected_date = _parse_event_date(match_date)
        if expected_date is None:
            return None, None, (
                f"Fecha inválida para {home_team} vs {away_team}: "
                f"{match_date}."
            )
        candidates = [
            m for m in candidates
            if _parse_event_date(m.get("commence")) == expected_date
        ]

    if not candidates:
        date_detail = f" en la fecha {match_date}" if match_date else ""
        return None, None, (
            f"No se encontraron cuotas para {home_team} vs {away_team}"
            f"{date_detail}."
        )

    if len(candidates) > 1:
        return None, None, (
            f"Se encontraron múltiples eventos para {home_team} vs "
            f"{away_team}; no se pueden seleccionar cuotas con seguridad."
        )

    match = candidates[0]
    complete_markets = [
        bm for bm in match["bookmakers"]
        if all(bm.get(key) for key in ("odd_home", "odd_draw", "odd_away"))
    ]
    if not complete_markets:
        return None, None, (
            f"No hay un mercado 1X2 completo de una sola casa para "
            f"{home_team} vs {away_team}."
        )

    def market_overround(bookmaker):
        return sum(
            1.0 / bookmaker[key]
            for key in ("odd_home", "odd_draw", "odd_away")
        )

    selected = min(complete_markets, key=market_overround)
    overround = market_overround(selected)
    best = {
        "odd_home": selected["odd_home"],
        "odd_draw": selected["odd_draw"],
        "odd_away": selected["odd_away"],
        "bm_home": selected["name"],
        "bm_draw": selected["name"],
        "bm_away": selected["name"],
        "bookmaker": selected["name"],
        "overround": overround,
    }
    market_msg = (
        f"{msg} Mercado de {selected['name']} · "
        f"overround {(overround - 1) * 100:+.2f}%."
    )
    return best, match["commence"], market_msg


def get_remaining_requests():
    """Chequea cuántos requests quedan en el plan gratuito."""
    _, msg = _get("/sports")
    return msg


def api_configured():
    return bool(ODDS_API_KEY)
