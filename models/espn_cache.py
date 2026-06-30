# models/espn_cache.py
# Capa de caché: evita pedirle a ESPN el mismo scoreboard varias veces
# en la misma sesión de Streamlit. No tiene lógica de parseo ni de
# requests — solo envuelve espn_api con cacheo.
#
# Usa st.cache_data cuando Streamlit está disponible; si el módulo se
# usa fuera de Streamlit (ej: test_api.py), cae a una caché simple en
# memoria de proceso para no romper.

from typing import Optional

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

from models import espn_api

# Rango de fechas del torneo completo — se usa como ventana fija para
# no tener que pasar fechas distintas en cada llamada.
TOURNAMENT_START = "20260611"
TOURNAMENT_END   = "20260719"

_memory_cache: dict = {}


def _cache_data(ttl_seconds: int = 300):
    """
    Decorator que usa st.cache_data si Streamlit está disponible,
    o una caché simple en memoria de proceso si no.
    """
    def decorator(func):
        if _HAS_STREAMLIT:
            return st.cache_data(ttl=ttl_seconds, show_spinner=False)(func)

        def wrapper(*args, **kwargs):
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            if key not in _memory_cache:
                _memory_cache[key] = func(*args, **kwargs)
            return _memory_cache[key]
        return wrapper
    return decorator


@_cache_data(ttl_seconds=300)
def get_cached_scoreboard() -> tuple[Optional[dict], str]:
    """
    Trae el scoreboard completo del torneo (todas las fechas), cacheado
    5 minutos. Evita golpear a ESPN en cada interacción de la UI.
    """
    return espn_api.fetch_scoreboard(TOURNAMENT_START, TOURNAMENT_END)


@_cache_data(ttl_seconds=120)
def get_cached_summary(event_id: str) -> tuple[Optional[dict], str]:
    """
    Trae el resumen de un partido específico, cacheado 2 minutos.
    TTL más corto que el scoreboard porque un partido en vivo cambia
    rápido; uno ya terminado de igual forma se sigue beneficiando del
    cache dentro de la ventana.
    """
    return espn_api.fetch_summary(event_id)


def clear_cache():
    """Limpia la caché manualmente (botón de 'forzar actualización')."""
    global _memory_cache
    _memory_cache = {}
    if _HAS_STREAMLIT:
        get_cached_scoreboard.clear()
        get_cached_summary.clear()
