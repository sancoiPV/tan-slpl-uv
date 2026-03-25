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
 *   totalWords:  number,   // paraules de diapositives + paraules de notes
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

    // Compta paraules del contingut de la diapositiva (àrea de presentació)
    const slideWords = _countWordsInXml(slideXml);

    // Obté paraules de les notes i si hi ha text real escrit per l'usuari
    const { hasNotes, noteWords } = await _obteNotesInfo(zip, slidePath);

    slides.push({ path: slidePath, isHidden, slideWords, noteWords, hasNotes });
  }

  // ── 4. Agrupa per visibles / ocultes
  const visibleSlides      = slides.filter(s => !s.isHidden);
  const hiddenSlides       = slides.filter(s =>  s.isHidden);
  const visibleWithNotes   = visibleSlides.filter(s => s.hasNotes);
  const hiddenWithNotes    = hiddenSlides.filter(s => s.hasNotes);

  // ── 5. Agrega estadístiques globals
  return {
    totalSlides: slides.length,
    // Total inclou paraules de diapositives + paraules de notes del presentador
    totalWords: slides.reduce((sum, s) => sum + s.slideWords + s.noteWords, 0),
    visible: {
      count:          visibleSlides.length,
      // Paraules del CONTINGUT de les diapositives visibles (NO notes)
      words:          visibleSlides.reduce((sum, s) => sum + s.slideWords, 0),
      // Nombre de diapositives visibles que tenen notes reals
      withNotes:      visibleWithNotes.length,
      // Paraules del CONTINGUT de les diapositives visibles que tenen notes (NO les notes en si)
      withNotesWords: visibleWithNotes.reduce((sum, s) => sum + s.slideWords, 0)
    },
    hidden: {
      count:          hiddenSlides.length,
      // Paraules del CONTINGUT de les diapositives ocultes (NO notes)
      words:          hiddenSlides.reduce((sum, s) => sum + s.slideWords, 0),
      // Nombre de diapositives ocultes que tenen notes reals
      withNotes:      hiddenWithNotes.length,
      // Paraules del CONTINGUT de les diapositives ocultes que tenen notes (NO les notes en si)
      withNotesWords: hiddenWithNotes.reduce((sum, s) => sum + s.slideWords, 0)
    },
    notes: {
      // Total de diapositives amb notes reals (visibles + ocultes)
      count: visibleWithNotes.length + hiddenWithNotes.length,
      // Total de paraules de TOTES les notes del presentador
      words: slides.reduce((sum, s) => sum + s.noteWords, 0)
    },
    slides
  };
}

/**
 * Obté informació de les notes d'una diapositiva.
 * Retorna { hasNotes, noteWords } on:
 *   - hasNotes: true NOMÉS si el cos de notes conté text real escrit per l'usuari
 *   - noteWords: recompte de paraules del text real (excloent camps automàtics i placeholders)
 *
 * Filtra estrictament:
 *   - NOMÉS processa shapes amb placeholder de tipus "body" (on l'usuari escriu)
 *   - EXCLOU shapes de sistema: sldNum, dt, sldImg, hdr, ftr, title
 *   - EXCLOU elements <a:fld> (camps automàtics com número de diapositiva)
 *   - EXCLOU shapes sense placeholder (no rellevants per a les notes)
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

  // Extreu NOMÉS el text del cos de les notes (shape body, sense camps automàtics)
  const notesText = _extrauTextNotes(notesXml).trim();
  if (!notesText) return { hasNotes: false, noteWords: 0 };

  const noteWords = countWords(notesText);
  return { hasNotes: noteWords > 0, noteWords };
}

/**
 * Extreu el text real del cos de les notes d'un notesSlide XML.
 *
 * Regles de filtratge (seguint l'especificació OOXML):
 *   1. Usa DOMParser amb namespaces eliminats per a parseig robust.
 *   2. Itera els <sp> (shapes) del document.
 *   3. Busca el placeholder (<ph>) dins de <nvSpPr><nvPr>.
 *   4. Si no hi ha <ph>: DESCARTA el shape (no és un placeholder de notes).
 *   5. Si hi ha <ph> amb type= "sldNum", "dt", "sldImg", "hdr", "ftr", "title": DESCARTA.
 *   6. Si hi ha <ph> amb type="body" o sense type (placeholder de cos): PROCESSA.
 *   7. Dins del shape processat: extreu text de <r><t> però IGNORA <fld> (camps automàtics).
 *
 * @param {string} notesXmlStr  Contingut del fitxer notesSlideN.xml
 * @returns {string}  Text pla real de les notes
 */
function _extrauTextNotes(notesXmlStr) {
  // Elimina namespaces per facilitar els selectors CSS (querySelector no suporta bé ns)
  const cleaned = notesXmlStr
    .replace(/\s+xmlns(?::[a-zA-Z0-9]+)?="[^"]*"/g, '')
    .replace(/([a-zA-Z0-9]+):/g, '');

  const parser = new DOMParser();
  const doc = parser.parseFromString(cleaned, 'application/xml');

  // Comprova errors de parseig
  const parseError = doc.querySelector('parsererror');
  if (parseError) return '';

  let notesText = '';

  const shapes = doc.querySelectorAll('sp');
  shapes.forEach(shape => {
    // Comprova si el shape té un placeholder (<ph> dins de nvSpPr > nvPr)
    const ph = shape.querySelector('nvSpPr nvPr ph');
    if (!ph) {
      // Shape sense placeholder: no és rellevant per a les notes → descarta
      return;
    }

    const phType = ph.getAttribute('type');

    // Descarta placeholders del sistema (no escrits per l'usuari)
    const tipusSistema = ['sldNum', 'dt', 'sldImg', 'hdr', 'ftr', 'title'];
    if (phType && tipusSistema.includes(phType)) {
      return;
    }

    // Processa NOMÉS placeholders de cos: type="body" o sense type (notes body, idx="1")
    // Extreu text de runs (<r><t>) però EXCLOU camps automàtics (<fld>)
    const paragraphs = shape.querySelectorAll('p');
    paragraphs.forEach(p => {
      // Processa els runs normals (r → t), no els camps (fld)
      const runs = p.querySelectorAll('r');
      runs.forEach(r => {
        // Comprova que el run NO és fill d'un camp automàtic
        if (r.closest('fld')) return;
        const tNodes = r.querySelectorAll('t');
        tNodes.forEach(t => {
          notesText += t.textContent + ' ';
        });
      });
    });
  });

  return notesText;
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
 * Extreu text pla dels elements <a:t> d'un XML OOXML (per a diapositives).
 * Nota: per a les notes s'usa _extrauTextNotes() que filtra per shape body.
 *
 * @param {string} xmlStr
 * @returns {string}
 */
function _extractTextFromXml(xmlStr) {
  const matches = xmlStr.match(/<a:t[^>]*>([^<]*)<\/a:t>/g) || [];
  return matches.map(node => node.replace(/<[^>]+>/g, '')).join(' ');
}

/**
 * Compta les paraules del text contingut en un fragment d'XML OOXML (per a diapositives).
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
 * Format de la taula (6 files de dades + capçalera):
 *   Secció                              | Diapositives | Paraules
 *   ─────────────────────────────────────────────────────────────
 *   Diapositives visibles               |      68      |  2.835
 *   — de les quals amb notes            |      65      |  2.690 (contingut de les 65)
 *   Diapositives ocultes                |      16      |    683
 *   — de les quals amb notes            |      14      |    655 (contingut de les 14)
 *   Notes a peu de diapositiva (total)  |      79      | 10.688 (text real de les notes)
 *   TOTAL                               |      84      | 14.206
 *
 * NOTA: Les files "— de les quals amb notes" mostren les paraules del CONTINGUT
 * d'eixes diapositives, NO les paraules de les notes. Les notes van a la seua pròpia fila.
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

  // Estils de cel·la comuns (explícits per assegurar visibilitat independentment del CSS global)
  const tdBase  = 'border:1px solid #999;padding:5px 10px;';
  const tdCentr = tdBase + 'text-align:center;';
  const tdItal  = tdBase + 'padding-left:25px;font-style:italic;color:#555;';

  // Files de diapositives ocultes (s'amaguen si count === 0)
  const hiddenRows = stats.hidden.count > 0 ? `
          <tr>
            <td style="${tdBase}">Diapositives ocultes</td>
            <td style="${tdCentr}">${fmt(stats.hidden.count)}</td>
            <td style="${tdCentr}">${fmt(stats.hidden.words)}</td>
          </tr>
          <tr>
            <td style="${tdItal}">— de les quals amb notes</td>
            <td style="${tdCentr}">${fmt(stats.hidden.withNotes)}</td>
            <td style="${tdCentr}">${fmt(stats.hidden.withNotesWords)}</td>
          </tr>` : '';

  const tdTotal = 'border:1px solid #999;border-top:2px solid #333;padding:5px 10px;font-weight:bold;';
  const tdTotalC = tdTotal + 'text-align:center;';

  el.innerHTML = `
    <div style="margin-top:12px;">
      <h4 style="margin-bottom:8px;font-size:14px;">
        📊 ${_escapeHtml(filename)}
        <span style="font-weight:normal;font-size:0.9em;color:#666;">
          (${fmt(stats.totalSlides)} diapositives en total)
        </span>
      </h4>
      <table style="max-width:580px;border-collapse:collapse;font-size:13px;margin-top:6px;">
        <thead>
          <tr style="background-color:#f0f0f0;">
            <th style="${tdBase}text-align:left;">Secció</th>
            <th style="${tdCentr}">Diapositives</th>
            <th style="${tdCentr}">Paraules</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="${tdBase}">Diapositives visibles</td>
            <td style="${tdCentr}">${fmt(stats.visible.count)}</td>
            <td style="${tdCentr}">${fmt(stats.visible.words)}</td>
          </tr>
          <tr>
            <td style="${tdItal}">— de les quals amb notes</td>
            <td style="${tdCentr}">${fmt(stats.visible.withNotes)}</td>
            <td style="${tdCentr}">${fmt(stats.visible.withNotesWords)}</td>
          </tr>
          ${hiddenRows}
          <tr>
            <td style="${tdBase}">Notes a peu de diapositiva (total)</td>
            <td style="${tdCentr}">${fmt(stats.notes.count)}</td>
            <td style="${tdCentr}">${fmt(stats.notes.words)}</td>
          </tr>
          <tr style="background-color:#f5f5f5;">
            <td style="${tdTotal}">TOTAL</td>
            <td style="${tdTotalC}">${fmt(stats.totalSlides)}</td>
            <td style="${tdTotalC}">${fmt(stats.totalWords)}</td>
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
