# -*- coding: utf-8 -*-
"""
Editor de documents amb preservació de format.

Classes per a editar documents .docx i .pptx substituint NOMÉS el text
dins dels elements XML <w:t> (docx) i <a:t> (pptx), preservant íntegrament
el format original (fonts, mides, negreta, cursiva, estils de paràgraf,
imatges, taules, capçaleres, peus de pàgina, etc.).

Estratègia:
1. Descomprimir el fitxer ZIP (docx/pptx són arxius ZIP)
2. Analitzar els XML interns (document.xml, slides, etc.)
3. Extraure text per paràgrafs (agrupant runs)
4. Substituir text redistribuint-lo en els runs originals
5. Opcionalment afegir ressaltat groc (w:highlight) per a correccions
6. Reempaquetar el ZIP preservant tots els altres fitxers
"""

import copy
import io
import os
import re
import zipfile
from datetime import datetime
from typing import Optional
from lxml import etree

# Espais de noms XML per a OOXML
DOCX_NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
}

PPTX_NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
}


class DocxFormatPreservingEditor:
    """
    Editor de documents DOCX que preserva el format original.

    Treballa directament sobre l'XML intern del document, substituint
    NOMÉS el text dins dels elements <w:t>, sense tocar <w:rPr> (format)
    ni cap altre element estructural.
    """

    def __init__(self, fitxer_entrada: str | bytes | io.BytesIO):
        """
        Carrega un fitxer DOCX.

        Args:
            fitxer_entrada: ruta al fitxer, bytes o objecte BytesIO
        """
        if isinstance(fitxer_entrada, str):
            with open(fitxer_entrada, 'rb') as f:
                self._zip_bytes = f.read()
        elif isinstance(fitxer_entrada, bytes):
            self._zip_bytes = fitxer_entrada
        else:
            self._zip_bytes = fitxer_entrada.read()

        self._zip = zipfile.ZipFile(io.BytesIO(self._zip_bytes), 'r')
        self._fitxers_xml = {}  # nom_fitxer -> etree.Element
        self._fitxers_modificats = set()

        # Carregar document.xml (cos principal)
        self._carrega_xml('word/document.xml')

        # Carregar capçaleres i peus de pàgina
        for nom in self._zip.namelist():
            if nom.startswith('word/header') or nom.startswith('word/footer'):
                if nom.endswith('.xml'):
                    self._carrega_xml(nom)

    def _carrega_xml(self, nom_fitxer: str):
        """Carrega i analitza un fitxer XML del ZIP."""
        try:
            contingut = self._zip.read(nom_fitxer)
            arbre = etree.fromstring(contingut)
            self._fitxers_xml[nom_fitxer] = arbre
        except (KeyError, etree.XMLSyntaxError):
            pass

    def extrau_paragrafs(self) -> list[dict]:
        """
        Extrau tots els paràgrafs del document amb el seu text complet.

        Retorna:
            Llista de dicts amb:
            - 'index': índex del paràgraf
            - 'text': text complet del paràgraf (concatenació de tots els runs)
            - 'fitxer': nom del fitxer XML d'origen
            - 'xpath': identificador per a localitzar el paràgraf
        """
        paragrafs = []
        idx = 0

        for nom_fitxer, arbre in self._fitxers_xml.items():
            for p in arbre.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                text = self._extrau_text_paragraf(p)
                if text.strip():  # Ignorar paràgrafs buits
                    paragrafs.append({
                        'index': idx,
                        'text': text,
                        'fitxer': nom_fitxer,
                        '_element': p,  # Referència interna
                    })
                    idx += 1

        return paragrafs

    def _extrau_text_paragraf(self, element_p) -> str:
        """Extrau el text complet d'un paràgraf (<w:p>) concatenant tots els <w:t>."""
        textos = []
        ns_w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for r in element_p.iter(f'{ns_w}r'):
            for t in r.iter(f'{ns_w}t'):
                if t.text:
                    textos.append(t.text)
        return ''.join(textos)

    def substitueix_paragraf(self, paragraf: dict, text_nou: str,
                             ressaltar: bool = False):
        """
        Substitueix el text d'un paràgraf redistribuint-lo en els runs originals.

        Estratègia:
        - Si el paràgraf té un sol run: posar tot el text nou en eixe run
        - Si en té diversos: posar tot el text en el primer run i buidar els altres
        - MAI eliminar runs (per preservar <w:rPr>)
        - Opcionalment afegir ressaltat groc a tots els runs modificats

        Args:
            paragraf: dict retornat per extrau_paragrafs()
            text_nou: text de substitució
            ressaltar: si True, afegeix ressaltat groc (w:highlight)
        """
        element_p = paragraf['_element']
        ns_w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

        runs = list(element_p.iter(f'{ns_w}r'))
        if not runs:
            return

        primer_run_amb_text = True
        for r in runs:
            ts = list(r.iter(f'{ns_w}t'))
            for t in ts:
                if primer_run_amb_text and t.text is not None:
                    t.text = text_nou
                    # Preservar espais
                    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                    primer_run_amb_text = False
                elif t.text is not None:
                    t.text = ''
                    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

            # Afegir ressaltat groc si cal
            if ressaltar:
                self._afegeix_ressaltat(r, ns_w)

        self._fitxers_modificats.add(paragraf['fitxer'])

    def substitueix_text_global(self, text_original: str, text_nou: str,
                                 ressaltar: bool = False) -> int:
        """
        Cerca i substitueix un text exacte en tot el document.

        Treballa a nivell de paràgraf: si el text_original coincideix
        amb el text complet d'un paràgraf, el substitueix.
        Si és una subcadena, fa la substitució dins del paràgraf.

        Retorna el nombre de substitucions fetes.
        """
        count = 0
        for p_info in self.extrau_paragrafs():
            if text_original in p_info['text']:
                text_modificat = p_info['text'].replace(text_original, text_nou, 1)
                self.substitueix_paragraf(p_info, text_modificat, ressaltar=ressaltar)
                count += 1
        return count

    def _afegeix_ressaltat(self, element_run, ns_w: str, color: str = 'yellow'):
        """Afegeix ressaltat (<w:highlight>) a un run."""
        rpr = element_run.find(f'{ns_w}rPr')
        if rpr is None:
            rpr = etree.SubElement(element_run, f'{ns_w}rPr')
            # Inserir-lo com a primer fill del run
            element_run.insert(0, rpr)

        # Comprovar si ja té ressaltat
        highlight = rpr.find(f'{ns_w}highlight')
        if highlight is None:
            highlight = etree.SubElement(rpr, f'{ns_w}highlight')
        highlight.set(f'{ns_w}val', color)

    def estableix_llengua(self, codi_llengua: str):
        """
        Estableix la llengua predeterminada de tot el document .docx.

        Args:
            codi_llengua: 'ca-ES' per a català/valencià, 'en-GB' per a anglés britànic, etc.

        Modifica:
        1. w:lang als estils predeterminats (styles.xml)
        2. w:lang a les propietats del document (settings.xml)
        3. w:lang de cada run i paràgraf individual al document.xml
        """
        W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

        # Determinar eastAsia associat
        east_asia = codi_llengua
        if codi_llengua.startswith('ca'):
            east_asia = 'ca-ES'
        elif codi_llengua.startswith('en'):
            east_asia = 'en-GB'

        # 1. Canvia en styles.xml (estils predeterminats)
        try:
            zip_in = zipfile.ZipFile(io.BytesIO(self._zip_bytes), 'r')
            styles_xml_bytes = zip_in.read('word/styles.xml')
            styles_root = etree.fromstring(styles_xml_bytes)
            for lang_el in styles_root.iter(f'{W}lang'):
                lang_el.set(f'{W}val', codi_llengua)
                lang_el.set(f'{W}eastAsia', east_asia)
            self._fitxers_xml['word/styles.xml'] = styles_root
            self._fitxers_modificats.add('word/styles.xml')
            zip_in.close()
        except (KeyError, etree.XMLSyntaxError):
            pass

        # 2. Canvia en settings.xml
        try:
            zip_in = zipfile.ZipFile(io.BytesIO(self._zip_bytes), 'r')
            settings_xml_bytes = zip_in.read('word/settings.xml')
            settings_root = etree.fromstring(settings_xml_bytes)
            for lang_el in settings_root.iter(f'{W}lang'):
                lang_el.set(f'{W}val', codi_llengua)
            self._fitxers_xml['word/settings.xml'] = settings_root
            self._fitxers_modificats.add('word/settings.xml')
            zip_in.close()
        except (KeyError, etree.XMLSyntaxError):
            pass

        # 3. Canvia en cada paràgraf i run del document.xml (i capçaleres/peus)
        for nom_fitxer, arbre in self._fitxers_xml.items():
            if not nom_fitxer.startswith('word/'):
                continue
            modificat = False
            for p in arbre.iter(f'{W}p'):
                # Propietats del paràgraf
                pPr = p.find(f'{W}pPr')
                if pPr is not None:
                    rPr = pPr.find(f'{W}rPr')
                    if rPr is not None:
                        for lang_el in rPr.findall(f'{W}lang'):
                            lang_el.set(f'{W}val', codi_llengua)
                            modificat = True
                # Cada run
                for r in p.findall(f'{W}r'):
                    rPr = r.find(f'{W}rPr')
                    if rPr is not None:
                        lang_els = rPr.findall(f'{W}lang')
                        if lang_els:
                            for lang_el in lang_els:
                                lang_el.set(f'{W}val', codi_llengua)
                                modificat = True
                        else:
                            lang_el = etree.SubElement(rPr, f'{W}lang')
                            lang_el.set(f'{W}val', codi_llengua)
                            modificat = True
            if modificat:
                self._fitxers_modificats.add(nom_fitxer)

    # ── Suport per a comentaris DOCX ────────────────────────────────────────

    def _inicialitza_comentaris(self):
        """Crea la infraestructura XML per a comentaris si no existeix."""
        if hasattr(self, '_comentaris_inicialitzats') and self._comentaris_inicialitzats:
            return

        ns_w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        ns_r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

        # Crear word/comments.xml si no existeix
        if 'word/comments.xml' not in self._fitxers_xml:
            comments_xml = etree.Element(
                f'{{{ns_w}}}comments',
                nsmap={'w': ns_w, 'r': ns_r},
            )
            self._fitxers_xml['word/comments.xml'] = comments_xml
            self._fitxers_modificats.add('word/comments.xml')

        self._comment_id_counter = 0
        self._comentaris_inicialitzats = True
        self._cal_afegir_comments_xml = True

    def ressalta_paragraf(self, paragraf: dict, color: str = 'yellow'):
        """Ressalta un paràgraf sencer en groc SENSE substituir el text."""
        element_p = paragraf['_element']
        ns_w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

        for r in element_p.iter(f'{ns_w}r'):
            self._afegeix_ressaltat(r, ns_w, color)

        self._fitxers_modificats.add(paragraf['fitxer'])

    def afegeix_comentari(self, paragraf: dict, text_comentari: str,
                           autor: str = 'Claude Sonnet'):
        """
        Afegeix un comentari de Word a un paràgraf.

        Crea un commentRangeStart/End al voltant del paràgraf i
        afig el comentari a word/comments.xml.
        """
        self._inicialitza_comentaris()

        ns_w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        ns_w_brace = f'{{{ns_w}}}'
        comment_id = str(self._comment_id_counter)
        self._comment_id_counter += 1

        element_p = paragraf['_element']

        # 1. Crear el comentari en word/comments.xml
        comments_root = self._fitxers_xml['word/comments.xml']
        comment_el = etree.SubElement(comments_root, f'{ns_w_brace}comment')
        comment_el.set(f'{ns_w_brace}id', comment_id)
        comment_el.set(f'{ns_w_brace}author', autor)
        comment_el.set(f'{ns_w_brace}initials', 'CS')
        comment_el.set(f'{ns_w_brace}date',
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + 'Z')

        # Paràgraf dins del comentari
        comment_p = etree.SubElement(comment_el, f'{ns_w_brace}p')
        comment_r = etree.SubElement(comment_p, f'{ns_w_brace}r')
        comment_rpr = etree.SubElement(comment_r, f'{ns_w_brace}rPr')
        comment_sz = etree.SubElement(comment_rpr, f'{ns_w_brace}sz')
        comment_sz.set(f'{ns_w_brace}val', '18')
        comment_t = etree.SubElement(comment_r, f'{ns_w_brace}t')
        comment_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        comment_t.text = text_comentari

        # 2. Inserir commentRangeStart COM A PRIMER FILL del paràgraf
        range_start = etree.Element(f'{ns_w_brace}commentRangeStart')
        range_start.set(f'{ns_w_brace}id', comment_id)
        element_p.insert(0, range_start)

        # 3. Inserir commentRangeEnd COM A ÚLTIM FILL del paràgraf
        range_end = etree.SubElement(element_p, f'{ns_w_brace}commentRangeEnd')
        range_end.set(f'{ns_w_brace}id', comment_id)

        # 4. Inserir un run amb commentReference al final del paràgraf
        ref_run = etree.SubElement(element_p, f'{ns_w_brace}r')
        ref_rpr = etree.SubElement(ref_run, f'{ns_w_brace}rPr')
        ref_style = etree.SubElement(ref_rpr, f'{ns_w_brace}rStyle')
        ref_style.set(f'{ns_w_brace}val', 'CommentReference')
        ref_ref = etree.SubElement(ref_run, f'{ns_w_brace}commentReference')
        ref_ref.set(f'{ns_w_brace}id', comment_id)

        self._fitxers_modificats.add(paragraf['fitxer'])
        self._fitxers_modificats.add('word/comments.xml')

    def desa(self, fitxer_sortida: str | io.BytesIO = None) -> bytes:
        """
        Desa el document modificat.
        Si s'han afegit comentaris, actualitza [Content_Types].xml i rels.
        """
        buffer_sortida = io.BytesIO()

        with zipfile.ZipFile(io.BytesIO(self._zip_bytes), 'r') as zip_original:
            with zipfile.ZipFile(buffer_sortida, 'w', zipfile.ZIP_DEFLATED) as zip_nou:
                noms_processats = set()

                for item in zip_original.infolist():
                    nom = item.filename

                    if nom in self._fitxers_xml and nom in self._fitxers_modificats:
                        xml_bytes = etree.tostring(
                            self._fitxers_xml[nom],
                            xml_declaration=True,
                            encoding='UTF-8',
                            standalone=True,
                        )
                        zip_nou.writestr(item, xml_bytes)
                    elif (hasattr(self, '_cal_afegir_comments_xml')
                          and self._cal_afegir_comments_xml
                          and nom == '[Content_Types].xml'):
                        # Afegir l'Override per a comments.xml
                        ct_bytes = zip_original.read(nom)
                        ct_root = etree.fromstring(ct_bytes)
                        ct_ns = ct_root.nsmap.get(None, 'http://schemas.openxmlformats.org/package/2006/content-types')

                        # Comprovar si ja existeix
                        ja_existeix = False
                        for override in ct_root:
                            if override.get('PartName') == '/word/comments.xml':
                                ja_existeix = True
                                break
                        if not ja_existeix:
                            override_el = etree.SubElement(ct_root, f'{{{ct_ns}}}Override')
                            override_el.set('PartName', '/word/comments.xml')
                            override_el.set('ContentType',
                                'application/vnd.openxmlformats-officedocument'
                                '.wordprocessingml.comments+xml')
                        zip_nou.writestr(item, etree.tostring(ct_root, xml_declaration=True,
                                                               encoding='UTF-8', standalone=True))
                    elif (hasattr(self, '_cal_afegir_comments_xml')
                          and self._cal_afegir_comments_xml
                          and nom == 'word/_rels/document.xml.rels'):
                        # Afegir la relació de comentaris
                        rels_bytes = zip_original.read(nom)
                        rels_root = etree.fromstring(rels_bytes)
                        rels_ns = rels_root.nsmap.get(None,
                            'http://schemas.openxmlformats.org/package/2006/relationships')
                        comments_type = ('http://schemas.openxmlformats.org/officeDocument'
                                         '/2006/relationships/comments')

                        ja_existeix = False
                        for rel in rels_root:
                            if rel.get('Type') == comments_type:
                                ja_existeix = True
                                break
                        if not ja_existeix:
                            rel_el = etree.SubElement(rels_root, f'{{{rels_ns}}}Relationship')
                            rel_el.set('Id', 'rIdCommentsAuto')
                            rel_el.set('Type', comments_type)
                            rel_el.set('Target', 'comments.xml')
                        zip_nou.writestr(item, etree.tostring(rels_root, xml_declaration=True,
                                                               encoding='UTF-8', standalone=True))
                    else:
                        zip_nou.writestr(item, zip_original.read(nom))
                    noms_processats.add(nom)

                # Afegir word/comments.xml si és nou (no existia al ZIP original)
                if (hasattr(self, '_cal_afegir_comments_xml')
                    and self._cal_afegir_comments_xml
                    and 'word/comments.xml' not in noms_processats
                    and 'word/comments.xml' in self._fitxers_xml):
                    xml_bytes = etree.tostring(
                        self._fitxers_xml['word/comments.xml'],
                        xml_declaration=True,
                        encoding='UTF-8',
                        standalone=True,
                    )
                    zip_nou.writestr('word/comments.xml', xml_bytes)

        resultat = buffer_sortida.getvalue()

        if fitxer_sortida:
            if isinstance(fitxer_sortida, str):
                with open(fitxer_sortida, 'wb') as f:
                    f.write(resultat)
            else:
                fitxer_sortida.write(resultat)

        return resultat

    def tanca(self):
        """Tanca el fitxer ZIP."""
        self._zip.close()


class PptxFormatPreservingEditor:
    """
    Editor de presentacions PPTX que preserva el format original.

    Treballa sobre l'XML intern de cada diapositiva, substituint
    NOMÉS el text dins dels elements <a:t>, sense tocar <a:rPr> (format)
    ni cap altre element estructural (imatges, formes, gràfics, etc.).
    """

    def __init__(self, fitxer_entrada: str | bytes | io.BytesIO):
        """
        Carrega un fitxer PPTX.

        Args:
            fitxer_entrada: ruta al fitxer, bytes o objecte BytesIO
        """
        if isinstance(fitxer_entrada, str):
            with open(fitxer_entrada, 'rb') as f:
                self._zip_bytes = f.read()
        elif isinstance(fitxer_entrada, bytes):
            self._zip_bytes = fitxer_entrada
        else:
            self._zip_bytes = fitxer_entrada.read()

        self._zip = zipfile.ZipFile(io.BytesIO(self._zip_bytes), 'r')
        self._fitxers_xml = {}
        self._fitxers_modificats = set()

        # Carregar totes les diapositives
        for nom in sorted(self._zip.namelist()):
            if re.match(r'ppt/slides/slide\d+\.xml$', nom):
                self._carrega_xml(nom)
            # Carregar també notes de diapositives
            elif re.match(r'ppt/notesSlides/notesSlide\d+\.xml$', nom):
                self._carrega_xml(nom)

    def _carrega_xml(self, nom_fitxer: str):
        """Carrega i analitza un fitxer XML del ZIP."""
        try:
            contingut = self._zip.read(nom_fitxer)
            arbre = etree.fromstring(contingut)
            self._fitxers_xml[nom_fitxer] = arbre
        except (KeyError, etree.XMLSyntaxError):
            pass

    def extrau_paragrafs(self) -> list[dict]:
        """
        Extrau tots els paràgrafs de totes les diapositives.

        Retorna:
            Llista de dicts amb:
            - 'index': índex global del paràgraf
            - 'text': text complet del paràgraf
            - 'fitxer': nom del fitxer XML d'origen (slide)
            - 'diapositiva': número de diapositiva (1-indexed)
        """
        paragrafs = []
        idx = 0
        ns_a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'

        for nom_fitxer in sorted(self._fitxers_xml.keys()):
            if 'notesSlides' in nom_fitxer:
                continue

            arbre = self._fitxers_xml[nom_fitxer]
            # Extraure número de diapositiva
            match = re.search(r'slide(\d+)\.xml$', nom_fitxer)
            num_diap = int(match.group(1)) if match else 0

            for p in arbre.iter(f'{ns_a}p'):
                text = self._extrau_text_paragraf(p, ns_a)
                if text.strip():
                    paragrafs.append({
                        'index': idx,
                        'text': text,
                        'fitxer': nom_fitxer,
                        'diapositiva': num_diap,
                        '_element': p,
                    })
                    idx += 1

        return paragrafs

    def _extrau_text_paragraf(self, element_p, ns_a: str) -> str:
        """Extrau el text complet d'un paràgraf (<a:p>) concatenant tots els <a:t>."""
        textos = []
        for r in element_p.iter(f'{ns_a}r'):
            for t in r.iter(f'{ns_a}t'):
                if t.text:
                    textos.append(t.text)
        return ''.join(textos)

    def substitueix_paragraf(self, paragraf: dict, text_nou: str):
        """
        Substitueix el text d'un paràgraf redistribuint-lo en els runs originals.

        Estratègia equivalent a la de DOCX però amb espai de noms DrawingML:
        - Tot el text en el primer run amb text, buidar els altres
        - MAI eliminar runs

        Args:
            paragraf: dict retornat per extrau_paragrafs()
            text_nou: text de substitució
        """
        element_p = paragraf['_element']
        ns_a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'

        runs = list(element_p.iter(f'{ns_a}r'))
        if not runs:
            return

        primer_run_amb_text = True
        for r in runs:
            ts = list(r.iter(f'{ns_a}t'))
            for t in ts:
                if primer_run_amb_text and t.text is not None:
                    t.text = text_nou
                    primer_run_amb_text = False
                elif t.text is not None:
                    t.text = ''

        self._fitxers_modificats.add(paragraf['fitxer'])

    def substitueix_text_global(self, text_original: str, text_nou: str) -> int:
        """
        Cerca i substitueix un text exacte en totes les diapositives.

        Retorna el nombre de substitucions fetes.
        """
        count = 0
        for p_info in self.extrau_paragrafs():
            if text_original in p_info['text']:
                text_modificat = p_info['text'].replace(text_original, text_nou, 1)
                self.substitueix_paragraf(p_info, text_modificat)
                count += 1
        return count

    def desa(self, fitxer_sortida: str | io.BytesIO = None) -> bytes:
        """
        Desa la presentació modificada.

        Args:
            fitxer_sortida: ruta de sortida o objecte BytesIO (opcional)

        Retorna:
            bytes del fitxer ZIP resultant
        """
        buffer_sortida = io.BytesIO()

        with zipfile.ZipFile(io.BytesIO(self._zip_bytes), 'r') as zip_original:
            with zipfile.ZipFile(buffer_sortida, 'w', zipfile.ZIP_DEFLATED) as zip_nou:
                for item in zip_original.infolist():
                    if item.filename in self._fitxers_xml and item.filename in self._fitxers_modificats:
                        xml_bytes = etree.tostring(
                            self._fitxers_xml[item.filename],
                            xml_declaration=True,
                            encoding='UTF-8',
                            standalone=True
                        )
                        zip_nou.writestr(item, xml_bytes)
                    else:
                        zip_nou.writestr(item, zip_original.read(item.filename))

        resultat = buffer_sortida.getvalue()

        if fitxer_sortida:
            if isinstance(fitxer_sortida, str):
                with open(fitxer_sortida, 'wb') as f:
                    f.write(resultat)
            else:
                fitxer_sortida.write(resultat)

        return resultat

    def estableix_llengua(self, codi_llengua: str):
        """
        Estableix la llengua predeterminada de tot el document .pptx.

        Args:
            codi_llengua: 'ca-ES' per a català/valencià, 'en-GB' per a anglés britànic, etc.

        En PPTX, la llengua s'estableix a l'atribut 'lang' dels elements <a:rPr>
        (run properties) dins de cada diapositiva.
        """
        A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'

        for nom_fitxer, arbre in self._fitxers_xml.items():
            modificat = False
            # Canvia tots els <a:rPr> (propietats de run)
            for rPr in arbre.iter(f'{A_NS}rPr'):
                rPr.set('lang', codi_llengua)
                modificat = True
            # Canvia tots els <a:defRPr> (propietats per defecte)
            for defRPr in arbre.iter(f'{A_NS}defRPr'):
                defRPr.set('lang', codi_llengua)
                modificat = True
            if modificat:
                self._fitxers_modificats.add(nom_fitxer)

    def tanca(self):
        """Tanca el fitxer ZIP."""
        self._zip.close()


def processa_document_traduccio(fitxer_bytes: bytes, extensio: str,
                                  funcio_traduccio, **kwargs) -> bytes:
    """
    Funció d'alt nivell: tradueix/corregeix un document preservant format.

    Args:
        fitxer_bytes: contingut del fitxer en bytes
        extensio: 'docx' o 'pptx'
        funcio_traduccio: callable que rep un text i retorna el text traduït/corregit
        **kwargs: arguments addicionals per a funcio_traduccio

    Retorna:
        bytes del document processat
    """
    if extensio.lower() == 'docx':
        editor = DocxFormatPreservingEditor(fitxer_bytes)
    elif extensio.lower() == 'pptx':
        editor = PptxFormatPreservingEditor(fitxer_bytes)
    else:
        raise ValueError(f"Extensió no suportada: {extensio}")

    try:
        paragrafs = editor.extrau_paragrafs()

        # Agrupar paràgrafs en lots per eficiència
        textos_originals = [p['text'] for p in paragrafs]

        # Traduir/corregir tots els textos
        textos_traduits = funcio_traduccio(textos_originals, **kwargs)

        # Substituir cada paràgraf
        for p, text_nou in zip(paragrafs, textos_traduits):
            if text_nou and text_nou != p['text']:
                ressaltar = kwargs.get('ressaltar', False) and extensio.lower() == 'docx'
                if extensio.lower() == 'docx':
                    editor.substitueix_paragraf(p, text_nou, ressaltar=ressaltar)
                else:
                    editor.substitueix_paragraf(p, text_nou)

        return editor.desa()
    finally:
        editor.tanca()


def processa_document_correccio(fitxer_bytes: bytes, extensio: str,
                                  correccions: list[dict]) -> bytes:
    """
    Aplica correccions a un document preservant format i afegint ressaltat groc.

    Args:
        fitxer_bytes: contingut del fitxer en bytes
        extensio: 'docx' o 'pptx'
        correccions: llista de dicts amb 'original' i 'correccio'

    Retorna:
        bytes del document processat amb correccions ressaltades
    """
    if extensio.lower() == 'docx':
        editor = DocxFormatPreservingEditor(fitxer_bytes)
    elif extensio.lower() == 'pptx':
        editor = PptxFormatPreservingEditor(fitxer_bytes)
    else:
        raise ValueError(f"Extensió no suportada: {extensio}")

    try:
        for correccio in correccions:
            original = correccio.get('original', '')
            corregit = correccio.get('correccio', correccio.get('corregit', ''))
            if original and corregit and original != corregit:
                ressaltar = extensio.lower() == 'docx'
                if extensio.lower() == 'docx':
                    editor.substitueix_text_global(original, corregit, ressaltar=ressaltar)
                else:
                    editor.substitueix_text_global(original, corregit)

        return editor.desa()
    finally:
        editor.tanca()


def processa_document_revisio(fitxer_bytes: bytes, extensio: str,
                                correccions: list[dict]) -> bytes:
    """
    Processa un document en mode REVISIÓ: ressalta en groc els fragments
    amb errors i afegeix comentaris de Word amb la proposta de correcció
    i la justificació normativa. NO substitueix el text original.

    Només disponible per a DOCX (els PPTX no admeten comentaris nativament).

    Args:
        fitxer_bytes: contingut del fitxer DOCX en bytes
        extensio: 'docx' (obligatori; pptx no suportat per a comentaris)
        correccions: llista de dicts amb 'paragraf' (§N), 'original',
                     'correccio', 'categoria', 'justificacio'

    Retorna:
        bytes del document DOCX amb ressaltat groc i comentaris
    """
    if extensio.lower() != 'docx':
        # Per a PPTX, fallback a correcció directa (no suporta comentaris)
        return processa_document_correccio(fitxer_bytes, extensio, correccions)

    editor = DocxFormatPreservingEditor(fitxer_bytes)

    try:
        paragrafs = editor.extrau_paragrafs()

        # Crear un mapa de correccions per paràgraf (§N → llista de correccions)
        correccions_per_paragraf = {}
        for c in correccions:
            ref = c.get('paragraf', '')
            # Extraure el número de paràgraf de "§N"
            match = re.search(r'§(\d+)', ref)
            if match:
                idx = int(match.group(1)) - 1  # 0-indexed
                correccions_per_paragraf.setdefault(idx, []).append(c)
            else:
                # Fallback: cercar per text original en tots els paràgrafs
                original = c.get('original', '')
                if original:
                    for p in paragrafs:
                        if original in p['text']:
                            correccions_per_paragraf.setdefault(
                                p['index'], []
                            ).append(c)
                            break

        # Aplicar ressaltat i comentaris a cada paràgraf afectat
        for p in paragrafs:
            idx = p['index']
            if idx not in correccions_per_paragraf:
                continue

            cors = correccions_per_paragraf[idx]

            # Ressaltar el paràgraf en groc
            editor.ressalta_paragraf(p, color='yellow')

            # Construir el text del comentari amb totes les correccions
            # d'aquest paràgraf
            linies_comentari = []
            for i, c in enumerate(cors, 1):
                cat = c.get('categoria', 'ORTO')
                original = c.get('original', '')
                correccio_text = c.get('correccio', c.get('corregit', ''))
                justificacio = c.get('justificacio', '')

                linia = f"[{cat}] \u00ab{original}\u00bb \u2192 \u00ab{correccio_text}\u00bb"
                if justificacio:
                    linia += f" \u2014 {justificacio}"
                linies_comentari.append(linia)

            text_comentari = "; ".join(linies_comentari)
            editor.afegeix_comentari(p, text_comentari, autor='Claude Sonnet')

        return editor.desa()
    finally:
        editor.tanca()
