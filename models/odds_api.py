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
import requests
from dotenv import load_dotenv

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


def get_best_odds(home_team, away_team):
    """
    Busca las mejores cuotas disponibles para un partido específico.
    Retorna las cuotas más altas entre todas las casas (mejor valor).
    """
    matches, msg = get_live_odds()
    
    for m in matches:
        if (home_team.lower() in m["home_team"].lower() or
            away_team.lower() in m["away_team"].lower()):
            
            best = {"odd_home": 0, "odd_draw": 0, "odd_away": 0,
                    "bm_home": "", "bm_draw": "", "bm_away": ""}
            
            for bm in m["bookmakers"]:
                if bm["odd_home"] and bm["odd_home"] > best["odd_home"]:
                    best["odd_home"] = bm["odd_home"]
                    best["bm_home"]  = bm["name"]
                if bm["odd_draw"] and bm["odd_draw"] > best["odd_draw"]:
                    best["odd_draw"] = bm["odd_draw"]
                    best["bm_draw"]  = bm["name"]
                if bm["odd_away"] and bm["odd_away"] > best["odd_away"]:
                    best["odd_away"] = bm["odd_away"]
                    best["bm_away"]  = bm["name"]
            
            return best, m["commence"], msg
    
    return None, None, f"Partido no encontrado en la API. {msg}"


def get_remaining_requests():
    """Chequea cuántos requests quedan en el plan gratuito."""
    _, msg = _get("/sports")
    return msg


def api_configured():
    return bool(ODDS_API_KEY)
