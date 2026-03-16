# -*- coding: utf-8 -*-
"""
preserva_pptx.py
----------------
Tradueix presentacions .pptx preservant el format original run a run.

Correccions aplicades:
  - neteja_traduccio(): versió robusta (equivalent a preserva_docx.py).
  - substitueix_text_para_pptx(): nova estratègia que BUIDA el text de
    tots els runs (sense eliminar-los del XML) i restaura el format
    explícitament.
  - _estableix_llengua_catalana_pptx(): marca lang="ca-ES" al a:rPr.
"""

import io
import re
import unicodedata

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


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


def _estableix_llengua_catalana_pptx(run) -> None:
    """
    Estableix l'atribut lang="ca-ES" al rPr (a:rPr) del run DrawingML.
    Sobreescriu qualsevol valor de llengua preexistent.
    """
    try:
        rPr = run._r.get_or_add_rPr()
        rPr.set('lang', 'ca-ES')
    except Exception:
        pass


def substitueix_text_para_pptx(para, text_traduit: str) -> None:
    """
    Substitueix el text del paràgraf PPTX preservant el format del primer run.

    Estratègia: usa el primer run com a plantilla de format,
    esborra el contingut de tots els runs (sense eliminar-los del XML),
    i posa tot el text traduït al primer run amb el seu format restaurat.
    """
    if not para.runs:
        return

    # Guarda el format del primer run com a plantilla
    run_plantilla = para.runs[0]
    format_guardat = {
        'bold':      run_plantilla.font.bold,
        'italic':    run_plantilla.font.italic,
        'underline': run_plantilla.font.underline,
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
    run_plantilla.font.bold      = format_guardat['bold']
    run_plantilla.font.italic    = format_guardat['italic']
    run_plantilla.font.underline = format_guardat['underline']
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
    _estableix_llengua_catalana_pptx(run_plantilla)


# ── Classe principal ───────────────────────────────────────────────────────────

class PreservadorPptx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_text_frame(self, tf):
        """
        Tradueix cada paràgraf del marc de text delegant a substitueix_text_para_pptx.
        """
        for para in tf.paragraphs:
            text = para.text.strip()
            if not text or not para.runs:
                continue
            traduit = neteja_traduccio(self.traductor(text))
            substitueix_text_para_pptx(para, traduit)

    def tradueix_shape(self, shape):
        try:
            if shape.has_text_frame:
                self.tradueix_text_frame(shape.text_frame)
            if shape.has_table:
                for fila in shape.table.rows:
                    for cel in fila.cells:
                        self.tradueix_text_frame(cel.text_frame)
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                for s in shape.shapes:
                    self.tradueix_shape(s)
        except Exception:
            pass

    def tradueix_document(self, entrada, sortida=None):
        if isinstance(entrada, bytes):
            entrada = io.BytesIO(entrada)
        prs = Presentation(entrada)
        for diap in prs.slides:
            for shape in diap.shapes:
                self.tradueix_shape(shape)
            if diap.has_notes_slide:
                try:
                    self.tradueix_text_frame(
                        diap.notes_slide.notes_text_frame)
                except Exception:
                    pass
        buf = io.BytesIO()
        prs.save(buf)
        if sortida:
            prs.save(sortida)
        return buf.getvalue()
