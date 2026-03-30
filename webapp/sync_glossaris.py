#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per copiar els glossaris del projecte actiu al repositori git.
Executar abans de fer git push per incloure els glossaris nous.

Ús: python webapp/sync_glossaris.py
"""
import shutil
from pathlib import Path

# Ruta dels glossaris actius (on l'API els desa)
ORIGEN = Path(__file__).parent.parent / "glossaris"
# Ruta del repositori git
REPO = Path(__file__).parent.parent / "tan-slpl-uv" / "glossaris"

if not ORIGEN.exists():
    print(f"No existeix la carpeta d'origen: {ORIGEN}")
    exit(1)

REPO.mkdir(parents=True, exist_ok=True)

copiats = 0
for tsv in ORIGEN.glob("*.tsv"):
    dest = REPO / tsv.name
    shutil.copy2(tsv, dest)
    copiats += 1
    print(f"  Copiat: {tsv.name}")

print(f"\n{copiats} glossaris sincronitzats a {REPO}")
