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

Correccions definitives (v3):
  C1 — neteja_traduccio_xml(): captura guions sense dígit (—Relé)
  C2 — substitueix_text_paragraf(): distribueix text proporcionalment
       entre runs existents (preserva el format de CADA run)
  C3 — divideix_per_oracions() + tradueix_text_llarg(): divideix sempre
       per oracions i aplica neteja internament
  C4 — regex PPTX definides dins de tradueix_document() per poder
       dependre de tradueix_notes; elimina paràmetre tradueix_plantilles
  C5 — TAGS_IMATGE ampliada amb NS_PIC, NS_WPD, NS_CHART
  C6 — Bucle principal: filtre len<2, f-string a warning

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

NS_W    = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS_A    = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_R    = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_P    = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_PIC  = 'http://schemas.openxmlformats.org/drawingml/2006/picture'
NS_WPD  = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
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

# ── Regex per a fitxers XML interns (DOCX sempre; PPTX es decideix dins de
#    tradueix_document() depenent de tradueix_notes) ──────────────────────────

DOCX_REGEX = re.compile(
    r'^word/(document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$'
)

# ── C5 — Tags d'imatge i gràfic ampliats ────────────────────────────────────

TAGS_IMATGE = frozenset({
    f'{{{NS_WPD}}}inline',
    f'{{{NS_WPD}}}anchor',
    f'{{{NS_A}}}graphicData',
    f'{{{NS_CHART}}}chart',
    f'{{{NS_PIC}}}pic',
    f'{{{NS_PIC}}}nvPicPr',
})


# ═══════════════════════════════════════════════════════════════════════════════
# C1/C2 — Neteja d'artefactes del motor de traducció (versió definitiva)
# ═══════════════════════════════════════════════════════════════════════════════

def neteja_traduccio_xml(text: str) -> str:
    """
    Neteja els artefactes que el motor de traducció afegeix incorrectament.
    S'aplica DESPRÉS de traduir i ABANS de reinjectar al XML.

    Correccions incloses:
    - Guions al principi (amb o sense dígit, amb o sense espai)
    - Números sols al principi seguits de majúscula
    - Markdown (**negreta**, *cursiva*, # Títol)
    - Apostrofacions: l' aigua → l'aigua, d' ell → d'ell
    - Ela geminada: al · lucinar → al·lucinar, l . l → l·l
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

    # ── Apostrofacions ────────────────────────────────────────────────────────
    # Cas 1: lletra + apòstrof + espais + paraula  →  lletra + apòstrof + paraula
    # ex: "l' aigua" → "l'aigua",  "d' ell" → "d'ell",  "m' ho" → "m'ho"
    text = re.sub(
        r"([a-z\u00e0-\u00f6\u00f8-\u017eA-Z\u00c0-\u00d6\u00d8-\u00f6])'(\s+)([^\s])",
        r"\1'\3", text
    )
    # Cas 2: paraula + espais + apòstrof + lletra  →  paraula + apòstrof + lletra
    text = re.sub(
        r"([^\s])(\s+)'([a-z\u00e0-\u00f6\u00f8-\u017e])",
        r"\1'\3", text
    )

    # ── Ela geminada ──────────────────────────────────────────────────────────
    # "al · lucinar" → "al·lucinar"  /  "col · legi" → "col·legi"
    text = re.sub(r'\s*·\s*', '·', text)
    # "l . l" → "l·l"  (punt volat escrit com a punt normal amb espais)
    text = re.sub(r'([lL])\s*\.\s*([lL])', r'\1·\2', text)
    # "l.l" → "l·l"  (punt normal sense espais)
    text = re.sub(r'([lL])\.([lL])', r'\1·\2', text)

    # ── Espais ────────────────────────────────────────────────────────────────
    text = re.sub(r' {2,}', ' ', text)
    # Elimina espais davant de puntuació final
    text = re.sub(r' ([.,;:!?»\)\]])', r'\1', text)

    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Correcció de paraules enganxades (C-PEng)
# ═══════════════════════════════════════════════════════════════════════════════

def corregeix_paraules_enganxades(text: str) -> str:
    """
    Detecta i corregeix paraules enganxades (sense espai entre elles).
    S'aplica al text final de cada paràgraf traduït, després de la neteja.

    Causa: la distribució proporcional entre runs pot produir fragments
    com "serveiEl" si la tokenització no és perfecta.

    Casos coberts:
    - Minúscula seguida de majúscula: "serveiEl" → "servei El"
    - Dígit seguit de lletra: "2023la" → "2023 la"
    - Lletra minúscula seguida de dígit: "text2" → "text 2"
    """
    if not text:
        return text

    # Minúscula (inclou accentuades) + Majúscula: serveiEl → servei El
    # Usa \p no disponible, per tant fem servir classe explícita amb caràcters reals
    _min = 'a-záéíóúàèìòùïüçl'
    _maj = 'A-ZÁÉÍÓÚÀÈÌÒÙÏÜÇ'
    text = re.sub(rf'([{_min}·])([{_maj}])', r'\1 \2', text)

    # Dígit + Lletra (majúscula o minúscula): 2023la → 2023 la
    text = re.sub(rf'(\d)([{_maj}{_min}])(?!\d)', r'\1 \2', text)

    # Lletra minúscula + Dígit: text2 → text 2
    text = re.sub(rf'([{_min}])(\d)', r'\1 \2', text)

    return text


# ═══════════════════════════════════════════════════════════════════════════════
# C3 — Segmentació per oracions i traducció de textos llargs
# ═══════════════════════════════════════════════════════════════════════════════

def divideix_per_oracions(text: str) -> list:
    """
    Divideix el text en oracions individuals per a traducció independent.
    Cada oració es tradueix per separat i es reuneix al final.

    C3: substitueix divideix_en_segments(). Ara divideix SEMPRE per oracions
    (no per nombre de caràcters), cosa que evita el truncament del model fins
    i tot en textos moderadament llargs.
    """
    if not text or len(text) < 100:
        return [text]
    # Divideix per punt, exclamació o interrogació seguit d'espai i majúscula/cometa/parèntesi
    oracions = re.split(
        r'(?<=[.!?])\s+(?=[A-Z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u017e"\(\u00bf\u00a1])',
        text,
    )
    return [o.strip() for o in oracions if o.strip()]


def tradueix_text_llarg(text: str, funcio_traduccio: Callable[[str], str]) -> str:
    """
    Tradueix un text dividint-lo per oracions per evitar truncaments del model.
    Aplica neteja_traduccio_xml() a cada segment traduït.

    C3: integra la neteja internament (per segments), de manera que la
    neteja s'aplica a cada oració traduïda per separat i de nou al resultat
    final al bucle principal.
    """
    if not text:
        return text

    oracions = divideix_per_oracions(text)

    if len(oracions) <= 1:
        resultat = funcio_traduccio(text)
        return neteja_traduccio_xml(resultat)

    traduits = []
    for oracio in oracions:
        try:
            traduit = funcio_traduccio(oracio)
            traduit = neteja_traduccio_xml(traduit)
            traduits.append(traduit)
        except Exception as e:
            log.warning(f'Error traduint oració: {e!r} — usa original')
            traduits.append(oracio)

    return ' '.join(traduits)


# ═══════════════════════════════════════════════════════════════════════════════
# C5 — Detecció de paràgrafs dins d'imatges o gràfics
# ═══════════════════════════════════════════════════════════════════════════════

def es_dins_imatge(node: etree._Element) -> bool:
    """
    Comprova si un node paràgraf és dins d'una imatge, gràfic o forma decorativa.
    En aquest cas el paràgraf no s'ha de traduir (text alternatiu, títol de
    gràfic, llegendes de sèries, etc.).

    C5: TAGS_IMATGE ampliada amb NS_PIC i NS_WPD per cobrir imatges incrustades
    i formes picture de PowerPoint.
    """
    parent = node.getparent()
    while parent is not None:
        if parent.tag in TAGS_IMATGE:
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
    Distribueix el text traduït entre els runs existents de forma proporcional,
    preservant exactament el format (<w:rPr>/<a:rPr>) de cada run original.

    C2 — Estratègia corregida (distribuir, no eliminar):
      Versió anterior: posava tot el text al primer run i eliminava la resta.
      Problema: tot el text heretava el format del primer run (ex. cursiva).

      Versió actual: distribueix les paraules proporcionalment entre TOTS
      els runs existents, mantenint exactament el mateix nombre de runs.
      Cada run conserva el seu <w:rPr> intacte, per tant el format de
      cada fragment del text queda associat al run correcte.

      Cas especial: hipervincles (<w:hyperlink>/<a:hlinkClick>) — els runs
      dins d'hipervincles s'inclouen en el recompte de runs normals.
    """
    tag_r         = f'{{{ns_para}}}r'
    tag_t         = f'{{{ns_para}}}t'
    tag_hyperlink = f'{{{ns_para}}}hyperlink'
    xml_space     = '{http://www.w3.org/XML/1998/namespace}space'

    # Recull tots els runs (fills directes del paràgraf + dins d'hipervincles)
    runs = []
    for child in p_node:
        if child.tag == tag_r:
            runs.append(child)
        elif child.tag == tag_hyperlink:
            for subchild in child:
                if subchild.tag == tag_r:
                    runs.append(subchild)

    if not runs:
        return

    # ── Cas simple: un sol run ───────────────────────────────────────────────
    if len(runs) == 1:
        t_nodes = [c for c in runs[0] if c.tag == tag_t]
        if t_nodes:
            t_nodes[0].text = text_traduit
            t_nodes[0].set(xml_space, 'preserve')
            for t in t_nodes[1:]:
                t.text = ''
        else:
            nou_t = etree.SubElement(runs[0], tag_t)
            nou_t.text = text_traduit
            nou_t.set(xml_space, 'preserve')
        return

    # ── Cas múltiples runs: distribució proporcional ─────────────────────────
    # Calcula la longitud original de text de cada run
    longituds = []
    for run in runs:
        text_run = ''.join((c.text or '') for c in run if c.tag == tag_t)
        longituds.append(max(len(text_run), 1))

    total_long  = sum(longituds)
    paraules    = text_traduit.split()
    total_pars  = len(paraules)

    if total_pars == 0:
        # Text buit: buida tots els <w:t>
        for run in runs:
            for t in run:
                if t.tag == tag_t:
                    t.text = ''
        return

    # Distribueix paraules proporcionalment mantenint almenys 1 per run
    # fins que s'esgotin les paraules
    fragments = []
    idx = 0
    n_runs = len(runs)
    for i, long_orig in enumerate(longituds):
        if i == n_runs - 1:
            # Últim run: totes les paraules restants
            fragment = ' '.join(paraules[idx:])
        else:
            proporcio = long_orig / total_long
            n = max(1, round(total_pars * proporcio))
            # Assegura que queda almenys 1 paraula per a cada run restant
            n = min(n, total_pars - idx - (n_runs - i - 1))
            n = max(n, 1)
            fragment = ' '.join(paraules[idx:idx + n])
            idx += n
        fragments.append(fragment)

    # Assigna cada fragment al <w:t>/<a:t> del seu run, preservant <w:rPr>
    # C4: assegura espai de separació al final de cada fragment intermedi
    #     per evitar paraules enganxades quan Word concatena runs adjacents.
    for i, (run, fragment) in enumerate(zip(runs, fragments)):
        if i < len(runs) - 1 and fragment and not fragment.endswith(' '):
            fragment = fragment + ' '
        t_nodes = [c for c in run if c.tag == tag_t]
        if t_nodes:
            t_nodes[0].text = fragment
            t_nodes[0].set(xml_space, 'preserve')
            for t in t_nodes[1:]:
                t.text = ''
        else:
            nou_t = etree.SubElement(run, tag_t)
            nou_t.text = fragment
            nou_t.set(xml_space, 'preserve')


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

    Estratègia (v3):
        1. Obre el ZIP en memòria (docx/pptx són ZIPs d'XMLs)
        2. C4: la regex de fitxers PPTX es tria aquí, depenent de tradueix_notes
        3. Per a cada XML de contingut:
           a. Parseja el XML amb lxml
           b. Per a cada paràgraf (<w:p> o <a:p>):
              - C5: si és dins d'imatge/gràfic → IGNORA
              - C6: si el text té menys de 2 caràcters → IGNORA
              - C3: tradueix per oracions per evitar truncaments
              - C1: aplica neteja d'artefactes
              - C2: distribueix text proporcionalment entre runs
           c. Serialitza l'XML modificat
           d. Força l'idioma ca-ES
        4. Escriu tots els fitxers al ZIP de sortida
    """
    extensio = extensio.lower().lstrip('.')
    es_docx = extensio == 'docx'
    es_pptx = extensio == 'pptx'

    if not es_docx and not es_pptx:
        raise ValueError(f'Format no suportat: {extensio!r}. Usa "docx" o "pptx".')

    # C4 — La regex de fitxers es decideix aquí, dins de la funció
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

                    # C6 — Bucle principal unificat amb totes les correccions
                    for p_node in arbre.iter(tag_para):
                        # C5: ignora paràgrafs dins d'imatges o gràfics
                        if es_dins_imatge(p_node):
                            continue

                        text_original = obte_text_paragraf(p_node, ns_text)

                        # C6: ignora paràgrafs buits o d'un sol caràcter
                        if not text_original or len(text_original.strip()) < 2:
                            continue

                        try:
                            # C3: traducció per oracions per evitar truncaments
                            text_traduit = tradueix_text_llarg(
                                text_original, funcio_traduccio
                            )
                            # C1/C2: neteja artefactes del model (segona passada)
                            text_traduit = neteja_traduccio_xml(text_traduit)
                            # C-PEng: corregeix paraules enganxades per la distribució
                            text_traduit = corregeix_paraules_enganxades(text_traduit)

                            if text_traduit and text_traduit.strip() != text_original.strip():
                                # C2: distribueix proporcionalment, preserva format
                                substitueix_text_paragraf(
                                    p_node, text_traduit, ns_text
                                )
                        except Exception as e:
                            log.warning(f'Error traduint: {e!r} — manté original')

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
