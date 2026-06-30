# ⚽ World Cup 2026 — Predictor v2

Sistema de predicción estadística con detección de value bets.
Versión corregida con 17 bugs críticos resueltos.

---

## 🚀 INSTALACIÓN (3 pasos)

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Setup inicial (UNA sola vez — seguro para repetir)
python setup.py

# 3. Abrir dashboard
streamlit run app.py
```

---

## 🔌 ACTIVAR CUOTAS EN TIEMPO REAL (opcional)

1. Registrarse gratis en https://the-odds-api.com
2. Copiar la API key
3. Renombrar `.env.example` a `.env`
4. Reemplazar `pega_tu_key_aqui` con tu key real
5. Reiniciar el dashboard

**Plan gratuito:** 500 requests/mes — suficiente para todo el Mundial.

---

## 🧠 CORRECCIONES v2

| # | Problema | Solución |
|---|----------|----------|
| 1 | Partidos duplicados | UNIQUE constraint en DB |
| 2 | Database locked | WAL mode + context managers |
| 4 | qualify sin terceros | qualify = 1° + 2° + mejor 3° |
| 5 | Terceros no registrados | Correctamente contabilizados |
| 6 | Fases desplazadas | R32=llegar, R16=llegar, etc. |
| 7 | Penales 50/50 | Penales proporcionales al rating |
| 8 | Ratings agresivos | Shrinkage bayesiano |
| 9 | México ≈ Argentina | Transformación exponencial |
| 10 | Sin ventaja anfitrión | HOST_BOOST aplicado |
| 11 | Sin incertidumbre | Ruido gaussiano por simulación |

---

## 📁 ESTRUCTURA

```
worldcup2026v2/
├── app.py                     # Dashboard Streamlit
├── setup.py                   # Setup inicial
├── requirements.txt
├── .env.example               # Plantilla para API key
├── worldcup2026.db            # Base de datos (auto-generada)
├── data/
│   ├── tournament_data.py     # Equipos, grupos, fixtures
│   └── database.py            # SQLite con WAL + UNIQUE
└── models/
    ├── prediction_engine.py   # Dixon-Coles + Monte Carlo
    └── odds_api.py            # The Odds API integration
```
