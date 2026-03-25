// pptx-analyzer.js — Anàlisi estadística de fitxers PPTX al navegador
// Motor de Traducció Automàtica Neuronal castellà→valencià (TANEU)
// Servei de Llengües i Política Lingüística · Universitat de València
//
// Requereix JSZip (https://stuk.github.io/jszip/) carregat com a script global.

'use strict';

/**
 * Analitza un fitxer PPTX i retorna estadístiques detallades de diapositives i paraules.
 * Les paraules de les notes del presentador s'inclouen en el total global.
 *
 * @param {File} file  Fitxer PPTX seleccionat per l'usuari
 * @returns {Promise<{
 *   totalSlides: number,
 *   totalWords:  number,   // diapositives + notes
 *   visible: { count, words, withNotes, withNotesWords },
 *   hidden:  { count, words, withNotes, withNotesWords },
 *   notes:   { count, words },
 *   slides:  Array<{path, isHidden, slideWords, noteWords, hasNotes}>
 * }>}
 */
async function analyzePptx(file) {
  const zip = await JSZip.loadAsync(file);

  // ── 1. Llegeix presentation.xml: obté la llista ordenada de rIds de diapositives
  const presFile = zip.file('ppt/presentation.xml');
  if (!presFile) throw new Error('No s\'ha trobat ppt/presentation.xml al fitxer PPTX.');
  const presXml = await presFile.async('text');

  // Extreu els rIds de <p:sldId r:id="rIdN"/> dins de <p:sldIdLst>
  const rIds = [];
  const sldIdLstMatch = presXml.match(/<p:sldIdLst\b[^>]*>([\s\S]*?)<\/p:sldIdLst>/);
  if (sldIdLstMatch) {
    const rIdPattern = /r:id="(rId\d+)"/g;
    let m;
    while ((m = rIdPattern.exec(sldIdLstMatch[1])) !== null) {
      rIds.push(m[1]);
    }
  }

  // ── 2. Llegeix presentation.xml.rels: mapeja rId → ruta de diapositiva (relativa a ppt/)
  const presRelsFile = zip.file('ppt/_rels/presentation.xml.rels');
  if (!presRelsFile) throw new Error('No s\'ha trobat ppt/_rels/presentation.xml.rels al fitxer PPTX.');
  const presRelsXml = await presRelsFile.async('text');

  const rIdToPath = {};
  const relPattern = /Id="(rId\d+)"[^>]*Target="([^"]+)"/g;
  let rm;
  while ((rm = relPattern.exec(presRelsXml)) !== null) {
    const [, id, target] = rm;
    // Filtra únicament diapositives (exclou slideMaster, slideLayout, etc.)
    if (/slides\/slide\d+\.xml$/.test(target)) {
      // Target és relatiu a ppt/; convertim a ruta completa al ZIP
      rIdToPath[id] = target.startsWith('ppt/') ? target : 'ppt/' + target;
    }
  }

  // ── 3. Processa cada diapositiva en ordre
  const slides = [];
  for (const rId of rIds) {
    const slidePath = rIdToPath[rId];
    if (!slidePath) continue;

    const slideFile = zip.file(slidePath);
    if (!slideFile) continue;

    const slideXml = await slideFile.async('text');

    // Detecta si la diapositiva és oculta: atribut show="0" a l'element arrel <p:sld>
    const rootTagMatch = slideXml.match(/<p:sld\b([^>]*)>/);
    const isHidden = rootTagMatch ? /\bshow="0"/.test(rootTagMatch[1]) : false;

    // Compta paraules del text de la diapositiva (àrea de presentació)
    const slideWords = _countWordsInXml(slideXml);

    // Obté paraules de les notes i si existeixen amb contingut real
    const { hasNotes, noteWords } = await _obteNotesInfo(zip, slidePath);

    slides.push({ path: slidePath, isHidden, slideWords, noteWords, hasNotes });
  }

  // ── 4. Agrupa per visibles / ocultes
  const visibleSlides = slides.filter(s => !s.isHidden);
  const hiddenSlides  = slides.filter(s =>  s.isHidden);

  // ── 5. Agrega estadístiques globals
  return {
    totalSlides: slides.length,
    totalWords: slides.reduce((sum, s) => sum + s.slideWords + s.noteWords, 0),
    visible: {
      count:          visibleSlides.length,
      words:          visibleSlides.reduce((sum, s) => sum + s.slideWords, 0),
      withNotes:      visibleSlides.filter(s => s.hasNotes).length,
      withNotesWords: visibleSlides.filter(s => s.hasNotes).reduce((sum, s) => sum + s.slideWords, 0)
    },
    hidden: {
      count:          hiddenSlides.length,
      words:          hiddenSlides.reduce((sum, s) => sum + s.slideWords, 0),
      withNotes:      hiddenSlides.filter(s => s.hasNotes).length,
      withNotesWords: hiddenSlides.filter(s => s.hasNotes).reduce((sum, s) => sum + s.slideWords, 0)
    },
    notes: {
      count: slides.filter(s => s.hasNotes).length,
      words: slides.reduce((sum, s) => sum + s.noteWords, 0)
    },
    slides
  };
}

/**
 * Obté informació de les notes d'una diapositiva: si existeixen i quantes paraules contenen.
 * Utilitza el fitxer .rels de la diapositiva per localitzar el notesSlide.
 *
 * @param {JSZip} zip
 * @param {string} slidePath  Ruta completa al ZIP (p.ex. 'ppt/slides/slide1.xml')
 * @returns {Promise<{hasNotes: boolean, noteWords: number}>}
 */
async function _obteNotesInfo(zip, slidePath) {
  const slideName     = slidePath.split('/').pop();
  const notesRelsPath = `ppt/slides/_rels/${slideName}.rels`;

  const notesRelsFile = zip.file(notesRelsPath);
  if (!notesRelsFile) return { hasNotes: false, noteWords: 0 };

  const notesRelsXml = await notesRelsFile.async('text');

  // Busca una relació de tipus notesSlide
  const notesRelMatch = notesRelsXml.match(
    /Type="[^"]*\/notesSlide"[^>]*Target="([^"]+)"/
  );
  if (!notesRelMatch) return { hasNotes: false, noteWords: 0 };

  // Resol la ruta relativa del notesSlide respecte a la diapositiva
  const notesPath = _resolveRelPath(slidePath, notesRelMatch[1]);
  const notesFile = zip.file(notesPath);
  if (!notesFile) return { hasNotes: false, noteWords: 0 };

  const notesXml = await notesFile.async('text');

  // Extreu text de les notes (els números de pàgina automàtics van dins <a:fld>,
  // no dins <a:t>, de manera que no s'inclouen en el recompte)
  const notesText = _extractTextFromXml(notesXml).trim();
  if (!notesText) return { hasNotes: false, noteWords: 0 };

  const noteWords = countWords(notesText);
  return { hasNotes: noteWords > 0, noteWords };
}

/**
 * Resol una ruta relativa respecte a la ruta base d'un fitxer dins el ZIP.
 * Segueix la convenció OPC (Open Packaging Convention).
 *
 * Exemple:
 *   _resolveRelPath('ppt/slides/slide1.xml', '../notesSlides/notesSlide1.xml')
 *   → 'ppt/notesSlides/notesSlide1.xml'
 *
 * @param {string} basePath   Ruta absoluta del fitxer de referència
 * @param {string} relTarget  Target relatiu del fitxer .rels
 * @returns {string}
 */
function _resolveRelPath(basePath, relTarget) {
  const parts = basePath.split('/');
  parts.pop(); // Elimina el nom del fitxer base, deixa el directori
  const relParts = relTarget.split('/');
  for (const part of relParts) {
    if (part === '..') {
      parts.pop();
    } else if (part !== '.') {
      parts.push(part);
    }
  }
  return parts.join('/');
}

/**
 * Extreu text pla dels elements <a:t> d'un XML OOXML.
 *
 * @param {string} xmlStr
 * @returns {string}
 */
function _extractTextFromXml(xmlStr) {
  const matches = xmlStr.match(/<a:t[^>]*>([^<]*)<\/a:t>/g) || [];
  return matches.map(node => node.replace(/<[^>]+>/g, '')).join(' ');
}

/**
 * Compta les paraules del text contingut en un fragment d'XML OOXML.
 *
 * @param {string} xmlStr
 * @returns {number}
 */
function _countWordsInXml(xmlStr) {
  return countWords(_extractTextFromXml(xmlStr));
}

/**
 * Compta les paraules d'un text pla dividint per espais en blanc.
 *
 * @param {string} text
 * @returns {number}
 */
function countWords(text) {
  if (!text || !text.trim()) return 0;
  return text.trim().split(/\s+/).filter(t => t.length > 0).length;
}

/**
 * Renderitza una taula d'estadístiques PPTX dins el contenidor indicat.
 * Format:
 *   Secció                             | Diapositives | Paraules
 *   Diapositives no ocultes            |     68       |  2.835
 *   — de les quals amb notes           |     65       |  2.690
 *   Diapositives ocultes               |     16       |    683
 *   — de les quals amb notes           |     14       |    655
 *   Notes a peu de diapositiva (total) |     79       | 10.688
 *   TOTAL                              |     84       | 14.206
 *
 * @param {{totalSlides, totalWords, visible, hidden, notes}} stats
 * @param {HTMLElement|string} container  Element DOM o ID de l'element contenidor
 * @param {string} filename  Nom del fitxer PPTX
 */
function renderPptxStats(stats, container, filename) {
  const el = typeof container === 'string'
    ? document.getElementById(container)
    : container;
  if (!el) return;

  const fmt = n => n.toLocaleString('ca-ES');

  // Files de diapositives ocultes (s'oculten si no n'hi ha cap)
  const hiddenRows = stats.hidden.count > 0 ? `
          <tr>
            <td>Diapositives ocultes</td>
            <td style="text-align:center;">${fmt(stats.hidden.count)}</td>
            <td style="text-align:center;">${fmt(stats.hidden.words)}</td>
          </tr>
          <tr>
            <td style="padding-left:1.4em; font-style:italic; color:#555;">
              — de les quals amb notes
            </td>
            <td style="text-align:center;">${fmt(stats.hidden.withNotes)}</td>
            <td style="text-align:center;">${fmt(stats.hidden.withNotesWords)}</td>
          </tr>` : '';

  el.innerHTML = `
    <div class="pptx-stats-card">
      <div class="pptx-stats-header">
        <span class="pptx-stats-icon">📊</span>
        <span class="pptx-stats-title">${_escapeHtml(filename)}</span>
        <span class="pptx-stats-total-badge">${fmt(stats.totalSlides)} diapositives</span>
      </div>
      <table class="pptx-stats-table">
        <thead>
          <tr>
            <th>Secció</th>
            <th style="text-align:center;">Diapositives</th>
            <th style="text-align:center;">Paraules</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Diapositives no ocultes</td>
            <td style="text-align:center;">${fmt(stats.visible.count)}</td>
            <td style="text-align:center;">${fmt(stats.visible.words)}</td>
          </tr>
          <tr>
            <td style="padding-left:1.4em; font-style:italic; color:#555;">
              — de les quals amb notes
            </td>
            <td style="text-align:center;">${fmt(stats.visible.withNotes)}</td>
            <td style="text-align:center;">${fmt(stats.visible.withNotesWords)}</td>
          </tr>
          ${hiddenRows}
          <tr>
            <td>Notes a peu de diapositiva (total)</td>
            <td style="text-align:center;">${fmt(stats.notes.count)}</td>
            <td style="text-align:center;">${fmt(stats.notes.words)}</td>
          </tr>
          <tr class="pptx-stats-total-row">
            <td><strong>TOTAL</strong></td>
            <td style="text-align:center;"><strong>${fmt(stats.totalSlides)}</strong></td>
            <td style="text-align:center;"><strong>${fmt(stats.totalWords)}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>`;

  el.style.display = 'block';
}

/**
 * Escapa caràcters especials HTML per evitar XSS.
 * @param {string} str
 * @returns {string}
 */
function _escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
