# reset_ko_only.py
# Borra ÚNICAMENTE los partidos de fases eliminatorias (r32, r16, qf, sf,
# final) de la base de datos, sin tocar absolutamente nada de la fase
# de grupos ni sus resultados ya cargados.
#
# Usar cuando se corrigió el bracket de Dieciseisavos en tournament_data.py
# y la base de datos tiene partidos KO guardados con el bracket viejo,
# lo que puede causar cruces mezclados/inconsistentes en la pestaña
# Eliminatorias.
#
# Ejecutar con: python reset_ko_only.py

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "worldcup2026.db")

KO_PHASES = ("r32", "r16", "qf", "sf", "final")


def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos en {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    # Contar antes de borrar, para mostrar confirmación clara
    placeholders = ",".join("?" * len(KO_PHASES))
    c.execute(f"SELECT COUNT(*) FROM matches WHERE phase IN ({placeholders})", KO_PHASES)
    count_before = c.fetchone()[0]

    c.execute(f"SELECT COUNT(*) FROM matches WHERE phase = 'groups'")
    count_groups = c.fetchone()[0]

    print(f"Partidos de grupos encontrados (NO se tocan): {count_groups}")
    print(f"Partidos de eliminatorias a borrar (r32/r16/qf/sf/final): {count_before}")
    print()

    if count_before == 0:
        print("No hay partidos KO para borrar. No se hizo ningún cambio.")
        conn.close()
        return

    confirm = input("¿Confirmás que querés borrar SOLO los partidos KO? (escribí 'si'): ")
    if confirm.strip().lower() != "si":
        print("Cancelado. No se hizo ningún cambio.")
        conn.close()
        return

    # Borrar primero estadísticas y notas asociadas a esos partidos KO,
    # para no dejar registros huérfanos en otras tablas.
    c.execute(f"""
        DELETE FROM match_stats WHERE match_id IN (
            SELECT id FROM matches WHERE phase IN ({placeholders})
        )
    """, KO_PHASES)

    c.execute(f"""
        DELETE FROM analyst_notes WHERE match_id IN (
            SELECT id FROM matches WHERE phase IN ({placeholders})
        )
    """, KO_PHASES)

    # Borrar los partidos KO en sí
    c.execute(f"DELETE FROM matches WHERE phase IN ({placeholders})", KO_PHASES)

    conn.commit()

    # Verificar resultado final
    c.execute(f"SELECT COUNT(*) FROM matches WHERE phase IN ({placeholders})", KO_PHASES)
    count_after = c.fetchone()[0]

    c.execute(f"SELECT COUNT(*) FROM matches WHERE phase = 'groups'")
    count_groups_after = c.fetchone()[0]

    conn.close()

    print()
    print(f"✅ Partidos KO eliminados: {count_before} -> {count_after}")
    print(f"✅ Partidos de grupos intactos: {count_groups_after} (antes: {count_groups})")
    print()
    print("Ahora volvé a abrir la app (streamlit run app.py).")
    print("La pestaña Eliminatorias va a regenerar los 16 partidos de")
    print("Dieciseisavos automáticamente con el bracket nuevo y correcto,")
    print("apenas la abras (gracias a init_ko_matches()).")


if __name__ == "__main__":
    main()
