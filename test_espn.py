# test_espn.py — Diagnóstico aislado de la integración con ESPN
# Ejecutar con: python test_espn.py
# No requiere API key. No toca la app ni la base de datos.

import sys
sys.path.insert(0, ".")

from models import espn_api, espn_parser

print("=" * 60)
print("TEST 1: Conexión directa a ESPN (scoreboard)")
print("=" * 60)
raw, msg = espn_api.fetch_scoreboard("20260611", "20260719", limit=200)
print(f"Mensaje: {msg}")
if raw:
    n_events = len(raw.get("events", []))
    print(f"Cantidad de eventos en la respuesta cruda: {n_events}")
else:
    print("❌ No se obtuvo respuesta. Revisá tu conexión a internet.")
    sys.exit(1)

print()
print("=" * 60)
print("TEST 2: Parseo del scoreboard")
print("=" * 60)
fixtures = espn_parser.parse_scoreboard(raw)
print(f"Partidos parseados correctamente: {len(fixtures)}")
if fixtures:
    print("\nPrimeros 3 partidos:")
    for f in fixtures[:3]:
        print(f"  {f['home_team']} vs {f['away_team']} — status={f['status']} "
              f"goles={f['home_goals']}-{f['away_goals']}")

print()
print("=" * 60)
print("TEST 3: Búsqueda de un partido por nombre en español")
print("=" * 60)
if fixtures:
    primer_partido = fixtures[0]
    print(f"Probando con: {primer_partido['home_team']} vs {primer_partido['away_team']}")
    # Probamos buscarlo usando el nombre tal como aparece en la API
    # (no sabemos a priori el nombre en español que tendría en tu BD)
    match = espn_parser.find_fixture(
        primer_partido["home_team"], primer_partido["away_team"], fixtures
    )
    print(f"Resultado de la búsqueda: {'✅ Encontrado' if match else '❌ No encontrado'}")

print()
print("=" * 60)
print("TEST 4: Estadísticas de un partido ya finalizado (si hay alguno)")
print("=" * 60)
finished = [f for f in fixtures if f["status"] == "FT"]
if finished:
    target = finished[0]
    print(f"Probando con: {target['home_team']} vs {target['away_team']} (finalizado)")
    summary_raw, summary_msg = espn_api.fetch_summary(target["fixture_id"])
    print(f"Mensaje: {summary_msg}")
    if summary_raw:
        stats = espn_parser.parse_statistics(summary_raw, target["home_team"])
        print(f"Estadísticas parseadas: {'✅ OK' if stats else '⚠️ Sin boxscore disponible'}")
        if stats:
            print(f"  Remates: {stats['home_shots']} - {stats['away_shots']}")
            print(f"  Posesión: {stats['home_possession']}% - {stats['away_possession']}%")
else:
    print("ℹ️ No hay partidos finalizados todavía en el rango de fechas consultado.")

print()
print("=" * 60)
print("FIN DEL DIAGNÓSTICO")
print("=" * 60)
