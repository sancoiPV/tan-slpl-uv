# -*- coding: utf-8 -*-
"""
descarrega_i_converteix.py
--------------------------
Descarrega el model projecte-aina/aina-translator-es-ca des de Hugging Face
i el prepara per a l'ús amb CTranslate2.

NOTA: Aquest model ja es distribueix en format CTranslate2 natiu (model.bin).
No cal cap conversió. L'script simplement:
  1. Descarrega el model si no existeix ja.
  2. Copia els fitxers al directori de treball (DIR_CT2).
  3. Renomena spm.model → source.spm i target.spm (vocabulari compartit).
  4. Verifica que tots els fitxers essencials hi són.
  5. Fa una prova de traducció per confirmar que tot funciona.

Prerequisits:
    pip install sentencepiece huggingface_hub ctranslate2

Ús:
    python descarrega_i_converteix.py
"""

import os
import sys
import shutil

# --- Rutes de treball ---
MODEL_HF_ID  = "projecte-aina/aina-translator-es-ca"
DIR_ORIGINAL = r"C:\Users\santi\OneDrive\Documents\SLPL\taneu\aina-model-original"
DIR_CT2      = r"C:\Users\santi\OneDrive\Documents\SLPL\taneu\aina-translator-es-ca"


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


def descarrega_model():
    """Descarrega el model des de Hugging Face si no existeix ja."""
    from huggingface_hub import snapshot_download

    # El model ja és CT2: comprova model.bin (no pytorch_model.bin)
    if os.path.isdir(DIR_ORIGINAL) and os.path.isfile(
            os.path.join(DIR_ORIGINAL, "model.bin")):
        mida = os.path.getsize(
            os.path.join(DIR_ORIGINAL, "model.bin")) / (1024 ** 3)
        print(f"   Model ja descarregat a: {DIR_ORIGINAL}")
        print(f"   (model.bin: {mida:.1f} GB)")
        return

    print(f"   Descarregant {MODEL_HF_ID} ...")
    print(f"   Destinació: {DIR_ORIGINAL}")
    print(f"   Mida aproximada: ~1.8 GB — pot trigar uns minuts.")

    os.makedirs(DIR_ORIGINAL, exist_ok=True)
    try:
        ruta = snapshot_download(
            repo_id=MODEL_HF_ID,
            local_dir=DIR_ORIGINAL,
        )
        print(f"   Model descarregat correctament a: {ruta}")
    except Exception as e:
        print(f"\nERROR durant la descàrrega: {e}")
        print("Comprova la connexió a internet i que Hugging Face és accessible.")
        sys.exit(1)


def copia_a_dir_ct2():
    """
    Copia els fitxers necessaris de DIR_ORIGINAL a DIR_CT2.

    El model AINA ja és en format CTranslate2 natiu. Fitxers copiats:
      - model.bin              → model.bin  (pesos del model)
      - spm.model              → source.spm (tokenitzador entrada)
      - spm.model              → target.spm (tokenitzador eixida; vocabulari compartit)
      - shared_vocabulary.txt  → shared_vocabulary.txt (requerit per CT2 per carregar
                                  el vocabulari objectiu)
    """
    fitxers_ct2 = ["model.bin", "source.spm", "target.spm", "shared_vocabulary.txt"]
    if os.path.isdir(DIR_CT2) and all(
            os.path.isfile(os.path.join(DIR_CT2, f)) for f in fitxers_ct2):
        print(f"   Tots els fitxers CT2 ja existeixen a: {DIR_CT2}")
        return

    os.makedirs(DIR_CT2, exist_ok=True)
    print(f"   Copiant fitxers de {DIR_ORIGINAL}")
    print(f"   cap a              {DIR_CT2}")

    # 1. Copia model.bin
    origen_model = os.path.join(DIR_ORIGINAL, "model.bin")
    desti_model  = os.path.join(DIR_CT2, "model.bin")
    if not os.path.isfile(desti_model):
        print(f"   Copiant model.bin (~1.8 GB, pot trigar uns segons)...")
        shutil.copy2(origen_model, desti_model)
        print(f"   model.bin copiat.")
    else:
        print(f"   model.bin ja existeix, s'omiteix.")

    # 2. Copia spm.model com source.spm i target.spm (vocabulari compartit)
    origen_spm = os.path.join(DIR_ORIGINAL, "spm.model")
    if not os.path.isfile(origen_spm):
        print(f"   ERROR: spm.model no trobat a {DIR_ORIGINAL}")
        sys.exit(1)

    for nom_desti in ("source.spm", "target.spm"):
        desti_spm = os.path.join(DIR_CT2, nom_desti)
        if not os.path.isfile(desti_spm):
            shutil.copy2(origen_spm, desti_spm)
            print(f"   spm.model → {nom_desti} copiat.")
        else:
            print(f"   {nom_desti} ja existeix, s'omiteix.")

    # 3. Copia shared_vocabulary.txt (necessari per CT2 per carregar el vocabulari)
    origen_vocab = os.path.join(DIR_ORIGINAL, "shared_vocabulary.txt")
    desti_vocab  = os.path.join(DIR_CT2, "shared_vocabulary.txt")
    if not os.path.isfile(origen_vocab):
        print(f"   ERROR: shared_vocabulary.txt no trobat a {DIR_ORIGINAL}")
        sys.exit(1)
    if not os.path.isfile(desti_vocab):
        shutil.copy2(origen_vocab, desti_vocab)
        print(f"   shared_vocabulary.txt copiat.")
    else:
        print(f"   shared_vocabulary.txt ja existeix, s'omiteix.")

    print(f"   Còpia completada.")


def verifica_model_ct2():
    """Verifica que tots els fitxers essencials del model CT2 existeixen."""
    # config.json no existeix en aquest model; shared_vocabulary.txt és requerit per CT2
    fitxers_obligatoris = ["model.bin", "source.spm", "target.spm",
                           "shared_vocabulary.txt"]
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
    """Prova de càrrega i traducció per confirmar que el model funciona."""
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

        text_prova = "El servicio de lenguas ofrece asesoramiento lingüístico."
        tokens     = sp_src.Encode(text_prova, out_type=str)
        resultat   = traductor.translate_batch([tokens])
        traduccio  = sp_tgt.Decode(resultat[0].hypotheses[0])
        print(f"   ES: {text_prova}")
        print(f"   CA: {traduccio}")
        print(f"   Prova de traducció OK.")
    except Exception as e:
        print(f"   AVIS: La prova de càrrega ha fallat: {e}")
        print(f"   Comprova que ctranslate2 està instal·lat correctament.")


def main():
    print("=" * 55)
    print("  Preparació model AINA per a CTranslate2")
    print("  (model ja en format CT2 natiu, sense conversió)")
    print("=" * 55)
    print()

    print("[1/4] Comprovant dependències...")
    comprova_dependencies()
    print()

    print("[2/4] Comprovant/descarregant model de Hugging Face...")
    descarrega_model()
    print()

    print("[3/4] Copiant fitxers al directori de treball...")
    copia_a_dir_ct2()
    print()

    print("[4/4] Verificació final...")
    ok = verifica_model_ct2()
    if ok:
        prova_carrega()
        print()
        print("=" * 55)
        print("  MODEL LLEST! Ja pots iniciar el servidor.")
        print(f"  Ruta: {DIR_CT2}")
        print("=" * 55)
    else:
        print()
        print("ERROR: Algun fitxer essencial no s'ha trobat.")
        print("Torna a executar aquest script per reintentar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
