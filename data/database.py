# data/database.py
# Base de datos SQLite con:
# - WAL mode (evita "database is locked")
# - UNIQUE constraints (evita partidos duplicados)
# - Context managers (conexiones siempre cerradas correctamente)
# - Timeout configurable

import sqlite3
import os
import json
import threading
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "worldcup2026.db")
DB_TIMEOUT = 10  # segundos antes de lanzar error por lock

_INIT_LOCK = threading.Lock()
_INITIALIZED_DB_PATH = None


@contextmanager
def get_db():
    """
    Context manager para conexiones SQLite.
    Garantiza que la conexión se cierra siempre, incluso si hay error.
    Usa WAL mode para evitar 'database is locked' con Streamlit.
    """
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    # WAL mode: permite lecturas simultáneas mientras se escribe
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """
    Crea todas las tablas con restricciones UNIQUE.
    Seguro para ejecutar múltiples veces (idempotente).
    """
    with get_db() as conn:
        c = conn.cursor()

        # ── Equipos ────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    UNIQUE NOT NULL,
                flag             TEXT,
                group_letter     TEXT,
                fifa_rating      REAL    DEFAULT 0.5,
                dynamic_rating   REAL    DEFAULT 0.5,
                created_at       TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Partidos ───────────────────────────────────────────────────────
        # UNIQUE(group_letter, home_team, away_team) evita duplicados
        c.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament       TEXT    DEFAULT 'FIFA World Cup 2026',
                phase            TEXT    NOT NULL,
                group_letter     TEXT,
                match_number     INTEGER,
                home_team        TEXT    NOT NULL,
                away_team        TEXT    NOT NULL,
                home_goals       INTEGER,
                away_goals       INTEGER,
                played           INTEGER DEFAULT 0,
                winner_team      TEXT,
                decided_by       TEXT,
                match_date       TEXT,
                venue            TEXT,
                created_at       TEXT    DEFAULT CURRENT_TIMESTAMP,
                updated_at       TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(phase, group_letter, home_team, away_team)
            )
        """)

        # ── Notas del analista ─────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS analyst_notes (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id            INTEGER REFERENCES matches(id),
                deserved_winner     TEXT,
                deserved_intensity  INTEGER DEFAULT 0,
                context_tags        TEXT    DEFAULT '[]',
                notes               TEXT    DEFAULT '',
                home_xg             REAL,
                away_xg             REAL,
                updated_at          TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(match_id)
            )
        """)

        # ── Predicciones guardadas ─────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
                matches_played   INTEGER DEFAULT 0,
                simulations      INTEGER DEFAULT 0,
                results_json     TEXT,
                notes            TEXT
            )
        """)

        # ── Cuotas de casas ────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS odds (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id         INTEGER REFERENCES matches(id),
                bookmaker        TEXT,
                market           TEXT,
                selection        TEXT,
                odd              REAL,
                implied_prob     REAL,
                recorded_at      TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Value bets detectados ──────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS value_bets (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id         INTEGER REFERENCES matches(id),
                market           TEXT,
                selection        TEXT,
                model_prob       REAL,
                implied_prob     REAL,
                odd              REAL,
                edge             REAL,
                ev               REAL,
                kelly_fraction   REAL,
                detected_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
                result           TEXT    DEFAULT 'pending'
            )
        """)

        # ── Estadísticas detalladas ────────────────────────────────────────
        # Mismo esquema utilizado históricamente por la migración de app.py.
        c.execute("""
            CREATE TABLE IF NOT EXISTS match_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER UNIQUE REFERENCES matches(id),
                home_shots INTEGER, away_shots INTEGER,
                home_shots_on INTEGER, away_shots_on INTEGER,
                home_possession REAL, away_possession REAL,
                home_passes INTEGER, away_passes INTEGER,
                home_pass_acc REAL, away_pass_acc REAL,
                home_fouls INTEGER, away_fouls INTEGER,
                home_yellows INTEGER, away_yellows INTEGER,
                home_reds INTEGER, away_reds INTEGER,
                home_offsides INTEGER, away_offsides INTEGER,
                home_corners INTEGER, away_corners INTEGER,
                home_xg REAL, away_xg REAL,
                home_formation TEXT, away_formation TEXT,
                home_lineup TEXT DEFAULT '[]',
                away_lineup TEXT DEFAULT '[]',
                home_key_absences TEXT DEFAULT '[]',
                away_key_absences TEXT DEFAULT '[]',
                extra_notes TEXT DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_stats_match ON match_stats(match_id)"
        )

        # ── Índices de performance ─────────────────────────────────────────
        c.execute("CREATE INDEX IF NOT EXISTS idx_matches_phase ON matches(phase)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_matches_played ON matches(played)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_matches_group ON matches(group_letter)")

    print("✅ Base de datos inicializada.")


# ── MATCHES ───────────────────────────────────────────────────────────────────

def insert_match(phase, group_letter, match_number, home_team, away_team):
    """Inserta un partido. Si ya existe, lo ignora (no duplica)."""
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO matches
                (phase, group_letter, match_number, home_team, away_team)
            VALUES (?,?,?,?,?)
        """, (phase, group_letter, match_number, home_team, away_team))


def save_match_result(match_id, home_goals, away_goals):
    with get_db() as conn:
        conn.execute("""
            UPDATE matches
            SET home_goals=?, away_goals=?, played=1, updated_at=?
            WHERE id=?
        """, (home_goals, away_goals, datetime.now().isoformat(), match_id))


def clear_match_result(match_id):
    """
    Borra el resultado de UN partido específico, devolviéndolo a estado
    'no jugado'. También limpia las estadísticas y notas del analista
    asociadas, para que el modelo no las siga teniendo en cuenta.
    """
    with get_db() as conn:
        conn.execute("""
            UPDATE matches
            SET home_goals=NULL, away_goals=NULL, played=0, updated_at=?
            WHERE id=?
        """, (datetime.now().isoformat(), match_id))
        conn.execute("DELETE FROM match_stats WHERE match_id=?", (match_id,))
        conn.execute("DELETE FROM analyst_notes WHERE match_id=?", (match_id,))


def get_all_matches(phase=None):
    with get_db() as conn:
        if phase:
            rows = conn.execute(
                "SELECT * FROM matches WHERE phase=? ORDER BY match_number", (phase,)
            ).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM matches
                ORDER BY CASE phase
                    WHEN 'groups' THEN 1
                    WHEN 'r32' THEN 2
                    WHEN 'r16' THEN 3
                    WHEN 'qf' THEN 4
                    WHEN 'sf' THEN 5
                    WHEN 'third_place' THEN 6
                    WHEN 'final' THEN 7
                    ELSE 8
                END,
                match_number
            """).fetchall()
    return [dict(r) for r in rows]


def get_played_matches():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM matches
            WHERE played=1
            ORDER BY CASE phase
                WHEN 'groups' THEN 1
                WHEN 'r32' THEN 2
                WHEN 'r16' THEN 3
                WHEN 'qf' THEN 4
                WHEN 'sf' THEN 5
                WHEN 'third_place' THEN 6
                WHEN 'final' THEN 7
                ELSE 8
            END,
            match_number
        """).fetchall()
    return [dict(r) for r in rows]


def reset_all_results():
    """Borra todos los resultados cargados (útil para testing)."""
    with get_db() as conn:
        conn.execute("UPDATE matches SET home_goals=NULL, away_goals=NULL, played=0")


# ── TEAMS ─────────────────────────────────────────────────────────────────────

def insert_team(name, flag, group_letter, fifa_rating):
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO teams (name, flag, group_letter, fifa_rating, dynamic_rating)
            VALUES (?,?,?,?,?)
        """, (name, flag, group_letter, fifa_rating, fifa_rating))


# ── ANALYST NOTES ─────────────────────────────────────────────────────────────

def save_analyst_note(match_id, deserved_winner, intensity, tags, notes,
                      home_xg=None, away_xg=None):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO analyst_notes
                (match_id, deserved_winner, deserved_intensity, context_tags,
                 notes, home_xg, away_xg, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(match_id) DO UPDATE SET
                deserved_winner    = excluded.deserved_winner,
                deserved_intensity = excluded.deserved_intensity,
                context_tags       = excluded.context_tags,
                notes              = excluded.notes,
                home_xg            = excluded.home_xg,
                away_xg            = excluded.away_xg,
                updated_at         = excluded.updated_at
        """, (match_id, deserved_winner, intensity, json.dumps(tags),
              notes, home_xg, away_xg, datetime.now().isoformat()))


def get_analyst_note(match_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM analyst_notes WHERE match_id=?", (match_id,)
        ).fetchone()
    return dict(row) if row else None


def get_all_analyst_notes():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM analyst_notes").fetchall()
    return {r["match_id"]: dict(r) for r in rows}


# ── PREDICTIONS ───────────────────────────────────────────────────────────────

def save_prediction(matches_played, simulations, results_dict):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO predictions (matches_played, simulations, results_json)
            VALUES (?,?,?)
        """, (matches_played, simulations, json.dumps(results_dict)))


def get_latest_prediction():
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM predictions ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
    if row:
        d = dict(row)
        d["results_json"] = json.loads(d["results_json"])
        return d
    return None


# ── VALUE BETS ────────────────────────────────────────────────────────────────

def save_value_bet(match_id, market, selection, model_prob,
                   implied_prob, odd, edge, ev, kelly):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO value_bets
                (match_id, market, selection, model_prob, implied_prob,
                 odd, edge, ev, kelly_fraction)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (match_id, market, selection, model_prob,
              implied_prob, odd, edge, ev, kelly))


def get_value_bets_history():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT vb.*, m.home_team, m.away_team, m.group_letter
            FROM value_bets vb
            JOIN matches m ON m.id = vb.match_id
            ORDER BY vb.detected_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ── KNOCKOUT PHASES ───────────────────────────────────────────────────────────

def init_ko_matches():
    """
    Crea los partidos de las fases eliminatorias en la DB.
    Es IDEMPOTENTE: primero limpia duplicados, luego asegura que
    exista exactamente 1 fila por (phase, match_number).

    NOTA TÉCNICA: NULL en SQLite nunca es igual a NULL en una
    restricción UNIQUE, por eso "phase + group_letter(NULL) + home + away"
    no protegía contra duplicados en fases KO. Esta versión usa
    phase + match_number como clave real de control, manejado en código.
    """
    ko_phases = [
        ("r32",   16),
        ("r16",    8),
        ("qf",     4),
        ("sf",     2),
        ("final",  1),
    ]
    with get_db() as conn:
        for phase, total in ko_phases:
            for i in range(1, total + 1):
                existing = conn.execute("""
                    SELECT id FROM matches WHERE phase=? AND match_number=?
                    ORDER BY id ASC
                """, (phase, i)).fetchall()

                if len(existing) == 0:
                    conn.execute("""
                        INSERT INTO matches
                            (phase, group_letter, match_number, home_team, away_team)
                        VALUES (?, NULL, ?, '', '')
                    """, (phase, i))
                elif len(existing) > 1:
                    # Ya hay duplicados: conservar el primero, borrar el resto
                    keep_id = existing[0]["id"]
                    ids_to_delete = [row["id"] for row in existing[1:]]
                    conn.executemany(
                        "DELETE FROM matches WHERE id=?",
                        [(did,) for did in ids_to_delete]
                    )


def _database_is_ready():
    """Comprueba esquema esencial y datos mínimos sin modificar la base."""
    required_tables = {
        "teams",
        "matches",
        "analyst_notes",
        "predictions",
        "odds",
        "value_bets",
        "match_stats",
    }
    try:
        conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
        existing_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not required_tables.issubset(existing_tables):
            return False

        team_count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        group_match_count = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE phase='groups'"
        ).fetchone()[0]
        return team_count >= 48 and group_match_count >= 72
    except sqlite3.Error:
        return False
    finally:
        if "conn" in locals():
            conn.close()


def _ensure_match_winner_columns():
    """Agrega de forma idempotente el ganador KO a bases creadas anteriormente."""
    with get_db() as conn:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='matches'"
        ).fetchone()
        if not table_exists:
            return

        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(matches)").fetchall()
        }
        if "winner_team" not in columns:
            conn.execute("ALTER TABLE matches ADD COLUMN winner_team TEXT")
        if "decided_by" not in columns:
            conn.execute("ALTER TABLE matches ADD COLUMN decided_by TEXT")


def ensure_database_initialized():
    """
    Inicializa esquema, equipos y fixture una sola vez cuando la base está vacía.

    Es idempotente: si la base local ya contiene las tablas y datos mínimos,
    no ejecuta escrituras. Reutiliza exactamente las funciones de setup.py.
    """
    global _INITIALIZED_DB_PATH

    normalized_path = os.path.abspath(DB_PATH)
    if _database_is_ready():
        _ensure_match_winner_columns()
    if (
        _INITIALIZED_DB_PATH == normalized_path
        and _database_is_ready()
    ):
        return False

    with _INIT_LOCK:
        if _database_is_ready():
            _INITIALIZED_DB_PATH = normalized_path
            return False

        from data.tournament_data import (
            FIFA_RATINGS,
            FLAGS,
            GROUP_FIXTURES,
            GROUPS,
        )

        init_database()
        _ensure_match_winner_columns()

        for group, teams in GROUPS.items():
            for team in teams:
                insert_team(
                    name=team,
                    flag=FLAGS.get(team, "🏳️"),
                    group_letter=group,
                    fifa_rating=FIFA_RATINGS.get(team, 0.5),
                )

        match_number = 1
        for group, fixtures in GROUP_FIXTURES.items():
            for home, away in fixtures:
                insert_match(
                    "groups",
                    group,
                    match_number,
                    home,
                    away,
                )
                match_number += 1

        init_ko_matches()
        _INITIALIZED_DB_PATH = normalized_path
        return True


def clean_ko_duplicates():
    """
    Limpia duplicados existentes en fases eliminatorias.
    Conserva la fila más antigua (menor id) de cada (phase, match_number)
    y prioriza conservar las que ya tienen resultado jugado.
    Útil para reparar bases de datos ya corrompidas por el bug anterior.
    """
    ko_phases = ["r32", "r16", "qf", "sf", "final"]
    deleted_count = 0

    with get_db() as conn:
        for phase in ko_phases:
            match_numbers = conn.execute("""
                SELECT DISTINCT match_number FROM matches WHERE phase=?
            """, (phase,)).fetchall()

            for row in match_numbers:
                mn = row["match_number"]
                rows = conn.execute("""
                    SELECT * FROM matches WHERE phase=? AND match_number=?
                    ORDER BY played DESC, id ASC
                """, (phase, mn)).fetchall()

                if len(rows) > 1:
                    keep_id = rows[0]["id"]
                    for r in rows[1:]:
                        conn.execute("DELETE FROM matches WHERE id=?", (r["id"],))
                        deleted_count += 1

    return deleted_count


def get_ko_matches(phase):
    """Retorna los partidos de una fase KO ordenados."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM matches
            WHERE phase = ?
            ORDER BY match_number
        """, (phase,)).fetchall()
    return [dict(r) for r in rows]


def update_ko_teams(phase, match_number, home_team, away_team):
    """
    Actualiza los equipos de un partido KO.

    Si el cruce cambia, se limpian los goles y el estado played de ese partido.
    Esto evita que un resultado cargado para un VS viejo quede aplicado a un
    VS nuevo cuando cambian los clasificados o los mejores terceros.
    """
    with get_db() as conn:
        current = conn.execute(
            "SELECT home_team, away_team FROM matches WHERE phase=? AND match_number=?",
            (phase, match_number)
        ).fetchone()

        teams_changed = (
            current is None
            or current["home_team"] != home_team
            or current["away_team"] != away_team
        )

        if teams_changed:
            conn.execute("""
                UPDATE matches
                SET home_team = ?, away_team = ?,
                    home_goals = NULL, away_goals = NULL, played = 0,
                    winner_team = NULL, decided_by = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE phase = ? AND match_number = ?
            """, (home_team, away_team, phase, match_number))
        else:
            conn.execute("""
                UPDATE matches
                SET home_team = ?, away_team = ?, updated_at = CURRENT_TIMESTAMP
                WHERE phase = ? AND match_number = ?
            """, (home_team, away_team, phase, match_number))


def save_ko_result(
    phase, match_number, home_goals, away_goals,
    winner_team=None, decided_by=None,
):
    """Guarda un resultado KO y exige el ganador cuando hubo penales."""
    with get_db() as conn:
        match = conn.execute("""
            SELECT home_team, away_team FROM matches
            WHERE phase = ? AND match_number = ?
        """, (phase, match_number)).fetchone()
        if not match:
            raise ValueError("No existe el partido de eliminatorias indicado.")

        valid_teams = {match["home_team"], match["away_team"]}
        if home_goals == away_goals:
            if winner_team not in valid_teams:
                raise ValueError("Seleccioná quién ganó la definición por penales.")
            decided_by = "penalties"
        else:
            score_winner = (
                match["home_team"] if home_goals > away_goals else match["away_team"]
            )
            if winner_team is not None and winner_team != score_winner:
                raise ValueError("El ganador no coincide con el marcador ingresado.")
            winner_team = score_winner
            decided_by = "regular"

        conn.execute("""
            UPDATE matches
            SET home_goals = ?, away_goals = ?, played = 1,
                winner_team = ?, decided_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE phase = ? AND match_number = ?
        """, (
            home_goals, away_goals, winner_team, decided_by,
            phase, match_number,
        ))


def clear_ko_result(phase, match_number):
    """
    Borra el resultado de un partido KO específico, devolviéndolo a
    estado 'no jugado'. También limpia estadísticas y notas asociadas.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM matches WHERE phase=? AND match_number=?",
            (phase, match_number)
        ).fetchone()
        conn.execute("""
            UPDATE matches
            SET home_goals=NULL, away_goals=NULL, played=0,
                winner_team=NULL, decided_by=NULL,
                updated_at=CURRENT_TIMESTAMP
            WHERE phase=? AND match_number=?
        """, (phase, match_number))
        if row:
            conn.execute("DELETE FROM match_stats WHERE match_id=?", (row["id"],))
            conn.execute("DELETE FROM analyst_notes WHERE match_id=?", (row["id"],))


def get_ko_winner(phase, match_number):
    """Retorna el ganador de un partido KO si ya fue jugado."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT home_team, away_team, home_goals, away_goals, played,
                   winner_team
            FROM matches
            WHERE phase = ? AND match_number = ?
        """, (phase, match_number)).fetchone()
    if not row or not row["played"]:
        return None
    if row["winner_team"] in (row["home_team"], row["away_team"]):
        return row["winner_team"]
    if row["home_goals"] is None or row["away_goals"] is None:
        return None
    if row["home_goals"] == row["away_goals"]:
        return None
    return row["home_team"] if row["home_goals"] > row["away_goals"] else row["away_team"]


# ── MATCH STATS ───────────────────────────────────────────────────────────────

def save_match_stats(match_id, stats: dict):
    """
    Guarda o actualiza las estadísticas completas de un partido.
    stats: dict con todas las métricas del partido.
    """
    import json
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM match_stats WHERE match_id=?", (match_id,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE match_stats SET
                    home_shots=?, away_shots=?,
                    home_shots_on=?, away_shots_on=?,
                    home_possession=?, away_possession=?,
                    home_passes=?, away_passes=?,
                    home_pass_acc=?, away_pass_acc=?,
                    home_fouls=?, away_fouls=?,
                    home_yellows=?, away_yellows=?,
                    home_reds=?, away_reds=?,
                    home_offsides=?, away_offsides=?,
                    home_corners=?, away_corners=?,
                    home_xg=?, away_xg=?,
                    home_formation=?, away_formation=?,
                    home_lineup=?, away_lineup=?,
                    home_key_absences=?, away_key_absences=?,
                    extra_notes=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE match_id=?
            """, (
                stats.get("home_shots"), stats.get("away_shots"),
                stats.get("home_shots_on"), stats.get("away_shots_on"),
                stats.get("home_possession"), stats.get("away_possession"),
                stats.get("home_passes"), stats.get("away_passes"),
                stats.get("home_pass_acc"), stats.get("away_pass_acc"),
                stats.get("home_fouls"), stats.get("away_fouls"),
                stats.get("home_yellows"), stats.get("away_yellows"),
                stats.get("home_reds"), stats.get("away_reds"),
                stats.get("home_offsides"), stats.get("away_offsides"),
                stats.get("home_corners"), stats.get("away_corners"),
                stats.get("home_xg"), stats.get("away_xg"),
                stats.get("home_formation"), stats.get("away_formation"),
                json.dumps(stats.get("home_lineup", [])),
                json.dumps(stats.get("away_lineup", [])),
                json.dumps(stats.get("home_key_absences", [])),
                json.dumps(stats.get("away_key_absences", [])),
                stats.get("extra_notes", ""),
                match_id,
            ))
        else:
            conn.execute("""
                INSERT INTO match_stats (
                    match_id,
                    home_shots, away_shots,
                    home_shots_on, away_shots_on,
                    home_possession, away_possession,
                    home_passes, away_passes,
                    home_pass_acc, away_pass_acc,
                    home_fouls, away_fouls,
                    home_yellows, away_yellows,
                    home_reds, away_reds,
                    home_offsides, away_offsides,
                    home_corners, away_corners,
                    home_xg, away_xg,
                    home_formation, away_formation,
                    home_lineup, away_lineup,
                    home_key_absences, away_key_absences,
                    extra_notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                match_id,
                stats.get("home_shots"), stats.get("away_shots"),
                stats.get("home_shots_on"), stats.get("away_shots_on"),
                stats.get("home_possession"), stats.get("away_possession"),
                stats.get("home_passes"), stats.get("away_passes"),
                stats.get("home_pass_acc"), stats.get("away_pass_acc"),
                stats.get("home_fouls"), stats.get("away_fouls"),
                stats.get("home_yellows"), stats.get("away_yellows"),
                stats.get("home_reds"), stats.get("away_reds"),
                stats.get("home_offsides"), stats.get("away_offsides"),
                stats.get("home_corners"), stats.get("away_corners"),
                stats.get("home_xg"), stats.get("away_xg"),
                stats.get("home_formation"), stats.get("away_formation"),
                json.dumps(stats.get("home_lineup", [])),
                json.dumps(stats.get("away_lineup", [])),
                json.dumps(stats.get("home_key_absences", [])),
                json.dumps(stats.get("away_key_absences", [])),
                stats.get("extra_notes", ""),
            ))


def get_match_stats(match_id):
    """Retorna las estadísticas de un partido, o None si no existen."""
    import json
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM match_stats WHERE match_id=?", (match_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    for field in ["home_lineup","away_lineup","home_key_absences","away_key_absences"]:
        try:
            d[field] = json.loads(d[field]) if d[field] else []
        except Exception:
            d[field] = []
    return d


def get_all_match_stats():
    """Retorna todas las estadísticas indexadas por match_id."""
    import json
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM match_stats").fetchall()
    result = {}
    for row in rows:
        d = dict(row)
        for field in ["home_lineup","away_lineup","home_key_absences","away_key_absences"]:
            try:
                d[field] = json.loads(d[field]) if d[field] else []
            except Exception:
                d[field] = []
        result[d["match_id"]] = d
    return result
