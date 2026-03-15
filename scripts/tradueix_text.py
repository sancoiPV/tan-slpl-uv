#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tradueix_text.py
Script principal de traducció automàtica castellà→català/valencià
usant el model AINA de Projecte AINA (BSC).

Model: projecte-aina/aina-translator-es-ca
Servei de Llengües i Política Lingüística - Universitat de València
"""

import sys
import time
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

MODEL_ID  = "projecte-aina/aina-translator-es-ca"
MODEL_DIR = Path(__file__).parent.parent / "models" / "aina-es-ca"

# ─── Càrrega del model ────────────────────────────────────────────────────────

def carrega_model(model_path: Path = MODEL_DIR):
    """
    Carrega el tokenitzador i el model MarianMT des del disc local.
    Si no existeix localment, el descarrega de HuggingFace Hub.

    Retorna: (tokenizer, model)
    """
    try:
        from transformers import MarianMTModel, MarianTokenizer
    except ImportError:
        print("ERROR: El paquet 'transformers' no està instal·lat.")
        print("Executa primer: pip install -r requirements.txt")
        sys.exit(1)

    origen = str(model_path) if model_path.exists() else MODEL_ID

    if model_path.exists():
        print(f"[INFO] Carregant model local: {model_path}")
    else:
        print(f"[INFO] Model local no trobat. Descarregant de HuggingFace: {MODEL_ID}")
        print("[INFO] Això pot trigar uns minuts la primera vegada...")

    tokenizer = MarianTokenizer.from_pretrained(origen)
    model     = MarianMTModel.from_pretrained(origen)

    print("[INFO] Model carregat correctament.")
    return tokenizer, model


# ─── Funció de traducció ──────────────────────────────────────────────────────

def translate(
    text:      str,
    tokenizer = None,
    model     = None,
    src:       str = "es",
    tgt:       str = "ca",
    max_length: int = 512,
    num_beams:  int = 4,
) -> str:
    """
    Tradueix un text de la llengua font (src) a la llengua destí (tgt).

    Paràmetres:
        text       -- text original a traduir
        tokenizer  -- tokenitzador MarianTokenizer (opcional; es carrega si és None)
        model      -- model MarianMTModel (opcional; es carrega si és None)
        src        -- codi de llengua font  (per defecte: 'es')
        tgt        -- codi de llengua destí (per defecte: 'ca')
        max_length -- longitud màxima de la traducció en tokens
        num_beams  -- amplada del feix de cerca (beam search)

    Retorna:
        str -- text traduït
    """
    if tokenizer is None or model is None:
        tokenizer, model = carrega_model()

    # Afegeix el prefix de llengua destí si el model ho requereix
    text_preparat = f">>{tgt}<< {text}"

    # Tokenitza
    entrades = tokenizer(
        [text_preparat],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=max_length,
    )

    # Genera la traducció
    sortides = model.generate(
        **entrades,
        num_beams=num_beams,
        max_length=max_length,
        early_stopping=True,
    )

    # Descodifica el resultat
    traduccio = tokenizer.decode(sortides[0], skip_special_tokens=True)
    return traduccio


# ─── Programa principal ───────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("  TANEU — Motor de Traducció Automàtica Neuronal")
    print("  Servei de Llengües i Política Lingüística - UV")
    print("=" * 60)
    print()

    # Carrega el model una sola vegada
    tokenizer, model = carrega_model()

    # ── Prova amb la frase de referència ──────────────────────────
    frase_prova = (
        "El sistema universitario valenciano necesita mejoras "
        "en sus servicios lingüísticos."
    )

    print()
    print("─" * 60)
    print("PROVA DE TRADUCCIÓ")
    print("─" * 60)
    print(f"  Original (es): {frase_prova}")

    inici = time.time()
    resultat = translate(frase_prova, tokenizer=tokenizer, model=model)
    temps    = time.time() - inici

    print(f"  Traducció (ca): {resultat}")
    print(f"  Temps: {temps:.2f} s")
    print("─" * 60)

    # ── Proves addicionals ────────────────────────────────────────
    frases_addicionals = [
        "El Servicio de Lenguas ofrece asesoramiento lingüístico a toda la comunidad universitaria.",
        "Los estudiantes pueden solicitar la revisión de sus trabajos académicos.",
        "La normalización lingüística es un proceso gradual que requiere compromiso institucional.",
    ]

    print()
    print("PROVES ADDICIONALS")
    print("─" * 60)
    for frase in frases_addicionals:
        trad = translate(frase, tokenizer=tokenizer, model=model)
        print(f"  ES: {frase}")
        print(f"  CA: {trad}")
        print()
