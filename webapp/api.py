#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api.py
API REST del Motor de Traducció Automàtica Neuronal castellà→valencià (TANEU)
Servei de Llengües i Política Lingüística - Universitat de València

Endpoints:
  POST /tradueix               — Traducció/correcció de text pla
  POST /tradueix-document      — Traducció de fitxers .docx i .pptx
  POST /desa-postedicio        — Desa una postedició humana al corpus
  GET  /estadistiques          — Estadístiques d'ús de la sessió
  GET  /salut                  — Estat del servei

Inici:
  uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import io
import json
import logging
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Literal, Optional

# ─── FastAPI i dependències web ───────────────────────────────────────────────
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

# ─── Rutes del projecte ───────────────────────────────────────────────────────
ARREL_PROJECTE  = Path(__file__).parent.parent
DIR_MODELS      = ARREL_PROJECTE / "models" / "aina-es-ca"
DIR_LOGS        = ARREL_PROJECTE / "logs"
DIR_POSTEDICIONS = ARREL_PROJECTE / "corpus" / "postedicions"
FITXER_LOG      = DIR_LOGS / "api.log"
FITXER_STATS    = DIR_LOGS / "estadistiques.json"

# ─── Constants ────────────────────────────────────────────────────────────────
VERSIO          = "1.0"
MODEL_ID        = "projecte-aina/aina-translator-es-ca"
MAX_MIDA_FITXER = 20 * 1024 * 1024          # 20 MB en bytes
EXTENSIONS_OK   = {".docx", ".pptx"}

# ─── Configuració del logging ─────────────────────────────────────────────────
DIR_LOGS.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(FITXER_LOG, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("taneu.api")

# ─── Imports de les classes preservadores de format ───────────────────────────
# Afegim l'arrel del projecte al path perquè 'scripts' siga trobable tant
# quan s'executa des de webapp/ com des de l'arrel (uvicorn webapp.api:app)
_arrel_sys = str(ARREL_PROJECTE)
if _arrel_sys not in sys.path:
    sys.path.insert(0, _arrel_sys)

try:
    from scripts.preserva_docx import PreservadorDocx
    from scripts.preserva_pptx import PreservadorPptx
    log.info("Classes preservadores de format carregades correctament.")
except ImportError as _err_import:
    PreservadorDocx = None  # type: ignore[assignment,misc]
    PreservadorPptx = None  # type: ignore[assignment,misc]
    log.warning("No s'han pogut importar les classes preservadores: %s", _err_import)

# ─── Estat global de l'aplicació ──────────────────────────────────────────────
_tokenizer  = None
_model      = None


def _carrega_postedicions_count() -> int:
    """Compta els fitxers de postedició existents al disc."""
    try:
        return len(list(DIR_POSTEDICIONS.glob("*.jsonl")))
    except Exception:
        return 0


_stats: dict = {
    "data":          str(date.today()),
    "paraules_avui": 0,
    "fitxers_avui":  0,
    "postedicions":  _carrega_postedicions_count(),
}


def _reinicia_stats_si_cal() -> None:
    """Reinicia els comptadors diaris si ha canviat el dia."""
    avui = str(date.today())
    if _stats["data"] != avui:
        _stats.update({
            "data":          avui,
            "paraules_avui": 0,
            "fitxers_avui":  0,
        })
        log.info("Comptadors diaris reiniciats per al dia %s", avui)


def _get_model():
    """Carrega el model i el tokenitzador de forma mandrosa (lazy loading)."""
    global _tokenizer, _model
    if _tokenizer is None or _model is None:
        try:
            from transformers import MarianMTModel, MarianTokenizer
            origen = str(DIR_MODELS) if DIR_MODELS.exists() else MODEL_ID
            log.info("Carregant model des de: %s", origen)
            _tokenizer = MarianTokenizer.from_pretrained(origen)
            _model     = MarianMTModel.from_pretrained(origen)
            log.info("Model carregat correctament.")
        except ImportError:
            log.error("Paquet 'transformers' no instal·lat.")
            raise HTTPException(
                status_code=503,
                detail="El servei de traducció no està disponible: "
                       "instal·la les dependències (pip install -r requirements.txt).",
            )
        except Exception as exc:
            log.exception("Error carregant el model: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"No s'ha pogut carregar el model de traducció: {exc}",
            )
    return _tokenizer, _model


def _tradueix_text(text: str) -> str:
    """Tradueix un text castellà→català usant el model AINA."""
    tokenizer, model = _get_model()
    preparat = f">>ca<< {text}"
    entrades = tokenizer(
        [preparat],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )
    sortides = model.generate(
        **entrades,
        num_beams=4,
        max_length=512,
        early_stopping=True,
    )
    return tokenizer.decode(sortides[0], skip_special_tokens=True)


def _compta_paraules(text: str) -> int:
    """Retorna el nombre de paraules d'un text."""
    return len(text.split())


# ─── Instàncies de les classes preservadores ──────────────────────────────────
# S'inicialitzen ací, after _tradueix_text, perquè el callable ja existeix.
_preservador_docx = PreservadorDocx(_tradueix_text) if PreservadorDocx else None
_preservador_pptx = PreservadorPptx(_tradueix_text) if PreservadorPptx else None

# ─── Creació de l'aplicació FastAPI ───────────────────────────────────────────
app = FastAPI(
    title       = "TANEU — Motor de Traducció Automàtica Neuronal",
    description = (
        "API REST del Motor de Traducció Automàtica Neuronal castellà→valencià "
        "del Servei de Llengües i Política Lingüística de la Universitat de València."
    ),
    version     = VERSIO,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# CORS: permet accés des de Netlify i qualsevol origen
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─── Esquemes Pydantic ────────────────────────────────────────────────────────

class PeticioTradueix(BaseModel):
    text: str = Field(
        ...,
        min_length  = 1,
        max_length  = 50_000,
        description = "Text en castellà a traduir o corregir.",
        examples    = ["El sistema universitario valenciano necesita mejoras."],
    )
    mode: Literal["traduccio", "correccio"] = Field(
        default     = "traduccio",
        description = "'traduccio' (es→ca) o 'correccio' (millora del text en valencià).",
    )


class RespostaTradueix(BaseModel):
    traduccio: str
    paraules:  int
    temps_ms:  int


class PeticioPostedicio(BaseModel):
    origen:      str = Field(..., description="Text original en castellà.")
    ta:          str = Field(..., description="Traducció automàtica generada pel sistema.")
    posteditada: str = Field(..., description="Traducció corregida pel tècnic.")
    tecnic:      str = Field(..., description="Identificador o nom del tècnic.")


class RespostaPostedicio(BaseModel):
    estat: str
    id:    str


class RespostaEstadistiques(BaseModel):
    paraules_avui: int
    fitxers_avui:  int
    postedicions:  int


class RespostaSalut(BaseModel):
    estat:  str
    model:  str
    versio: str


# ─── Endpoint: GET /salut ─────────────────────────────────────────────────────

@app.get(
    "/salut",
    response_model = RespostaSalut,
    summary        = "Comprova l'estat del servei",
    tags           = ["Sistema"],
)
async def salut() -> RespostaSalut:
    """Retorna l'estat operatiu de l'API i la versió."""
    log.debug("GET /salut — petició rebuda")
    origen_model = str(DIR_MODELS) if DIR_MODELS.exists() else MODEL_ID
    return RespostaSalut(
        estat  = "actiu",
        model  = origen_model,
        versio = VERSIO,
    )


@app.get("/health")
async def health():
    return await salut()


# ─── Endpoint: POST /translate (àlies per al frontend) ───────────────────────
# Accepta el format del frontend: {"text": "...", "src": "es", "tgt": "ca"}
# Retorna el format del frontend:  {"translation": "..."}

@app.post("/translate", tags=["Traducció"],
          summary="Àlies /tradueix compatible amb el frontend")
async def translate(peticio: dict):
    """
    Àlies de /tradueix amb format compatible amb config.js:
      Entrada: {"text": "...", "src": "es", "tgt": "ca"}
      Eixida:  {"translation": "...", "temps_ms": ...}
    """
    text = (peticio.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400,
                            detail="El camp 'text' és obligatori.")
    _reinicia_stats_si_cal()
    inici = time.perf_counter()
    try:
        resultat = _tradueix_text(text)
    except Exception as exc:
        log.exception("Error durant la traducció (/translate): %s", exc)
        raise HTTPException(status_code=500,
                            detail=f"Error intern: {exc}")
    temps_ms = int((time.perf_counter() - inici) * 1000)
    n_paraules = _compta_paraules(text)
    _stats["paraules_avui"] += n_paraules
    log.info("POST /translate — %d ms, %d paraules", temps_ms, n_paraules)
    return {"translation": resultat, "temps_ms": temps_ms}


# ─── Endpoint: POST /tradueix ─────────────────────────────────────────────────

@app.post(
    "/tradueix",
    response_model = RespostaTradueix,
    summary        = "Tradueix o corregeix text pla",
    tags           = ["Traducció"],
)
async def tradueix(peticio: PeticioTradueix) -> RespostaTradueix:
    """
    Tradueix text castellà→català (mode *traduccio*) o millora
    un text ja en valencià (mode *correccio*).
    """
    _reinicia_stats_si_cal()
    log.info("POST /tradueix — mode=%s paraules=%d", peticio.mode, _compta_paraules(peticio.text))

    if not peticio.text.strip():
        raise HTTPException(status_code=422, detail="El camp 'text' no pot estar buit.")

    inici = time.perf_counter()
    try:
        resultat = _tradueix_text(peticio.text)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Error durant la traducció: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Error intern durant la traducció: {exc}",
        )
    temps_ms = int((time.perf_counter() - inici) * 1000)

    n_paraules = _compta_paraules(peticio.text)
    _stats["paraules_avui"] += n_paraules
    log.info("Traducció completada en %d ms (%d paraules)", temps_ms, n_paraules)

    return RespostaTradueix(
        traduccio = resultat,
        paraules  = n_paraules,
        temps_ms  = temps_ms,
    )


# ─── Endpoint: POST /tradueix-document ───────────────────────────────────────

@app.post(
    "/tradueix-document",
    summary = "Tradueix un document .docx o .pptx",
    tags    = ["Traducció"],
)
async def tradueix_document(
    fitxer: UploadFile = File(..., description="Fitxer .docx o .pptx (màx. 20 MB)."),
    mode:   str        = Form(default="traduccio", description="'traduccio' o 'correccio'"),
) -> StreamingResponse:
    """
    Rep un fitxer .docx o .pptx, tradueix tot el text que conté
    i retorna el fitxer amb el **mateix nom i extensió** que l'original.
    """
    _reinicia_stats_si_cal()

    # ── Validació del fitxer ──────────────────────────────────────
    nom_original = fitxer.filename or "document"
    extensio     = Path(nom_original).suffix.lower()

    if extensio not in EXTENSIONS_OK:
        raise HTTPException(
            status_code = 415,
            detail      = (
                f"Extensió '{extensio}' no admesa. "
                f"Els formats acceptats són: {', '.join(sorted(EXTENSIONS_OK))}."
            ),
        )

    contingut = await fitxer.read()
    if len(contingut) > MAX_MIDA_FITXER:
        raise HTTPException(
            status_code = 413,
            detail      = (
                f"El fitxer supera la mida màxima de 20 MB "
                f"({len(contingut) / 1_048_576:.1f} MB rebuts)."
            ),
        )

    log.info(
        "POST /tradueix-document — fitxer='%s' mida=%.1f KB mode=%s",
        nom_original, len(contingut) / 1024, mode,
    )

    inici       = time.perf_counter()
    total_par   = 0
    buffer_eixida = io.BytesIO()

    try:
        if extensio == ".docx":
            total_par = _tradueix_docx(contingut, buffer_eixida)
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:  # .pptx
            total_par = _tradueix_pptx(contingut, buffer_eixida)
            mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Error traduint el document '%s': %s", nom_original, exc)
        raise HTTPException(
            status_code = 500,
            detail      = f"Error intern processant el document: {exc}",
        )

    temps_ms = int((time.perf_counter() - inici) * 1000)
    _stats["paraules_avui"] += total_par
    _stats["fitxers_avui"]  += 1

    log.info(
        "Document traduït en %d ms (%d paraules) → '%s'",
        temps_ms, total_par, nom_original,
    )

    buffer_eixida.seek(0)
    return StreamingResponse(
        buffer_eixida,
        media_type = mime_type,
        headers    = {
            "Content-Disposition": f'attachment; filename="{nom_original}"',
            "X-Paraules-Traduides": str(total_par),
            "X-Temps-Ms":          str(temps_ms),
        },
    )


def _tradueix_docx(contingut: bytes, eixida: io.BytesIO) -> int:
    """
    Tradueix un .docx usant PreservadorDocx (capçaleres, peus, quadres de text,
    camps especials protegits). Retorna el nombre de paraules de l'original.
    """
    if _preservador_docx is None:
        raise HTTPException(
            status_code=503,
            detail="La classe PreservadorDocx no està disponible. "
                   "Comprova que scripts/preserva_docx.py existeix i que "
                   "python-docx està instal·lat.",
        )
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="El paquet 'python-docx' no està instal·lat.",
        )

    # Compta paraules de l'original abans de traduir
    doc_original = Document(io.BytesIO(contingut))
    total_par = sum(
        _compta_paraules(p.text)
        for p in doc_original.paragraphs
        if p.text.strip()
    )

    # Traducció preservant format (retorna bytes)
    resultat = _preservador_docx.tradueix_document(contingut)
    eixida.write(resultat)
    eixida.seek(0)
    return total_par


def _tradueix_pptx(contingut: bytes, eixida: io.BytesIO) -> int:
    """
    Tradueix un .pptx usant PreservadorPptx (grups, taules, notes del presentador).
    Retorna el nombre de paraules de l'original.
    """
    if _preservador_pptx is None:
        raise HTTPException(
            status_code=503,
            detail="La classe PreservadorPptx no està disponible. "
                   "Comprova que scripts/preserva_pptx.py existeix i que "
                   "python-pptx està instal·lat.",
        )
    try:
        from pptx import Presentation
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="El paquet 'python-pptx' no està instal·lat.",
        )

    # Compta paraules de l'original abans de traduir
    prs_original = Presentation(io.BytesIO(contingut))
    total_par = 0
    for diapositiva in prs_original.slides:
        for forma in diapositiva.shapes:
            if forma.has_text_frame:
                for para in forma.text_frame.paragraphs:
                    text = "".join(r.text for r in para.runs)
                    total_par += _compta_paraules(text)

    # Traducció preservant format (retorna bytes)
    resultat = _preservador_pptx.tradueix_document(contingut)
    eixida.write(resultat)
    eixida.seek(0)
    return total_par


# ─── Endpoint: POST /recompte-paraules ───────────────────────────────────────

@app.post(
    "/recompte-paraules",
    summary = "Compta les paraules d'un document .docx o .pptx",
    tags    = ["Traducció"],
)
async def recompte_paraules(fitxer: UploadFile = File(...)):
    nom  = fitxer.filename or ""
    ext  = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
    contingut = await fitxer.read()
    buf  = io.BytesIO(contingut)
    buf.seek(0)
    total = 0
    if ext == "docx":
        from docx import Document
        doc = Document(buf)
        for para in doc.paragraphs:
            total += len(para.text.split())
        for taula in doc.tables:
            for fila in taula.rows:
                for cel in fila.cells:
                    for para in cel.paragraphs:
                        total += len(para.text.split())
    elif ext == "pptx":
        from pptx import Presentation
        prs = Presentation(buf)
        for diap in prs.slides:
            for shape in diap.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        total += len(para.text.split())
    return {"paraules": total, "fitxer": nom}


# ─── Endpoint: POST /desa-postedicio ─────────────────────────────────────────

@app.post(
    "/desa-postedicio",
    response_model = RespostaPostedicio,
    summary        = "Desa una postedició humana al corpus",
    tags           = ["Corpus"],
)
async def desa_postedicio(peticio: PeticioPostedicio) -> RespostaPostedicio:
    """
    Desa un parell (traducció automàtica, traducció corregida) al corpus
    de postedicions per a l'entrenament i l'avaluació del sistema.
    """
    _reinicia_stats_si_cal()

    if not peticio.origen.strip() or not peticio.posteditada.strip():
        raise HTTPException(
            status_code=422,
            detail="Els camps 'origen' i 'posteditada' no poden estar buits.",
        )

    id_entrada = str(uuid.uuid4())
    avui       = str(date.today())

    entrada = {
        "id":          id_entrada,
        "data":        avui,
        "tecnic":      peticio.tecnic.strip(),
        "origen":      peticio.origen.strip(),
        "ta":          peticio.ta.strip(),
        "posteditada": peticio.posteditada.strip(),
    }

    # Desa al fitxer JSONL del dia actual
    DIR_POSTEDICIONS.mkdir(parents=True, exist_ok=True)
    fitxer_dia = DIR_POSTEDICIONS / f"postedicions_{avui}.jsonl"
    try:
        with open(fitxer_dia, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.error("No s'ha pogut desar la postedició: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Error desant la postedició al disc: {exc}",
        )

    _stats["postedicions"] += 1
    log.info(
        "Postedició desada — id=%s tecnic='%s' fitxer=%s",
        id_entrada, peticio.tecnic, fitxer_dia.name,
    )

    return RespostaPostedicio(estat="desat", id=id_entrada)


# ─── Endpoint: GET /estadistiques ────────────────────────────────────────────

@app.get(
    "/estadistiques",
    response_model = RespostaEstadistiques,
    summary        = "Estadístiques d'ús de la sessió actual",
    tags           = ["Sistema"],
)
async def estadistiques() -> RespostaEstadistiques:
    """Retorna el recompte de paraules traduïdes, fitxers processats i postedicions del dia."""
    _reinicia_stats_si_cal()
    return RespostaEstadistiques(
        paraules_avui = _stats["paraules_avui"],
        fitxers_avui  = _stats["fitxers_avui"],
        postedicions  = _stats["postedicions"],
    )


# ─── Gestió global d'errors ───────────────────────────────────────────────────

@app.exception_handler(404)
async def no_trobat(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=404,
        content={"error": "Recurs no trobat", "detall": str(exc.detail)},
    )


@app.exception_handler(500)
async def error_intern(request, exc):
    from fastapi.responses import JSONResponse
    log.error("Error intern no controlat: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Error intern del servidor", "detall": "Consulta els registres de l'API."},
    )


# ─── Inici del servidor (execució directa) ───────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    log.info("Iniciant servidor TANEU API v%s", VERSIO)
    uvicorn.run(
        "api:app",
        host    = "0.0.0.0",
        port    = 8000,
        reload  = True,
        log_level = "info",
    )

