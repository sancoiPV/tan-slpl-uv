# -*- coding: utf-8 -*-
"""
descarrega_i_converteix.py
--------------------------
Descarrega el model projecte-aina/aina-translator-es-ca des de Hugging Face
i el converteix al format CTranslate2 optimitzat per a CPU.

Prerequisits:
    pip install ctranslate2 sentencepiece huggingface_hub

Ús:
    python descarrega_i_converteix.py
"""

import os
import sys
import shutil

# --- Rutes de treball ---
MODEL_HF_ID   = "projecte-aina/aina-translator-es-ca"
DIR_ORIGINAL  = r"C:\SLPL\TAN\aina-model-original"
DIR_CT2       = r"C:\SLPL\TAN\aina-translator-es-ca"
QUANTITZACIO  = "int8"   # int8 = millor rendiment CPU; float32 = màxima qualitat


def comprova_dependencies():
    """Comprova que les biblioteques necessàries estan instal·lades."""
    errors = []
    try:
        import ctranslate2
        print(f"   ctranslate2 {ctranslate2.__version__} OK")
    except ImportError:
        errors.append("ctranslate2  →  pip install ctranslate2")
    try:
        import sentencepiece
        print(f"   sentencepiece OK")
    except ImportError:
        errors.append("sentencepiece  →  pip install sentencepiece")
    try:
        import huggingface_hub
        print(f"   huggingface_hub OK")
    except ImportError:
        errors.append("huggingface_hub  →  pip install huggingface_hub")
    if errors:
        print("\nERROR: Falten biblioteques:")
        for e in errors:
            print(f"   {e}")
        sys.exit(1)


def descarrega_model_original():
    """Descarrega el model original MarianMT des de Hugging Face."""
    from huggingface_hub import snapshot_download

    if os.path.isdir(DIR_ORIGINAL) and os.path.isfile(
            os.path.join(DIR_ORIGINAL, "pytorch_model.bin")):
        print(f"   Model original ja descarregat a: {DIR_ORIGINAL}")
        return

    print(f"   Descarregant {MODEL_HF_ID} ...")
    print(f"   Destinació: {DIR_ORIGINAL}")
    print(f"   (Pot trigar uns minuts...)")

    os.makedirs(DIR_ORIGINAL, exist_ok=True)
    try:
        ruta = snapshot_download(
            repo_id=MODEL_HF_ID,
            local_dir=DIR_ORIGINAL,
            ignore_patterns=["*.msgpack", "flax_model*", "tf_model*",
                              "rust_model*", "*.ot"],
        )
        print(f"   Model descarregat correctament a: {ruta}")
    except Exception as e:
        print(f"\nERROR durant la descàrrega: {e}")
        print("Comprova la connexió a internet i que Hugging Face és accessible.")
        sys.exit(1)


def converteix_a_ctranslate2():
    """Converteix el model MarianMT al format CTranslate2."""
    import ctranslate2

    if os.path.isdir(DIR_CT2) and os.path.isfile(
            os.path.join(DIR_CT2, "model.bin")):
        print(f"   Model CTranslate2 ja existeix a: {DIR_CT2}")
        return

    print(f"   Convertint a CTranslate2 (quantització: {QUANTITZACIO})...")
    print(f"   Origen:     {DIR_ORIGINAL}")
    print(f"   Destinació: {DIR_CT2}")

    os.makedirs(DIR_CT2, exist_ok=True)
    try:
        convertidor = ctranslate2.converters.OpusMTConverter(DIR_ORIGINAL)
        convertidor.convert(DIR_CT2, quantization=QUANTITZACIO, force=True)
        print(f"   Conversió completada.")
    except Exception as e:
        print(f"\nERROR durant la conversió: {e}")
        sys.exit(1)


def copia_fitxers_tokenitzador():
    """
    Copia els fitxers .spm del directori original al directori CT2
    si la conversió no els ha copiat automàticament.
    """
    fitxers_spm = ["source.spm", "target.spm"]
    for nom in fitxers_spm:
        desti = os.path.join(DIR_CT2, nom)
        if not os.path.isfile(desti):
            origen = os.path.join(DIR_ORIGINAL, nom)
            if os.path.isfile(origen):
                shutil.copy2(origen, desti)
                print(f"   Copiat tokenitzador: {nom}")
            else:
                # Alguns repositoris usen 'tokenizer.model' en lloc de .spm
                alternativa = os.path.join(DIR_ORIGINAL, "tokenizer.model")
                if os.path.isfile(alternativa) and nom == "source.spm":
                    shutil.copy2(alternativa, desti)
                    shutil.copy2(alternativa,
                                 os.path.join(DIR_CT2, "target.spm"))
                    print(f"   Copiat tokenitzador alternatiu: tokenizer.model")
                else:
                    print(f"   AVIS: No s'ha trobat {nom} — el servidor "
                          f"podria fallar en iniciar.")


def verifica_model_ct2():
    """Verifica que tots els fitxers essencials del model CT2 existeixen."""
    fitxers_obligatoris = ["model.bin", "source.spm", "target.spm",
                           "config.json"]
    print(f"\n   Verificació dels fitxers a {DIR_CT2}:")
    tot_ok = True
    for nom in fitxers_obligatoris:
        ruta = os.path.join(DIR_CT2, nom)
        if os.path.isfile(ruta):
            mida = os.path.getsize(ruta) / (1024 * 1024)
            print(f"   [OK] {nom}  ({mida:.1f} MB)")
        else:
            print(f"   [FALTA] {nom}")
            tot_ok = False
    return tot_ok


def prova_carrega():
    """Prova de càrrega del model per confirmar que funciona."""
    import ctranslate2
    import sentencepiece as spm

    print("\n   Provant càrrega del model...")
    try:
        traductor = ctranslate2.Translator(
            DIR_CT2, device="cpu", inter_threads=4
        )
        sp_src = spm.SentencePieceProcessor()
        sp_src.Load(os.path.join(DIR_CT2, "source.spm"))
        sp_tgt = spm.SentencePieceProcessor()
        sp_tgt.Load(os.path.join(DIR_CT2, "target.spm"))

        # Frase de prova
        text_prova = "Hola mundo"
        tokens = sp_src.Encode(text_prova, out_type=str)
        resultat = traductor.translate_batch([tokens])
        traduccio = sp_tgt.Decode(resultat[0].hypotheses[0])
        print(f"   Prova de traducció OK: '{text_prova}' → '{traduccio}'")
    except Exception as e:
        print(f"   AVIS: La prova de càrrega ha fallat: {e}")
        print(f"   El model podria funcionar igualment amb el servidor Flask.")


def main():
    print("=" * 55)
    print("  Descàrrega i conversió model AINA → CTranslate2")
    print("=" * 55)
    print()

    print("[1/4] Comprovant dependències...")
    comprova_dependencies()
    print()

    print("[2/4] Descarregant model original de Hugging Face...")
    descarrega_model_original()
    print()

    print("[3/4] Convertint a format CTranslate2...")
    converteix_a_ctranslate2()
    copia_fitxers_tokenitzador()
    print()

    print("[4/4] Verificació final...")
    ok = verifica_model_ct2()
    if ok:
        prova_carrega()
        print()
        print("=" * 55)
        print("  MODEL LLEST! Ja pots iniciar el servidor.")
        print(f"  Ruta del model: {DIR_CT2}")
        print("=" * 55)
    else:
        print()
        print("AVIS: Algun fitxer essencial no s'ha trobat.")
        print("Torna a executar aquest script per reintentar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
