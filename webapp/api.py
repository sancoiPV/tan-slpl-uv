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

import base64
import csv
import io
import json
import logging
import re
import sys
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional

# ─── FastAPI i dependències web ───────────────────────────────────────────────
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

# ─── Rutes del projecte ───────────────────────────────────────────────────────
ARREL_PROJECTE  = Path(__file__).parent.parent
DIR_MODELS      = ARREL_PROJECTE / "model-afinar"
DIR_LOGS        = ARREL_PROJECTE / "logs"
DIR_POSTEDICIONS = ARREL_PROJECTE / "corpus" / "postedicions"
FITXER_LOG      = DIR_LOGS / "api.log"
FITXER_STATS    = DIR_LOGS / "estadistiques.json"

# ─── Constants ────────────────────────────────────────────────────────────────
VERSIO          = "1.0"
MODEL_ID        = "projecte-aina/aina-translator-es-ca"
MAX_MIDA_FITXER = 20 * 1024 * 1024          # 20 MB en bytes
EXTENSIONS_OK   = {".docx", ".pptx"}

# ─── Glossaris ────────────────────────────────────────────────────────────────
DIR_GLOSSARIS = ARREL_PROJECTE / "glossaris"
DIR_GLOSSARIS.mkdir(exist_ok=True)

DOMINIS = [
    "Art i Història de l'Art",
    "Biologia",
    "Ciències Polítiques",
    "Comunicacions institucionals i discursos",
    "Convenis",
    "Convocatòries: cursos, premis, beques, concursos",
    "Dret",
    "Economia",
    "Enginyeries",
    "Farmàcia",
    "Filologia i Lingüística",
    "Filosofia",
    "Física",
    "Formació del professorat i Ciències de l'Educació",
    "Geografia",
    "Història i Antropologia",
    "Informàtica",
    "Medicina i Infermeria",
    "Medi Ambient",
    "Música",
    "Notes de Premsa",
    "Pedagogia",
    "Psicologia",
    "Química",
    "Salut Laboral i Prevenció de Riscos",
]


def nom_fitxer_glossari(domini: str) -> Path:
    """Retorna la ruta del fitxer TSV per a un domini."""
    nom = re.sub(r'[^\w\s-]', '', domini, flags=re.UNICODE)
    nom = re.sub(r'\s+', '_', nom.strip())
    return DIR_GLOSSARIS / f"{nom}.tsv"


def carrega_glossari(domini: str) -> list[dict]:
    """Carrega les entrades d'un glossari des del disc."""
    path = nom_fitxer_glossari(domini)
    if not path.exists():
        return []
    entrades = []
    with open(path, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row.get('es') and row.get('ca'):
                entrades.append({
                    'es':     row['es'].strip(),
                    'ca':     row['ca'].strip(),
                    'tecnic': row.get('tecnic', '').strip(),
                    'data':   row.get('data', '').strip(),
                    'domini': domini,
                })
    return entrades


def desa_glossari(domini: str, entrades: list[dict]) -> None:
    """Desa les entrades d'un glossari al disc."""
    path = nom_fitxer_glossari(domini)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(
            f, fieldnames=['es', 'ca', 'tecnic', 'data', 'domini'],
            delimiter='\t',
        )
        writer.writeheader()
        writer.writerows(entrades)


def genera_nom_traduit(nom_original: str) -> str:
    """
    Genera el nom del fitxer traduït afegint el sufix _VAL.

    Si el nom conté _CAS (sense distingir majúscules/minúscules),
    el substitueix per _VAL. En cas contrari, afegeix _VAL just
    abans de l'extensió.

    Exemples:
      informe_CAS.docx     → informe_VAL.docx
      text_cas.pptx        → text_VAL.pptx
      document_Cas.docx    → document_VAL.docx
      presentacio.pptx     → presentacio_VAL.pptx
    """
    p = Path(nom_original)
    stem_nou, n_substitucions = re.subn(r'_cas', '_VAL', p.stem, flags=re.IGNORECASE)
    if n_substitucions == 0:
        stem_nou = p.stem + '_VAL'
    return stem_nou + p.suffix


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

# ─── Import del mòdul de preservació de format (estratègia XML directa) ───────
# Afegim l'arrel del projecte al path perquè 'scripts' siga trobable tant
# quan s'executa des de webapp/ com des de l'arrel (uvicorn webapp.api:app)
_arrel_sys = str(ARREL_PROJECTE)
if _arrel_sys not in sys.path:
    sys.path.insert(0, _arrel_sys)

try:
    from scripts.preserva_xml import tradueix_document as _tradueix_document_xml
    log.info("Mòdul preserva_xml carregat correctament.")
except ImportError as _err_import:
    _tradueix_document_xml = None  # type: ignore[assignment]
    log.warning("No s'ha pogut importar preserva_xml: %s", _err_import)

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
# expose_headers és IMPRESCINDIBLE perquè el navegador puga llegir
# Content-Disposition (nom del fitxer) en respostes fetch() cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = False,          # ha de ser False quan allow_origins=["*"]
    allow_methods     = ["*"],
    allow_headers     = ["*"],
    expose_headers    = [               # capçaleres llegibles per JavaScript
        "Content-Disposition",
        "X-Paraules-Traduides",
        "X-Temps-Ms",
    ],
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

    mime_types = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    mime_type = mime_types[extensio]

    try:
        total_par = _tradueix_fitxer_xml(contingut, extensio.lstrip('.'), buffer_eixida)
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

    nom_sortida = genera_nom_traduit(nom_original)
    log.info(
        "Document traduït en %d ms (%d paraules) → '%s'",
        temps_ms, total_par, nom_sortida,
    )

    buffer_eixida.seek(0)
    return StreamingResponse(
        buffer_eixida,
        media_type = mime_type,
        headers    = {
            "Content-Disposition": f'attachment; filename="{nom_sortida}"',
            "X-Paraules-Traduides": str(total_par),
            "X-Temps-Ms":          str(temps_ms),
        },
    )


def _tradueix_fitxer_xml(contingut: bytes, extensio: str, eixida: io.BytesIO) -> int:
    """
    Tradueix un .docx o .pptx usant manipulació directa de l'XML intern
    (scripts/preserva_xml.py). Retorna el nombre de paraules de l'original.

    El recompte de paraules es fa llegint el ZIP directament amb lxml,
    sense necessitat de python-docx ni python-pptx.
    """
    if _tradueix_document_xml is None:
        raise HTTPException(
            status_code=503,
            detail="El mòdul preserva_xml no està disponible. "
                   "Comprova que scripts/preserva_xml.py existeix i que "
                   "lxml està instal·lat (pip install lxml).",
        )

    # ── Recompte de paraules de l'original via lxml ──────────────────────────
    import zipfile as _zf
    from lxml import etree as _et

    _NS_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    _NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    # DOCX_REGEX / PPTX_REGEX es van moure dins de tradueix_document() (C4, v3).
    # Es defineixen localment aquí per al recompte de paraules.
    import re as _re
    _DOCX_REGEX = _re.compile(
        r'^word/(document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$'
    )
    _PPTX_REGEX = _re.compile(
        r'^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$'
    )

    regex  = _DOCX_REGEX if extensio == 'docx' else _PPTX_REGEX
    ns_t   = _NS_W      if extensio == 'docx' else _NS_A
    tag_t  = f'{{{ns_t}}}t'

    total_par = 0
    with _zf.ZipFile(io.BytesIO(contingut)) as z:
        for nom in z.namelist():
            if regex.match(nom):
                try:
                    arbre = _et.fromstring(z.read(nom))
                    for t in arbre.iter(tag_t):
                        if t.text:
                            total_par += _compta_paraules(t.text)
                except Exception:
                    pass

    # ── Traducció preservant format ──────────────────────────────────────────
    resultat = _tradueix_document_xml(contingut, extensio, _tradueix_text)
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


# ─── Esquemes Pydantic — Glossari ────────────────────────────────────────────

class PeticioEntradaGlossari(BaseModel):
    es:     str
    ca:     str
    tecnic: str = ''
    domini: str


class RespostaGlossari(BaseModel):
    domini:   str
    entrades: list[dict]
    total:    int


# ─── Endpoints: Glossaris ─────────────────────────────────────────────────────

@app.get("/glossaris", tags=["Glossari"],
         summary="Llista els dominis disponibles")
async def llista_dominis():
    """Retorna la llista de dominis temàtics dels glossaris."""
    return {"dominis": DOMINIS}


@app.get("/glossari/{domini}", response_model=RespostaGlossari,
         tags=["Glossari"], summary="Obté les entrades d'un glossari")
async def obte_glossari(domini: str):
    """Retorna totes les entrades del glossari d'un domini."""
    if domini not in DOMINIS:
        raise HTTPException(status_code=404,
                            detail=f"Domini no trobat: {domini}")
    entrades = carrega_glossari(domini)
    return RespostaGlossari(domini=domini, entrades=entrades, total=len(entrades))


@app.post("/glossari/{domini}", tags=["Glossari"],
          summary="Afegeix o actualitza una entrada del glossari")
async def afegeix_entrada(domini: str, peticio: PeticioEntradaGlossari):
    """
    Afegeix una nova entrada o actualitza una existent (per terme en castellà).
    Si el terme ja existeix, n'actualitza la traducció i el tècnic.
    """
    if domini not in DOMINIS:
        raise HTTPException(status_code=404,
                            detail=f"Domini no trobat: {domini}")
    entrades = carrega_glossari(domini)
    for e in entrades:
        if e['es'].lower() == peticio.es.lower():
            e['ca']     = peticio.ca
            e['tecnic'] = peticio.tecnic
            e['data']   = datetime.now().strftime('%Y-%m-%d')
            desa_glossari(domini, entrades)
            log.info("Glossari '%s' — terme actualitzat: '%s'", domini, peticio.es)
            return {"estat": "actualitzat", "entrada": e}
    nova = {
        'es':     peticio.es.strip(),
        'ca':     peticio.ca.strip(),
        'tecnic': peticio.tecnic.strip(),
        'data':   datetime.now().strftime('%Y-%m-%d'),
        'domini': domini,
    }
    entrades.append(nova)
    desa_glossari(domini, entrades)
    log.info("Glossari '%s' — terme afegit: '%s'", domini, peticio.es)
    return {"estat": "afegit", "entrada": nova}


@app.delete("/glossari/{domini}/{terme_es}", tags=["Glossari"],
            summary="Elimina una entrada del glossari")
async def elimina_entrada(domini: str, terme_es: str):
    """Elimina una entrada del glossari pel terme en castellà."""
    if domini not in DOMINIS:
        raise HTTPException(status_code=404,
                            detail=f"Domini no trobat: {domini}")
    entrades       = carrega_glossari(domini)
    entrades_noves = [e for e in entrades if e['es'].lower() != terme_es.lower()]
    if len(entrades_noves) == len(entrades):
        raise HTTPException(status_code=404,
                            detail=f"Terme no trobat: {terme_es}")
    desa_glossari(domini, entrades_noves)
    log.info("Glossari '%s' — terme eliminat: '%s'", domini, terme_es)
    return {"estat": "eliminat", "terme": terme_es}


@app.get("/glossari/{domini}/exporta", tags=["Glossari"],
         summary="Exporta el glossari d'un domini com a fitxer TSV")
async def exporta_glossari(domini: str):
    """Exporta el glossari d'un domini com a fitxer TSV descarregable."""
    from fastapi.responses import FileResponse

    if domini not in DOMINIS:
        raise HTTPException(status_code=404, detail=f"Domini no trobat: {domini}")

    path = nom_fitxer_glossari(domini)
    if not path.exists() or path.stat().st_size == 0:
        raise HTTPException(status_code=404,
                            detail="El glossari és buit, no hi ha res a exportar.")

    # Nom del fitxer: glossari_NomDomini_ddmmaaaa.tsv
    data_avui      = datetime.now().strftime('%d%m%Y')
    nom_domini_net = re.sub(r'[^\w]', '_', domini).strip('_')
    nom_fitxer     = f"glossari_{nom_domini_net}_{data_avui}.tsv"

    log.info("GET /glossari/%s/exporta → %s", domini, nom_fitxer)
    return FileResponse(
        path        = str(path),
        media_type  = 'text/tab-separated-values; charset=utf-8',
        filename    = nom_fitxer,
        headers     = {"Content-Disposition": f'attachment; filename="{nom_fitxer}"'},
    )


# ─── Traducció d'imatges amb Gemini (Nano Banana Pro) ────────────────────────

PROMPT_TRADUCCIO_IMATGE_DEFAULT = (
    "Usa Nano Banana Pro i edita aquesta imatge per a traduir-ne tot el text del castellà "
    "(espanyol), anglès i/o qualsevol altra llengua a la varietat valenciana universitària "
    "del català. Has de retornar exactament la mateixa imatge (mateix format, grandària, "
    "disposició, distribució i separació del text, grafisme, tipografia, fons, disseny, "
    "icones, estructura, colors, tipus i grandària de les fonts, espaiat, imatges, etc.) "
    "però amb tot el text traduït al català valencià i amb el menor pes de fitxer possible, "
    "sempre preservant-ne una resolució òptima i la màxima llegibilitat del text."
)


class PeticioTraduccioImatge(BaseModel):
    imatge_base64:     str
    tipus_mime:        str = "image/png"
    prompt_addicional: str = ""
    mode:              str = "traduccio"  # 'traduccio' o 'refinament'


@app.post("/tradueix-imatge", tags=["Traducció"],
          summary="Tradueix el text d'una imatge del castellà/anglès al valencià (Gemini)")
async def tradueix_imatge(peticio: PeticioTraduccioImatge):
    """
    Tradueix el text inserit en una imatge del castellà/anglès al valencià
    usant l'API de Gemini (Nano Banana Pro / gemini-3-pro-image-preview).
    Usa el nou paquet google-genai (>=1.0.0).
    """
    import os
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY no configurada. Introdueix-la al panell de configuració.",
        )

    try:
        client = genai.Client(api_key=api_key)
        imatge_bytes = base64.b64decode(peticio.imatge_base64)

        # Construeix el prompt segons el mode
        if peticio.mode == 'refinament':
            # Per a refinament: aplica únicament les instruccions del tècnic
            prompt_final = (
                "Edita aquesta imatge aplicant les modificacions indicades sobre el text. "
                "No canvies cap element visual (colors, fonts, disseny, layout) excepte el "
                "text especificat. Retorna exactament la mateixa imatge amb únicament els "
                "canvis de text sol·licitats.\n\n"
                + peticio.prompt_addicional.strip()
            )
        else:
            # Per a traducció nova: usa el prompt complet de valencianització
            prompt_final = PROMPT_TRADUCCIO_IMATGE_DEFAULT
            if peticio.prompt_addicional.strip():
                prompt_final += (
                    f"\n\nInstruccions addicionals:\n{peticio.prompt_addicional.strip()}"
                )

        resposta = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[
                types.Part.from_bytes(
                    data=imatge_bytes,
                    mime_type=peticio.tipus_mime,
                ),
                prompt_final,
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        for part in resposta.candidates[0].content.parts:
            if part.inline_data is not None:
                imatge_traduit_b64 = base64.b64encode(
                    part.inline_data.data
                ).decode('utf-8')
                log.info("POST /tradueix-imatge — OK tipus=%s", part.inline_data.mime_type)
                return {
                    "imatge_base64": imatge_traduit_b64,
                    "tipus_mime":    part.inline_data.mime_type,
                    "estat":         "ok",
                }

        raise HTTPException(
            status_code=500,
            detail="Gemini no ha retornat cap imatge. Prova amb un prompt diferent.",
        )

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Error en la traducció d'imatge: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error en la traducció d'imatge: {e}",
        )


@app.post("/configura-gemini", tags=["Configuració"],
          summary="Configura la clau API de Gemini per a la sessió actual")
async def configura_gemini(api_key: str = Body(..., embed=True)):
    """
    Desa la clau API de Gemini a la variable d'entorn GEMINI_API_KEY
    per a la sessió actual del servidor. Cal tornar-la a introduir si
    uvicorn es reinicia. Per a configuració permanent, afegeix-la al
    fitxer .env de l'arrel del projecte (ja al .gitignore).
    """
    import os
    if not api_key.startswith("AIza"):
        raise HTTPException(
            status_code=400,
            detail="Clau API de Gemini no vàlida (ha de començar per 'AIza').",
        )
    os.environ["GEMINI_API_KEY"] = api_key
    log.info("Clau API de Gemini configurada per a aquesta sessió.")
    return {"estat": "ok", "missatge": "Clau API configurada correctament."}


# ─── Correcció/postedició de documents en valencià ────────────────────────────

# Clau API d'Anthropic (es pot establir per entorn o via /configura-anthropic)
ANTHROPIC_API_KEY_CORRECCIO: str = ""

PROMPT_CORRECCIO_SISTEMA = """Ets un corrector ortogràfic, gramatical i estilístic especialitzat en **valencià normatiu universitari**.
La teua funció és revisar textos en català/valencià i retornar-los completament corregits, aplicant estrictament les normes que es detallen a continuació.

════════════════════════════════════════════════════════════════
BLOC A — CRITERIS LINGÜÍSTICS DE LES UNIVERSITATS VALENCIANES
════════════════════════════════════════════════════════════════

A1. DEMOSTRATIUS. Usa exclusivament el sistema binari reforçat en registre formal:
    · Proximitat: aquest/aquesta/aquests/aquestes (NO este/esta/estos/estes)
    · Llunyania: aquell/aquella/aquells/aquelles
    · Elimina el sistema ternari: este/eixe/aquell → aquest/aquell

A2. VERBS INCOATIUS. Forma culta amb -esc/-eix (no -isc/-ix):
    · servesc/serveixes/serveix/servim/serviu/serveixen
    · patesc/pateixes/pateix/patim/patiu/pateixen
    · oferesc/ofereixes/ofereix/oferim/oferiu/ofereixen
    · establesc, aparesc, meresc, conec, aparesc, pertanys

A3. POSSESSIUS. Forma amb -u- (tònica):
    · meua/teua/seua (NO meva/teva/seva)
    · meus/teus/seus, meues/teues/seues (NO meves/teves/seves)

A4. ACCENTUACIÓ. Segueix la norma del català central excepte:
    · anglès/anglesa (NO anglés/anglesa)
    · francès/francesa (NO francés/francesa)
    · cortès/cortesa (NO cortés/cortesa)
    · Al remat de paraula: café → cafè, però mantén: perquè, però

A5. LÈXIC. Prefereix les formes cultes i generals:
    · avui (NO hui), però → però/ara bé
    · menut/menuda (NO xicotet/xicoteta en registre formal)
    · aprendre (NO dependre en el sentit cognitiu)
    · vespre (NO vesprada com a sinònim de tarda en formal)

A6. PLURALS DELS MOTS EN -C/-G/-X:
    · discos, textos, èxits (NO discs, texts, èxits)
    · Però: aspectes, projectes (correctes)

A7. PARTICIPIS. Formes regulars en -it (no irregulars afavorides en col·loquial):
    · complit (NO complert), oferit (NO ofert)
    · establit (NO establert), omplit (NO omplert)
    · Excepcions lexicalitzades: obert, escrit, vist, dit, fet, mort (formes fortes acceptades)

A8. CONNECTORS DISCURSIUS. Usa connectors propis del registre escrit formal:
    · Per tant, per consegüent, de manera que, tanmateix, malgrat això
    · Evita: llavors (com a connector causal), aleshores (excepte en sentit temporal)

A9. TRACTAMENT PERSONAL. En comunicació institucional:
    · Vós/vosaltres per al tractament de cortesia col·lectiu
    · Vostè/vostès en comunicació molt formal i protocol·lària

A10. FORMES VERBALS PERIFRÀSTIQUES. Pretèrit perfet perifràstic:
     · va fer, va dir, van anar (formes acceptades)
     · NB: el perfet sintètic (feu, digué, anaren) és preferible en estil literari formal

════════════════════════════════════════════════════════════════
BLOC B — GRAMÀTICA: NORMES SINTÀCTIQUES I MORFOLÒGIQUES (60 REGLES)
════════════════════════════════════════════════════════════════

B1.  GÈNERE: masculí per defecte en noms epicens institucionals quan no hi ha referent concret.
B2.  NOMBRE: concordança estricta subjecte–verb fins i tot en construccions invertides.
B3.  ARTICLE DEFINIT: el/la/els/les davant noms propis geogràfics catalans (el País Valencià).
B4.  ARTICLE NEUTRE: ho (no el) com a pronom neutre (m'agrada ← ho faig bé).
B5.  APOSTROFACIÓ: l'home, l'hora, l'IVAM; però: la universitat (vocal feble no s'apostrofa si és u àtona).
B6.  PREPOSICIONS. De/del/de la: no contraure si és nom propi femení (de la Maria).
B7.  QUE/QUÈ: qué interrogatiu/exclamatiu → qué; relatiu sense pausa → que.
B8.  RELATIU QUI: reservat a persones (la persona qui ho fa); QUE per a coses.
B9.  ON/ON QUE: on (lloc); on que (incorrecte → on / en el qual).
B10. PER A / PER: finalitat → per a; causa/agent → per.
B11. EN / AMB: mitjà instrumental → amb; lloc dins → en.
B12. INFINITIU: no usar -r final en contacte amb pronom (fer-lo, dir-li; NO fè-lo).
B13. GERUNDI. Evita gerundis no concurrents o de posterioritat.
B14. PASIVA REFLEXA: es construeix amb se (es publica, se celebrarà) en registre formal.
B15. PRONOM SE: no confondre se reflexiu i se passiu; no usar en registre formal.
B16. PRONOMS FEBLES. Ordre: reflexiu > datiu > acusatiu > hi > en (se li'n dóna).
B17. CLÍTICS. No duplicar pronoms si l'objecte és tònic (ho fa ell, no *el fa ell).
B18. EN ENANTIOPOSICIÓ: en davant de numerals partitius (en tinc tres, no *tinc tres).
B19. HI/HI HA: hi ha (existencial); hi ha d'haver (obligació); no *hi ha de que.
B20. ARTICLE + ADJECTIU POSSESSIU: la meua feina (article + possessiu obligatori en català).
B21. DEMOSTRATIU + POSSESSIU: aquesta feina meua (ordre fix).
B22. NEGACIÓ: no + verb; ni … ni (correlativa); tampoc (no *tampoc no en registre no marcat).
B23. DOBLE NEGACIÓ: en registre formal, evitar «no … pas» (dialectalisme).
B24. SUBJECTIU VALOR MODAL: cal que + subjuntiu; és necessari que + subjuntiu.
B25. CONDICIONAL HIPOTÈTIC: si + imperfet de subjuntiu, condicional simple (si tinguera, faria).
B26. CONCORDANÇA TEMPORAL: mantén la seqüència temporal (narració al passat → imperfet/plusquamperfet).
B27. VOZ ACTIVA preferible a veu passiva perifràstica en registre administratiu.
B28. QUEISME: evitar *de que quan la subordinada és subjecte o objecte directe.
B29. DEQUEISME: usar de que quan el verb regeix preposició de (estic segur que → estic segur que ← correcte).
B30. COMPLEMENT PREDICATIU: concorda amb el subjecte (van arribar contents, no *content).
B31. ADJECTIU ATRIBUTIU: posició preferent postnominal en registre formal (informe detallat).
B32. ADVERBI DE MANERA: forma en -ment (clarament, ràpidament); evita perífrasis innecessàries.
B33. COMPARATIVES. Igualtat: tan … com; superioritat: més … que; inferioritat: menys … que.
B34. SUPERLATIUS. Absolut: molt + adj. o -íssim (utilíssim); relatiu: el més + adj.
B35. CONSTRUCCIÓ ABSOLUTA: havent acabat la reunió, … (correcte); *Acabant la reunió, … (evitar).
B36. ORACIONS DE RELATIU EXPLICATIVES: amb comes (la proposta, que fou aprovada, …).
B37. ORACIONS DE RELATIU ESPECIFICATIVES: sense comes (la proposta que fou aprovada …).
B38. MAJÚSCULES: noms propis, institucions, càrrecs en protocol, però no adjectius de gentilici.
B39. NUMERALS. Escriu en lletra els nombres de l'u al nou en prosa; xifres des del 10.
B40. FRACCIONS: la meitat, un terç, tres quartes parts (no *tres cuartos en calc del castellà).
B41. PERCENTATGE: el 35 % (amb espai i sense punt entre xifra i símbol).
B42. DATA: dia mes any (15 de març de 2026); no usar el format anglès ni abreviatures de mesos.
B43. HORA: les 9.30 h (punts, no dos punts); les 12 del migdia, les 0 hores.
B44. DIVISES: 1.500 € (punt per a milers, coma per a decimals: 1.500,75 €).
B45. ABREVIATURES. Usos normatius: pàg./pàgs., núm./núms., Sr./Sra., Dra./Dr.
B46. SIGLES: sense punts (UV, UPV, IEC); article concorda amb el substantiu elidit (l'IEC, la UV).
B47. TOPÒNIMS: forma oficial catalana (el País Valencià, Alacant, Castelló de la Plana).
B48. ANTROPÒNIMS: respecta la forma oficial de cada persona; en documentació usa nom complet en primera menció.
B49. ESTRANGERISMES: en cursiva si no adaptats; adapta els que tenen forma catalana (internet → internet, sense cursiva).
B50. LLATINISMES: en cursiva si no lexicalitzats (in situ, ex aequo, curriculum).
B51. TECNICISMES: usa la terminologia normativa del camp (consulta el TERMCAT si cal).
B52. CALCS DEL CASTELLÀ: evita calcs sintàctics i lèxics (a nivell de → pel que fa a; en base a → basant-se en; de cara a → per a).
B53. REPETICIONS: evita repeticions lèxiques innecessàries; usa pronoms i sinònims contextuals.
B54. ECONOMIA LINGÜÍSTICA: no usar circumlocucions on hi ha un terme precís.
B55. COHERÈNCIA TERMINOLÒGICA: un sol terme per a cada concepte al llarg del document.
B56. PARAL·LELISME: manté estructura paral·lela en enumeracions i elements coordinats.
B57. PUNTUACIÓ: coma davant de connectors adversatius (però, tanmateix, sinó); punt i coma per a separar elements llargs d'una enumeració.
B58. COMETES: « » (angulars) en català; " " per a cites internes.
B59. GUIÓ/GUIONET: guió llarg (—) per a incisos; guionet (-) per a compostos i prefixos.
B60. PARÈNTESI/CLAUDÀTOR: parèntesi per a aclariments; claudàtor per a interpolacions en citació textual.

════════════════════════════════════════════════════════════════
BLOC C — MANUAL DE DOCUMENTS ADMINISTRATIUS (UV)
════════════════════════════════════════════════════════════════

C1. ENCAPÇALAMENTS. L'encapçalament del document inclou: emissor, destinatari, assumpte i data.
C2. SALUTACIÓ. En comunicació oficial: "Senyor/Senyora," o "Benvolgut/Benvolguda,".
    Evita fórmules col·loquials o estrangeres.
C3. COMIAT. Formes protocol·làries: "Atentament," "Amb respecte," "Cordialment,".
    Evita: "Quedant a la vostra disposició" (gal·licisme) → "Restant a la vostra disposició".
C4. VERB EN REGISTRE ADMINISTRATIU. Usa les formes plenes:
    · sol·licitar (NO demanar en context formal), manifestar (NO dir), comunicar (NO avisar).
C5. ESTRUCTURES FIXES DOCUMENTALS.
    · "Faig constar que…" (certificats)
    · "Expose / Sol·licite / …" (instàncies)
    · "…, i a tal efecte, RESOLC:" (resolucions)
C6. VOZ I PERSONA. Prefereix la primera persona del singular en documents personals;
    impersonal en documents institucionals.
C7. TRACTAMENT INSTITUCIONAL. La Universitat de València (no *l'Universitat);
    el Rectorat, la Junta de Govern, el Consell de Govern (majúscules en noms d'òrgans).
C8. CITACIÓ DE NORMATIVA. "D'acord amb l'article 5 de la Llei…" (amb article determinat davant «article»).

════════════════════════════════════════════════════════════════
INSTRUCCIONS DE RESPOSTA
════════════════════════════════════════════════════════════════

Quan rebis un text per corregir:
1. Retorna el text completament corregit aplicant totes les regles anteriors.
2. Proporciona una llista detallada de les correccions realitzades en format JSON dins de ```json ``` amb aquest esquema:
   [
     {
       "original": "text original amb l'error",
       "corregit": "text corregit",
       "tipus": "ortografia|morfologia|sintaxi|lèxic|estil|puntuació|registre",
       "regla": "codi de la regla (p. ex. A1, B52, C4)",
       "justificacio": "explicació breu de la correcció"
     },
     ...
   ]
3. Proporciona un resum breu (1-2 frases) de les principals àrees de millora detectades.

Format de resposta OBLIGATORI:
---TEXT CORREGIT---
[text complet corregit]
---FI TEXT---
---CORRECCIONS---
```json
[llista de correccions]
```
---FI CORRECCIONS---
---RESUM---
[resum breu]
---FI RESUM---
"""


class PeticioCorreccio(BaseModel):
    text: str = Field(
        ...,
        min_length  = 1,
        max_length  = 100_000,
        description = "Text en valencià a corregir.",
    )
    usar_languagetool: bool = Field(
        default     = True,
        description = "Si cal aplicar primer la capa de LanguageTool (ca-ES).",
    )
    usar_claude: bool = Field(
        default     = True,
        description = "Si cal aplicar la capa de correcció amb Claude Sonnet.",
    )


class ItemCorreccioLT(BaseModel):
    missatge:  str
    offset:    int
    longitud:  int
    original:  str
    suggerits: list[str]
    regla_id:  str


class ItemCorreccioC(BaseModel):
    original:     str
    corregit:     str
    tipus:        str
    regla:        str
    justificacio: str


class RespostaCorreccio(BaseModel):
    text_original:     str
    text_corregit:     str
    correccions_lt:    list[dict]
    correccions_claude: list[dict]
    resum:             str
    estat:             str


@app.post("/configura-anthropic", tags=["Configuració"],
          summary="Configura la clau API d'Anthropic per a la sessió actual")
async def configura_anthropic(api_key: str = Body(..., embed=True)):
    """
    Desa la clau API d'Anthropic a la variable d'entorn ANTHROPIC_API_KEY
    per a la sessió actual. Cal tornar-la a introduir si uvicorn es reinicia.
    """
    import os
    global ANTHROPIC_API_KEY_CORRECCIO
    if not api_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=400,
            detail="Clau API d'Anthropic no vàlida (ha de començar per 'sk-ant-').",
        )
    os.environ["ANTHROPIC_API_KEY"] = api_key
    ANTHROPIC_API_KEY_CORRECCIO = api_key
    log.info("Clau API d'Anthropic configurada per a aquesta sessió.")
    return {"estat": "ok", "missatge": "Clau API d'Anthropic configurada correctament."}


@app.post(
    "/corregeix",
    response_model = RespostaCorreccio,
    summary        = "Corregeix un text en valencià (LanguageTool + Claude Sonnet)",
    tags           = ["Correcció"],
)
async def corregeix(peticio: PeticioCorreccio) -> RespostaCorreccio:
    """
    Corregeix un text en valencià aplicant dues capes:
    1. LanguageTool (API pública, ca-ES): errors ortogràfics i gramaticals bàsics.
    2. Claude Sonnet (claude-sonnet-4-6): normes específiques del valencià universitari.

    Retorna el text corregit, la llista de correccions de cada capa i un resum.
    """
    import os
    import httpx
    import anthropic as _anthropic
    import json as _json

    text_entrant = peticio.text.strip()
    if not text_entrant:
        raise HTTPException(status_code=422, detail="El camp 'text' no pot estar buit.")

    correccions_lt: list[dict] = []
    text_despres_lt = text_entrant

    # ── CAPA 1: LanguageTool ──────────────────────────────────────────────────
    if peticio.usar_languagetool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.languagetool.org/v2/check",
                    data={
                        "text":     text_entrant,
                        "language": "ca-ES",
                    },
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                dades_lt = resp.json()

            for match in dades_lt.get("matches", []):
                context  = match.get("context", {})
                original = context.get("text", "")[
                    context.get("offset", 0):
                    context.get("offset", 0) + context.get("length", 0)
                ]
                suggerits = [r.get("value", "") for r in match.get("replacements", [])[:3]]
                correccions_lt.append({
                    "missatge":  match.get("message", ""),
                    "offset":    match.get("offset", 0),
                    "longitud":  match.get("length", 0),
                    "original":  original,
                    "suggerits": suggerits,
                    "regla_id":  match.get("rule", {}).get("id", ""),
                })

            # Aplica el primer suggerit de cada correcció (ordre invers per no desplaçar offsets)
            text_despres_lt = text_entrant
            for c in sorted(correccions_lt, key=lambda x: x["offset"], reverse=True):
                if c["suggerits"]:
                    ini = c["offset"]
                    fi  = ini + c["longitud"]
                    text_despres_lt = (
                        text_despres_lt[:ini]
                        + c["suggerits"][0]
                        + text_despres_lt[fi:]
                    )
            log.info("LanguageTool — %d coincidències trobades", len(correccions_lt))

        except httpx.HTTPError as exc:
            log.warning("Error en la petició a LanguageTool: %s", exc)
            # Continua sense LanguageTool si l'API no respon
        except Exception as exc:
            log.warning("Error inesperat a LanguageTool: %s", exc)

    # ── CAPA 2: Claude Sonnet ─────────────────────────────────────────────────
    correccions_claude: list[dict] = []
    text_final = text_despres_lt
    resum = ""

    if peticio.usar_claude:
        api_key_anthropic = (
            ANTHROPIC_API_KEY_CORRECCIO
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        if not api_key_anthropic:
            raise HTTPException(
                status_code=503,
                detail=(
                    "ANTHROPIC_API_KEY no configurada. "
                    "Introdueix-la al panell de configuració."
                ),
            )

        try:
            client_a = _anthropic.Anthropic(api_key=api_key_anthropic)

            missatge_usuari = (
                f"Corregeix el text següent en valencià aplicant totes les normes indicades:\n\n"
                f"{text_despres_lt}"
            )

            resposta = client_a.messages.create(
                model      = "claude-sonnet-4-6",
                max_tokens = 8192,
                system     = PROMPT_CORRECCIO_SISTEMA,
                messages   = [{"role": "user", "content": missatge_usuari}],
            )

            contingut_resposta = resposta.content[0].text

            # Extreu el text corregit
            m_text = re.search(
                r'---TEXT CORREGIT---\s*(.*?)\s*---FI TEXT---',
                contingut_resposta,
                re.DOTALL,
            )
            if m_text:
                text_final = m_text.group(1).strip()

            # Extreu la llista de correccions JSON
            m_corr = re.search(
                r'---CORRECCIONS---.*?```json\s*(.*?)\s*```.*?---FI CORRECCIONS---',
                contingut_resposta,
                re.DOTALL,
            )
            if m_corr:
                try:
                    correccions_claude = _json.loads(m_corr.group(1).strip())
                except _json.JSONDecodeError:
                    log.warning("No s'ha pogut parsejar el JSON de correccions de Claude.")

            # Extreu el resum
            m_resum = re.search(
                r'---RESUM---\s*(.*?)\s*---FI RESUM---',
                contingut_resposta,
                re.DOTALL,
            )
            if m_resum:
                resum = m_resum.group(1).strip()

            log.info(
                "Claude Sonnet — %d correccions aplicades",
                len(correccions_claude),
            )

        except _anthropic.AuthenticationError:
            raise HTTPException(
                status_code=401,
                detail="Clau API d'Anthropic invàlida o caducada.",
            )
        except Exception as exc:
            log.exception("Error en la correcció amb Claude: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"Error en la correcció amb Claude Sonnet: {exc}",
            )

    return RespostaCorreccio(
        text_original      = text_entrant,
        text_corregit      = text_final,
        correccions_lt     = correccions_lt,
        correccions_claude = correccions_claude,
        resum              = resum,
        estat              = "ok",
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

