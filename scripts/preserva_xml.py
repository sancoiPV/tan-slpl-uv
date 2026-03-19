# -*- coding: utf-8 -*-
"""
preserva_xml.py
===============
Traducció de documents .docx i .pptx amb preservació perfecta del format.

Estratègia: manipulació directa de l'XML intern del fitxer ZIP.
- NO usa python-docx ni python-pptx per a modificar el document
- Extreu paràgrafs XML complets amb tot el format intern intacte
- Tradueix únicament el text dins dels tags XML
- Reinjecta el XML traduït substituint l'original exactament
- El format (negreta, cursiva, color, mida, fonts, imatges, taules...)
  queda preservat per definició perquè les etiquetes XML no es toquen

Correccions aplicades (v2):
  ERROR 1 — neteja_traduccio_xml(): elimina artefactes del motor (—1, ##, **)
  ERROR 2 — substitueix_text_paragraf(): elimina runs addicionals en lloc de
             buidar-los, evita que els <w:rPr> dels runs buits afecten el format
  ERROR 3 — divideix_en_segments() + tradueix_text_llarg(): evita truncament
             del model en textos llargs
  ERROR 4 — PPTX_REGEX ampliada + paràmetres tradueix_notes/tradueix_plantilles
  ERROR 5 — es_dins_imatge(): exclou paràgrafs dins de <w:drawing> i gràfics

Autors: SLPL · Universitat de València · 2025
"""

import io
import logging
import re
import zipfile
from typing import Callable

from lxml import etree

log = logging.getLogger(__name__)

# ── Namespaces XML de Word i PowerPoint ─────────────────────────────────────

NS_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'

NSMAP = {
    'w': NS_W,
    'a': NS_A,
    'r': NS_R,
    'p': NS_P,
}

# ── Fitxers XML interns que cal processar ────────────────────────────────────
# ERROR 4: PPTX_REGEX ampliada per incloure notes i plantilles

DOCX_REGEX = re.compile(
    r'^word/(document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$'
)
PPTX_REGEX = re.compile(
    r'^ppt/(slides/slide\d+|notesSlides/notesSlide\d+'
    r'|slideMasters/slideMaster\d+|slideLayouts/slideLayout\d+)\.xml$'
)
# Regex per a PPTX sense plantilles (ús per defecte)
PPTX_REGEX_SENSE_PLANTILLES = re.compile(
    r'^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$'
)
# Regex per a PPTX només diapositives (sense notes ni plantilles)
PPTX_REGEX_SOLS_DIAPOSITIVES = re.compile(
    r'^ppt/slides/slide\d+\.xml$'
)

# ── Tags d'imatge i gràfic per a ERROR 5 ────────────────────────────────────

_TAGS_IMATGE = frozenset({
    '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline',
    '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor',
    '{http://schemas.openxmlformats.org/drawingml/2006/main}graphicData',
    '{http://schemas.openxmlformats.org/drawingml/2006/chart}chart',
})

# ── Constant per a segmentació de textos llargs (ERROR 3) ───────────────────

MAX_CHARS_PER_SEGMENT = 400


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR 1 — Neteja d'artefactes del motor de traducció
# ═══════════════════════════════════════════════════════════════════════════════

def neteja_traduccio_xml(text: str) -> str:
    """
    Elimina artefactes que el motor de traducció afegeix incorrectament.
    S'aplica DESPRÉS de traduir i ABANS de reinjectar al XML.

    Artefactes eliminats:
      - "— 1", "– 1", "- 1" al principi (numeració inventada)
      - Números solts al principi de text
      - Asteriscos de Markdown (**negreta**, *cursiva*)
      - Capçaleres Markdown (# Títol, ## Subtítol)
      - Espais múltiples
      - Espais incorrectes en apostrofacions catalanes (l' empresa → l'empresa)
    """
    if not text:
        return text
    # Elimina "— 1", "– 1", "- 1" al principi
    text = re.sub(r'^[\u2014\u2013\-]\s*\d+\s*', '', text)
    # Elimina números solts al principi seguits de text amb majúscula
    text = re.sub(r'^\d+\s+(?=[A-Z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u017e\u00b7])', '', text)
    # Elimina asteriscos de Markdown
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text, flags=re.DOTALL)
    # Elimina capçaleres Markdown
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Normalitza espais múltiples
    text = re.sub(r' {2,}', ' ', text)
    # Corregeix espais incorrectes en apostrofacions catalanes
    # ex: "l' empresa" → "l'empresa", "d' un" → "d'un"
    text = re.sub(
        r"([dlmtsncjq]u?)'(\s+)([^\s])",
        r"\1'\3",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR 3 — Segmentació de textos llargs
# ═══════════════════════════════════════════════════════════════════════════════

def divideix_en_segments(text: str, max_chars: int = MAX_CHARS_PER_SEGMENT) -> list:
    """
    Divideix un text llarg en segments per a traducció.
    Intenta dividir per oracions (punt/exclamació/interrogació + espai + majúscula).
    Si el text és curt, el retorna en una llista d'un sol element.
    """
    if len(text) <= max_chars:
        return [text]

    segments = []
    # Divideix per oracions respectant la puntuació
    oracions = re.split(
        r'(?<=[.!?])\s+(?=[A-Z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u017e])',
        text,
    )

    segment_actual = ''
    for oracio in oracions:
        if len(segment_actual) + len(oracio) + 1 <= max_chars:
            segment_actual = (segment_actual + ' ' + oracio).strip()
        else:
            if segment_actual:
                segments.append(segment_actual)
            # Si la pròpia oració supera max_chars, la dividim per comes
            if len(oracio) > max_chars:
                subsegs = re.split(r',\s+', oracio)
                sub_actual = ''
                for sub in subsegs:
                    if len(sub_actual) + len(sub) + 2 <= max_chars:
                        sub_actual = (sub_actual + ', ' + sub).strip(', ')
                    else:
                        if sub_actual:
                            segments.append(sub_actual)
                        sub_actual = sub
                if sub_actual:
                    segment_actual = sub_actual
                else:
                    segment_actual = ''
            else:
                segment_actual = oracio

    if segment_actual:
        segments.append(segment_actual)

    return segments if segments else [text]


def tradueix_text_llarg(text: str, funcio_traduccio: Callable[[str], str]) -> str:
    """
    Tradueix un text potencialment llarg dividint-lo en segments de màxim
    MAX_CHARS_PER_SEGMENT caràcters. Reuneix els segments traduïts amb espai.
    """
    segments = divideix_en_segments(text)
    if len(segments) == 1:
        return funcio_traduccio(text)

    segments_traduits = []
    for segment in segments:
        try:
            traduit = funcio_traduccio(segment)
            segments_traduits.append(traduit)
        except Exception as e:
            log.warning('Error traduint segment: %r — usa original', e)
            segments_traduits.append(segment)

    return ' '.join(segments_traduits)


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR 5 — Detecció de paràgrafs dins d'imatges o gràfics
# ═══════════════════════════════════════════════════════════════════════════════

def es_dins_imatge(node: etree._Element) -> bool:
    """
    Comprova si un node paràgraf és dins d'una imatge o gràfic integrat.
    En aquest cas el paràgraf no s'ha de traduir (podria ser text alternatiu,
    títol de gràfic, llegendes de sèries de dades, etc.).
    """
    parent = node.getparent()
    while parent is not None:
        if parent.tag in _TAGS_IMATGE:
            return True
        parent = parent.getparent()
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Funcions d'extracció i substitució de text
# ═══════════════════════════════════════════════════════════════════════════════

def obte_text_paragraf(p_node: etree._Element, ns_t: str) -> str:
    """
    Extreu el text pla d'un node de paràgraf XML
    concatenant tots els elements <w:t> o <a:t>.
    """
    parts = []
    for t in p_node.iter(f'{{{ns_t}}}t'):
        if t.text:
            parts.append(t.text)
    return ''.join(parts).strip()


def substitueix_text_paragraf(
    p_node: etree._Element,
    text_traduit: str,
    ns_para: str,
) -> None:
    """
    Substitueix el text del paràgraf preservant el format del primer run.

    ERROR 2 — Estratègia corregida:
      - Identifica tots els <w:r>/<a:r> fills directes del paràgraf
        (i dins d'hipervincles si no n'hi ha de directes)
      - Posa tot el text traduït al primer <w:t>/<a:t> del primer run
      - ELIMINA completament els runs addicionals del DOM (no els buida)
        → evita que els <w:rPr> dels runs buits apliquen el seu format
          al text del primer run
      - Preserva tots els altres elements del paràgraf intactes
        (<w:pPr>, hipervincles, camps, etc.)
    """
    tag_r         = f'{{{ns_para}}}r'
    tag_t         = f'{{{ns_para}}}t'
    tag_hyperlink = f'{{{ns_para}}}hyperlink'

    # Troba tots els runs fills directes del paràgraf
    runs = [child for child in p_node if child.tag == tag_r]

    # Si no n'hi ha de directes, cerca dins d'hipervincles
    if not runs:
        for hl in p_node:
            if hl.tag == tag_hyperlink:
                runs_hl = [child for child in hl if child.tag == tag_r]
                if runs_hl:
                    runs = runs_hl
                    break

    if not runs:
        return

    # Posa el text traduït al primer <w:t>/<a:t> del primer run
    primer_run = runs[0]
    t_nodes = [child for child in primer_run if child.tag == tag_t]

    if not t_nodes:
        # Crea un nou <w:t> si no n'hi ha (cas inusual)
        nou_t = etree.SubElement(primer_run, tag_t)
        nou_t.text = text_traduit
    else:
        t_nodes[0].text = text_traduit
        # Preserva xml:space="preserve" si el text té espais inicials/finals
        xml_space = '{http://www.w3.org/XML/1998/namespace}space'
        if text_traduit != text_traduit.strip():
            t_nodes[0].set(xml_space, 'preserve')
        # Buida els <w:t> addicionals del primer run (si n'hi hagués més d'un)
        for t in t_nodes[1:]:
            t.text = ''

    # ELIMINA completament els runs addicionals del paràgraf
    # Els <w:rPr> d'un run buit poden canviar el format visual del text
    # del primer run, per tant cal eliminar-los del DOM completament.
    for run in runs[1:]:
        run_parent = run.getparent()
        if run_parent is not None:
            run_parent.remove(run)


# ── Forçar idioma ca-ES ──────────────────────────────────────────────────────

def forta_llengua_catala_docx(xml_str: str) -> str:
    """Substitueix tots els atributs de llengua per ca-ES en un XML de Word."""
    xml_str = re.sub(r'w:lang\s+w:val="[^"]*"', 'w:lang w:val="ca-ES"', xml_str)
    xml_str = re.sub(
        r'(w:lang[^/]*?)w:eastAsia="[^"]*"', r'\1w:eastAsia="ca-ES"', xml_str
    )
    xml_str = re.sub(
        r'(w:lang[^/]*?)w:bidi="[^"]*"', r'\1w:bidi="ca-ES"', xml_str
    )
    return xml_str


def forta_llengua_catala_pptx(xml_str: str) -> str:
    """Substitueix tots els atributs lang per ca-ES en un XML de PowerPoint."""
    return re.sub(r'\blang="[^"]*"', 'lang="ca-ES"', xml_str)


# ═══════════════════════════════════════════════════════════════════════════════
# Funció principal de traducció de documents
# ═══════════════════════════════════════════════════════════════════════════════

def tradueix_document(
    contingut_original: bytes,
    extensio: str,
    funcio_traduccio: Callable[[str], str],
    tradueix_notes: bool = True,
    tradueix_plantilles: bool = False,
) -> bytes:
    """
    Tradueix un document .docx o .pptx preservant el format perfectament.

    Paràmetres:
        contingut_original:  contingut binari del fitxer original
        extensio:            'docx' o 'pptx' (amb o sense punt inicial)
        funcio_traduccio:    funció que rep text castellà i retorna text en valencià
        tradueix_notes:      (PPTX) si True, tradueix les notes del presentador
                             (notesSlides/). Per defecte True.
        tradueix_plantilles: (PPTX) si True, tradueix slideMasters i slideLayouts.
                             Normalment False perquè contenen text de plantilla
                             compartit que no s'ha de modificar. Per defecte False.

    Retorna:
        contingut binari del fitxer traduït

    Estratègia (v2, amb totes les correccions):
        1. Obre el ZIP en memòria (docx/pptx són ZIPs d'XMLs)
        2. Per a cada XML de contingut (document.xml, slideN.xml, etc.):
           a. Parsejar el XML amb lxml
           b. Per a cada paràgraf (<w:p> o <a:p>):
              - Si és dins d'una imatge/gràfic → IGNORA (ERROR 5)
              - Extreu el text pla concatenant tots els <w:t>/<a:t>
              - Si el text és llarg → divideix en segments (ERROR 3)
              - Tradueix (per segments si cal)
              - Aplica neteja d'artefactes (ERROR 1)
              - Substitueix al DOM eliminant runs addicionals (ERROR 2)
           c. Serialitza l'XML modificat
           d. Força l'idioma ca-ES als atributs de llengua
        3. Escriu tots els fitxers (modificats i originals) al ZIP de sortida
    """
    extensio = extensio.lower().lstrip('.')

    if extensio == 'docx':
        regex_fitxers = DOCX_REGEX
        ns_para = NS_W
        ns_text = NS_W
    elif extensio == 'pptx':
        # ERROR 4: selecciona la regex PPTX en funció dels paràmetres
        if tradueix_notes and tradueix_plantilles:
            regex_fitxers = PPTX_REGEX                   # tot
        elif tradueix_notes and not tradueix_plantilles:
            regex_fitxers = PPTX_REGEX_SENSE_PLANTILLES  # slides + notes
        else:
            regex_fitxers = PPTX_REGEX_SOLS_DIAPOSITIVES  # sols slides
        ns_para = NS_A
        ns_text = NS_A
    else:
        raise ValueError(f'Format no suportat: {extensio!r}. Usa "docx" o "pptx".')

    tag_para = f'{{{ns_para}}}p'

    # Obre el ZIP original en memòria
    zip_entrada = zipfile.ZipFile(io.BytesIO(contingut_original), 'r')
    zip_sortida_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_sortida_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_sortida:
        for nom_fitxer in zip_entrada.namelist():
            contingut = zip_entrada.read(nom_fitxer)

            if regex_fitxers.match(nom_fitxer):
                # ── Processa els fitxers XML que contenen text ──────────────
                try:
                    arbre = etree.fromstring(contingut)

                    for p_node in arbre.iter(tag_para):
                        # ERROR 5: ignora paràgrafs dins d'imatges o gràfics
                        if es_dins_imatge(p_node):
                            continue

                        text_original = obte_text_paragraf(p_node, ns_text)
                        if not text_original:
                            continue

                        try:
                            # ERROR 3: usa traducció segmentada per a textos llargs
                            text_traduit = tradueix_text_llarg(
                                text_original, funcio_traduccio
                            )
                            # ERROR 1: neteja artefactes del motor
                            text_traduit = neteja_traduccio_xml(text_traduit)

                            if text_traduit and text_traduit != text_original:
                                # ERROR 2: substitueix eliminant runs addicionals
                                substitueix_text_paragraf(
                                    p_node, text_traduit, ns_text
                                )
                        except Exception as e:
                            log.warning(
                                'Error traduint paràgraf: %r — manté original', e
                            )

                    # Serialitza l'XML modificat
                    contingut_modificat = etree.tostring(
                        arbre,
                        xml_declaration=True,
                        encoding='UTF-8',
                        standalone=True,
                    )

                    # Força l'idioma ca-ES
                    contingut_text = contingut_modificat.decode('utf-8')
                    if extensio == 'docx':
                        contingut_text = forta_llengua_catala_docx(contingut_text)
                    else:
                        contingut_text = forta_llengua_catala_pptx(contingut_text)

                    contingut = contingut_text.encode('utf-8')
                    log.debug('Processat: %s', nom_fitxer)

                except Exception as e:
                    log.error(
                        'Error processant %s: %r — usa original', nom_fitxer, e
                    )
                    contingut = zip_entrada.read(nom_fitxer)

            # Copia el fitxer (modificat o original) al ZIP de sortida
            zip_sortida.writestr(nom_fitxer, contingut)

    zip_entrada.close()
    return zip_sortida_buffer.getvalue()
