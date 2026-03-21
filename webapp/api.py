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

