# -*- coding: utf-8 -*-
"""
server_portatil.py
------------------
Servidor Flask amb motor CTranslate2 per a traducció automàtica
castellà → valencià (AINA) optimitzat per a CPU (Intel Core i7).

Ús:
    python server_portatil.py

Endpoints:
    POST /translate   {"text": "...", "src": "es", "tgt": "ca"}
    GET  /health      Comprova l'estat del servidor
"""

import os
import sys
import time
import logging

from flask import Flask, request, jsonify

# --- Configuració de rutes ---
MODEL_DIR = r"C:\Users\santi\OneDrive\Documents\SLPL\taneu\aina-translator-es-ca"
PORT      = 5001

# --- Paràmetres CTranslate2 (optimitzats per i7-1255U, 10 nuclis) ---
# inter_threads: fils paral·lels per a traduccions concurrents
# intra_threads: fils per operació de traducció interna
CT2_DEVICE        = "cpu"
CT2_INTER_THREADS = 8
CT2_INTRA_THREADS = 4

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ======================================================================
# Càrrega del model (en iniciar el servidor)
# ======================================================================

traductor  = None
sp_source  = None
sp_target  = None
_model_ok  = False
_t_inici   = None


def carrega_model():
    """Carrega el model CTranslate2 i els tokenitzadors sentencepiece."""
    global traductor, sp_source, sp_target, _model_ok, _t_inici

    log.info("Carregant model CTranslate2...")
    log.info(f"  Ruta: {MODEL_DIR}")
    log.info(f"  Device: {CT2_DEVICE}  |  inter_threads={CT2_INTER_THREADS}  "
             f"|  intra_threads={CT2_INTRA_THREADS}")

    # Comprova que el directori del model existeix
    if not os.path.isdir(MODEL_DIR):
        log.error(f"ERROR: El directori del model no existeix: {MODEL_DIR}")
        log.error("Executa primer descarrega_i_converteix.py")
        sys.exit(1)

    # Comprova fitxers essencials
    fitxers = ["model.bin", "source.spm", "target.spm"]
    for nom in fitxers:
        if not os.path.isfile(os.path.join(MODEL_DIR, nom)):
            log.error(f"ERROR: Fitxer no trobat: {os.path.join(MODEL_DIR, nom)}")
            log.error("Executa primer descarrega_i_converteix.py")
            sys.exit(1)

    try:
        import ctranslate2
        import sentencepiece as spm

        t0 = time.time()

        # Càrrega del model de traducció
        traductor = ctranslate2.Translator(
            MODEL_DIR,
            device=CT2_DEVICE,
            inter_threads=CT2_INTER_THREADS,
            intra_threads=CT2_INTRA_THREADS,
            compute_type="int8",          # Consistent amb la quantització del model
        )

        # Càrrega dels tokenitzadors sentencepiece
        sp_source = spm.SentencePieceProcessor()
        sp_source.Load(os.path.join(MODEL_DIR, "source.spm"))

        sp_target = spm.SentencePieceProcessor()
        sp_target.Load(os.path.join(MODEL_DIR, "target.spm"))

        t1 = time.time()
        _model_ok = True
        _t_inici  = time.time()

        log.info(f"Model carregat correctament en {t1 - t0:.1f}s")
        log.info(f"Servidor llest a http://127.0.0.1:{PORT}")

    except ImportError as e:
        log.error(f"ERROR: Biblioteca no instal·lada: {e}")
        log.error("Executa primer: instala_entorn.bat")
        sys.exit(1)
    except Exception as e:
        log.error(f"ERROR en carregar el model: {e}")
        sys.exit(1)


# ======================================================================
# Lògica de traducció
# ======================================================================

def tradueix_fragment(text: str) -> str:
    """
    Tradueix un fragment de text de castellà a valencià/català
    usant el model CTranslate2 AINA.

    Args:
        text: text en castellà

    Returns:
        text traduït al valencià
    """
    text = text.strip()
    if not text:
        return ""

    # Tokenització amb sentencepiece
    tokens_entrada = sp_source.Encode(text, out_type=str)

    # Traducció amb CTranslate2
    resultats = traductor.translate_batch(
        [tokens_entrada],
        beam_size=4,
        max_decoding_length=512,
        no_repeat_ngram_size=3,
    )

    # Descodificació del resultat
    tokens_eixida = resultats[0].hypotheses[0]
    traduccio = sp_target.Decode(tokens_eixida)

    return traduccio


def tradueix_text_llarg(text: str, max_car: int = 500) -> str:
    """
    Tradueix un text llarg dividint-lo en fragments per paràgrafs
    i frases per no superar el límit de tokens del model.

    Args:
        text:    text en castellà (pot ser llarg)
        max_car: màxim de caràcters per fragment

    Returns:
        text complet traduït al valencià
    """
    # Dividir per paràgrafs (conserva línies en blanc)
    paragraf_originals = text.split("\n")
    resultats = []

    for paragraf in paragraf_originals:
        paragraf = paragraf.strip()

        if not paragraf:
            resultats.append("")
            continue

        # Si el paràgraf és curt, traduïm directament
        if len(paragraf) <= max_car:
            resultats.append(tradueix_fragment(paragraf))
            continue

        # Paràgrafs llargs: dividim per frases (punt + espai)
        frases    = []
        acumulat  = ""
        for part in paragraf.replace(". ", ".|").replace("? ", "?|").replace("! ", "!|").split("|"):
            if len(acumulat) + len(part) <= max_car:
                acumulat += part + " "
            else:
                if acumulat.strip():
                    frases.append(acumulat.strip())
                acumulat = part + " "
        if acumulat.strip():
            frases.append(acumulat.strip())

        # Traduïm cada fragment i reunim
        trad_frases = [tradueix_fragment(f) for f in frases]
        resultats.append(" ".join(trad_frases))

    return "\n".join(resultats)


# ======================================================================
# Aplicació Flask
# ======================================================================

app = Flask(__name__)


@app.after_request
def afegeix_cors(response):
    """
    Afegeix les capçaleres CORS a TOTES les respostes (incloses les d'error).
    Substitueix flask-cors per evitar inconsistències entre versions.
    """
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition, X-Temps-Ms'
    return response


@app.route("/health", methods=["GET", "OPTIONS"])
def salut():
    """
    GET /health
    Retorna l'estat del servidor i informació bàsica.
    OPTIONS /health — respon al preflight CORS del navegador.
    """
    if request.method == "OPTIONS":
        return '', 204

    if not _model_ok:
        return jsonify({"estat": "error", "missatge": "Model no carregat"}), 503

    temps_actiu = int(time.time() - _t_inici) if _t_inici else 0
    hores  = temps_actiu // 3600
    minuts = (temps_actiu % 3600) // 60
    segons = temps_actiu % 60

    return jsonify({
        "estat":        "ok",
        "model":        "projecte-aina/aina-translator-es-ca",
        "backend":      "CTranslate2",
        "device":       CT2_DEVICE,
        "port":         PORT,
        "temps_actiu":  f"{hores:02d}:{minuts:02d}:{segons:02d}",
    })


@app.route("/translate", methods=["POST", "OPTIONS"])
def tradueix():
    """
    POST /translate
    Cos de la petició (JSON):
        {"text": "El texto a traducir", "src": "es", "tgt": "ca"}

    Resposta (JSON):
        {"translation": "El text traduït", "temps_ms": 123}

    OPTIONS /translate — respon al preflight CORS del navegador.

    Errors:
        400 si falta el camp 'text'
        503 si el model no està carregat
    """
    if request.method == "OPTIONS":
        return '', 204

    if not _model_ok:
        return jsonify({
            "error": "El model no està carregat. Comprova l'inici del servidor."
        }), 503

    # Valida la petició
    dades = request.get_json(silent=True)
    if not dades:
        return jsonify({"error": "Cal enviar un cos JSON vàlid."}), 400

    text = dades.get("text", "").strip()
    if not text:
        return jsonify({"error": "El camp 'text' és obligatori i no pot ser buit."}), 400

    src = dades.get("src", "es")
    tgt = dades.get("tgt", "ca")

    # Comprova la parella de llengua (només es→ca suportada)
    if src != "es" or tgt not in ("ca", "val", "va"):
        return jsonify({
            "error": f"Parella no suportada: {src}→{tgt}. "
                     f"Únicament es→ca/val.",
        }), 400

    # Traducció
    t0 = time.perf_counter()
    try:
        traduccio = tradueix_text_llarg(text)
    except Exception as e:
        log.exception(f"Error traduint: {e}")
        return jsonify({"error": f"Error intern de traducció: {e}"}), 500
    t1 = time.perf_counter()

    temps_ms = round((t1 - t0) * 1000)
    log.info(f"Traduït ({len(text)} car, {temps_ms} ms): "
             f"{text[:60]}{'...' if len(text) > 60 else ''}")

    return jsonify({
        "translation": traduccio,
        "temps_ms":    temps_ms,
        "car_entrada": len(text),
    })


# ======================================================================
# Punt d'entrada
# ======================================================================

if __name__ == "__main__":
    print()
    print("=" * 55)
    print("  Servidor TAN portàtil - SLPL Universitat de València")
    print("  Model: projecte-aina/aina-translator-es-ca")
    print("  Backend: CTranslate2 (CPU)")
    print("=" * 55)
    print()

    # Carrega el model abans d'iniciar Flask
    carrega_model()

    print()
    print(f"  Servidor escoltant a: http://127.0.0.1:{PORT}")
    print(f"  Salut:     GET  http://127.0.0.1:{PORT}/health")
    print(f"  Traducció: POST http://127.0.0.1:{PORT}/translate")
    print()
    print("  Prem Ctrl+C per aturar el servidor.")
    print("=" * 55)
    print()

    # Inicia Flask (debug=False per a producció)
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
