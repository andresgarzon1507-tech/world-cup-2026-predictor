# ⚽ World Cup 2026 Predictor

Aplicación web para seguir y proyectar el Mundial 2026 mediante simulaciones Monte Carlo, resultados reales, un bracket dinámico y análisis de value bets.

> **Demo:** publicación en Streamlit Community Cloud pendiente.

## Funcionalidades

- Simulación Monte Carlo completa y consciente de resultados eliminatorios.
- Probabilidades de avance a R32, octavos, cuartos, semifinal, final y título.
- Bracket dinámico que combina resultados finalizados con partidos pendientes.
- Modos público y administrador protegidos mediante Streamlit Secrets.
- Carga de resultados, estadísticas y notas de análisis en SQLite.
- Integración opcional con ESPN para enriquecer datos de partidos.
- Detector de value bets con probabilidad implícita, edge y valor esperado.
- Visualizaciones interactivas con Plotly.

## Stack

- Python
- Streamlit
- SQLite
- pandas
- NumPy
- SciPy
- Plotly

## Ejecución local

### 1. Crear el entorno virtual

```bash
python -m venv venv
```

Activar en Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Activar en macOS o Linux:

```bash
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Inicializar la base de datos

```bash
python setup.py
```

### 4. Ejecutar Streamlit

```bash
streamlit run app.py
```

## Configuración del modo administrador

Crear el archivo local `.streamlit/secrets.toml`:

```toml
ADMIN_PASSWORD = "tu_clave_segura"
```

En Streamlit Community Cloud, agregar la misma variable desde la configuración de **Secrets** de la aplicación.

Si `ADMIN_PASSWORD` no existe, la aplicación continúa funcionando en modo público.

## Integraciones opcionales

Las claves de servicios externos pueden configurarse mediante variables de entorno siguiendo `.env.example`.

La integración de cuotas nunca genera cuotas ficticias: si no hay proveedor configurado, el usuario debe introducir una cuota real para analizarla.

## Seguridad y datos locales

Los siguientes archivos no deben subirse al repositorio:

- `.streamlit/secrets.toml`
- `worldcup2026.db`
- archivos WAL o journal de SQLite
- `.env`

Las plantillas `.streamlit/secrets.example.toml` y `.env.example` sí pueden versionarse.

## Tests

```bash
pytest -q
```

## Capturas

> Pendiente: agregar capturas de la portada, probabilidades por fase, bracket y detector de value bets.

## Roadmap

- [ ] Publicación en Streamlit Community Cloud.
- [ ] Evolución temporal de probabilidades.
- [ ] Ranking de selecciones que suben y bajan.
- [ ] Histórico visual de predicciones.
- [ ] Panel optimizado de actualización de resultados.

## Aviso responsable

Las probabilidades son estimaciones estadísticas. El módulo de value bets no constituye asesoramiento financiero ni garantiza ganancias.
