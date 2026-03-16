# -*- coding: utf-8 -*-
"""
preserva_docx.py
----------------
Tradueix documents .docx preservant el format original run a run.

Correccions aplicades:
  - obte_runs_complets(): inclou runs dins d'hipervincles (w:hyperlink).
  - substitueix_text_paragraf(): nova estratègia que buida tots els runs
    (inclosos els d'hipervincles), restaura el format de forma condicional
    (només si el valor és explícit, no None) i estableix la llengua ca-ES.
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

def neteja_traduccio(text: str) -> str:
    """Elimina tots els artefactes Markdown i caràcters espuris del model."""
    if not text:
        return text

    # Elimina negreta i cursiva Markdown (**text**, *text*, __text__)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)

    # Elimina capçaleres Markdown (# Títol, ## Subtítol)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Elimina guions de llista al principi de línia
    text = re.sub(r'^[\-\–\—\•]\s+', '', text, flags=re.MULTILINE)

    # Elimina numeració al principi de línia (1. text, 1) text, 1- text)
    text = re.sub(r'^\d+[\.\)\-]\s+', '', text, flags=re.MULTILINE)

    # Elimina numeració solta (el número "1" sol al principi o final)
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)

    # Elimina asteriscos solts que hagin quedat
    text = re.sub(r'\*+', '', text)

    # Normalitza espais (elimina espais múltiples i espais de no-ruptura)
    text = re.sub(r'[\u00a0\u200b\u200c\u200d\ufeff]', ' ', text)
    text = re.sub(r' {2,}', ' ', text)

    # Elimina espais davant de puntuació
    text = re.sub(r' ([.,;:!?»\)])', r'\1', text)

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


def substitueix_text_paragraf(para, text_traduit: str) -> None:
    """
    Substitueix el text del paràgraf preservant el format del primer run.

    Estratègia:
      1. Obté TOTS els runs (inclosos els d'hipervincles).
      2. Captura el format del primer run.
      3. Buida el text de tots els runs (sense eliminar-los del XML).
      4. Posa el text traduït al primer run.
      5. Restaura el format explícitament (NOMÉS si el valor era explícit,
         no None, per evitar crear elements rPr on no n'hi havia).
      6. Estableix la llengua ca-ES.
    """
    runs_tots = obte_runs_complets(para)
    if not runs_tots:
        return

    # ── Captura el format del primer run ──────────────────────────────────────
    run0 = runs_tots[0]
    fmt = {
        'bold':      run0.bold,
        'italic':    run0.italic,
        'underline': run0.underline,
        'font_name': run0.font.name,
        'font_size': run0.font.size,
    }
    try:
        fmt['color'] = run0.font.color.rgb
    except Exception:
        fmt['color'] = None

    # ── Buida el text de TOTS els runs (preserva l'estructura XML) ────────────
    for run in runs_tots:
        run.text = ''

    # ── Posa el text traduït al primer run ────────────────────────────────────
    run0.text = text_traduit

    # ── Restaura el format CONDICIONALMENT (no escriu None explícit) ──────────
    # Escriure run.bold = None sobre un run que ja no tenia <w:b> crea
    # elements <w:rPr/> buits innecessaris. Només restaurem valors explícits.
    if fmt['bold'] is not None:
        run0.bold = fmt['bold']
    if fmt['italic'] is not None:
        run0.italic = fmt['italic']
    if fmt['underline'] is not None:
        run0.underline = fmt['underline']
    if fmt['font_name']:
        run0.font.name = fmt['font_name']
    if fmt['font_size']:
        run0.font.size = fmt['font_size']
    if fmt['color']:
        try:
            run0.font.color.rgb = fmt['color']
        except Exception:
            pass

    # ── Estableix la llengua catalana ─────────────────────────────────────────
    _estableix_llengua_catalana(run0)


# ── Classe principal ───────────────────────────────────────────────────────────

class PreservadorDocx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_paragraf(self, para):
        """
        Tradueix el text d'un paràgraf delegant a substitueix_text_paragraf.

        Usa obte_runs_complets() per detectar text en hipervincles que
        para.runs no retorna. Protegeix camps especials (TOC, camps calculats).
        """
        text = para.text.strip()
        runs_tots = obte_runs_complets(para)
        if not text or not runs_tots:
            return

        # Protegeix camps especials (TOC, camps calculats, etc.)
        for run in runs_tots:
            if run._r.find(qn('w:fldChar')) is not None:
                return
            if run._r.find(qn('w:instrText')) is not None:
                return

        # Traducció + neteja amb logging DEBUG per diagnosticar artefactes
        traduit_raw = self.traductor(text)
        log.debug("NETEJA IN:  %r", traduit_raw[:120])
        traduit = neteja_traduccio(traduit_raw)
        log.debug("NETEJA OUT: %r", traduit[:120])

        substitueix_text_paragraf(para, traduit)

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
