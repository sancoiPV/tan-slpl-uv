# -*- coding: utf-8 -*-
"""
corpus_builder.py
-----------------
Processa fitxers Word i PowerPoint paral·lels (_CAS/_VAL) i genera
un corpus d'entrenament i validació per al motor TAN SLPL·UV.

Ús:
  python corpus_builder.py --input <carpeta_corpus> --output <carpeta_sortida>

Arguments:
  --input   Carpeta amb fitxers _CAS.docx, _VAL.docx, _CAS.pptx, _VAL.pptx
  --output  Carpeta on es desaran els fitxers resultants

Fitxers generats a --output:
  train.es        Frases castellà d'entrenament (90%)
  train.ca        Frases valencià d'entrenament (90%)
  val.es          Frases castellà de validació (10%)
  val.ca          Frases valencià de validació (10%)
  corpus_net.tsv  Tots els parells vàlids en format TSV per a revisió
  informe.txt     Resum del processament

Dependències: python-docx, python-pptx, nltk
"""

import argparse
import logging
import random
import re
import sys
from pathlib import Path

# ── Dependències opcionals amb missatge d'error clar ──────────────────────────
try:
    from docx import Document as DocxDocument
except ImportError:
    sys.exit('[ERROR] python-docx no instal·lat. Executa: pip install python-docx')

try:
    from pptx import Presentation
except ImportError:
    sys.exit('[ERROR] python-pptx no instal·lat. Executa: pip install python-pptx')

try:
    import nltk
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', quiet=True)
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    from nltk.tokenize import sent_tokenize
    _NLTK_OK = True
except ImportError:
    _NLTK_OK = False

# ── Configuració del logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Extracció de text
# ═══════════════════════════════════════════════════════════════════════════════

def extrau_paragrafs_docx(path: Path) -> list[str]:
    """Retorna la llista de paràgrafs no buits d'un fitxer .docx."""
    doc = DocxDocument(path)
    paragrafs = []
    # Cos principal
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragrafs.append(text)
    # Taules
    for taula in doc.tables:
        for fila in taula.rows:
            for cel in fila.cells:
                for para in cel.paragraphs:
                    text = para.text.strip()
                    if text:
                        paragrafs.append(text)
    return paragrafs


def extrau_paragrafs_pptx(path: Path) -> list[str]:
    """Retorna la llista de paràgrafs no buits d'un fitxer .pptx."""
    prs = Presentation(path)
    paragrafs = []
    for diapositiva in prs.slides:
        for forma in diapositiva.shapes:
            if not forma.has_text_frame:
                continue
            for para in forma.text_frame.paragraphs:
                text = para.text.strip()
                if text:
                    paragrafs.append(text)
    return paragrafs


def segmenta_frases(text: str, llengua: str = 'spanish') -> list[str]:
    """
    Segmenta un text en frases individuals.
    Usa nltk si disponible; si no, divideix per punts/salts de línia.
    """
    if _NLTK_OK:
        try:
            frases = sent_tokenize(text, language=llengua)
            return [f.strip() for f in frases if f.strip()]
        except Exception:
            pass
    # Fallback: divideix per punts finals i salts de línia
    frases = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [f.strip() for f in frases if f.strip()]


# ═══════════════════════════════════════════════════════════════════════════════
# Neteja i validació de parells
# ═══════════════════════════════════════════════════════════════════════════════

def es_valid(src: str, tgt: str, min_tok: int = 3, max_tok: int = 120) -> bool:
    """
    Comprova si un parell és vàlid per al corpus.
    Filtra frases massa curtes, massa llargues, idèntiques o poc alfabètiques.
    """
    s_tok = src.split()
    t_tok = tgt.split()
    if not (min_tok <= len(s_tok) <= max_tok):
        return False
    if not (min_tok <= len(t_tok) <= max_tok):
        return False
    if src.lower() == tgt.lower():
        return False
    # Mínim 40% de caràcters alfabètics (filtra taules de números, codis, etc.)
    if sum(c.isalpha() for c in src) / max(len(src), 1) < 0.4:
        return False
    if sum(c.isalpha() for c in tgt) / max(len(tgt), 1) < 0.4:
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Processament de parells de fitxers
# ═══════════════════════════════════════════════════════════════════════════════

def processa_parell_docx(path_cas: Path, path_val: Path) -> list[tuple[str, str]]:
    """Extreu i alinea les frases d'un parell de fitxers .docx."""
    paragrafs_es = extrau_paragrafs_docx(path_cas)
    paragrafs_ca = extrau_paragrafs_docx(path_val)

    parells = []
    n_min = min(len(paragrafs_es), len(paragrafs_ca))
    if len(paragrafs_es) != len(paragrafs_ca):
        log.warning(
            '  ⚠ Nombre de paràgrafs diferent: %s (%d) vs %s (%d). '
            'S\'usaran els primers %d.',
            path_cas.name, len(paragrafs_es),
            path_val.name, len(paragrafs_ca),
            n_min,
        )

    for es_text, ca_text in zip(paragrafs_es[:n_min], paragrafs_ca[:n_min]):
        # Segmenta en frases si el paràgraf és llarg (> 150 caràcters)
        if len(es_text) > 150 or len(ca_text) > 150:
            frases_es = segmenta_frases(es_text, 'spanish')
            frases_ca = segmenta_frases(ca_text, 'catalan')
            for f_es, f_ca in zip(frases_es, frases_ca):
                parells.append((f_es, f_ca))
        else:
            parells.append((es_text, ca_text))

    return parells


def processa_parell_pptx(path_cas: Path, path_val: Path) -> list[tuple[str, str]]:
    """Extreu i alinea les frases d'un parell de fitxers .pptx."""
    paragrafs_es = extrau_paragrafs_pptx(path_cas)
    paragrafs_ca = extrau_paragrafs_pptx(path_val)

    parells = []
    n_min = min(len(paragrafs_es), len(paragrafs_ca))
    if len(paragrafs_es) != len(paragrafs_ca):
        log.warning(
            '  ⚠ Nombre de paràgrafs diferent: %s (%d) vs %s (%d). '
            'S\'usaran els primers %d.',
            path_cas.name, len(paragrafs_es),
            path_val.name, len(paragrafs_ca),
            n_min,
        )

    for es_text, ca_text in zip(paragrafs_es[:n_min], paragrafs_ca[:n_min]):
        if len(es_text) > 150 or len(ca_text) > 150:
            frases_es = segmenta_frases(es_text, 'spanish')
            frases_ca = segmenta_frases(ca_text, 'catalan')
            for f_es, f_ca in zip(frases_es, frases_ca):
                parells.append((f_es, f_ca))
        else:
            parells.append((es_text, ca_text))

    return parells


# ═══════════════════════════════════════════════════════════════════════════════
# Funció principal
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Genera corpus TAN des de fitxers _CAS/_VAL (docx/pptx)',
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
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        sys.exit(f'[ERROR] La carpeta d\'entrada no existeix: {input_dir}')

    output_dir.mkdir(parents=True, exist_ok=True)
    log.info('Carpeta entrada:  %s', input_dir)
    log.info('Carpeta sortida:  %s', output_dir)

    # ── Cerca tots els fitxers _CAS ────────────────────────────────────────────
    fitxers_cas_docx = sorted(input_dir.glob('**/*_CAS.docx'))
    fitxers_cas_pptx = sorted(input_dir.glob('**/*_CAS.pptx'))

    total_fitxers   = 0
    total_extrets   = 0
    total_eliminats = 0
    registre_fitxers = []  # Per a l'informe

    all_pairs = []

    # ── Processa fitxers DOCX ──────────────────────────────────────────────────
    for path_cas in fitxers_cas_docx:
        path_val = path_cas.parent / path_cas.name.replace('_CAS', '_VAL')
        if not path_val.exists():
            log.warning('No s\'ha trobat el fitxer VAL per a: %s', path_cas.name)
            continue
        log.info('DOCX: %s + %s', path_cas.name, path_val.name)
        try:
            parells = processa_parell_docx(path_cas, path_val)
            all_pairs.extend(parells)
            log.info('  → %d parells extrets', len(parells))
            total_fitxers += 2
            total_extrets += len(parells)
            registre_fitxers.append(
                f'DOCX  {path_cas.name} + {path_val.name}  →  {len(parells)} parells'
            )
        except Exception as exc:
            log.error('Error processant %s: %s', path_cas.name, exc)

    # ── Processa fitxers PPTX ──────────────────────────────────────────────────
    for path_cas in fitxers_cas_pptx:
        path_val = path_cas.parent / path_cas.name.replace('_CAS', '_VAL')
        if not path_val.exists():
            log.warning('No s\'ha trobat el fitxer VAL per a: %s', path_cas.name)
            continue
        log.info('PPTX: %s + %s', path_cas.name, path_val.name)
        try:
            parells = processa_parell_pptx(path_cas, path_val)
            all_pairs.extend(parells)
            log.info('  → %d parells extrets', len(parells))
            total_fitxers += 2
            total_extrets += len(parells)
            registre_fitxers.append(
                f'PPTX  {path_cas.name} + {path_val.name}  →  {len(parells)} parells'
            )
        except Exception as exc:
            log.error('Error processant %s: %s', path_cas.name, exc)

    if total_fitxers == 0:
        log.warning('No s\'ha trobat cap parell _CAS/_VAL a: %s', input_dir)

    # ── Neteja i deduplicació ──────────────────────────────────────────────────
    clean_pairs = []
    seen = set()
    for src, tgt in all_pairs:
        src, tgt = src.strip(), tgt.strip()
        if not es_valid(src, tgt):
            total_eliminats += 1
            continue
        clau = f'{src.lower()}|||{tgt.lower()}'
        if clau in seen:
            total_eliminats += 1
            continue
        seen.add(clau)
        clean_pairs.append((src, tgt))

    total_valid = len(clean_pairs)

    # ── Divisió train/val ──────────────────────────────────────────────────────
    random.seed(42)
    random.shuffle(clean_pairs)
    tall = int(len(clean_pairs) * 0.9)
    train_pairs = clean_pairs[:tall]
    val_pairs   = clean_pairs[tall:]

    # ── Guardat dels fitxers de sortida ───────────────────────────────────────
    def escriu_parells(pairs: list, prefix: str) -> None:
        path_es = output_dir / f'{prefix}.es'
        path_ca = output_dir / f'{prefix}.ca'
        with open(path_es, 'w', encoding='utf-8') as fe, \
             open(path_ca, 'w', encoding='utf-8') as fc:
            for src, tgt in pairs:
                fe.write(src + '\n')
                fc.write(tgt + '\n')

    escriu_parells(train_pairs, 'train')
    escriu_parells(val_pairs, 'val')

    # Fitxer TSV complet per a revisió
    tsv_path = output_dir / 'corpus_net.tsv'
    with open(tsv_path, 'w', encoding='utf-8') as f:
        f.write('castellà\tvalencià\n')
        for src, tgt in clean_pairs:
            f.write(f'{src}\t{tgt}\n')

    # ── Informe de processament ────────────────────────────────────────────────
    informe_lines = [
        '=' * 55,
        '  INFORME DE PROCESSAMENT — corpus_builder.py',
        '  Servei de Llengües i Política Lingüística · UV',
        '=' * 55,
        '',
        f'  Carpeta entrada:  {input_dir}',
        f'  Carpeta sortida:  {output_dir}',
        '',
        '  FITXERS PROCESSATS:',
    ]
    for linia in registre_fitxers:
        informe_lines.append(f'    {linia}')
    if not registre_fitxers:
        informe_lines.append('    (cap fitxer processat)')
    informe_lines += [
        '',
        '  ESTADÍSTIQUES:',
        f'    Fitxers processats:  {total_fitxers}',
        f'    Parells extrets:     {total_extrets}',
        f'    Parells eliminats:   {total_eliminats}',
        f'    Parells vàlids:      {total_valid}',
        f'    Parells train (90%): {len(train_pairs)}',
        f'    Parells val   (10%): {len(val_pairs)}',
        '',
        '  FITXERS GENERATS:',
        f'    train.es / train.ca  ({len(train_pairs)} parells)',
        f'    val.es   / val.ca    ({len(val_pairs)} parells)',
        f'    corpus_net.tsv       ({total_valid} parells + capçalera)',
        '',
    ]
    if total_valid < 500:
        informe_lines += [
            '  ⚠ ADVERTÈNCIA: corpus molt petit (< 500 parells).',
            '    Recomana acumular més textos abans de fer l\'afinament.',
            '',
        ]
    informe_lines.append('=' * 55)

    informe_text = '\n'.join(informe_lines)
    informe_path = output_dir / 'informe.txt'
    with open(informe_path, 'w', encoding='utf-8') as f:
        f.write(informe_text + '\n')

    # ── Mostra resum per consola ───────────────────────────────────────────────
    print()
    print(informe_text)
    print()
    log.info('Fitxers desats a: %s', output_dir)

    if total_valid < 500:
        sys.exit(1)


if __name__ == '__main__':
    main()
