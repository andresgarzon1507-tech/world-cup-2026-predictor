"""Exportación y lectura segura de datos públicos versionables.

Este módulo nunca escribe en SQLite. Lee la base local mediante las funciones
existentes y publica instantáneas JSON para el modo público de Streamlit.
"""

from collections.abc import Mapping
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

from data.database import (
    get_all_analyst_notes,
    get_all_matches,
    get_latest_prediction,
)
from data.tournament_data import GROUPS, GROUP_LETTERS


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DATA_DIR = PROJECT_ROOT / "public_data"
PUBLIC_FILES = (
    "metadata",
    "matches",
    "predictions",
    "standings",
    "bracket",
    "analyst_notes",
)
KO_PHASES = ("r32", "r16", "qf", "sf", "third_place", "final")


def make_json_safe(obj: Any) -> Any:
    """Convierte objetos comunes de SQLite/pandas/numpy a JSON estándar."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Mapping):
        return {
            str(key): make_json_safe(value)
            for key, value in obj.items()
        }
    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(value) for value in obj]

    # numpy/pandas suelen exponer item() para convertir escalares.
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return make_json_safe(item())
        except (TypeError, ValueError):
            pass

    try:
        return make_json_safe(dict(obj))
    except (TypeError, ValueError):
        return str(obj)


def _build_standings(matches: list[dict]) -> dict[str, list[dict]]:
    """Calcula tablas reales únicamente desde resultados de grupos cargados."""
    standings = {}
    for group in GROUP_LETTERS:
        table = {
            team: {
                "team": team,
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "points": 0,
            }
            for team in GROUPS[group]
        }

        for match in matches:
            if (
                match.get("phase") != "groups"
                or match.get("group_letter") != group
                or not match.get("played")
            ):
                continue

            home = match.get("home_team")
            away = match.get("away_team")
            if home not in table or away not in table:
                continue

            home_goals = int(match.get("home_goals") or 0)
            away_goals = int(match.get("away_goals") or 0)
            table[home]["played"] += 1
            table[away]["played"] += 1
            table[home]["goals_for"] += home_goals
            table[home]["goals_against"] += away_goals
            table[away]["goals_for"] += away_goals
            table[away]["goals_against"] += home_goals

            if home_goals > away_goals:
                table[home]["won"] += 1
                table[away]["lost"] += 1
                table[home]["points"] += 3
            elif away_goals > home_goals:
                table[away]["won"] += 1
                table[home]["lost"] += 1
                table[away]["points"] += 3
            else:
                table[home]["drawn"] += 1
                table[away]["drawn"] += 1
                table[home]["points"] += 1
                table[away]["points"] += 1

        for row in table.values():
            row["goal_difference"] = (
                row["goals_for"] - row["goals_against"]
            )

        standings[group] = sorted(
            table.values(),
            key=lambda row: (
                row["points"],
                row["goal_difference"],
                row["goals_for"],
            ),
            reverse=True,
        )
    return standings


def _write_json(path: Path, payload: Any) -> None:
    """Escribe de forma atómica para no dejar un JSON incompleto."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(
            make_json_safe(payload),
            stream,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")
    temporary.replace(path)


def export_public_data(predictions=None) -> list[str]:
    """Genera la instantánea pública desde la base SQLite local."""
    matches = get_all_matches()
    analyst_notes = get_all_analyst_notes()
    latest_prediction = get_latest_prediction()

    if predictions is None and latest_prediction:
        predictions = latest_prediction.get("results_json")
    predictions = predictions or {}

    played_matches = sum(
        1 for match in matches if bool(match.get("played"))
    )
    total_matches = len(matches)
    generated_at = datetime.now(timezone.utc).isoformat()

    bracket = {
        phase: [
            match for match in matches
            if match.get("phase") == phase
        ]
        for phase in KO_PHASES
    }

    metadata = {
        "generated_at": generated_at,
        "played_matches": played_matches,
        "total_matches": total_matches,
        "remaining_matches": total_matches - played_matches,
        "model_version": predictions.get("model_version"),
        "simulations": predictions.get("simulations"),
        "prediction_generated_at": (
            latest_prediction.get("generated_at")
            if latest_prediction
            else None
        ),
        "source": "local_export",
    }

    payloads = {
        "metadata": metadata,
        "matches": matches,
        "predictions": predictions,
        "standings": _build_standings(matches),
        # Fuente de verdad: filas KO existentes, sin reconstruir ni ordenar
        # por probabilidades.
        "bracket": bracket,
        "analyst_notes": analyst_notes,
    }

    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    generated_files = []
    for name in PUBLIC_FILES:
        destination = PUBLIC_DATA_DIR / f"{name}.json"
        _write_json(destination, payloads[name])
        generated_files.append(str(destination.relative_to(PROJECT_ROOT)))
    return generated_files


def load_public_data() -> dict[str, Any]:
    """Carga los JSON disponibles; un archivo ausente/dañado no rompe la app."""
    loaded = {}
    errors = {}
    for name in PUBLIC_FILES:
        path = PUBLIC_DATA_DIR / f"{name}.json"
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as stream:
                loaded[name] = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            errors[name] = str(exc)

    if errors:
        loaded["_errors"] = errors
    return loaded
