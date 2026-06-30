# setup.py
# Seguro para ejecutar múltiples veces.
# INSERT OR IGNORE evita duplicados aunque se corra N veces.

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from data.database import init_database, insert_team, insert_match, get_all_matches, init_ko_matches
from data.tournament_data import GROUPS, FIFA_RATINGS, FLAGS, GROUP_FIXTURES

def setup():
    print("=" * 55)
    print("  WORLD CUP 2026 — SISTEMA DE PREDICCIÓN v2")
    print("=" * 55)

    print("\n📦 Inicializando base de datos...")
    init_database()

    print("👕 Cargando equipos...")
    for group, teams in GROUPS.items():
        for team in teams:
            insert_team(
                name        = team,
                flag        = FLAGS.get(team, "🏳️"),
                group_letter= group,
                fifa_rating = FIFA_RATINGS.get(team, 0.5),
            )

    print("📅 Cargando fixture de grupos...")
    match_num = 1
    for group, fixtures in GROUP_FIXTURES.items():
        for home, away in fixtures:
            insert_match("groups", group, match_num, home, away)
            match_num += 1

    print("🏆 Inicializando fases eliminatorias...")
    init_ko_matches()

    total = len(get_all_matches())
    print(f"\n✅ Setup completado. {total} partidos en la base de datos.")
    print("\n▶  Para abrir el dashboard ejecutá:")
    print("   streamlit run app.py")
    print("=" * 55)

if __name__ == "__main__":
    setup()
