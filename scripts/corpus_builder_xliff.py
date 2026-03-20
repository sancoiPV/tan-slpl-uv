# -*- coding: utf-8 -*-
"""
corpus_builder_xliff.py
=======================
Pipeline professional de preparació del corpus d'entrenament basat en XLIFF.

Flux de treball:
1. Per a cada parell _CAS/_VAL:
   a. Usa Tikal per convertir _CAS.docx/_CAS.pptx → _CAS.docx.xlf
   b. Usa Tikal per convertir _VAL.docx/_VAL.pptx → _VAL.docx.xlf
   c. Extreu segments de _CAS.xlf (source) i _VAL.xlf (target)
   d. Alinea per id de segment (alineació perfecta garantida)
2. Neteja i deduplicació dels parells
3. Divisió train/val i exportació

Requeriments:
- Okapi Framework Tikal instal·lat a tools/tikal/
- Java 11+ instal·lat i accessible al PATH

Ús:
  python scripts/corpus_builder_xliff.py
      --input "corpus d'entrenament i afinament"
      --output "corpus d'entrenament i afinament/processed"
      --tikal tools/tikal/tikal.cmd
      --max-delta 999
      --min-similitud 0.10

Fitxers generats a --output:
  train.es            Frases castellà d'entrenament (90%)
  train.ca            Frases valencià d'entrenament (90%)
  val.es              Frases castellà de validació (10%)
  val.ca              Frases valencià de validació (10%)
  corpus_net.tsv      Tots els parells vàlids en format TSV per a revisió
  informe_xliff.txt   Resum del processament
"""

import argparse
import csv
import logging
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

# ── Configuració del logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)

# ── Namespaces XLIFF ──────────────────────────────────────────────────────────
XLIFF_NS = 'urn:oasis:names:tc:xliff:document:1.2'
ET.register_namespace('', XLIFF_NS)


# ═══════════════════════════════════════════════════════════════════════════════
# Conversió de documents a XLIFF via Tikal
# ═══════════════════════════════════════════════════════════════════════════════

def converteix_a_xliff(
    path_document: Path,
    path_xliff_desti: Path,
    tikal_cmd: str,
) -> bool:
    """
    Converteix un document DOCX o PPTX a XLIFF usant Tikal.

    Comportament real de Tikal: desa el XLIFF al MATEIX directori que
    el document original, amb el nom: document.docx.xlf
    (no usa -od; el fitxer generat es copia a path_xliff_desti).

    Retorna True si la conversió i la còpia han tingut èxit.
    """
    cmd = [
        tikal_cmd,
        '-x', str(path_document),
        '-sl', 'es',   # llengua font: castellà
        '-tl', 'ca',   # llengua destí: català/valencià
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Tikal desa el XLIFF al directori del document original
        # amb el nom: document.docx.xlf
        xliff_generat = path_document.parent / (path_document.name + '.xlf')

        if not xliff_generat.exists():
            log.warning(
                'Tikal no ha generat el XLIFF per a %s: %s',
                path_document.name,
                result.stderr[:300],
            )
            return False

        # Copia el XLIFF al directori de treball temporal
        shutil.copy2(xliff_generat, path_xliff_desti)

        # Elimina el XLIFF original per no deixar fitxers al corpus
        xliff_generat.unlink()

        return True

    except subprocess.TimeoutExpired:
        log.warning('Tikal timeout per a %s', path_document.name)
        return False
    except Exception as e:
        log.warning('Error executant Tikal per a %s: %r', path_document.name, e)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Extracció de segments XLIFF
# ═══════════════════════════════════════════════════════════════════════════════

def _text_net(element) -> str:
    """
    Extreu el text pla d'un element XML eliminant TOTES les etiquetes inline.
    Gestiona etiquetes XLIFF inline: <g>, <x/>, <bx/>, <ex/>, <ph>, <it>,
    i qualsevol altra etiqueta XML que Tikal puga generar (<run1>, <tags1/>, etc.)
    """
    # Serialitza l'element a text amb totes les etiquetes incloses
    try:
        raw = ET.tostring(element, encoding='unicode', method='xml')
    except Exception:
        return (element.text or '').strip()

    # Elimina TOTES les etiquetes XML (obertes, tancades i autotancades)
    text = re.sub(r'<[^>]+>', '', raw)

    # Descodifica entitats HTML/XML residuals
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&apos;', "'")
    text = text.replace('&#160;', ' ')

    # Normalitza espais múltiples
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def extrau_segments_xliff(path_xliff: Path) -> dict[str, str]:
    """
    Extreu els segments source d'un fitxer XLIFF 1.2.
    Retorna un diccionari {id_segment: text_source}.
    """
    segments: dict[str, str] = {}
    try:
        arbre = ET.parse(path_xliff)
        arrel = arbre.getroot()
        ns = {'xliff': XLIFF_NS}
        for trans_unit in arrel.findall('.//xliff:trans-unit', ns):
            seg_id = trans_unit.get('id', '')
            if not seg_id:
                continue
            source = trans_unit.find('xliff:source', ns)
            if source is not None:
                text = _text_net(source)
                if text:
                    segments[seg_id] = text
    except ET.ParseError as e:
        log.warning('Error parsejant %s: %r', path_xliff.name, e)
    return segments


def extrau_traduccions_xliff(path_xliff: Path) -> dict[str, str]:
    """
    Extreu les traduccions target d'un fitxer XLIFF 1.2.
    Retorna un diccionari {id_segment: text_target}.
    Si un segment no té target, usa el source com a fallback.
    """
    segments: dict[str, str] = {}
    try:
        arbre = ET.parse(path_xliff)
        arrel = arbre.getroot()
        ns = {'xliff': XLIFF_NS}
        for trans_unit in arrel.findall('.//xliff:trans-unit', ns):
            seg_id = trans_unit.get('id', '')
            if not seg_id:
                continue
            target = trans_unit.find('xliff:target', ns)
            if target is not None:
                text = _text_net(target)
                if text:
                    segments[seg_id] = text
            else:
                # Fallback: usa source si no hi ha target
                source = trans_unit.find('xliff:source', ns)
                if source is not None:
                    text = _text_net(source)
                    if text:
                        segments[seg_id] = text
    except ET.ParseError as e:
        log.warning('Error parsejant %s: %r', path_xliff.name, e)
    return segments


def alinea_xliffs(
    path_xliff_cas: Path,
    path_xliff_val: Path,
) -> list[tuple[str, str]]:
    """
    Alinea els segments de dos fitxers XLIFF per id de segment.

    Garantia d'alineació perfecta: Tikal assigna el mateix id als
    segments homòlegs de la versió font (_CAS) i la versió traduïda (_VAL).
    No hi ha alineació per posició ni risc de desplaçament.

    Retorna una llista de parells (text_castellà, text_valencià) alineats.
    """
    segments_cas = extrau_segments_xliff(path_xliff_cas)
    segments_val = extrau_traduccions_xliff(path_xliff_val)

    ids_comuns = set(segments_cas.keys()) & set(segments_val.keys())
    log.debug(
        'IDs CAS=%d  VAL=%d  comuns=%d',
        len(segments_cas), len(segments_val), len(ids_comuns),
    )

    # Ordena els ids numèricament si és possible, lexicogràficament si no
    def clau_ordre(seg_id: str):
        try:
            return (0, int(seg_id))
        except ValueError:
            return (1, seg_id)

    parells = []
    for seg_id in sorted(ids_comuns, key=clau_ordre):
        src = segments_cas[seg_id]
        tgt = segments_val[seg_id]
        if src and tgt:
            parells.append((src, tgt))

    return parells


# ═══════════════════════════════════════════════════════════════════════════════
# Filtre de qualitat dels parells
# ═══════════════════════════════════════════════════════════════════════════════

def similitud_bigrames(text1: str, text2: str) -> float:
    """
    Similitud de Jaccard basada en bigrames de caràcters.
    Retorna un valor entre 0 (cap similitud) i 1 (idèntics).
    """
    def bigrames(text: str) -> set[str]:
        t = text.lower().strip()
        return set(t[i:i+2] for i in range(len(t) - 1))

    bg1 = bigrames(text1)
    bg2 = bigrames(text2)
    if not bg1 or not bg2:
        return 0.0
    interseccio = len(bg1 & bg2)
    unio = len(bg1 | bg2)
    return interseccio / unio if unio > 0 else 0.0


def es_valid(
    src: str,
    tgt: str,
    min_tok: int = 3,
    max_tok: int = 200,
    min_similitud: float = 0.10,
) -> bool:
    """
    Comprova si un parell és vàlid per al corpus d'entrenament.
    Filtra segments massa curts, massa llargs, idèntics, poc alfabètics
    o amb baixa similitud de bigrames (probable mal alineament ES/CA).
    """
    s_tok = src.split()
    t_tok = tgt.split()
    if not (min_tok <= len(s_tok) <= max_tok):
        return False
    if not (min_tok <= len(t_tok) <= max_tok):
        return False
    if src.strip() == tgt.strip():
        return False
    # Mínim 40% de caràcters alfabètics
    if sum(c.isalpha() for c in src) / max(len(src), 1) < 0.4:
        return False
    if sum(c.isalpha() for c in tgt) / max(len(tgt), 1) < 0.4:
        return False
    # Filtre de similitud bigrames ES/CA
    if similitud_bigrames(src, tgt) < min_similitud:
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Funció principal
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Genera corpus paral·lel ES→CA via XLIFF + Okapi Tikal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--input', required=True,
        help='Carpeta amb fitxers _CAS.docx/_VAL.docx i _CAS.pptx/_VAL.pptx',
    )
    parser.add_argument(
        '--output', required=True,
        help='Carpeta on es desaran els fitxers resultants',
    )
    parser.add_argument(
        '--tikal', default='tools/tikal/tikal.cmd',
        help='Ruta a l\'executable Tikal (defecte: tools/tikal/tikal.cmd)',
    )
    parser.add_argument(
        '--max-delta', type=int, default=999, dest='max_delta',
        help='No s\'usa per a XLIFF (alineació per id), conservat per compatibilitat',
    )
    parser.add_argument(
        '--min-similitud', type=float, default=0.10, dest='min_similitud',
        help='Similitud mínima de bigrames ES/CA (defecte: 0.10)',
    )
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output)
    tikal_cmd  = str(Path(args.tikal).resolve())

    if not input_dir.exists():
        import sys
        sys.exit(f'[ERROR] La carpeta d\'entrada no existeix: {input_dir}')

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Verifica Tikal ─────────────────────────────────────────────────────────
    if not Path(tikal_cmd).exists():
        log.error('Tikal no trobat a: %s', tikal_cmd)
        log.error('Executa: powershell scripts\\instala_tikal.ps1')
        return

    log.info('Tikal:            %s ✓', tikal_cmd)
    log.info('Carpeta entrada:  %s', input_dir)
    log.info('Carpeta sortida:  %s', output_dir)
    log.info('Min similitud:    %.2f', args.min_similitud)

    # ── Cerca parells _CAS/_VAL ────────────────────────────────────────────────
    parells_fitxers: list[tuple[Path, Path]] = []
    for ext in ('docx', 'pptx'):
        for cas_path in sorted(input_dir.glob(f'**/*_CAS.{ext}')):
            val_path = cas_path.parent / cas_path.name.replace('_CAS', '_VAL')
            if val_path.exists():
                parells_fitxers.append((cas_path, val_path))
            else:
                log.warning('No s\'ha trobat el fitxer VAL per a: %s', cas_path.name)

    log.info('Parells trobats:  %d', len(parells_fitxers))

    if not parells_fitxers:
        log.warning('Cap parell _CAS/_VAL a: %s', input_dir)
        return

    # ── Processa cada parell via XLIFF temporal ────────────────────────────────
    all_pairs: list[tuple[str, str]] = []
    fitxers_ok    = 0
    fitxers_error = 0
    registre: list[str] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        for i, (cas_path, val_path) in enumerate(parells_fitxers, 1):
            log.info('[%d/%d] %s', i, len(parells_fitxers), cas_path.name)

            # Noms XLIFF temporals (extensió .xlf, igual que Tikal genera)
            xliff_cas = tmp_path / (cas_path.stem + '_CAS.xlf')
            xliff_val = tmp_path / (val_path.stem + '_VAL.xlf')

            # Converteix CAS → XLIFF
            if not converteix_a_xliff(cas_path, xliff_cas, tikal_cmd):
                log.warning('  ✗ Conversió fallida: %s', cas_path.name)
                fitxers_error += 1
                registre.append(f'ERROR  {cas_path.name}  (conversió CAS fallida)')
                continue

            # Converteix VAL → XLIFF
            if not converteix_a_xliff(val_path, xliff_val, tikal_cmd):
                log.warning('  ✗ Conversió fallida: %s', val_path.name)
                fitxers_error += 1
                registre.append(f'ERROR  {val_path.name}  (conversió VAL fallida)')
                continue

            # Alinea per id de segment
            pairs = alinea_xliffs(xliff_cas, xliff_val)
            log.info('  ✓ %d parells extrets', len(pairs))
            all_pairs.extend(pairs)
            fitxers_ok += 1
            registre.append(
                f'OK     {cas_path.name} + {val_path.name}  →  {len(pairs)} parells'
            )

    # ── Neteja i deduplicació ──────────────────────────────────────────────────
    clean_pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    eliminats_qualitat   = 0
    eliminats_duplicats  = 0
    eliminats_similitud  = 0

    for src, tgt in all_pairs:
        src, tgt = src.strip(), tgt.strip()
        # Comptabilitza específicament els eliminats pel filtre de similitud
        if (
            es_valid(src, tgt, min_similitud=0.0)
            and similitud_bigrames(src, tgt) < args.min_similitud
        ):
            eliminats_similitud += 1
        if not es_valid(src, tgt, min_similitud=args.min_similitud):
            eliminats_qualitat += 1
            continue
        clau = f'{src.lower()}|||{tgt.lower()}'
        if clau in seen:
            eliminats_duplicats += 1
            continue
        seen.add(clau)
        clean_pairs.append((src, tgt))

    # ── Divisió train/val (90%/10%) ────────────────────────────────────────────
    random.seed(42)
    random.shuffle(clean_pairs)
    tall        = int(len(clean_pairs) * 0.9)
    train_pairs = clean_pairs[:tall]
    val_pairs   = clean_pairs[tall:]

    # ── Guardat dels fitxers de sortida ───────────────────────────────────────
    def escriu_columna(path: Path, linies: list[str]) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            for linia in linies:
                f.write(linia + '\n')

    escriu_columna(output_dir / 'train.es', [s for s, _ in train_pairs])
    escriu_columna(output_dir / 'train.ca', [t for _, t in train_pairs])
    escriu_columna(output_dir / 'val.es',   [s for s, _ in val_pairs])
    escriu_columna(output_dir / 'val.ca',   [t for _, t in val_pairs])

    tsv_path = output_dir / 'corpus_net.tsv'
    with open(tsv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['castellà', 'valencià'])
        writer.writerows(clean_pairs)

    # ── Informe ────────────────────────────────────────────────────────────────
    informe_lines = [
        '=' * 55,
        '  INFORME DE PROCESSAMENT — corpus_builder_xliff.py',
        '  Servei de Llengües i Política Lingüística · UV',
        '  Pipeline: Okapi Framework Tikal + XLIFF',
        '=' * 55,
        '',
        f'  Carpeta entrada:    {input_dir}',
        f'  Carpeta sortida:    {output_dir}',
        f'  Tikal:              {tikal_cmd}',
        f'  Min similitud:      {args.min_similitud:.2f}',
        '',
        '  FITXERS PROCESSATS:',
    ]
    for linia in registre:
        informe_lines.append(f'    {linia}')
    if not registre:
        informe_lines.append('    (cap fitxer processat)')

    informe_lines += [
        '',
        '  ESTADÍSTIQUES:',
        f'    Parells de fitxers trobats: {len(parells_fitxers)}',
        f'    Fitxers processats amb èxit:{fitxers_ok}',
        f'    Fitxers amb error:          {fitxers_error}',
        f'    Parells extrets (total):    {len(all_pairs)}',
        f'    Eliminats (qualitat):       {eliminats_qualitat}',
        f'      (baixa similitud):        {eliminats_similitud}',
        f'    Eliminats (duplicats):      {eliminats_duplicats}',
        f'    Parells vàlids:             {len(clean_pairs)}',
        f'    Parells train (90%):        {len(train_pairs)}',
        f'    Parells val   (10%):        {len(val_pairs)}',
        '',
        '  FITXERS GENERATS:',
        f'    train.es / train.ca         ({len(train_pairs)} parells)',
        f'    val.es   / val.ca           ({len(val_pairs)} parells)',
        f'    corpus_net.tsv              ({len(clean_pairs)} parells + capçalera)',
        f'    informe_xliff.txt',
        '',
    ]

    if len(clean_pairs) < 500:
        informe_lines += [
            '  ⚠ ADVERTÈNCIA: corpus molt petit (< 500 parells).',
            '    Afegiu més documents al corpus abans de l\'afinament.',
            '',
        ]

    informe_lines.append('=' * 55)
    informe_text = '\n'.join(informe_lines)

    with open(output_dir / 'informe_xliff.txt', 'w', encoding='utf-8') as f:
        f.write(informe_text + '\n')

    print()
    print(informe_text)
    print()
    log.info('Fitxers desats a: %s', output_dir)


if __name__ == '__main__':
    main()
