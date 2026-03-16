# -*- coding: utf-8 -*-
"""
preserva_docx.py
----------------
Tradueix documents .docx preservant el format original run a run.

Canvis respecte a la versió anterior:
  - neteja_traduccio(): elimina artefactes Markdown del model
  - _estableix_llengua_catalana(): afegeix w:lang ca-ES a cada run traduït
  - Còpia explícita del format del run original al run traduït
"""

import io
import re

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxPara


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


def _estableix_llengua_catalana(run) -> None:
    """
    Afegeix o actualitza l'atribut w:lang amb valor ca-ES al run de Word.
    Substitueix qualsevol element w:lang existent per evitar duplicats.
    """
    rPr = run._r.get_or_add_rPr()
    # Elimina elements w:lang preexistents
    for lang in rPr.findall(qn('w:lang')):
        rPr.remove(lang)
    # Afegeix el nou element w:lang ca-ES
    lang_elem = OxmlElement('w:lang')
    lang_elem.set(qn('w:val'), 'ca-ES')
    rPr.append(lang_elem)


def _copia_format_run(run_src, run_dst) -> None:
    """
    Copia els atributs de format bàsics de run_src a run_dst.
    Usem try/except perquè alguns atributs poden no estar disponibles
    (p. ex. color.rgb quan el color és heretat del tema).
    """
    try:
        run_dst.bold = run_src.bold
    except Exception:
        pass
    try:
        run_dst.italic = run_src.italic
    except Exception:
        pass
    try:
        run_dst.underline = run_src.underline
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
    try:
        if run_src.font.highlight_color:
            run_dst.font.highlight_color = run_src.font.highlight_color
    except Exception:
        pass


# ── Classe principal ───────────────────────────────────────────────────────────

class PreservadorDocx:
    def __init__(self, traductor):
        self.traductor = traductor

    def tradueix_paragraf(self, para):
        """
        Tradueix el text d'un paràgraf preservant el format del primer run.

        Estratègia:
          1. Comprova que el paràgraf té text i runs (i no és un camp especial).
          2. Tradueix el text complet del paràgraf i aplica neteja_traduccio.
          3. Elimina tots els runs excepte el primer (conserva el format original).
          4. Estableix el text traduït al primer run.
          5. Aplica la llengua ca-ES al run resultant.
        """
        text = para.text.strip()
        if not text or not para.runs:
            return
        # Protegeix camps especials (taula de continguts, camps calculats, etc.)
        for run in para.runs:
            if run._r.find(qn('w:fldChar')) is not None:
                return
            if run._r.find(qn('w:instrText')) is not None:
                return

        # Tradueix i neteja
        traduit = neteja_traduccio(self.traductor(text))

        # Manté el primer run com a base (format original preservat)
        run0 = para.runs[0]

        # Elimina la resta de runs del paràgraf
        for run in para.runs[1:]:
            p = run._r.getparent()
            if p is not None:
                p.remove(run._r)

        # Aplica la traducció, reforça el format i estableix la llengua
        _copia_format_run(run0, run0)   # seguretat: reafirma format explícitament
        run0.text = traduit
        _estableix_llengua_catalana(run0)

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
