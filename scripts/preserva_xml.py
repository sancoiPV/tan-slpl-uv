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

DOCX_REGEX = re.compile(
    r'^word/(document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$'
)
PPTX_REGEX = re.compile(
    r'^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$'
)

# ── Funcions d'extracció i substitució de text ───────────────────────────────

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
    ns_t: str,
) -> None:
    """
    Substitueix el text dins del paràgraf XML preservant totes les etiquetes.
    Estratègia: posa tot el text traduït al primer element <w:t> o <a:t>
    i buida la resta, sense tocar cap altra etiqueta XML.
    """
    t_nodes = list(p_node.iter(f'{{{ns_t}}}t'))
    if not t_nodes:
        return

    # Posa el text traduït al primer <w:t> o <a:t>
    t_nodes[0].text = text_traduit

    # Preserva l'atribut xml:space="preserve" si el text té espais inicials/finals
    xml_space = '{http://www.w3.org/XML/1998/namespace}space'
    if text_traduit != text_traduit.strip():
        t_nodes[0].set(xml_space, 'preserve')

    # Buida la resta de nodes <w:t> o <a:t>
    for t in t_nodes[1:]:
        t.text = ''


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


# ── Funció principal de traducció de documents ───────────────────────────────

def tradueix_document(
    contingut_original: bytes,
    extensio: str,
    funcio_traduccio: Callable[[str], str],
) -> bytes:
    """
    Tradueix un document .docx o .pptx preservant el format perfectament.

    Paràmetres:
        contingut_original: contingut binari del fitxer original
        extensio:           'docx' o 'pptx' (amb o sense punt inicial)
        funcio_traduccio:   funció que rep text en castellà i retorna text en valencià

    Retorna:
        contingut binari del fitxer traduït

    L'estratègia és:
        1. Obrir el ZIP en memòria (docx/pptx són ZIPs d'XMLs)
        2. Per a cada XML de contingut (document.xml, slideN.xml, etc.):
           a. Parsejar el XML amb lxml
           b. Per a cada paràgraf (<w:p> o <a:p>):
              - Extreure el text pla concatenant tots els <w:t>/<a:t>
              - Si hi ha text, cridar funcio_traduccio
              - Posar el resultat al primer <w:t>/<a:t> i buidar la resta
           c. Serialitzar l'XML modificat (les etiquetes de format no s'han tocat)
           d. Forçar l'idioma ca-ES als atributs de llengua
        3. Escriure tots els fitxers (modificats i originals) a un nou ZIP
    """
    extensio = extensio.lower().lstrip('.')

    if extensio == 'docx':
        regex_fitxers = DOCX_REGEX
        ns_para = NS_W
        ns_text = NS_W
    elif extensio == 'pptx':
        regex_fitxers = PPTX_REGEX
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

                    # Itera sobre tots els paràgrafs del document
                    for p_node in arbre.iter(tag_para):
                        text_original = obte_text_paragraf(p_node, ns_text)

                        if not text_original:
                            continue

                        try:
                            text_traduit = funcio_traduccio(text_original)
                            if text_traduit and text_traduit != text_original:
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
