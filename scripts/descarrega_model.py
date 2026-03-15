#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
descarrega_model.py
Script per descarregar el model AINA (castellà→català) de HuggingFace
i guardar-lo localment a la carpeta de models del projecte TANEU.

Servei de Llengües i Política Lingüística - Universitat de València
"""

import os
import sys
from pathlib import Path

# Identificador del model a HuggingFace Hub
MODEL_ID = "projecte-aina/aina-translator-es-ca"

# Ruta local on es desarà el model
MODEL_DIR = Path(__file__).parent.parent / "models" / "aina-es-ca"


def descarrega_model(model_id: str = MODEL_ID, dest: Path = MODEL_DIR) -> None:
    """Descarrega el model i el tokenitzador de HuggingFace i els desa localment."""
    try:
        from transformers import MarianMTModel, MarianTokenizer
    except ImportError:
        print("ERROR: El paquet 'transformers' no està instal·lat.")
        print("Executa: pip install transformers sentencepiece torch")
        sys.exit(1)

    dest.mkdir(parents=True, exist_ok=True)
    print(f"Descarregant model '{model_id}'...")
    print(f"Destinació: {dest}")

    # Descarrega tokenitzador
    print("  → Descarregant tokenitzador...")
    tokenizer = MarianTokenizer.from_pretrained(model_id)
    tokenizer.save_pretrained(str(dest))

    # Descarrega model
    print("  → Descarregant pesos del model (pot trigar uns minuts)...")
    model = MarianMTModel.from_pretrained(model_id)
    model.save_pretrained(str(dest))

    print(f"\nModel desat correctament a: {dest}")
    print("Fitxers del model:")
    for f in sorted(dest.iterdir()):
        mida = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name:40s} {mida:8.2f} MB")


if __name__ == "__main__":
    descarrega_model()
