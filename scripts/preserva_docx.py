# -*- coding: utf-8 -*-
"""
preserva_docx.py
----------------
Tradueix documents .docx preservant el format original run a run.

Correccions aplicades:
  - neteja_traduccio(): versió robusta que cobreix Markdown imbricat,
    capçaleres #, guions no inicials i caràcters Unicode espuris.
  - substitueix_text_paragraf(): nova estratègia que BUIDA el text de
    tots els runs (sense eliminar-los del XML) i restaura el format
    explícitament, evitant la corrupció d'estils vinculats.
  - _estableix_llengua_catalana(): marca ca-ES al w:lang de cada run.
"""

import io
import re
import unicodedata

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxPara


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
    Afegeix o actualitza l'atribut w:lang amb valor ca-ES al run de Word.
    Substitueix qualsevol element w:lang existent per evitar duplicats.
    """
    rPr = run._r.get_or_add_rPr()
    for lang in rPr.findall(qn('w:lang')):
        rPr.remove(lang)
    lang_elem = OxmlElement('w:lang')
    lang_elem.set(qn('w:val'), 'ca-ES')
    rPr.append(lang_elem)


def substitueix_text_paragraf(para, text_traduit: str) -> None:
    """
    Substitueix el text del paràgraf preservant el format de cada run.

    Estratègia: usa el primer run com a plantilla de format,
    esborra el contingut de tots els runs (sense eliminar-los del XML,
    per evitar corrupció d'estils), i posa tot el text traduït al primer
    run amb el seu format original restaurat explícitament.
    """
    if not para.runs:
        return

    # Guarda el format del primer run com a plantilla
    run_plantilla = para.runs[0]
    format_guardat = {
        'bold':      run_plantilla.bold,
        'italic':    run_plantilla.italic,
        'underline': run_plantilla.underline,
        'font_name': run_plantilla.font.name,
        'font_size': run_plantilla.font.size,
    }
    # Intenta guardar el color si és explícit (no heretat del tema)
    try:
        format_guardat['color'] = run_plantilla.font.color.rgb
    except Exception:
        format_guardat['color'] = None

    # Esborra el text de TOTS els runs (sense modificar l'estructura XML)
    for run in para.runs:
        run.text = ''

    # Posa tot el text traduït al primer run
    run_plantilla.text = text_traduit

    # Restaura el format explícitament
    run_plantilla.bold      = format_guardat['bold']
    run_plantilla.italic    = format_guardat['italic']
    run_plantilla.underline = format_guardat['underline']
    if format_guardat['font_name']:
        run_plantilla.font.name = format_guardat['font_name']
    if format_guardat['font_size']:
        run_plantilla.font.size = format_guardat['font_size']
    if format_guardat['color']:
        try:
            run_plantilla.font.color.rgb = format_guardat['color']
        except Exception:
            pass

    # Estableix la llengua catalana al run resultant
    _estableix_llengua_catalana(run_plantilla)


# ── Classe principal ───────────────────────────────────────────────────────────

class PreservadorDocx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_paragraf(self, para):
        """
        Tradueix el text d'un paràgraf delegant a substitueix_text_paragraf.

        Protegeix camps especials (taula de continguts, camps calculats, etc.)
        que no s'han de traduir mai.
        """
        text = para.text.strip()
        if not text or not para.runs:
            return
        # Protegeix camps especials (TOC, camps calculats, etc.)
        for run in para.runs:
            if run._r.find(qn('w:fldChar')) is not None:
                return
            if run._r.find(qn('w:instrText')) is not None:
                return

        traduit = neteja_traduccio(self.traductor(text))
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
