# -*- coding: utf-8 -*-
"""
preserva_xml.py
===============
Traducció de documents .docx i .pptx amb preservació perfecta del format.

Estratègia: manipulació directa de l'XML intern del fitxer ZIP.
- NO usa python-docx ni python-pptx per a modificar el document
- Parseja els XMLs interns amb lxml
- Tradueix el paràgraf complet per màxima qualitat lingüística
- Distribueix el resultat per segments de format homogeni (v6)

Estratègia híbrida definitiva (v6):
  Per paràgrafs d'un sol format: tot el text al primer run.
  Per paràgrafs amb formats mixtos: agrupa runs contigus de format
  homogeni en segments i tradueix cada segment per separat.
  Això garanteix que la cursiva, la negreta, etc. queden exactament
  als mateixos mots que a l'original, sense redistribució proporcional.

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

NS_W      = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS_A      = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_MATH_PX = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
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

# ── Regex per a contingut no traduïble ──────────────────────────────────────

_RE_NO_TRADUIR = re.compile(
    r'^[\d\s\.\,\:\;\!\?\(\)\[\]\{\}\-\_\+\=\*\/\\<>@#%&|~^`\'\"]+$'
)

# ── Constants d'apòstrof ─────────────────────────────────────────────────────

APOSTREF_RECTE      = "'"   # U+0027
APOSTREF_TIPOGRAFIC = "\u2019"  # U+2019  '
APOSTREF_OBERT      = "\u2018"  # U+2018  '


# ═══════════════════════════════════════════════════════════════════════════════
# Normalització d'apostrofacions i ela geminada (versió definitiva v6)
# ═══════════════════════════════════════════════════════════════════════════════

def normalitza_apostrofacions(text: str) -> str:
    """
    Normalitza tots els apòstrofs (rectes i tipogràfics) i elimina TOTS
    els espais al voltant dels apòstrofs sense excepció.
    Converteix el resultat a apòstrof tipogràfic (U+2019) entre paraules.

    Casos coberts:
      l' aigua        → l'aigua       (espai després)
      l\u2019 aigua   → l'aigua       (apòstrof tipogràfic + espai)
      d ' Enginyeria  → d'Enginyeria  (espais a banda i banda)
      de Enginyeria   → d'Enginyeria  (de + vocal)
      al · lucinar    → al·lucinar    (ela geminada amb espais)
      l.l             → l·l           (ela geminada amb punt)
    """
    if not text:
        return text

    # Pas 1: Normalitza tots els apòstrofs a rectes per processar uniformement
    text = text.replace(APOSTREF_TIPOGRAFIC, APOSTREF_RECTE)
    text = text.replace(APOSTREF_OBERT, APOSTREF_RECTE)

    # Pas 2: Elimina TOTS els espais al voltant de l'apòstrof
    # Cas complet: paraula + espais + apòstrof + espais + paraula
    text = re.sub(r"(\w)\s*'\s*(\w)", r"\1'\2", text)
    # Cas residual: apòstrof al principi seguit d'espai
    text = re.sub(r"^'\s+", "'", text)
    # Cas residual: espai + apòstrof al final
    text = re.sub(r"\s+'$", "'", text)
    # Cas residual: qualsevol espai just davant o darrere d'apòstrof
    text = re.sub(r"\s+'", "'", text)
    text = re.sub(r"'\s+", "'", text)

    # Pas 3: Conversions gramaticals catalanes/valencianes
    # "de " + vocal/h inicial de mot → "d'" (ex: "de Enginyeria" → "d'Enginyeria")
    text = re.sub(
        r'\bde\s+([aeiouàèéíïòóúüh])',
        lambda m: "d'" + m.group(1),
        text,
        flags=re.IGNORECASE,
    )
    # Corregeix "l' " residual (apòstrof ja unit a l però amb espai posterior)
    text = re.sub(r"\bl'\s+", "l'", text, flags=re.IGNORECASE)

    # Pas 4: Ela geminada (usa el caràcter · directament — \u en substitució no vàlid)
    text = re.sub(r'\s*·\s*', '·', text)              # al · lucinar → al·lucinar
    text = re.sub(r'([lL])\s*\.\s*([lL])', r'\1·\2', text)  # l . l → l·l
    text = re.sub(r'([lL])\.([lL])', r'\1·\2', text)         # l.l → l·l

    # Pas 5: Converteix apòstrofs rectes entre paraules a tipogràfics (U+2019)
    text = re.sub(r"(\w)'(\w)", r"\1" + APOSTREF_TIPOGRAFIC + r"\2", text)

    # Pas 6: Neteja espais múltiples
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


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
    - Apostrofacions i ela geminada (via normalitza_apostrofacions)
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
    text = re.sub(r' ([.,;:!?\u00bb\)\]])', r'\1', text)

    # Apostrofacions i ela geminada
    text = normalitza_apostrofacions(text)

    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Filtre d'al·lucinacions del model de traducció
# ═══════════════════════════════════════════════════════════════════════════════

def filtra_alucinacions(text_original: str, text_traduit: str) -> str:
    """
    Detecta i elimina paraules al·lucinatòries que el model afegeix sense
    que existeixin al text original.

    Criteri d'al·lucinació: paraules completament en majúscules de més de
    2 caràcters que NO apareixen a l'original en cap forma.

    Nota: el nom de la funció usa 'alucinacions' (sense punt volat) perquè
    el punt volat \u00b7 no és vàlid en identificadors Python.
    """
    if not text_traduit or not text_original:
        return text_traduit

    paraules_traduit       = text_traduit.split()
    paraules_original_lower = set(text_original.lower().split())

    resultat = []
    for paraula in paraules_traduit:
        paraula_neta = re.sub(r'[^\w]', '', paraula).lower()

        # Paraula en majúscules de >2 caràcters absent de l'original → al·lucinació
        if (paraula.isupper() and len(paraula_neta) > 2
                and paraula_neta not in paraules_original_lower):
            log.warning('Al·lucinació detectada i eliminada: %r', paraula)
            continue

        resultat.append(paraula)

    text_net = ' '.join(resultat)
    text_net = re.sub(r' {2,}', ' ', text_net)
    return text_net.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Detecció de nodes dins d'imatges o gràfics
# ═══════════════════════════════════════════════════════════════════════════════

def es_dins_imatge(node: etree._Element) -> bool:
    """
    Comprova si un node paràgraf és dins d'una imatge, gràfic o forma decorativa.
    En aquest cas el paràgraf no s'ha de traduir.
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

_XML_SPACE_ATTR = '{http://www.w3.org/XML/1998/namespace}space'


def _obte_text_node(t_node: etree._Element) -> str:
    """
    Retorna el text d'un node <w:t> o <a:t> respectant xml:space='preserve'.
    - Si t_node.text no és None, retorna'l directament (pot ser buit '').
    - Si t_node.text és None però el node té xml:space='preserve', retorna ' '.
      Açò cobrix el cas de nodes creats sense text però marcats com a espai.
    - Altrament retorna ''.
    """
    if t_node.text is not None:
        return t_node.text
    if t_node.get(_XML_SPACE_ATTR) == 'preserve':
        return ' '
    return ''


def _te_formula(element: etree._Element) -> bool:
    """
    Detecta si un element (paràgraf <w:p> o <a:p>) conté fórmules matemàtiques
    que no haurien de ser traduïdes ni modificades:
    - OMML nativa (Word 2007+): <m:oMath>, <m:oMathPara>
    - Equation Editor antic (OLE): <w:object>
    - Equacions com a imatge VML: <w:pict>
    Retorna True si cal ometre el paràgraf de la traducció.
    """
    # OMML — equacions natives de Word 2007+
    if element.find(f'.//{{{NS_MATH_PX}}}oMath') is not None:
        return True
    if element.find(f'.//{{{NS_MATH_PX}}}oMathPara') is not None:
        return True
    # Objectes OLE (Equation Editor 3.x)
    if element.find(f'.//{{{NS_W}}}object') is not None:
        return True
    # Equacions rasteritzades com a imatge VML
    if element.find(f'.//{{{NS_W}}}pict') is not None:
        return True
    return False


def obte_text_paragraf(p_node: etree._Element, ns_t: str) -> str:
    """
    Extreu el text pla d'un node de paràgraf XML concatenant tots els
    elements <w:t> o <a:t>. Usat per al filtratge ràpid de paràgrafs buits.
    """
    parts = []
    for t in p_node.iter(f'{{{ns_t}}}t'):
        val = _obte_text_node(t)
        if val:
            parts.append(val)
    return ''.join(parts).strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers de format de runs
# ═══════════════════════════════════════════════════════════════════════════════

def tots_runs_mateix_format(runs: list, tag_rpr: str) -> bool:
    """
    Retorna True ÚNICAMENT en dos casos:
    a) Tots els runs no tenen cap format especial (tots normals).
    b) Tots els runs tenen exactament el mateix conjunt de formats especials.

    És molt conservador: qualsevol barreja (algun cursiu i algun normal)
    retorna False per garantir la distribució per segments i evitar que
    tot el paràgraf herete el format del primer run.
    """
    if len(runs) <= 1:
        return True

    _TAGS_FORMAT = frozenset({
        'i', 'b', 'u', 'strike', 'vertAlign', 'color',
        'sz', 'szCs', 'rFonts', 'highlight', 'shd',
        'caps', 'smallCaps', 'emboss', 'imprint', 'shadow',
    })

    def te_format_especial(run: etree._Element) -> bool:
        rpr = run.find(tag_rpr)
        if rpr is None:
            return False
        for child in rpr:
            nom = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if nom in _TAGS_FORMAT:
                return True
        return False

    formats_especials = [te_format_especial(r) for r in runs]

    if not any(formats_especials):
        return True
    if not all(formats_especials):
        return False

    _NS_W = NS_W

    def empremta_format(run: etree._Element) -> frozenset:
        rpr = run.find(tag_rpr)
        if rpr is None:
            return frozenset()
        return frozenset(
            (child.tag, child.get(f'{{{_NS_W}}}val', ''))
            for child in rpr
        )

    primer = empremta_format(runs[0])
    return all(empremta_format(r) == primer for r in runs[1:])


def agrupa_runs_per_format(runs: list, tag_rpr: str) -> list:
    """
    Agrupa els runs contigus amb el mateix format en segments.
    Retorna una llista de tuples (format_key, [runs]).

    Cada segment és un grup de runs contigus que comparteixen el mateix
    conjunt de formats especials (cursiva, negreta, etc.). Açò permet
    traduir cada segment per separat preservant exactament on comença
    i acaba cada format al document final.
    """
    _TAGS_VISUALS = frozenset({
        'i', 'b', 'u', 'strike', 'caps', 'smallCaps', 'vertAlign',
    })

    def format_key(run: etree._Element) -> str:
        rpr = run.find(tag_rpr)
        if rpr is None:
            return 'normal'
        tags = frozenset(
            child.tag.split('}')[-1]
            for child in rpr
            if (child.tag.split('}')[-1] if '}' in child.tag else child.tag)
            in _TAGS_VISUALS
        )
        return str(sorted(tags)) if tags else 'normal'

    if not runs:
        return []

    segments      = []
    format_actual = format_key(runs[0])
    segment_actual = [runs[0]]

    for run in runs[1:]:
        fmt = format_key(run)
        if fmt == format_actual:
            segment_actual.append(run)
        else:
            segments.append((format_actual, segment_actual))
            format_actual  = fmt
            segment_actual = [run]

    segments.append((format_actual, segment_actual))
    return segments


# ═══════════════════════════════════════════════════════════════════════════════
# Estratègia híbrida definitiva v6
# ═══════════════════════════════════════════════════════════════════════════════

def tradueix_i_preserva_format(
    p_node: etree._Element,
    ns_para: str,
    funcio_traduccio: Callable[[str], str],
) -> None:
    """
    Estratègia híbrida definitiva (v6):
    - Paràgrafs d'un sol format: tradueix el text complet i posa'l al
      primer run; buida la resta (conserva <w:rPr>).
    - Paràgrafs amb formats mixtos: agrupa runs contigus de format
      homogeni en segments i tradueix cada segment per separat.
      Açò garanteix que la cursiva, la negreta, etc. queden
      als mateixos mots que a l'original.

    Pipeline de postprocessament per a cada traducció:
      funcio_traduccio → filtra_alucinacions → neteja_traduccio_xml
      → normalitza_apostrofacions

    Els runs dins d'hipervincles (<w:hyperlink>) s'ometen (contenen URLs).
    """
    tag_r         = f'{{{ns_para}}}r'
    tag_t         = f'{{{ns_para}}}t'
    tag_rpr       = f'{{{ns_para}}}rPr'
    tag_hyperlink = f'{{{ns_para}}}hyperlink'
    xml_space     = '{http://www.w3.org/XML/1998/namespace}space'

    # Runs fills directes del paràgraf (no els dins d'hipervincles)
    runs = [child for child in p_node if child.tag == tag_r]
    if not runs:
        return

    # Text complet del paràgraf per a context i validació
    # _obte_text_node() respecta xml:space='preserve' amb text None
    text_complet = ''.join(
        ''.join(_obte_text_node(c) for c in run if c.tag == tag_t)
        for run in runs
    ).strip()

    if not text_complet or len(text_complet) < 3:
        return
    if re.match(r'^[\d\s\.\,\:\;\!\?\(\)\[\]\{\}\-\_\+\=\*\/\\]+$', text_complet):
        return

    # ── CAS SIMPLE: un sol format a tot el paràgraf ──────────────────────────
    if tots_runs_mateix_format(runs, tag_rpr):
        try:
            text_traduit = funcio_traduccio(text_complet)
            text_traduit = filtra_alucinacions(text_complet, text_traduit)
            text_traduit = neteja_traduccio_xml(text_traduit)
            text_traduit = normalitza_apostrofacions(text_traduit)

            if not text_traduit or text_traduit.strip() == text_complet:
                return

            t_primer = [c for c in runs[0] if c.tag == tag_t]
            if t_primer:
                t_primer[0].text = text_traduit
                t_primer[0].set(xml_space, 'preserve')
                for t in t_primer[1:]:
                    t.text = ''
                    if xml_space in t.attrib:
                        del t.attrib[xml_space]
            else:
                nou_t = etree.SubElement(runs[0], tag_t)
                nou_t.text = text_traduit
                nou_t.set(xml_space, 'preserve')

            # Buida els runs addicionals i neteja xml:space (conserva <w:rPr>)
            for run in runs[1:]:
                for t in run:
                    if t.tag == tag_t:
                        t.text = ''
                        if xml_space in t.attrib:
                            del t.attrib[xml_space]

        except Exception as e:
            log.warning(f'Error traduint paràgraf simple: {e!r}')
        return

    # ── CAS MIXT: segments de format homogeni ────────────────────────────────
    segments = agrupa_runs_per_format(runs, tag_rpr)

    for fmt_key, runs_segment in segments:
        # Text del segment (tots els runs concatenats)
        # _obte_text_node() respecta xml:space='preserve' amb text None
        text_segment = ''.join(
            ''.join(_obte_text_node(c) for c in run if c.tag == tag_t)
            for run in runs_segment
        )
        text_segment_net = text_segment.strip()

        if not text_segment_net or len(text_segment_net) < 2:
            continue

        # Salta segments purament simbòlics o d'una sola paraula
        if re.match(
            r'^[\d\s\.\,\:\;\!\?\(\)\[\]\{\}\-\_\+\=\*\/\\\u03a6]+$',
            text_segment_net,
        ):
            continue
        if len(text_segment_net.split()) < 2:
            continue

        try:
            text_traduit = funcio_traduccio(text_segment_net)
            text_traduit = filtra_alucinacions(text_segment_net, text_traduit)
            text_traduit = neteja_traduccio_xml(text_traduit)
            text_traduit = normalitza_apostrofacions(text_traduit)

            if not text_traduit or text_traduit.strip() == text_segment_net:
                continue

            # Distribueix les paraules de la traducció entre els runs del segment
            paraules   = text_traduit.split()
            longituds  = [
                max(len(''.join(_obte_text_node(c) for c in r if c.tag == tag_t)), 1)
                for r in runs_segment
            ]
            total_long = sum(longituds)
            total_par  = len(paraules)
            idx        = 0
            n_seg      = len(runs_segment)

            for i, (run, long) in enumerate(zip(runs_segment, longituds)):
                if i == n_seg - 1:
                    fragment = ' '.join(paraules[idx:])
                else:
                    n = max(1, round(total_par * long / total_long))
                    n = min(n, total_par - idx - (n_seg - i - 1))
                    n = max(n, 1)
                    fragment = ' '.join(paraules[idx:idx + n])
                    idx = min(idx + n, total_par)

                # Espai de separació entre runs adjacents del segment
                if i < n_seg - 1 and fragment and not fragment.endswith(' '):
                    fragment += ' '

                # Postprocessament del fragment individual
                fragment = normalitza_apostrofacions(fragment)

                t_nodes = [c for c in run if c.tag == tag_t]
                if t_nodes:
                    t_nodes[0].text = fragment
                    t_nodes[0].set(xml_space, 'preserve')
                    for t in t_nodes[1:]:
                        t.text = ''
                        if xml_space in t.attrib:
                            del t.attrib[xml_space]
                elif fragment.strip():
                    nou_t = etree.SubElement(run, tag_t)
                    nou_t.text = fragment
                    nou_t.set(xml_space, 'preserve')

        except Exception as e:
            log.warning(
                f'Error traduint segment {text_segment_net[:40]!r}: {e!r}'
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

    Retorna:
        contingut binari del fitxer traduït

    Estratègia (v6 — segments de format homogeni):
        1. Obre el ZIP en memòria
        2. Per a cada XML de contingut:
           a. Parseja el XML amb lxml
           b. Per a cada paràgraf (<w:p> o <a:p>):
              - Si és dins d'imatge/gràfic → IGNORA
              - Si el text té menys de 3 caràcters → IGNORA
              - Crida tradueix_i_preserva_format() (estratègia v6)
           c. Serialitza l'XML modificat
           d. Força l'idioma ca-ES
        3. Escriu tots els fitxers al ZIP de sortida
    """
    extensio = extensio.lower().lstrip('.')
    es_docx  = extensio == 'docx'
    es_pptx  = extensio == 'pptx'

    if not es_docx and not es_pptx:
        raise ValueError(f'Format no suportat: {extensio!r}. Usa "docx" o "pptx".')

    if es_docx:
        regex_fitxers = re.compile(
            r'^word/(document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$'
        )
    else:
        if tradueix_notes:
            regex_fitxers = re.compile(
                r'^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$'
            )
        else:
            regex_fitxers = re.compile(r'^ppt/slides/slide\d+\.xml$')

    ns_para  = NS_W if es_docx else NS_A
    ns_text  = NS_W if es_docx else NS_A
    tag_para = f'{{{ns_para}}}p'

    zip_entrada        = zipfile.ZipFile(io.BytesIO(contingut_original), 'r')
    zip_sortida_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_sortida_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_sortida:
        for nom_fitxer in zip_entrada.namelist():
            contingut = zip_entrada.read(nom_fitxer)

            if regex_fitxers.match(nom_fitxer):
                try:
                    arbre = etree.fromstring(contingut)

                    # ── Bucle principal: estratègia híbrida v6 ───────────────
                    for p_node in arbre.iter(tag_para):
                        if es_dins_imatge(p_node):
                            continue

                        # Omiteix paràgrafs amb fórmules/equacions matemàtiques
                        if _te_formula(p_node):
                            continue

                        text_complet = obte_text_paragraf(p_node, ns_text)
                        if not text_complet or len(text_complet.strip()) < 3:
                            continue

                        try:
                            tradueix_i_preserva_format(
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

            zip_sortida.writestr(nom_fitxer, contingut)

    zip_entrada.close()
    return zip_sortida_buffer.getvalue()
