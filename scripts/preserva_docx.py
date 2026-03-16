# -*- coding: utf-8 -*-
"""
preserva_docx.py
----------------
Tradueix documents .docx preservant el format original run a run.

Correccions aplicades:
  - substitueix_text_paragraf_runs(): estratègia "tot al primer run".
    Tot el text traduït va al primer run; la resta es buiden.
    El format dominant és el del run amb més text original (text_len).
  - tradueix_paragraf(): extreu text EXCLOENT w:r dins de w:hyperlink.
    Tradueix únicament els runs normals (para.runs); els hipervincles
    no es toquen i mantenen la clicabilitat.
  - neteja_traduccio(): versió robusta (Markdown complet + Unicode espuri).
  - Logging DEBUG per diagnosticar text brut vs. text net del model.
"""

import io
import logging
import re
import unicodedata

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxPara
from docx.text.run import Run

log = logging.getLogger(__name__)


# ── Helpers globals ────────────────────────────────────────────────────────────

# Detecta URLs per protegir-les abans de traduir (el model les trenca afegint espais)
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+|www\.[^\s<>"\']+',
    re.IGNORECASE
)


def protegeix_urls(text: str) -> tuple[str, dict]:
    """Substitueix les URLs per marcadors i retorna el text modificat i el mapa.

    Usa el format URLTOKEN{n}XEND per evitar que el model el processe com
    a paraula normal (els guions baixos i els dobles guions sí que els modifica).
    """
    urls: dict = {}

    def reemplaca(m):
        key = f'URLTOKEN{len(urls)}XEND'
        urls[key] = m.group(0)
        return key

    text_protegit = URL_PATTERN.sub(reemplaca, text)
    return text_protegit, urls


def restaura_urls(text: str, urls: dict) -> str:
    """Restaura les URLs originals als marcadors."""
    for key, url in urls.items():
        text = text.replace(key, url)
    return text


def te_format_explicit(fmt: dict) -> bool:
    """Retorna True si el run tenia almenys un atribut de format definit explícitament."""
    return any([
        fmt['bold'] is not None,
        fmt['italic'] is not None,
        fmt['underline'] is not None,
        fmt['font_name'] is not None,
        fmt['font_size'] is not None,
        fmt['color'] is not None,
    ])


def corregeix_paraules_enganxades(text: str) -> str:
    """
    Detecta paraules enganxades (minúscula seguida directament de majúscula
    o lletres seguides de números sense espai) i afegeix l'espai que falta.
    Aplica NOMÉS als casos clars per evitar falsos positius.
    """
    # Cas: lletra minúscula enganxada amb majúscula (ex: "serveiEl" → "servei El")
    text = re.sub(r'([a-záéíóúàèìòùïüç])([A-ZÁÉÍÓÚÀÈÌÒÙÏÜÇ])', r'\1 \2', text)
    # Cas: número enganxat amb lletra (ex: "2023la" → "2023 la")
    text = re.sub(r'(\d)([A-ZÁÉÍÓÚÀÈÌÒÙÏÜÇa-záéíóúàèìòùïüç])', r'\1 \2', text)
    # Cas: lletra enganxada amb número (ex: "any2023" → "any 2023")
    # EXCEPCIÓ: no se separen URLs ni codis tècnics (ja protegits amb marcadors)
    text = re.sub(r'([a-záéíóúàèìòùïüç])(\d)', r'\1 \2', text)
    return text


def corregeix_apostrofacions(text: str) -> str:
    """
    Corregeix els espais incorrectes en apostrofacions catalanes/valencianes.
    Casos: l' , d' , m' , t' , s' , n' , c' , j' , qu'
    Exemples: "d' exemple" → "d'exemple", "l' ús" → "l'ús"
    """
    # Elimina espai entre apòstrof i paraula següent
    text = re.sub(r"([dlmtsncjq]u?)'(\s+)([^\s])", r"\1'\3", text, flags=re.IGNORECASE)

    # "de " + vocal/h → "d'" (prepositional elision)
    # NOTA: pot produir falsos positius en noms propis; descomenta si cal
    text = re.sub(
        r'\bde\s+([aeiouàèéíïòóúüh])',
        lambda m: "d'" + m.group(1),
        text,
        flags=re.IGNORECASE,
    )

    # Normalitza espais múltiples que puguen haver quedat
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def neteja_traduccio(text: str) -> str:
    """Elimina tots els artefactes Markdown i caràcters espuris del model."""
    if not text:
        return text

    # Elimina negreta i cursiva Markdown (**text**, *text*, __text__)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text, flags=re.DOTALL)

    # Elimina capçaleres Markdown
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Elimina guions de llista al principi de línia
    text = re.sub(r'^[\-\–\—\•]\s+', '', text, flags=re.MULTILINE)

    # Elimina numeració al principi de línia AMB puntuació (1. text, 1) text)
    text = re.sub(r'^\d+[\.\)\-]\s+', '', text, flags=re.MULTILINE)

    # Elimina número sol al principi de línia SENSE puntuació (el cas "1 Segons")
    text = re.sub(r'^\d+\s+(?=[A-ZÁÉÍÓÚÀÈÌÒÙÏÜÇ·])', '', text, flags=re.MULTILINE)

    # Elimina número sol al principi de text (sense salts de línia)
    text = re.sub(r'^\d+\s+', '', text)

    # Elimina asteriscos solts que hagin quedat
    text = re.sub(r'\*+', '', text)

    # Normalitza espais de no-ruptura i caràcters de control Unicode
    text = re.sub(r'[\u00a0\u200b\u200c\u200d\ufeff]', ' ', text)
    text = re.sub(r' {2,}', ' ', text)

    # Elimina espais davant de puntuació
    text = re.sub(r' ([.,;:!?»\)\]])', r'\1', text)

    # Elimina línies buides múltiples
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _estableix_llengua_catalana(run) -> None:
    """
    Afegeix o actualitza l'atribut w:lang ca-ES al run de Word.
    Substitueix qualsevol element w:lang existent per evitar duplicats.
    """
    rPr = run._r.get_or_add_rPr()
    for lang in rPr.findall(qn('w:lang')):
        rPr.remove(lang)
    lang_elem = OxmlElement('w:lang')
    lang_elem.set(qn('w:val'), 'ca-ES')
    rPr.append(lang_elem)


def obte_runs_complets(para) -> list:
    """
    Retorna tots els runs del paràgraf, inclosos els dins d'hipervincles
    (w:hyperlink), que python-docx no inclou a para.runs per defecte.
    """
    runs = list(para.runs)
    for hipervinc in para._p.findall('.//' + qn('w:hyperlink')):
        for r_elem in hipervinc.findall(qn('w:r')):
            runs.append(Run(r_elem, para))
    return runs


def _aplica_format(run, fmt: dict) -> None:
    """
    Aplica el format guardat a un run DOCX.
    Escriu NOMÉS els valors explícits (no None) per evitar crear elements
    <w:rPr/> buits sobre runs que no tenien format propi.
    """
    if fmt['bold'] is not None:
        run.bold = fmt['bold']
    if fmt['italic'] is not None:
        run.italic = fmt['italic']
    if fmt['underline'] is not None:
        run.underline = fmt['underline']
    if fmt['font_name']:
        run.font.name = fmt['font_name']
    if fmt['font_size']:
        run.font.size = fmt['font_size']
    if fmt['color']:
        try:
            run.font.color.rgb = fmt['color']
        except Exception:
            pass


def substitueix_text_paragraf_runs(runs: list, text_traduit: str) -> None:
    """
    Substitueix el text d'una llista de runs posant tot el text al primer run
    i buidant la resta. Usa el format del run amb més text (format dominant).

    Estratègia:
      1. Captura el format i la longitud de text de tots els runs.
      2. Determina el format dominant (run amb més text original).
      3. Posa tot el text traduït al primer run amb el format dominant.
      4. Buida els runs restants.
      5. Estableix la llengua ca-ES al primer run.
    """
    if not runs:
        return

    # ── Captura el format de TOTS els runs ────────────────────────────────────
    formats = []
    for run in runs:
        fmt = {
            'bold':      run.bold,
            'italic':    run.italic,
            'underline': run.underline,
            'font_name': run.font.name,
            'font_size': run.font.size,
        }
        try:
            fmt['color'] = run.font.color.rgb
        except Exception:
            fmt['color'] = None
        fmt['text_len'] = len(run.text)
        formats.append(fmt)

    # ── Format dominant: el run amb més text original ─────────────────────────
    fmt_dominant = max(formats, key=lambda f: f.get('text_len', 0))

    # ── Buida els runs secundaris (preserva l'estructura XML) ─────────────────
    for run in runs[1:]:
        run.text = ''

    # ── Tot el text al primer run amb el format dominant ──────────────────────
    runs[0].text = text_traduit
    if te_format_explicit(fmt_dominant):
        _aplica_format(runs[0], fmt_dominant)
    _estableix_llengua_catalana(runs[0])


# ── Classe principal ───────────────────────────────────────────────────────────

class PreservadorDocx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_segment(self, text: str) -> str:
        """
        Tradueix un segment de text aplicant tota la canonada de processament:
          1. Retorna sense canvis si el text és buit o és únicament una URL.
          2. Protegeix les URLs amb marcadors URLTOKEN{n}XEND.
          3. Tradueix amb el model.
          4. Neteja artefactes Markdown (neteja_traduccio).
          5. Restaura les URLs originals.
          6. Corregeix paraules enganxades (corregeix_paraules_enganxades).
          7. Corregeix apostrofacions incorrectes (corregeix_apostrofacions).
        """
        text = text.strip()
        if not text:
            return text
        # Si el segment és únicament una URL, no el tradueixis
        if URL_PATTERN.fullmatch(text):
            return text
        # Protegeix les URLs dins del text
        text_protegit, urls = protegeix_urls(text)
        # Traducció + neteja amb logging DEBUG per diagnosticar artefactes
        traduit_raw = self.traductor(text_protegit)
        log.debug("NETEJA IN:  %r", traduit_raw[:120])
        traduit = neteja_traduccio(traduit_raw)
        log.debug("NETEJA OUT: %r", traduit[:120])
        # Restaura les URLs originals
        traduit = restaura_urls(traduit, urls)
        # Postprocessament
        traduit = corregeix_paraules_enganxades(traduit)
        traduit = corregeix_apostrofacions(traduit)
        return traduit

    def tradueix_paragraf(self, para):
        """
        Tradueix el text d'un paràgraf delegant a tradueix_segment i
        substitueix_text_paragraf_runs. Protegeix camps especials (TOC, etc.)
        i deixa els hipervincles (w:hyperlink) intactes.

        Estratègia:
          - Extreu el text NOMÉS dels w:r fills directes del paràgraf
            (exclou els w:r dins de w:hyperlink per preservar-los).
          - Tradueix únicament els runs normals (para.runs).
          - Els hipervincles no es toquen.
        """
        # ── Extreu text EXCLOENT els w:r dins de w:hyperlink ──────────────────
        text_sense_links = ''
        for child in para._p:
            if child.tag == qn('w:r'):
                for t in child.findall(qn('w:t')):
                    text_sense_links += t.text or ''

        text = text_sense_links.strip()
        runs_normals = list(para.runs)

        if not text or not runs_normals:
            return

        # ── Protegeix camps especials (TOC, camps calculats, etc.) ─────────────
        for run in runs_normals:
            if run._r.find(qn('w:fldChar')) is not None:
                return
            if run._r.find(qn('w:instrText')) is not None:
                return

        traduit = self.tradueix_segment(text)
        substitueix_text_paragraf_runs(runs_normals, traduit)

    def tradueix_taula(self, taula):
        for fila in taula.rows:
            for cel in fila.cells:
                for para in cel.paragraphs:
                    self.tradueix_paragraf(para)

    def tradueix_document(self, entrada, sortida=None):
        if isinstance(entrada, bytes):
            entrada = io.BytesIO(entrada)
        doc = Document(entrada)
        # Paràgrafs del cos principal
        for para in doc.paragraphs:
            self.tradueix_paragraf(para)
        # Taules
        for taula in doc.tables:
            self.tradueix_taula(taula)
        # Capçaleres i peus de pàgina
        for seccio in doc.sections:
            for part in [seccio.header, seccio.footer]:
                try:
                    for para in part.paragraphs:
                        self.tradueix_paragraf(para)
                except Exception:
                    pass
        # Quadres de text (textboxes)
        for txbx in doc.element.body.iter(qn('w:txbxContent')):
            for p_elem in txbx.iter(qn('w:p')):
                try:
                    self.tradueix_paragraf(DocxPara(p_elem, doc))
                except Exception:
                    pass
        buf = io.BytesIO()
        doc.save(buf)
        if sortida:
            doc.save(sortida)
        return buf.getvalue()
