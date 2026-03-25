// pptx-analyzer.js — Anàlisi estadística de fitxers PPTX al navegador
// Motor de Traducció Automàtica Neuronal castellà→valencià (TANEU)
// Servei de Llengües i Política Lingüística · Universitat de València
//
// Requereix JSZip (https://stuk.github.io/jszip/) carregat com a script global.

'use strict';

/**
 * Analitza un fitxer PPTX i retorna estadístiques de diapositives i paraules.
 *
 * @param {File} file  Fitxer PPTX seleccionat per l'usuari
 * @returns {Promise<{
 *   totalSlides: number,
 *   visible:     number,
 *   hidden:      number,
 *   withNotes:   number,
 *   totalWords:  number,
 *   slides:      Array<{path:string, isHidden:boolean, words:number, hasNotes:boolean}>
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
  let m;
  while ((m = relPattern.exec(presRelsXml)) !== null) {
    const [, id, target] = m;
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

    // Compta paraules del text de la diapositiva (text de l'àrea de presentació)
    const words = _countWordsInXml(slideXml);

    // Detecta notes: comprova el fitxer .rels de la diapositiva
    const hasNotes = await _detectaNotes(zip, slidePath);

    slides.push({ path: slidePath, isHidden, words, hasNotes });
  }

  // ── 4. Agrega estadístiques globals
  const totalSlides = slides.length;
  const visible     = slides.filter(s => !s.isHidden).length;
  const hidden      = slides.filter(s =>  s.isHidden).length;
  const withNotes   = slides.filter(s =>  s.hasNotes).length;
  const totalWords  = slides.reduce((acc, s) => acc + s.words, 0);

  return { totalSlides, visible, hidden, withNotes, totalWords, slides };
}

/**
 * Comprova si una diapositiva té notes amb contingut de text real.
 * Utilitza el fitxer .rels de la diapositiva per localitzar el notesSlide.
 *
 * @param {JSZip} zip
 * @param {string} slidePath  Ruta completa al ZIP (p.ex. 'ppt/slides/slide1.xml')
 * @returns {Promise<boolean>}
 */
async function _detectaNotes(zip, slidePath) {
  // Nom del fitxer de diapositiva sense directori (p.ex. 'slide1.xml')
  const slideName   = slidePath.split('/').pop();
  const notesRelsPath = `ppt/slides/_rels/${slideName}.rels`;

  const notesRelsFile = zip.file(notesRelsPath);
  if (!notesRelsFile) return false;

  const notesRelsXml = await notesRelsFile.async('text');

  // Busca una relació de tipus notesSlide
  const notesRelMatch = notesRelsXml.match(
    /Type="[^"]*\/notesSlide"[^>]*Target="([^"]+)"/
  );
  if (!notesRelMatch) return false;

  // Resol la ruta relativa del notesSlide respecte a la diapositiva
  const notesPath = _resolveRelPath(slidePath, notesRelMatch[1]);
  const notesFile = zip.file(notesPath);
  if (!notesFile) return false;

  const notesXml = await notesFile.async('text');

  // Comprova que hi ha text real a les notes (els números de pàgina automàtics
  // van dins <a:fld>, no dins <a:t>, de manera que no es compten aquí)
  const textNodes = notesXml.match(/<a:t[^>]*>([^<]+)<\/a:t>/g) || [];
  return textNodes.some(node => {
    const contingut = node.replace(/<[^>]+>/g, '').trim();
    return contingut.length > 0;
  });
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
 *
 * @param {{totalSlides:number, visible:number, hidden:number,
 *          withNotes:number, totalWords:number}} stats
 * @param {HTMLElement|string} container  Element DOM o ID de l'element contenidor
 * @param {string} filename  Nom del fitxer PPTX
 */
function renderPptxStats(stats, container, filename) {
  const el = typeof container === 'string'
    ? document.getElementById(container)
    : container;
  if (!el) return;

  const hiddenRow = stats.hidden > 0
    ? `<tr>
         <td class="pptx-stats-label">Diapositives ocultes</td>
         <td class="pptx-stats-value pptx-stats-hidden">${stats.hidden.toLocaleString('ca')}</td>
       </tr>`
    : '';

  const notesRow = stats.withNotes > 0
    ? `<tr>
         <td class="pptx-stats-label">Amb notes de presentació</td>
         <td class="pptx-stats-value">${stats.withNotes.toLocaleString('ca')}</td>
       </tr>`
    : '';

  el.innerHTML = `
    <div class="pptx-stats-card">
      <div class="pptx-stats-header">
        <span class="pptx-stats-icon">📊</span>
        <span class="pptx-stats-title">${_escapeHtml(filename)}</span>
      </div>
      <table class="pptx-stats-table">
        <tbody>
          <tr>
            <td class="pptx-stats-label">Diapositives totals</td>
            <td class="pptx-stats-value">${stats.totalSlides.toLocaleString('ca')}</td>
          </tr>
          <tr>
            <td class="pptx-stats-label">Diapositives visibles</td>
            <td class="pptx-stats-value pptx-stats-visible">${stats.visible.toLocaleString('ca')}</td>
          </tr>
          ${hiddenRow}
          ${notesRow}
          <tr class="pptx-stats-words-row">
            <td class="pptx-stats-label">Total de paraules</td>
            <td class="pptx-stats-value pptx-stats-words">${stats.totalWords.toLocaleString('ca')}</td>
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
