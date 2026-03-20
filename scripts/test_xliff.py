# -*- coding: utf-8 -*-
"""
test_xliff.py
=============
Prova ràpida de la funció converteix_a_xliff() amb un sol fitxer.

Ús (des del directori arrel del projecte):
  .venv\Scripts\python scripts\test_xliff.py

Modifica les variables CAS_PATH i TIKAL si cal.
"""

import sys
import tempfile
from pathlib import Path

# ── Configuració ──────────────────────────────────────────────────────────────
# Fitxer de prova (un dels DOCX del corpus)
CAS_PATH = Path("corpus d'entrenament i afinament/06. Orfeó.29.06.25_CAS.docx")

# Ruta a tikal.cmd (ajusta si Tikal s'ha instal·lat en una subcarpeta diferent)
TIKAL_PATTERN = "tools/tikal"

# ── Cerca tikal.cmd ───────────────────────────────────────────────────────────
def troba_tikal() -> str | None:
    tikal_dir = Path(TIKAL_PATTERN)
    if not tikal_dir.exists():
        return None
    found = list(tikal_dir.rglob('tikal.cmd'))
    return str(found[0]) if found else None

# ── Import de les funcions del pipeline ───────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.corpus_builder_xliff import converteix_a_xliff, extrau_segments_xliff

# ── Execució de la prova ──────────────────────────────────────────────────────
def main():
    tikal_cmd = troba_tikal()
    if not tikal_cmd:
        print(f"[ERROR] tikal.cmd no trobat a '{TIKAL_PATTERN}'")
        print("        Executa: powershell -ExecutionPolicy Bypass -File scripts\\instala_tikal.ps1")
        sys.exit(1)

    print(f"Tikal:       {tikal_cmd}")
    print(f"Fitxer:      {CAS_PATH}")

    if not CAS_PATH.exists():
        print(f"[ERROR] El fitxer de prova no existeix: {CAS_PATH}")
        print("        Ajusta la variable CAS_PATH a test_xliff.py")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        xliff_cas = tmp_path / "test_CAS.xlf"

        print()
        print("Convertint DOCX → XLF via Tikal...")
        ok = converteix_a_xliff(CAS_PATH, xliff_cas, tikal_cmd)

        if not ok:
            print("[ERROR] La conversió ha fallat.")
            sys.exit(1)

        print(f"Conversió:   OK  ({xliff_cas.stat().st_size // 1024} KB)")

        segs = extrau_segments_xliff(xliff_cas)
        print(f"Segments:    {len(segs)}")
        print()
        print("Primers 5 segments:")
        print("-" * 60)
        for k, v in list(segs.items())[:5]:
            print(f"  [{k:>4}]  {v[:70]}")
        print("-" * 60)
        print()
        print("✓ Prova completada correctament.")

if __name__ == '__main__':
    main()
