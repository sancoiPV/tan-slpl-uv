# -*- coding: utf-8 -*-
"""
test_traduccio.py
-----------------
Script de prova per al servidor TAN portàtil.
Comprova que el servidor funciona i fa la traducció de la frase de referència.

Ús (amb el servidor ja en marcha):
    python test_traduccio.py

    o bé:
    python test_traduccio.py http://127.0.0.1:5001
"""

import sys
import json
import time

try:
    import requests
except ImportError:
    print("ERROR: La biblioteca 'requests' no està instal·lada.")
    print("Activa l'entorn virtual i executa: pip install requests")
    sys.exit(1)

# URL del servidor (per defecte local, pot passarse com a argument)
BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:5001"

# Frases de prova
PROVES = [
    # Frase principal requerida
    "El servicio de lenguas ofrece asesoramiento lingüístico a la comunidad universitaria.",
    # Frases addicionals de verificació
    "La universidad organiza cursos de formación para el personal docente e investigador.",
    "Los estudiantes deben matricularse antes del final del plazo establecido.",
    "El rector ha firmado el convenio de colaboración con otras instituciones académicas.",
    "Hay que revisar los criterios de evaluación de los trabajos finales de grado.",
]

SEPARADOR = "─" * 60


def comprova_salut():
    """Comprova que el servidor respon al endpoint /health."""
    print(f"Connectant a: {BASE_URL}/health ...")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        if r.status_code == 200:
            dades = r.json()
            print(f"   Estat:      {dades.get('estat', '?')}")
            print(f"   Model:      {dades.get('model', '?')}")
            print(f"   Backend:    {dades.get('backend', '?')}")
            print(f"   Device:     {dades.get('device', '?')}")
            print(f"   Temps actiu: {dades.get('temps_actiu', '?')}")
            return True
        else:
            print(f"   Resposta inesperable: HTTP {r.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\nERROR: No s'ha pogut connectar a {BASE_URL}")
        print("Comprova que el servidor està en marcha (start_server_portatil.bat)")
        return False
    except Exception as e:
        print(f"   Error: {e}")
        return False


def traduccio_prova(text: str) -> dict:
    """Envia una petició de traducció i retorna el resultat."""
    peticio = {"text": text, "src": "es", "tgt": "ca"}
    t0 = time.perf_counter()
    r = requests.post(
        f"{BASE_URL}/translate",
        json=peticio,
        timeout=60,
    )
    t1 = time.perf_counter()

    if r.status_code == 200:
        dades = r.json()
        dades["temps_total_ms"] = round((t1 - t0) * 1000)
        return dades
    else:
        return {"error": f"HTTP {r.status_code}: {r.text}"}


def main():
    print()
    print(SEPARADOR)
    print("  Prova de funcionament — Servidor TAN portàtil")
    print(f"  Servidor: {BASE_URL}")
    print(SEPARADOR)
    print()

    # 1. Comprova salut del servidor
    print("[1] Comprovant l'estat del servidor...")
    if not comprova_salut():
        sys.exit(1)
    print()

    # 2. Tradueix les frases de prova
    print("[2] Executant proves de traducció...")
    print()

    errors = 0
    for i, text in enumerate(PROVES, 1):
        print(f"  Prova {i}/{len(PROVES)}:")
        print(f"  ES: {text}")

        resultat = traduccio_prova(text)

        if "error" in resultat:
            print(f"  CA: [ERROR] {resultat['error']}")
            errors += 1
        else:
            traduccio = resultat.get("translation", "")
            temps     = resultat.get("temps_ms", resultat.get("temps_total_ms", 0))
            print(f"  CA: {traduccio}")
            print(f"      ({temps} ms)")
        print()

    # 3. Resum
    print(SEPARADOR)
    if errors == 0:
        print(f"  RESULTAT: Totes {len(PROVES)} proves han passat correctament.")
        print()
        print("  Frase de referència:")
        print(f"  ES: {PROVES[0]}")
        print(f"  CA: {traduccio_prova(PROVES[0]).get('translation', '[error]')}")
    else:
        print(f"  RESULTAT: {errors} de {len(PROVES)} proves han fallat.")
    print(SEPARADOR)
    print()


if __name__ == "__main__":
    main()
