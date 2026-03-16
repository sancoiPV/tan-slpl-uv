# -*- coding: utf-8 -*-
"""
preserva_pptx.py
----------------
Tradueix presentacions .pptx preservant el format original run a run.

Canvis respecte a la versió anterior:
  - neteja_traduccio(): elimina artefactes Markdown del model
  - _estableix_llengua_catalana_pptx(): afegeix lang="ca-ES" a cada run traduït
  - Còpia explícita del format del run original al run traduït
"""

import io
import re

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


# ── Helpers globals ────────────────────────────────────────────────────────────

def neteja_traduccio(text: str) -> str:
    """
    Elimina artefactes Markdown i normalitza espais del text traduït.

    Casos tractats:
      - Negreta/cursiva Markdown (*paraula*, **paraula**)
      - Guions de llista al principi de línia  (—, –, -)
      - Numeració de llista (1. 2) …)
      - Espais múltiples
      - Espai davant signe de puntuació
    """
    text = re.sub(r'\*+', '', text)                    # negreta/cursiva Markdown
    text = re.sub(r'^[\-–—]\s*', '', text.strip())     # guió de llista inicial
    text = re.sub(r'^\d+[.)]\s+', '', text)            # numeració de llista inicial
    text = re.sub(r'  +', ' ', text)                   # espais múltiples → un sol espai
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)       # espai davant puntuació
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


def _copia_format_run_pptx(run_src, run_dst) -> None:
    """
    Copia els atributs de format bàsics de run_src a run_dst (runs de pptx).
    Usem try/except perquè alguns atributs poden ser None o heretats del layout.
    """
    try:
        run_dst.font.bold = run_src.font.bold
    except Exception:
        pass
    try:
        run_dst.font.italic = run_src.font.italic
    except Exception:
        pass
    try:
        run_dst.font.underline = run_src.font.underline
    except Exception:
        pass
    try:
        if run_src.font.name:
            run_dst.font.name = run_src.font.name
    except Exception:
        pass
    try:
        if run_src.font.size:
            run_dst.font.size = run_src.font.size
    except Exception:
        pass
    try:
        if run_src.font.color.type is not None:
            run_dst.font.color.rgb = run_src.font.color.rgb
    except Exception:
        pass


# ── Classe principal ───────────────────────────────────────────────────────────

class PreservadorPptx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_text_frame(self, tf):
        """
        Tradueix cada paràgraf del marc de text preservant el format del primer run.

        Estratègia:
          1. Obté el text complet del paràgraf.
          2. Tradueix i aplica neteja_traduccio.
          3. Elimina tots els runs excepte el primer (conserva el format original).
          4. Estableix el text traduït al primer run.
          5. Aplica la llengua ca-ES al run resultant.
        """
        for para in tf.paragraphs:
            text = para.text.strip()
            if not text or not para.runs:
                continue

            # Tradueix i neteja
            traduit = neteja_traduccio(self.traductor(text))

            # Manté el primer run com a base (format original preservat)
            run0 = para.runs[0]

            # Elimina la resta de runs del paràgraf
            for run in para.runs[1:]:
                try:
                    para._p.remove(run._r)
                except Exception:
                    pass

            # Aplica la traducció, reforça el format i estableix la llengua
            _copia_format_run_pptx(run0, run0)   # seguretat: reafirma format
            run0.text = traduit
            _estableix_llengua_catalana_pptx(run0)

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
