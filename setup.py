# setup.py
# Inicialización manual opcional. La app ejecuta la misma función al arrancar.

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from data.database import ensure_database_initialized, get_all_matches


def setup():
    print("=" * 55)
    print("  WORLD CUP 2026 — SISTEMA DE PREDICCIÓN v2")
    print("=" * 55)

    initialized = ensure_database_initialized()
    total = len(get_all_matches())

    print()
    if initialized:
        print("✅ Base inicializada con equipos y fixture completo.")
    else:
        print("✅ La base ya estaba inicializada; no se modificaron datos.")

    print(f"📅 Partidos disponibles: {total}")
    print()
    print("▶  Para abrir el dashboard ejecutá:")
    print("   streamlit run app.py")
    print("=" * 55)


if __name__ == "__main__":
    setup()
