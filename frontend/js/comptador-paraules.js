/**
 * comptador-paraules.js
 * Recompte de paraules client-side per a fitxers .docx i .rtf
 * Projecte TANEU · Servei de Llengües i Política Lingüística · UV
 */

'use strict';

/**
 * Compta les paraules d'una cadena de text plana.
 * Divideix per espais en blanc i filtra tokens buits.
 * @param {string} text
 * @returns {number}
 */
function contarParaulesText(text) {
  if (!text || !text.trim()) return 0;
  return text.trim().split(/\s+/).filter(Boolean).length;
}

/**
 * Extrau tot el text d'un fitxer .docx a partir dels elements <w:t>
 * de word/document.xml (no inclou capçaleres, peus de pàgina ni notes).
 * Requereix JSZip carregat globalment.
 * @param {File} file
 * @returns {Promise<string>}
 */
async function _extrauTextDocx(file) {
  const zip = await JSZip.loadAsync(file);

  const docFile = zip.file('word/document.xml');
  if (!docFile) {
    throw new Error('No s\'ha trobat word/document.xml al fitxer .docx');
  }

  const xmlStr = await docFile.async('text');

  // Usem l'espai de noms W per obtenir els nodes <w:t> amb text real
  const NS_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlStr, 'application/xml');

  if (doc.querySelector('parsererror')) {
    throw new Error('Error analitzant word/document.xml');
  }

  const tNodes = doc.getElementsByTagNameNS(NS_W, 't');
  return Array.from(tNodes).map(n => n.textContent).join(' ');
}

/**
 * Extrau el text pla d'un fitxer .rtf eliminant el marcatge RTF:
 *   - Grups de destinació oculta {\*\keyword ...}
 *   - Codis de caràcter hexadecimal \'xx
 *   - Paraules de control \keyword i paràmetres
 *   - Claus {}
 * @param {File} file
 * @returns {Promise<string>}
 */
async function _extrauTextRtf(file) {
  const raw = await file.text();

  let text = raw
    // Elimina grups de destinació oculta ({\*\...})
    .replace(/\{\\\*\\[^{}]*\}/g, ' ')
    // Elimina codis de caràcter hexadecimal \'xx
    .replace(/\\'[0-9a-fA-F]{2}/g, ' ')
    // Elimina paraules de control RTF \keyword i paràmetres numèrics opcionals
    .replace(/\\[a-zA-Z]+[-]?\d*\s?/g, ' ')
    // Elimina claus delimitadores de grups
    .replace(/[{}]/g, ' ')
    // Normalitza espais múltiples
    .replace(/\s+/g, ' ');

  return text.trim();
}

/**
 * Compta les paraules d'un document .docx o .rtf de manera client-side.
 * Detecta l'extensió i aplica el mètode corresponent.
 * @param {File} file
 * @returns {Promise<number>}
 */
async function contarParaulesDocument(file) {
  const ext = file.name.split('.').pop().toLowerCase();

  if (ext === 'docx') {
    const text = await _extrauTextDocx(file);
    return contarParaulesText(text);
  }

  if (ext === 'rtf') {
    const text = await _extrauTextRtf(file);
    return contarParaulesText(text);
  }

  throw new Error(`Format no compatible per al recompte client-side: .${ext}`);
}
