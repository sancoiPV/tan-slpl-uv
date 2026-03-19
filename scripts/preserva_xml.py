# -*- coding: utf-8 -*-
"""
preserva_xml.py
===============
Traducció de documents .docx i .pptx amb preservació perfecta del format.

Estratègia: manipulació directa de l'XML intern del fitxer ZIP.
- NO usa python-docx ni python-pptx per a modificar el document
- Parseja els XMLs interns amb lxml
- Tradueix CADA RUN (<w:r>/<a:r>) de forma independent
- El <w:rPr>/<a:rPr> (format: negreta, cursiva, color, mida...) NO es toca mai
- El format queda preservat per definició: cada run conserva el seu propi format

Estratègia run per run (v4):
  La versió anterior (v3) extraia el text complet del paràgraf, el traduïa
  com un bloc i redistribuïa el text proporcionalment entre els runs. Açò és
  estructuralment incorrecte: la traducció canvia l'ordre de les paraules i la
  redistribució desplaça els límits del format.

  La versió actual (v4) tradueix cada run individualment:
  - Cada <w:r> porta el seu propi <w:rPr> → format perfectament preservat
  - No cal redistribució ni heurístiques proporcionals
  - La qualitat és lleugerament inferior per a runs molt curts (el model
    perd context), però el format és perfecte per definició.

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

NS_W     = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS_A     = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_R     = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_P     = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_PIC   = 'http://schemas.openxmlformats.org/drawingml/2006/picture'
NS_WPD   = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
NS_CHART = 'http://schemas.openxmlformats.org/drawingml/2006/chart'

NSMAP = {
    'w':     NS_W,
    'a':     NS_A,
    'r':     NS_R,
    'p':     NS_P,
    'pic':   NS_PIC,
    'wpd':   NS_WPD,
    'chart': NS_CHART,
}

# ── Regex per a fitxers XML interns ─────────────────────────────────────────
# DOCX és constant; PPTX es decideix dins de tradueix_document() (depèn de
# tradueix_notes), per la qual cosa PPTX_REGEX NO s'exporta com a constant.

DOCX_REGEX = re.compile(
    r'^word/(document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$'
)

# ── Tags d'imatge i gràfic ───────────────────────────────────────────────────

TAGS_IMATGE = frozenset({
    f'{{{NS_WPD}}}inline',
    f'{{{NS_WPD}}}anchor',
    f'{{{NS_A}}}graphicData',
    f'{{{NS_CHART}}}chart',
    f'{{{NS_PIC}}}pic',
    f'{{{NS_PIC}}}nvPicPr',
})

# ── Regex per a detectar contingut no traduïble ──────────────────────────────
# Runs que contenen únicament números, símbols, espais o codis curts
_RE_NO_TRADUIR = re.compile(
    r'^[\d\s\.\,\:\;\!\?\(\)\[\]\{\}\-\_\+\=\*\/\\<>@#%&|~^`\'\"]+$'
)


# ═══════════════════════════════════════════════════════════════════════════════
# Neteja d'artefactes del motor de traducció
# ═══════════════════════════════════════════════════════════════════════════════

def neteja_traduccio_xml(text: str) -> str:
    """
    Neteja els artefactes que el motor de traducció afegeix incorrectament.
    S'aplica DESPRÉS de traduir i ABANS de reinjectar al XML.

    Correccions incloses:
    - Guions al principi (amb o sense dígit, amb o sense espai)
    - Números sols al principi seguits de majúscula
    - Markdown (**negreta**, *cursiva*, # Títol)
    - Espais davant de puntuació: "text ." → "text."
    """
    if not text:
        return text

    # ── Artefactes del model ──────────────────────────────────────────────────

    # Elimina guió llarg/mitjà/curt al principi (amb o sense espai o dígit)
    text = re.sub(r'^[\u2014\u2013\-]+\s*\d*\s*', '', text)

    # Elimina número sol al principi seguit de lletra majúscula o accentuada
    text = re.sub(
        r'^\d+\s+(?=[A-Z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u017e\u00b7])', '', text
    )

    # Elimina Markdown
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # ── Espais ────────────────────────────────────────────────────────────────
    text = re.sub(r' {2,}', ' ', text)
    # Elimina espais davant de puntuació final
    text = re.sub(r' ([.,;:!?»\)\]])', r'\1', text)

    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Postprocessament d'apostrofacions i ela geminada per run
# ═══════════════════════════════════════════════════════════════════════════════

def corregeix_apostrofacions_run(text: str) -> str:
    """
    Corregeix els espais incorrectes en apostrofacions catalanes/valencianes
    i en l'ela geminada dins d'un run individual.

    S'aplica DESPRÉS de neteja_traduccio_xml() sobre el text de cada run.

    Casos coberts:
      l' aigua       → l'aigua
      d' Enginyeria  → d'Enginyeria
      m' ho          → m'ho
      al · lucinar   → al·lucinar
      l . l          → l·l
      l.l            → l·l
    """
    if not text:
        return text

    # Cas 1: lletra + apòstrof + espai(s) + caràcter → lletra + apòstrof + caràcter
    # Cobreix: "l' aigua", "d' ell", "m' ho", "d' Enginyeria"
    text = re.sub(
        r"([a-z\u00e0-\u00f6\u00f8-\u017eA-Z\u00c0-\u00d6\u00d8-\u00f6])'(\s+)([^\s])",
        r"\1'\3", text
    )
    # Cas 2: paraula + espai(s) + apòstrof + lletra minúscula
    text = re.sub(
        r"([^\s])(\s+)'([a-z\u00e0-\u00f6\u00f8-\u017e])",
        r"\1'\3", text
    )

    # Ela geminada amb espais al voltant del punt volat: al · lucinar → al·lucinar
    text = re.sub(r'\s*·\s*', '·', text)
    # Ela geminada amb punt normal i espais: l . l → l·l
    text = re.sub(r'([lL])\s*\.\s*([lL])', r'\1·\2', text)
    # Ela geminada amb punt normal sense espais: l.l → l·l
    text = re.sub(r'([lL])\.([lL])', r'\1·\2', text)

    return text


# ═══════════════════════════════════════════════════════════════════════════════
# Detecció de nodes dins d'imatges o gràfics
# ═══════════════════════════════════════════════════════════════════════════════

def es_dins_imatge(node: etree._Element) -> bool:
    """
    Comprova si un node paràgraf és dins d'una imatge, gràfic o forma decorativa.
    En aquest cas el paràgraf no s'ha de traduir (text alternatiu, llegendes
    de sèries, etc.).
    """
    parent = node.getparent()
    while parent is not None:
        if parent.tag in TAGS_IMATGE:
            return True
        parent = parent.getparent()
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Extracció de text per a filtratge
# ═══════════════════════════════════════════════════════════════════════════════

def obte_text_paragraf(p_node: etree._Element, ns_t: str) -> str:
    """
    Extreu el text pla d'un node de paràgraf XML
    concatenant tots els elements <w:t> o <a:t>.
    Usat per al filtratge ràpid de paràgrafs buits.
    """
    parts = []
    for t in p_node.iter(f'{{{ns_t}}}t'):
        if t.text:
            parts.append(t.text)
    return ''.join(parts).strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Traducció run per run — estratègia v4
# ═══════════════════════════════════════════════════════════════════════════════

def tradueix_paragraf_per_runs(
    p_node: etree._Element,
    ns_para: str,
    funcio_traduccio: Callable[[str], str],
) -> None:
    """
    Tradueix cada run del paràgraf de forma independent, preservant
    exactament el format (<w:rPr>/<a:rPr>) de cada run original.

    Estratègia (v4):
    - Cada <w:r>/<a:r> es tradueix per separat
    - El <w:rPr>/<a:rPr> de cada run NO es toca mai
    - El text traduït es posa al <w:t>/<a:t> del mateix run
    - Els runs buits, molt curts o purament numèrics/simbòlics es
      preserven intactes (no s'envien al motor de traducció)
    - Els runs dins d'hipervincles (<w:hyperlink>) NO es tradueixen
      perquè solen contenir URLs o text d'ancoratge crític

    Paràmetres:
        p_node:           node <w:p> o <a:p> del paràgraf
        ns_para:          namespace (NS_W per a DOCX, NS_A per a PPTX)
        funcio_traduccio: funció que rep text castellà i retorna text en valencià
    """
    tag_r         = f'{{{ns_para}}}r'
    tag_t         = f'{{{ns_para}}}t'
    tag_hyperlink = f'{{{ns_para}}}hyperlink'
    xml_space     = '{http://www.w3.org/XML/1998/namespace}space'

    # Recull únicament els runs fills directes del paràgraf.
    # Els runs dins d'hipervincles (<w:hyperlink>) s'ometen deliberadament.
    runs_directes = [child for child in p_node if child.tag == tag_r]

    if not runs_directes:
        return

    for run in runs_directes:
        t_nodes = [child for child in run if child.tag == tag_t]
        if not t_nodes:
            continue

        # Extreu el text complet del run (pot tenir múltiples <w:t>)
        text_run = ''.join((t.text or '') for t in t_nodes)
        text_net = text_run.strip()

        # Ignora runs buits, d'un sol caràcter o purament numèrics/simbòlics
        if not text_net or len(text_net) < 2:
            continue
        if _RE_NO_TRADUIR.match(text_net):
            continue

        try:
            # Preserva els espais inicials i finals del run original
            espai_inicial = text_run[: len(text_run) - len(text_run.lstrip())]
            espai_final   = text_run[len(text_run.rstrip()):]

            # Tradueix el contingut net (sense espais marginals)
            text_traduit = funcio_traduccio(text_net)
            text_traduit = neteja_traduccio_xml(text_traduit)
            text_traduit = corregeix_apostrofacions_run(text_traduit)

            # No substitueix si el resultat és buit o idèntic a l'original
            if not text_traduit or text_traduit == text_net:
                continue

            # Reconstrueix amb espais originals
            text_final = espai_inicial + text_traduit + espai_final

            # Substitueix el text al primer <w:t>, buida els addicionals
            t_nodes[0].text = text_final
            t_nodes[0].set(xml_space, 'preserve')
            for t in t_nodes[1:]:
                t.text = ''

        except Exception as e:
            log.warning(
                f'Error traduint run {text_net[:40]!r}: {e!r} — manté original'
            )


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
) -> bytes:
    """
    Tradueix un document .docx o .pptx preservant el format perfectament.

    Paràmetres:
        contingut_original: contingut binari del fitxer original
        extensio:           'docx' o 'pptx' (amb o sense punt inicial)
        funcio_traduccio:   funció que rep text castellà i retorna text en valencià
        tradueix_notes:     (PPTX) si True, inclou les notes del presentador
                            (notesSlides/). Per defecte True.

    Retorna:
        contingut binari del fitxer traduït

    Estratègia (v4 — run per run):
        1. Obre el ZIP en memòria (docx/pptx són ZIPs d'XMLs)
        2. La regex de fitxers PPTX es tria aquí, depenent de tradueix_notes
        3. Per a cada XML de contingut:
           a. Parseja el XML amb lxml
           b. Per a cada paràgraf (<w:p> o <a:p>):
              - Si és dins d'imatge/gràfic → IGNORA
              - Si el text del paràgraf té menys de 2 caràcters → IGNORA
              - Crida tradueix_paragraf_per_runs() per traduir run per run
           c. Serialitza l'XML modificat
           d. Força l'idioma ca-ES
        4. Escriu tots els fitxers al ZIP de sortida
    """
    extensio = extensio.lower().lstrip('.')
    es_docx  = extensio == 'docx'
    es_pptx  = extensio == 'pptx'

    if not es_docx and not es_pptx:
        raise ValueError(f'Format no suportat: {extensio!r}. Usa "docx" o "pptx".')

    # La regex de fitxers PPTX es decideix aquí, depenent de tradueix_notes
    if es_docx:
        regex_fitxers = re.compile(
            r'^word/(document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$'
        )
    else:  # pptx
        if tradueix_notes:
            regex_fitxers = re.compile(
                r'^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$'
            )
        else:
            regex_fitxers = re.compile(r'^ppt/slides/slide\d+\.xml$')

    ns_para  = NS_W if es_docx else NS_A
    ns_text  = NS_W if es_docx else NS_A
    tag_para = f'{{{ns_para}}}p'

    # Obre el ZIP original en memòria
    zip_entrada        = zipfile.ZipFile(io.BytesIO(contingut_original), 'r')
    zip_sortida_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_sortida_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_sortida:
        for nom_fitxer in zip_entrada.namelist():
            contingut = zip_entrada.read(nom_fitxer)

            if regex_fitxers.match(nom_fitxer):
                # ── Processa els fitxers XML que contenen text ──────────────
                try:
                    arbre = etree.fromstring(contingut)

                    # ── Bucle principal: traducció run per run ───────────────
                    for p_node in arbre.iter(tag_para):
                        # Ignora paràgrafs dins d'imatges o gràfics
                        if es_dins_imatge(p_node):
                            continue

                        # Filtratge ràpid: ignora paràgrafs buits o trivials
                        text_complet = obte_text_paragraf(p_node, ns_text)
                        if not text_complet or len(text_complet.strip()) < 2:
                            continue

                        # Tradueix cada run del paràgraf preservant el format
                        try:
                            tradueix_paragraf_per_runs(
                                p_node,
                                ns_text,
                                funcio_traduccio,
                            )
                        except Exception as e:
                            log.warning(
                                f'Error processant paràgraf: {e!r} — manté original'
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
                    if es_docx:
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
