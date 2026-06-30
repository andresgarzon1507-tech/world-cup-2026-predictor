# Informe técnico de refactorización

## Problemas corregidos

1. Asignación voraz e incorrecta de mejores terceros.
2. Orden de dieciseisavos incompatible con las dependencias oficiales de octavos.
3. Clasificación reducida a puntos, diferencia y goles.
4. Tres implementaciones distintas de clasificación y bracket.
5. Empates KO adjudicados implícitamente al visitante.
6. Simulación sin prórroga y con probabilidades KO distintas de las simuladas.
7. Monte Carlo que ignoraba resultados eliminatorios jugados.
8. Falta del partido M103 por el tercer puesto.
9. Unicidad KO no garantizada por SQLite cuando `group_letter` era NULL.
10. Migraciones de estadísticas dentro de la interfaz.
11. Error de parámetros duplicados en `save_match_stats()`.
12. Estadísticas y notas huérfanas al cambiar participantes.
13. Clasificados proyectados elegidos por probabilidad total y no por posición.
14. Propagación de rondas basada en parejas secuenciales en lugar de M73–M104.
15. Ausencia de pruebas del torneo.

## Solución

La lógica reglamentaria reside en `engine/`. `build_official_bracket()` es la única construcción del cuadro y se usa tanto en Monte Carlo como en Streamlit. El Anexo C se valida al cargar: 495 claves, todas las combinaciones de ocho grupos y ocho asignaciones únicas por fila.

SQLite se migra sin borrar ni recrear datos existentes. Los resultados KO conservan marcador, ganador y método de decisión por separado.

## Fuentes

- Reglamento FIFA 2026, Anexo C: https://digitalhub.fifa.com/m/636f5c9c6f29771f/original/FWC2026_regulations_EN.pdf
- Calendario oficial: https://fwc26teambasecamps.fifa.com/ReactApps/TBC/dist/static/media/match-schedule-english.071cf28145379e10f0cf.pdf
- Desempates FIFA: https://www.fifa.com/en/articles/groups-how-teams-qualify-tie-breakers
