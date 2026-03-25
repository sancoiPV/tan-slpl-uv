'use strict';

// ─── Estat global ─────────────────────────────────────────────────────────────
let traduitMemoria   = '';
let fitxerActualTd   = null;   // fitxer pendent a "Traducció de documents"
let fitxerActualCd   = null;   // fitxer pendent a "Correcció de documents"

// ─── Comprovació estat del motor ──────────────────────────────────────────────
async function comprova() {
  const dot = document.getElementById('dot');
  const txt = document.getElementById('statusTxt');
  // Indica estat "comprovant" mentre es detecta
  dot.className = 'dot';
  txt.textContent = 'Comprovant...';
  TAN.showServerStatus('Detectant servidor...', 'loading');

  const endpoint = await TAN.detectActiveEndpoint();
  if (endpoint) {
    dot.className = 'dot ok';
    txt.textContent = 'Motor actiu';
  } else {
    dot.className = 'dot err';
    txt.textContent = 'Motor no disponible';
  }
}

// ─── Navegació (5 pestanyes) ──────────────────────────────────────────────────
function mostra(id, btn) {
  document.querySelectorAll('.seccio').forEach(s => s.classList.remove('vis'));
  document.querySelectorAll('.nav-btn, .tab-btn').forEach(b => b.classList.remove('act'));
  // Amaga pestanyes addicionals (glossaris, etc.) quan se selecciona una secció normal
  document.querySelectorAll('.tab-content').forEach(t => { t.style.display = 'none'; });
  document.getElementById('s-' + id).classList.add('vis');
  btn.classList.add('act');
}

// ─── CANVI 5A · Comptadors de paraules en temps real ─────────────────────────
function actualComp() {
  const t = document.getElementById('origen').value;
  const n = t.trim() ? t.trim().split(/\s+/).length : 0;
  document.getElementById('comp-orig').textContent =
    n.toLocaleString() + ' paraule' + (n === 1 ? '' : 's');
}

function actualCompDesti() {
  const t = document.getElementById('desti').value;
  const n = t.trim() ? t.trim().split(/\s+/).length : 0;
  document.getElementById('comp-desti').textContent =
    n.toLocaleString() + ' paraule' + (n === 1 ? '' : 's');
}

function actualCompCorr() {
  const t = document.getElementById('origen-c').value;
  const n = t.trim() ? t.trim().split(/\s+/).length : 0;
  document.getElementById('comp-orig-c').textContent =
    n.toLocaleString() + ' paraule' + (n === 1 ? '' : 's');
}

function actualCompDestiCorr() {
  const t = document.getElementById('desti-c').value;
  const n = t.trim() ? t.trim().split(/\s+/).length : 0;
  document.getElementById('comp-desti-c').textContent =
    n.toLocaleString() + ' paraule' + (n === 1 ? '' : 's');
}

// ─── Neteja ───────────────────────────────────────────────────────────────────
function neteja() {
  document.getElementById('origen').value = '';
  document.getElementById('desti').value  = '';
  document.getElementById('temps').textContent = '';
  document.getElementById('btnDesa').style.display = 'none';
  actualComp();
  actualCompDesti();
}

function netejaCorr() {
  document.getElementById('origen-c').value = '';
  document.getElementById('desti-c').value  = '';
  document.getElementById('temps-c').textContent = '';
  document.getElementById('btnDesaC').style.display = 'none';
  actualCompCorr();
  actualCompDestiCorr();
}

// ─── Traducció de text ────────────────────────────────────────────────────────
async function tradueixText() {
  const textOriginal = document.getElementById('origen').value.trim();
  if (!textOriginal) return;
  const btn = document.getElementById('btnT');
  btn.disabled = true;
  btn.textContent = '⏳';
  try {
    const t0 = performance.now();
    const traduccio = await TAN.translate(textOriginal, 'es', 'ca');
    const temps_ms = Math.round(performance.now() - t0);
    const dest = document.getElementById('desti');
    dest.value = traduccio;
    traduitMemoria = traduccio;
    document.getElementById('temps').textContent = temps_ms + ' ms';
    dest.readOnly = true;
    actualCompDesti();   // CANVI 5A: actualitza comptador destí
  } catch (e) {
    document.getElementById('desti').value = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Tradueix';
  }
}

// ─── Correcció de text ────────────────────────────────────────────────────────
async function corregeixText() {
  const textOriginal = document.getElementById('origen-c').value.trim();
  if (!textOriginal) return;
  const btn = document.getElementById('btnC');
  btn.disabled = true;
  btn.textContent = '⏳';
  try {
    const t0 = performance.now();
    const traduccio = await TAN.translate(textOriginal, 'es', 'ca');
    const temps_ms = Math.round(performance.now() - t0);
    const dest = document.getElementById('desti-c');
    dest.value = traduccio;
    document.getElementById('temps-c').textContent = temps_ms + ' ms';
    dest.readOnly = true;
    actualCompDestiCorr();  // CANVI 5A
  } catch (e) {
    document.getElementById('desti-c').value = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Corregeix';
  }
}

// ─── Accions panells de text ──────────────────────────────────────────────────
function edita() {
  const d = document.getElementById('desti');
  d.readOnly = false;
  d.focus();
  document.getElementById('btnDesa').style.display = 'inline-block';
}

function copia() {
  navigator.clipboard.writeText(document.getElementById('desti').value);
}

function editaCorr() {
  const d = document.getElementById('desti-c');
  d.readOnly = false;
  d.focus();
  document.getElementById('btnDesaC').style.display = 'inline-block';
}

function copiaCorr() {
  navigator.clipboard.writeText(document.getElementById('desti-c').value);
}

async function desaPost() {
  const btn = document.getElementById('btnDesa');
  try {
    await fetch(await TAN.getUrlAvancada() + '/desa-postedicio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origen:      document.getElementById('origen').value,
        ta:          traduitMemoria,
        posteditada: document.getElementById('desti').value,
        tecnic:      'slpl-uv'
      })
    });
    btn.textContent = '✓ Desat al corpus';
    setTimeout(() => { btn.textContent = '💾 Desa postedició'; }, 2500);
  } catch (e) {
    if (window.TAN) window.TAN.resetEndpointAvancat();
    alert('Error en desar: ' + e.message);
  }
}

async function desaPostCorr() {
  const btn = document.getElementById('btnDesaC');
  try {
    await fetch(await TAN.getUrlAvancada() + '/desa-postedicio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origen:      document.getElementById('origen-c').value,
        ta:          '',
        posteditada: document.getElementById('desti-c').value,
        tecnic:      'slpl-uv'
      })
    });
    btn.textContent = '✓ Desat al corpus';
    setTimeout(() => { btn.textContent = '💾 Desa postedició'; }, 2500);
  } catch (e) {
    if (window.TAN) window.TAN.resetEndpointAvancat();
    alert('Error en desar: ' + e.message);
  }
}

// ─── CANVI 5B · Documents: selecció i recompte immediat ──────────────────────
// Mapeig de mode a sufix d'IDs
function sfx(mode) { return mode === 'traduccio' ? 'td' : 'cd'; }

function onDropDocs(e, mode) {
  e.preventDefault();
  document.getElementById('upload-area-' + sfx(mode)).classList.remove('drag-over');
  if (e.dataTransfer.files[0]) seleccionaFitxer(e.dataTransfer.files[0], mode);
}

async function seleccionaFitxer(fitxer, mode) {
  if (!fitxer) return;
  const ext = fitxer.name.split('.').pop().toLowerCase();
  if (!['docx', 'pptx'].includes(ext)) {
    alert('Format no suportat. Usa .docx o .pptx'); return;
  }
  if (fitxer.size > 150 * 1024 * 1024) {
    alert('El fitxer supera el límit de 150 MB'); return;
  }

  // Guarda referència al fitxer actual
  if (mode === 'traduccio') fitxerActualTd = fitxer;
  else                      fitxerActualCd = fitxer;

  const s = sfx(mode);

  // Mostra informació immediatament
  document.getElementById('fitxer-ico-'  + s).textContent = ext === 'pptx' ? '📊' : '📄';
  document.getElementById('fitxer-nom-'  + s).textContent = fitxer.name;
  document.getElementById('fitxer-meta-' + s).textContent =
    (fitxer.size / 1024).toFixed(0) + ' KB · comptant paraules...';
  document.getElementById('fitxer-info-' + s).style.display = 'flex';
  document.getElementById('resCard-'     + s).style.display = 'none';

  // Recompte de paraules via backend (/recompte-paraules)
  try {
    const form = new FormData();
    form.append('fitxer', fitxer);
    const r = await fetch(await TAN.getUrlAvancada() + '/recompte-paraules', {
      method: 'POST', body: form
    });
    if (r.ok) {
      const d = await r.json();
      document.getElementById('fitxer-meta-' + s).textContent =
        (fitxer.size / 1024).toFixed(0) + ' KB · ' +
        d.paraules.toLocaleString() + ' paraules';
    } else {
      document.getElementById('fitxer-meta-' + s).textContent =
        (fitxer.size / 1024).toFixed(0) + ' KB';
    }
  } catch {
    if (window.TAN) window.TAN.resetEndpointAvancat();
    document.getElementById('fitxer-meta-' + s).textContent =
      (fitxer.size / 1024).toFixed(0) + ' KB';
  }

  // Mostra el selector de domini quan es carrega un fitxer per a traducció
  if (mode === 'traduccio') mostraDocDominiSelector();

  // Estadístiques PPTX (anàlisi al navegador sense servidor)
  const statsContainerId = `pptx-stats-${s}`;
  const statsContainer = document.getElementById(statsContainerId);
  if (statsContainer) {
    statsContainer.style.display = 'none';
    statsContainer.innerHTML = '';
  }
  if (ext === 'pptx' && statsContainer && typeof analyzePptx === 'function') {
    analyzePptx(fitxer)
      .then(stats => {
        renderPptxStats(stats, statsContainer, fitxer.name);
        // Actualitza el recompte de paraules amb el total real (diapositives + notes)
        document.getElementById('fitxer-meta-' + s).textContent =
          (fitxer.size / 1024).toFixed(0) + ' KB · ' +
          stats.totalWords.toLocaleString('ca-ES') + ' paraules (incl. notes)';
      })
      .catch(() => { /* en cas d'error, simplement no mostrem les estadístiques */ });
  }
}

// ─── Extreu el nom del fitxer de la capçalera Content-Disposition ─────────────
function extrauNomFitxer(contentDisposition, nomFallback) {
  // Content-Disposition: attachment; filename="document_VAL.docx"
  if (!contentDisposition) return nomFallback;
  const match = contentDisposition.match(/filename="?([^";\n]+)"?/i);
  return match ? match[1].trim() : nomFallback;
}

// ─── CANVI 8 · Barra de progrés amb missatges canviants ──────────────────────
async function processaFitxerActual(mode) {
  const fitxer = mode === 'traduccio' ? fitxerActualTd : fitxerActualCd;
  if (!fitxer) { alert('Primer selecciona un document.'); return; }

  const s   = sfx(mode);
  const ext = fitxer.name.split('.').pop().toLowerCase();

  // Amaga info i resultat, mostra progrés
  document.getElementById('fitxer-info-' + s).style.display = 'none';
  document.getElementById('resCard-'     + s).style.display = 'none';
  const pc = document.getElementById('progCont-' + s);
  pc.style.display = 'block';

  // Missatges progressius (CANVI 8)
  const missatges = [
    'Analitzant el document...',
    'Traduint paràgrafs...',
    'Aplicant el format original...',
    'Finalitzant...'
  ];
  let idx = 0;
  document.getElementById('progLbl-' + s).textContent = missatges[idx++];
  const interval = setInterval(() => {
    if (idx < missatges.length) {
      document.getElementById('progLbl-' + s).textContent = missatges[idx++];
    }
  }, 2500);

  const form = new FormData();
  form.append('fitxer', fitxer);
  form.append('mode', mode);
  // Afegeix el domini seleccionat (només per a la pestanya de traducció)
  if (mode === 'traduccio') {
    const dominiSelect = document.getElementById('doc-domini-select');
    if (dominiSelect) form.append('domini', dominiSelect.value);
  }

  try {
    const r = await fetch(await TAN.getUrlAvancada() + '/tradueix-document', {
      method: 'POST', body: form
    });
    if (!r.ok) throw new Error(await r.text());

    // Llegeix la capçalera ABANS de consumir el cos (r.blob())
    const contentDisposition = r.headers.get('Content-Disposition');
    const nomDescarrega = extrauNomFitxer(contentDisposition, fitxer.name);

    clearInterval(interval);
    const blob = await r.blob();
    pc.style.display = 'none';

    // Mostra targeta de resultat
    const card = document.getElementById('resCard-' + s);
    card.style.display = 'flex';
    document.getElementById('resIco-'  + s).textContent = ext === 'pptx' ? '📊' : '📄';
    document.getElementById('resNom-'  + s).textContent = nomDescarrega;   // ← _VAL
    document.getElementById('resDet-'  + s).textContent =
      (blob.size / 1024).toFixed(0) + ' KB · ' + ext.toUpperCase() +
      ' · ' + (mode === 'traduccio' ? 'Traducció ES→CA' : 'Correcció en valencià');

    document.getElementById('btnDesc-' + s).onclick = () => {
      const url = URL.createObjectURL(blob);
      const a   = document.createElement('a');
      a.href = url; a.download = nomDescarrega; a.click();   // ← _VAL
      URL.revokeObjectURL(url);
    };

    // Mostra de nou la info del fitxer
    document.getElementById('fitxer-info-' + s).style.display = 'flex';

  } catch (e) {
    if (window.TAN) window.TAN.resetEndpointAvancat();
    clearInterval(interval);
    pc.style.display = 'none';
    document.getElementById('fitxer-info-' + s).style.display = 'flex';
    alert('Error en la traducció: ' + e.message);
  }
}

// ─── SUBSTITUÏT per la implementació completa de Gemini (vegeu més avall) ────
// Les funcions onDropImatge / seleccionaImatge / ocrITradueix han estat
// reemplaçades per handleImageDrop / handleImageSelect / tradueixImatges.

// ─── Inici ────────────────────────────────────────────────────────────────────
comprova();
setInterval(comprova, 30000);

// ═══════════════════════════════════════════════════════
// PESTANYA GLOSSARIS: ACTUALITZACIÓ
// ═══════════════════════════════════════════════════════

let glossariActual = [];
let dominiActual = '';

/**
 * Activa la pestanya de glossaris (gestiona la visibilitat de totes les
 * seccions normals i del panell de glossaris).
 */
function activaTab(id) {
  // Amaga totes les seccions normals i totes les tab-content
  document.querySelectorAll('.seccio').forEach(s => s.classList.remove('vis'));
  document.querySelectorAll('.tab-content').forEach(t => { t.style.display = 'none'; });
  document.querySelectorAll('.nav-btn, .tab-btn').forEach(b => b.classList.remove('act'));

  // Mostra la pestanya seleccionada
  const seccio = document.getElementById('tab-' + id);
  if (seccio) seccio.style.display = 'block';
  const btn = document.querySelector('[data-tab="' + id + '"]');
  if (btn) btn.classList.add('act');

  // Inicialitzacions CONDICIONALS (només si encara no s'han fet)
  // per evitar esborrar l'estat de les altres pestanyes
  if (id === 'glossaris' && document.getElementById('domini-select')?.options.length <= 1) {
    inicialitzaGlossari();
  }
  // NOTA: imatgesSeleccionades, imatgesTradudes, _documentSeleccionat,
  // _documentCorregitBlob, fitxerActualTd, fitxerActualCd
  // NO s'han de reinicialitzar en canviar de pestanya.
}

async function inicialitzaGlossari() {
  try {
    const url = await TAN.getUrlAvancada();
    const resp = await fetch(`${url}/glossaris`);
    if (!resp.ok) return;
    const data = await resp.json();
    const select = document.getElementById('domini-select');
    data.dominis.forEach(domini => {
      const opt = document.createElement('option');
      opt.value = domini;
      opt.textContent = domini;
      select.appendChild(opt);
    });
  } catch (e) {
    console.warn('Glossari no disponible:', e.message);
  }
}

async function carregaGlossari() {
  const select = document.getElementById('domini-select');
  dominiActual = select.value;
  const form = document.getElementById('glossari-form');
  const taulaContainer = document.getElementById('glossari-taula-container');
  const badge = document.getElementById('glossari-total');

  if (!dominiActual) {
    form.style.display = 'none';
    taulaContainer.style.display = 'none';
    badge.style.display = 'none';
    return;
  }

  form.style.display = 'block';
  taulaContainer.style.display = 'block';

  try {
    const url = await TAN.getUrlAvancada();
    const resp = await fetch(`${url}/glossari/${encodeURIComponent(dominiActual)}`);
    if (!resp.ok) throw new Error(`Error ${resp.status}`);
    const data = await resp.json();
    glossariActual = data.entrades;
    renderitzaTaula(glossariActual);
    badge.textContent = `${data.total} entrada${data.total !== 1 ? 's' : ''}`;
    badge.style.display = data.total > 0 ? 'inline' : 'none';
  } catch (e) {
    console.error('Error carregant glossari:', e);
  }
}

function renderitzaTaula(entrades) {
  const tbody = document.getElementById('glossari-tbody');
  const buit = document.getElementById('glossari-buit');
  tbody.innerHTML = '';
  if (entrades.length === 0) {
    buit.style.display = 'block';
    return;
  }
  buit.style.display = 'none';
  entrades.forEach(e => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${escapeHtml(e.es)}</td>
      <td><strong>${escapeHtml(e.ca)}</strong></td>
      <td>${escapeHtml(e.tecnic || '—')}</td>
      <td>${escapeHtml(e.data || '—')}</td>
      <td>
        <button class="btn-eliminar-terme"
                onclick="eliminaTerme('${escapeHtml(e.es).replace(/'/g, "\\'")}')">
          🗑
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filtraGlossari() {
  const cerca = document.getElementById('glossari-cerca').value.toLowerCase();
  const filtrades = glossariActual.filter(e =>
    e.es.toLowerCase().includes(cerca) ||
    e.ca.toLowerCase().includes(cerca)
  );
  renderitzaTaula(filtrades);
}

async function descarregaGlossari() {
  if (!dominiActual) {
    mostraMissatgeGlossari('error', 'Selecciona un domini primer.');
    return;
  }
  if (glossariActual.length === 0) {
    mostraMissatgeGlossari('error', 'El glossari és buit, no hi ha res a descarregar.');
    return;
  }
  try {
    const url = await TAN.getUrlAvancada();
    const resp = await fetch(
      `${url}/glossari/${encodeURIComponent(dominiActual)}/exporta`
    );
    if (!resp.ok) throw new Error(`Error ${resp.status}`);

    // Obté el nom del fitxer de la capçalera Content-Disposition
    const disposition = resp.headers.get('Content-Disposition') || '';
    const nomMatch = disposition.match(/filename="([^"]+)"/);
    const nomFitxer = nomMatch ? nomMatch[1] : `glossari_${dominiActual}.tsv`;

    // Descàrrega al navegador
    const blob = await resp.blob();
    const urlBlob = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = urlBlob;
    a.download = nomFitxer;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(urlBlob);

    mostraMissatgeGlossari('ok', `✓ Descarregant ${nomFitxer}`);
  } catch (e) {
    mostraMissatgeGlossari('error', `Error en la descàrrega: ${e.message}`);
  }
}

async function afegeixTerme() {
  const es = document.getElementById('terme-es').value.trim();
  const ca = document.getElementById('terme-ca').value.trim();
  const tecnic = document.getElementById('terme-tecnic').value;

  if (!es || !ca) {
    mostraMissatgeGlossari('error', 'Cal omplir el terme en castellà i la traducció valenciana.');
    return;
  }
  if (!tecnic) {
    mostraMissatgeGlossari('error', "Identifica't seleccionant el teu nom.");
    return;
  }
  if (!dominiActual) {
    mostraMissatgeGlossari('error', 'Selecciona un domini primer.');
    return;
  }

  try {
    const url = await TAN.getUrlAvancada();
    const resp = await fetch(
      `${url}/glossari/${encodeURIComponent(dominiActual)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ es, ca, tecnic, domini: dominiActual }),
      }
    );
    if (!resp.ok) throw new Error(`Error ${resp.status}`);
    const data = await resp.json();
    const accio = data.estat === 'actualitzat' ? 'actualitzat' : 'afegit';
    mostraMissatgeGlossari('ok', `✓ Terme "${es}" ${accio} correctament.`);
    document.getElementById('terme-es').value = '';
    document.getElementById('terme-ca').value = '';
    await carregaGlossari();
  } catch (e) {
    mostraMissatgeGlossari('error', `Error afegint el terme: ${e.message}`);
  }
}

async function eliminaTerme(termeEs) {
  if (!confirm(`Eliminar el terme "${termeEs}" del glossari?`)) return;
  try {
    const url = await TAN.getUrlAvancada();
    const resp = await fetch(
      `${url}/glossari/${encodeURIComponent(dominiActual)}/${encodeURIComponent(termeEs)}`,
      { method: 'DELETE' }
    );
    if (!resp.ok) throw new Error(`Error ${resp.status}`);
    mostraMissatgeGlossari('ok', `✓ Terme "${termeEs}" eliminat.`);
    await carregaGlossari();
  } catch (e) {
    mostraMissatgeGlossari('error', `Error eliminant el terme: ${e.message}`);
  }
}

function mostraMissatgeGlossari(tipus, text) {
  const el = document.getElementById('glossari-missatge');
  el.textContent = text;
  el.className = `glossari-missatge glossari-missatge-${tipus}`;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 4000);
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', () => {
  inicialitzaGlossari();
});


// ═══════════════════════════════════════════════════════
// PESTANYA TRADUCCIÓ D'IMATGES AMB TEXT (Gemini)
// ═══════════════════════════════════════════════════════

let imatgesSeleccionades = [];
let imatgesTradudes = [];

// configurarGeminiKey() — substituïda pel modal centralitzat 🔑 Claus API
// La gestió de la clau de Gemini es fa des de obreModalClausAPI()

function handleImageDrop(event) {
  event.preventDefault();
  const fitxers = Array.from(event.dataTransfer.files).filter(
    f => f.type.startsWith('image/')
  );
  afegeixImatges(fitxers);
}

function handleImageSelect(event) {
  const fitxers = Array.from(event.target.files);
  afegeixImatges(fitxers);
  event.target.value = '';
}

function afegeixImatges(fitxers) {
  fitxers.forEach(fitxer => {
    if (fitxer.size > 10 * 1024 * 1024) {
      mostraMissatgeImatge('error', `"${fitxer.name}" supera el límit de 10 MB.`);
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      imatgesSeleccionades.push({
        nom: fitxer.name,
        tipus: fitxer.type,
        base64: e.target.result.split(',')[1],
        dataUrl: e.target.result,
      });
      renderitzaLlistaImatges();
    };
    reader.readAsDataURL(fitxer);
  });
}

function renderitzaLlistaImatges() {
  const llista = document.getElementById('imatges-llista');
  const prompt = document.getElementById('imatge-prompt-container');
  const accions = document.getElementById('imatge-accions');

  if (imatgesSeleccionades.length === 0) {
    llista.style.display = 'none';
    prompt.style.display = 'none';
    accions.style.display = 'none';
    return;
  }

  llista.style.display = 'flex';
  prompt.style.display = 'block';
  accions.style.display = 'flex';
  document.getElementById('btn-descarregar-imatge').style.display = 'none';

  llista.innerHTML = imatgesSeleccionades.map((img, i) => `
    <div class="imatge-item" id="imatge-item-${i}">
      <img src="${img.dataUrl}" alt="${escapeHtml(img.nom)}"
           class="imatge-preview-thumb imatge-clicable"
           title="Clica per veure en gran"
           onclick="obreLightbox('${img.dataUrl}', '${escapeHtml(img.nom)}', 'Original', null)">
      <div class="imatge-item-info">
        <span class="imatge-item-nom">${escapeHtml(img.nom)}</span>
        <button onclick="eliminaImatge(${i})" class="btn-eliminar-terme">🗑</button>
      </div>
    </div>
  `).join('');
}

function eliminaImatge(index) {
  imatgesSeleccionades.splice(index, 1);
  imatgesTradudes = [];
  document.getElementById('imatge-resultats').style.display = 'none';
  renderitzaLlistaImatges();
}

async function tradueixImatges() {
  if (imatgesSeleccionades.length === 0) {
    mostraMissatgeImatge('error', 'Puja almenys una imatge primer.');
    return;
  }

  const btnTraduir = document.getElementById('btn-traduir-imatge');
  const promptAddicional = document.getElementById('imatge-prompt-addicional').value.trim();

  btnTraduir.disabled = true;
  btnTraduir.textContent = '⏳ Traduint...';
  imatgesTradudes = [];

  try {
    const url = await TAN.getUrlAvancada();
    const totalImatges = imatgesSeleccionades.length;

    for (let i = 0; i < totalImatges; i++) {
      const img = imatgesSeleccionades[i];
      actualitzaProgress('imatge',
        (i / totalImatges) * 90,
        `Traduint imatge ${i + 1} de ${totalImatges}...`,
        'Nano Banana Pro (Gemini 3 Pro Image)'
      );
      mostraMissatgeImatge('info', `Traduint imatge ${i + 1} de ${totalImatges}...`);

      const resp = await fetch(`${url}/tradueix-imatge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imatge_base64: img.base64,
          tipus_mime: img.tipus,
          prompt_addicional: promptAddicional,
          mode: 'traduccio',
        })
      });

      if (!resp.ok) {
        const error = await resp.json();
        throw new Error(error.detail || `Error ${resp.status}`);
      }

      const data = await resp.json();
      imatgesTradudes.push({
        nom: img.nom.replace(/(\.[^.]+)$/, '_VAL$1'),
        tipus: data.tipus_mime,
        base64: data.imatge_base64,
        dataUrl: `data:${data.tipus_mime};base64,${data.imatge_base64}`,
      });
    }

    actualitzaProgress('imatge', 100, 'Traducció completada!', '');
    setTimeout(() => amagaProgress('imatge'), 2000);

    renderitzaResultats();
    document.getElementById('btn-descarregar-imatge').style.display = 'inline-flex';
    mostraMissatgeImatge('ok', `✓ ${imatgesTradudes.length} imatge${imatgesTradudes.length !== 1 ? 's' : ''} traduïda${imatgesTradudes.length !== 1 ? 's' : ''} correctament.`);

  } catch (e) {
    amagaProgress('imatge');
    mostraMissatgeImatge('error', `Error en la traducció: ${e.message}`);
  } finally {
    btnTraduir.disabled = false;
    btnTraduir.textContent = '🔄 Traduir imatge';
  }
}

function renderitzaResultats() {
  const resultats = document.getElementById('imatge-resultats');
  const refinament = document.getElementById('imatge-refinament');

  resultats.style.display = 'flex';
  resultats.innerHTML = `
    <h3>Imatges traduïdes</h3>
    <div class="imatge-resultats-grid">
      ${imatgesTradudes.map((img, i) => `
        <div class="imatge-resultat-item">
          <div class="imatge-resultat-header">
            <span class="imatge-item-nom">${escapeHtml(img.nom)}</span>
            <button onclick="descarregaImatgeIndividual(${i})"
                    class="btn-descarrega-glossari">
              ⬇ Descarregar
            </button>
          </div>
          <img src="${img.dataUrl}" alt="${escapeHtml(img.nom)}"
               class="imatge-preview imatge-preview-gran imatge-clicable"
               title="Clica per veure en gran"
               onclick="obreLightbox('${img.dataUrl}', '${escapeHtml(img.nom)}', 'Traduïda', ${i})">
        </div>
      `).join('')}
    </div>
  `;

  // Mostra el bloc de refinament iteratiu
  if (refinament) {
    refinament.style.display = 'block';
    document.getElementById('imatge-modificacions').value = '';
  }
}

async function aplicaModificacions() {
  const modificacions = document.getElementById('imatge-modificacions').value.trim();

  if (!modificacions) {
    mostraMissatgeImatge('error', 'Introdueix les modificacions que cal aplicar.');
    return;
  }
  if (imatgesTradudes.length === 0) {
    mostraMissatgeImatge('error', 'No hi ha cap imatge traduïda sobre la qual aplicar modificacions.');
    return;
  }

  const btn = document.getElementById('btn-aplicar-modificacions');
  btn.disabled = true;
  btn.textContent = '⏳ Aplicant modificacions...';

  try {
    const url = await TAN.getUrlAvancada();
    const imatgesRefinades = [];

    for (let i = 0; i < imatgesTradudes.length; i++) {
      const img = imatgesTradudes[i];
      mostraMissatgeImatge('info', `Aplicant modificacions a la imatge ${i + 1} de ${imatgesTradudes.length}...`);

      const resp = await fetch(`${url}/tradueix-imatge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imatge_base64: img.base64,
          tipus_mime: img.tipus,
          prompt_addicional: modificacions,
          mode: 'refinament',
        })
      });

      if (!resp.ok) {
        const error = await resp.json();
        throw new Error(error.detail || `Error ${resp.status}`);
      }

      const data = await resp.json();
      imatgesRefinades.push({
        nom: img.nom,
        tipus: data.tipus_mime,
        base64: data.imatge_base64,
        dataUrl: `data:${data.tipus_mime};base64,${data.imatge_base64}`,
      });
    }

    // Substitueix les imatges traduïdes per les refinades
    imatgesTradudes = imatgesRefinades;
    renderitzaResultats();
    document.getElementById('imatge-modificacions').value = '';
    mostraMissatgeImatge('ok', '✓ Modificacions aplicades correctament.');

  } catch (e) {
    mostraMissatgeImatge('error', `Error aplicant les modificacions: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = '✅ Aplicar les modificacions';
  }
}

function descarregaImatgeIndividual(index) {
  const img = imatgesTradudes[index];
  const a = document.createElement('a');
  a.href = img.dataUrl;
  a.download = img.nom;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function descarregaImattgesTradudes() {
  if (imatgesTradudes.length === 0) {
    mostraMissatgeImatge('error', 'No hi ha imatges traduïdes per descarregar.');
    return;
  }
  imatgesTradudes.forEach((img, i) => {
    setTimeout(() => descarregaImatgeIndividual(i), i * 300);
  });
}

function mostraMissatgeImatge(tipus, text) {
  const el = document.getElementById('imatge-missatge');
  el.textContent = text;
  el.className = `imatge-missatge imatge-missatge-${tipus}`;
  el.style.display = 'block';
  if (tipus !== 'info') {
    setTimeout(() => { el.style.display = 'none'; }, 5000);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// CORRECCIÓ / POSTEDICIÓ DE TEXTOS EN VALENCIÀ
// ═══════════════════════════════════════════════════════════════════════════════

let _dadesCorreccio = null;  // Última resposta de /corregeix

// configurarAnthropicKey() — substituïda pel modal centralitzat 🔑 Claus API
// La gestió de la clau d'Anthropic es fa des de obreModalClausAPI()

// ── Corregeix el text ──────────────────────────────────────────────────────

async function corregeixText() {
  const text = document.getElementById('correccio-textarea').value.trim();
  if (!text) {
    mostraMissatgeCorreccio('error', 'Introdueix un text per a corregir.');
    return;
  }

  const usarLT     = document.getElementById('opt-languagetool').checked;
  const usarClaude = document.getElementById('opt-claude').checked;

  if (!usarLT && !usarClaude) {
    mostraMissatgeCorreccio('error', 'Activa almenys una capa de correcció.');
    return;
  }

  // Amaga resultats anteriors i mostra càrrega
  document.getElementById('correccio-resultats').style.display = 'none';
  document.getElementById('correccio-missatge').style.display  = 'none';
  document.getElementById('correccio-carregant').style.display = 'flex';
  document.getElementById('btn-corregeix').disabled = true;

  const passos = [];
  if (usarLT)     passos.push('LanguageTool');
  if (usarClaude) passos.push('Claude Sonnet');
  document.getElementById('correccio-carregant-txt').textContent =
    `Corregint amb ${passos.join(' + ')}…`;

  actualitzaProgress('correccio', 5, 'Enviant text a Claude Sonnet...', '');

  try {
    const url  = await TAN.getUrlAvancada();
    const resp = await fetch(`${url}/corregeix`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        text:              text,
        usar_languagetool: usarLT,
        usar_claude:       usarClaude,
      }),
    });

    const dades = await resp.json();

    if (!resp.ok) {
      throw new Error(dades.detail || `Error ${resp.status}`);
    }

    actualitzaProgress('correccio', 100, 'Correcció completada!', '');
    setTimeout(() => amagaProgress('correccio'), 2000);

    _dadesCorreccio = dades;
    renderitzaCorreccions(dades);

  } catch (e) {
    amagaProgress('correccio');
    mostraMissatgeCorreccio('error', 'Error: ' + e.message);
  } finally {
    document.getElementById('correccio-carregant').style.display = 'none';
    document.getElementById('btn-corregeix').disabled = false;
  }
}

// ── Renderitza els resultats ───────────────────────────────────────────────

function renderitzaCorreccions(dades) {
  const nLT = (dades.correccions_lt    || []).length;
  const nCL = (dades.correccions_claude || []).length;
  const nTotal = nLT + nCL;

  // Estadístiques
  document.getElementById('stat-total').textContent = nTotal;
  document.getElementById('stat-lt').textContent    = nLT;
  document.getElementById('stat-cl').textContent    = nCL;
  document.getElementById('badge-lt').textContent   = nLT;
  document.getElementById('badge-cl').textContent   = nCL;

  // Resum
  const resumBloc = document.getElementById('correccio-resum-bloc');
  if (dades.resum) {
    document.getElementById('correccio-resum-text').textContent = dades.resum;
    resumBloc.style.display = 'flex';
  } else {
    resumBloc.style.display = 'none';
  }

  // Text corregit
  document.getElementById('correccio-text-resultat').textContent =
    dades.text_corregit || dades.text_original;

  // Llista LanguageTool
  const elLT = document.getElementById('correccio-lt-llista');
  if (nLT === 0) {
    elLT.innerHTML = '<p class="correccio-buit">Cap error detectat per LanguageTool. ✅</p>';
  } else {
    elLT.innerHTML = (dades.correccions_lt || []).map((c, i) => `
      <div class="correccio-item correccio-item-lt">
        <div class="correccio-item-cap">
          <span class="correccio-regla-badge correccio-badge-lt">${escapeHtmlC(c.regla_id || 'LT')}</span>
          <span class="correccio-item-original">${escapeHtmlC(c.original || '')}</span>
          ${c.suggerits && c.suggerits[0]
            ? `→ <span class="correccio-item-corregit">${escapeHtmlC(c.suggerits[0])}</span>`
            : ''}
        </div>
        <div class="correccio-item-missatge">${escapeHtmlC(c.missatge || '')}</div>
        ${c.suggerits && c.suggerits.length > 1
          ? `<div class="correccio-suggerits">Suggerits: ${c.suggerits.map(s => `<span class="correccio-suggerit">${escapeHtmlC(s)}</span>`).join(' ')}</div>`
          : ''}
      </div>`).join('');
  }

  // Llista Claude
  renderitzaLlistaClaude(dades.correccions_claude || []);

  // Activa la pestanya de text i mostra resultats
  activaCorrecciöTab('text');
  document.getElementById('correccio-resultats').style.display = 'block';
}

function renderitzaLlistaClaude(correccions) {
  const el = document.getElementById('correccio-cl-llista');
  if (!correccions || correccions.length === 0) {
    el.innerHTML = '<p class="correccio-buit">Cap correcció addicional per Claude Sonnet. ✅</p>';
    return;
  }
  el.innerHTML = correccions.map((c, i) => `
    <div class="correccio-item correccio-item-cl" data-tipus="${escapeHtmlC((c.tipus || '').toLowerCase())}">
      <div class="correccio-item-cap">
        <span class="correccio-regla-badge correccio-badge-cl">${escapeHtmlC(c.regla || '—')}</span>
        <span class="correccio-tipus-badge correccio-tipus-${escapeHtmlC((c.tipus || 'estil').toLowerCase())}">${escapeHtmlC(c.tipus || 'estil')}</span>
        <span class="correccio-item-original">${escapeHtmlC(c.original || '')}</span>
        ${c.corregit ? `→ <span class="correccio-item-corregit">${escapeHtmlC(c.corregit)}</span>` : ''}
      </div>
      <div class="correccio-item-justificacio">${escapeHtmlC(c.justificacio || '')}</div>
    </div>`).join('');
}

// ── Filtra correccions Claude per tipus ───────────────────────────────────

function filtraCorreccions() {
  if (!_dadesCorreccio) return;
  const tipus = document.getElementById('correccio-filtre-tipus').value.toLowerCase();
  const correccions = (_dadesCorreccio.correccions_claude || []).filter(c => {
    if (!tipus) return true;
    return (c.tipus || '').toLowerCase() === tipus;
  });
  renderitzaLlistaClaude(correccions);
}

// ── Pestanyes de resultats ─────────────────────────────────────────────────

function activaCorrecciöTab(id) {
  const panels = ['text', 'lt', 'cl'];
  panels.forEach(p => {
    const btn   = document.getElementById(`ctab-${p}`);
    const panel = document.getElementById(`cpanel-${p}`);
    if (btn)   btn.classList.toggle('correccio-tab-activa', p === id);
    if (panel) panel.style.display = p === id ? 'block' : 'none';
  });
}

// ── Copia el text corregit ─────────────────────────────────────────────────

async function copiaTextCorregit() {
  const text = document.getElementById('correccio-text-resultat').textContent;
  try {
    await navigator.clipboard.writeText(text);
    mostraMissatgeCorreccio('ok', '✅ Text copiat al porta-retalls.');
  } catch (e) {
    mostraMissatgeCorreccio('error', 'No s\'ha pogut copiar: ' + e.message);
  }
}

// ── Descarrega el text corregit com a .txt ─────────────────────────────────

function descarregaTextCorregit() {
  if (!_dadesCorreccio) return;
  const text = _dadesCorreccio.text_corregit || '';
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `text_corregit_${new Date().toISOString().slice(0, 10)}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Neteja la secció de correcció ─────────────────────────────────────────

function netejaCorreccio() {
  document.getElementById('correccio-textarea').value = '';
  document.getElementById('correccio-comptador').textContent = '0 caràcters';
  document.getElementById('correccio-resultats').style.display = 'none';
  document.getElementById('correccio-missatge').style.display  = 'none';
  _dadesCorreccio = null;
  activaCorrecciöTab('text');
}

// ── Actualitza el comptador de caràcters ──────────────────────────────────

function actualitzaEstadistiques() {
  const text = document.getElementById('correccio-textarea').value;
  const n    = text.length;
  const par  = text.trim() ? text.trim().split(/\s+/).length : 0;
  document.getElementById('correccio-comptador').textContent =
    `${n.toLocaleString('ca')} caràcters · ${par.toLocaleString('ca')} paraules`;
}

// ── Missatges d'estat de la secció correcció ──────────────────────────────

function mostraMissatgeCorreccio(tipus, text) {
  const el = document.getElementById('correccio-missatge');
  el.textContent = text;
  el.className = `correccio-missatge correccio-missatge-${tipus}`;
  el.style.display = 'block';
  if (tipus !== 'info') {
    setTimeout(() => { el.style.display = 'none'; }, 7000);
  }
}

// ── Funció d'escapament HTML (reutilitzable) ──────────────────────────────

function escapeHtmlC(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── Correcció de documents DOCX / PPTX ────────────────────────────────────

let _documentSeleccionat   = null;
let _documentCorregitBlob  = null;
let _nomDocumentCorregit   = '';

function handleDocumentSelect(event) {
  const fitxer = event.target.files[0];
  if (!fitxer) return;

  const ext = fitxer.name.split('.').pop().toLowerCase();
  if (!['docx', 'pptx'].includes(ext)) {
    mostraMissatgeCorreccio('error', 'Només s\'admeten fitxers .docx i .pptx.');
    event.target.value = '';
    return;
  }
  if (fitxer.size > 150 * 1024 * 1024) {
    mostraMissatgeCorreccio('error', 'El fitxer supera el límit de 150 MB.');
    event.target.value = '';
    return;
  }

  _documentSeleccionat  = fitxer;
  _documentCorregitBlob = null;

  const icones = { docx: '📝', pptx: '📊' };
  document.getElementById('correccio-doc-icona').textContent = icones[ext] || '📄';
  document.getElementById('correccio-doc-nom').textContent   = fitxer.name;
  document.getElementById('correccio-doc-mida').textContent  =
    `(${(fitxer.size / 1024).toFixed(0)} KB)`;
  document.getElementById('correccio-doc-info').style.display      = 'flex';
  document.getElementById('btn-corregir-document').style.display   = 'inline-flex';
  document.getElementById('btn-descarregar-document').style.display = 'none';

  // Estadístiques PPTX (anàlisi al navegador sense servidor)
  const statsCd = document.getElementById('pptx-stats-cd');
  if (statsCd) { statsCd.style.display = 'none'; statsCd.innerHTML = ''; }
  if (ext === 'pptx' && statsCd && typeof analyzePptx === 'function') {
    analyzePptx(fitxer)
      .then(stats => renderPptxStats(stats, statsCd, fitxer.name))
      .catch(() => {});
  }

  event.target.value = '';
}

function eliminaDocument() {
  _documentSeleccionat  = null;
  _documentCorregitBlob = null;
  document.getElementById('correccio-doc-info').style.display      = 'none';
  document.getElementById('btn-corregir-document').style.display   = 'none';
  document.getElementById('btn-descarregar-document').style.display = 'none';
  document.getElementById('correccio-doc-input').value = '';
  const statsCd = document.getElementById('pptx-stats-cd');
  if (statsCd) { statsCd.style.display = 'none'; statsCd.innerHTML = ''; }
}

async function corregeixDocument() {
  if (!_documentSeleccionat) {
    mostraMissatgeCorreccio('error', 'Apuja un document primer.');
    return;
  }

  const btn    = document.getElementById('btn-corregir-document');
  const txtOri = btn.textContent;
  btn.disabled    = true;
  btn.textContent = '⏳ Corregint...';

  mostraMissatgeCorreccio('info',
    `Corregint "${_documentSeleccionat.name}"… Pot trigar uns minuts depenent de la llargada del document.`
  );

  actualitzaProgress('correccio', 10, 'Processant el document...', 'Analitzant el contingut');

  // Simula progrés incremental mentre es corregeix
  let _progressInterval = setInterval(() => {
    const barEl = document.getElementById('correccio-progress-bar');
    const barActual = parseFloat(barEl?.style.width || '10');
    if (barActual < 85) {
      actualitzaProgress('correccio', barActual + 3, 'Corregint segments...', 'Aplicant normes AVL i Gramàtica Zero');
    }
  }, 1500);

  try {
    const url      = await TAN.getUrlAvancada();
    const formData = new FormData();
    formData.append('fitxer', _documentSeleccionat);

    const resp = await fetch(`${url}/corregeix-document`, {
      method: 'POST',
      body:   formData,
    });

    clearInterval(_progressInterval);

    if (!resp.ok) {
      let detall = `Error ${resp.status}`;
      try { const err = await resp.json(); detall = err.detail || detall; } catch (_) {}
      throw new Error(detall);
    }

    // Nom del fitxer a partir de la capçalera Content-Disposition
    const disp     = resp.headers.get('Content-Disposition') || '';
    const nomMatch = disp.match(/filename="([^"]+)"/);
    _nomDocumentCorregit = nomMatch
      ? nomMatch[1]
      : _documentSeleccionat.name.replace(/(\.[^.]+)$/, '_corregit$1');

    _documentCorregitBlob = await resp.blob();

    actualitzaProgress('correccio', 100, 'Document corregit!', '');
    setTimeout(() => amagaProgress('correccio'), 2000);

    document.getElementById('btn-descarregar-document').style.display = 'inline-flex';
    mostraMissatgeCorreccio('ok',
      '✅ Document corregit. Clica "⬇ Descarregar document corregit" per obtenir-lo.'
    );

  } catch (e) {
    clearInterval(_progressInterval);
    amagaProgress('correccio');
    mostraMissatgeCorreccio('error', `Error en la correcció del document: ${e.message}`);
  } finally {
    btn.disabled    = false;
    btn.textContent = txtOri;
  }
}

function descarregaDocumentCorregit() {
  if (!_documentCorregitBlob) {
    mostraMissatgeCorreccio('error', 'No hi ha cap document corregit per descarregar.');
    return;
  }
  const urlBlob = URL.createObjectURL(_documentCorregitBlob);
  const a       = document.createElement('a');
  a.href        = urlBlob;
  a.download    = _nomDocumentCorregit;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(urlBlob);
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODAL — CLAUS API
// ═══════════════════════════════════════════════════════════════════════════════

async function obreModalClausAPI() {
  document.getElementById('modal-claus-api').style.display = 'flex';
  await carregaEstatClausAPI();
}

function tancaModalClausAPI() {
  document.getElementById('modal-claus-api').style.display = 'none';
}

// Tanca el modal si l'usuari fa clic a l'overlay (fora del contingut)
function tancaModalSiOverlay(event) {
  if (event.target === document.getElementById('modal-claus-api')) {
    tancaModalClausAPI();
  }
}

async function carregaEstatClausAPI() {
  try {
    const url  = await TAN.getUrlAvancada();
    const resp = await fetch(`${url}/api-keys/estat`);
    if (!resp.ok) return;
    const data = await resp.json();

    // Gemini
    const geminiEstat  = document.getElementById('gemini-estat-badge');
    const geminiActual = document.getElementById('gemini-clau-actual');
    if (geminiEstat) {
      if (data.gemini.configurada) {
        geminiEstat.textContent = '✓ Configurada';
        geminiEstat.className   = 'modal-clau-estat estat-ok';
        if (geminiActual) geminiActual.textContent = `Clau actual: ${data.gemini.clau_parcial}`;
      } else {
        geminiEstat.textContent = '✗ No configurada';
        geminiEstat.className   = 'modal-clau-estat estat-error';
        if (geminiActual) geminiActual.textContent = '';
      }
    }

    // Anthropic
    const anthropicEstat  = document.getElementById('anthropic-estat-badge');
    const anthropicActual = document.getElementById('anthropic-clau-actual');
    if (anthropicEstat) {
      if (data.anthropic.configurada) {
        anthropicEstat.textContent = '✓ Configurada';
        anthropicEstat.className   = 'modal-clau-estat estat-ok';
        if (anthropicActual) anthropicActual.textContent = `Clau actual: ${data.anthropic.clau_parcial}`;
      } else {
        anthropicEstat.textContent = '✗ No configurada';
        anthropicEstat.className   = 'modal-clau-estat estat-error';
        if (anthropicActual) anthropicActual.textContent = '';
      }
    }
  } catch (e) {
    console.warn('No s\'ha pogut carregar l\'estat de les claus API:', e.message);
  }
}

async function desarClauAPI(servei) {
  const inputId    = servei === 'gemini' ? 'modal-gemini-key'    : 'modal-anthropic-key';
  const missatgeId = servei === 'gemini' ? 'gemini-missatge'     : 'anthropic-missatge';
  const clau       = document.getElementById(inputId).value.trim();

  if (!clau) {
    mostraModalMissatge(missatgeId, 'error', 'Introdueix una clau API.');
    return;
  }

  try {
    const url  = await TAN.getUrlAvancada();
    const resp = await fetch(`${url}/api-keys/desa`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ servei, clau }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || `Error ${resp.status}`);
    }

    const data = await resp.json();
    mostraModalMissatge(
      missatgeId, 'ok',
      `✓ Clau desada correctament: ${data.clau_parcial}`
    );
    document.getElementById(inputId).value = '';
    await carregaEstatClausAPI();

  } catch (e) {
    mostraModalMissatge(missatgeId, 'error', `✗ ${e.message}`);
  }
}

function alternaVisibilitatClau(inputId, boto) {
  const input = document.getElementById(inputId);
  if (input.type === 'password') {
    input.type       = 'text';
    boto.textContent = '🙈';
    boto.title       = 'Amaga la clau';
  } else {
    input.type       = 'password';
    boto.textContent = '👁';
    boto.title       = 'Mostra la clau';
  }
}

function mostraModalMissatge(id, tipus, text) {
  const el      = document.getElementById(id);
  el.textContent = text;
  el.className   = `modal-clau-missatge modal-clau-missatge-${tipus}`;
  el.style.display = 'block';
  if (tipus !== 'info') {
    setTimeout(() => { el.style.display = 'none'; }, 5000);
  }
}

// Comprova l'estat de les claus en carregar la pàgina i actualitza el botó nav
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(async () => {
    try {
      const url  = await TAN.getUrlAvancada();
      const resp = await fetch(`${url}/api-keys/estat`);
      if (!resp.ok) return;
      const data = await resp.json();
      const totes = data.gemini.configurada && data.anthropic.configurada;
      const btn   = document.getElementById('btn-claus-api');
      if (btn && !totes) {
        btn.classList.add('btn-claus-api-atencio');
        btn.title = 'Hi ha claus API sense configurar — clica per gestionar-les';
      } else if (btn) {
        btn.classList.remove('btn-claus-api-atencio');
        btn.title = 'Gestiona les claus API de Gemini i Anthropic';
      }
    } catch (_) {}
  }, 2500);
});

// ═══════════════════════════════════════════════════════
// BARRES DE PROGRÉS EN TEMPS REAL
// ═══════════════════════════════════════════════════════

function actualitzaProgress(prefix, percentatge, text, detall) {
  const container = document.getElementById(`${prefix}-progress-container`);
  const bar       = document.getElementById(`${prefix}-progress-bar`);
  const textEl    = document.getElementById(`${prefix}-progress-text`);
  const percentEl = document.getElementById(`${prefix}-progress-percent`);
  const detallEl  = document.getElementById(`${prefix}-progress-detall`);

  if (!container) return;

  if (percentatge === null) {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'block';
  bar.style.width = `${Math.min(100, Math.max(0, percentatge))}%`;
  if (text) textEl.textContent = text;
  percentEl.textContent = `${Math.round(percentatge)}%`;
  if (detall !== undefined) detallEl.textContent = detall || '';

  // Color de la barra segons el progrés
  if (percentatge >= 100) {
    bar.className = 'progress-bar-fill progress-bar-complet';
  } else if (percentatge > 50) {
    bar.className = 'progress-bar-fill progress-bar-mig';
  } else {
    bar.className = 'progress-bar-fill';
  }
}

function amagaProgress(prefix) {
  actualitzaProgress(prefix, null, '', '');
}

// ═══════════════════════════════════════════════════════
// LIGHTBOX DE PREVISUALITZACIÓ D'IMATGES
// ═══════════════════════════════════════════════════════

let _lightboxIndexDescarrega = null;

function obreLightbox(dataUrl, nom, tipus, indexDescarrega) {
  document.getElementById('lightbox-imatge').src = dataUrl;
  document.getElementById('lightbox-titol').textContent =
    `${tipus === 'Traduïda' ? '✅ Imatge traduïda' : '🖼 Imatge original'}: ${nom}`;
  document.getElementById('lightbox-peu-text').textContent =
    tipus === 'Traduïda'
      ? 'Comprova que el text s\'ha traduït correctament. Si cal, fes modificacions al camp inferior.'
      : 'Imatge original pujada pel tècnic.';

  const btnDescarrega = document.getElementById('lightbox-descarrega');
  if (tipus === 'Traduïda' && indexDescarrega !== null) {
    _lightboxIndexDescarrega = indexDescarrega;
    btnDescarrega.style.display = 'inline-flex';
  } else {
    _lightboxIndexDescarrega = null;
    btnDescarrega.style.display = 'none';
  }

  document.getElementById('lightbox-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function tancaLightbox() {
  document.getElementById('lightbox-overlay').style.display = 'none';
  document.getElementById('lightbox-imatge').src = '';
  document.body.style.overflow = '';
}

function descarregaDesLightbox() {
  if (_lightboxIndexDescarrega !== null) {
    descarregaImatgeIndividual(_lightboxIndexDescarrega);
  }
}

// Tanca el lightbox amb Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') tancaLightbox();
});

// ═══════════════════════════════════════════════════════
// SELECTOR DE DOMINI LINGÜÍSTIC — Pestanya Traducció de documents
// ═══════════════════════════════════════════════════════

async function inicialitzaDominiSelector() {
  try {
    const url = await TAN.getUrlAvancada();
    const resp = await fetch(`${url}/dominis-amb-glossari`);
    if (!resp.ok) return;
    const data = await resp.json();

    const select = document.getElementById('doc-domini-select');
    if (!select) return;

    // Neteja opcions existents (excepte la primera)
    while (select.options.length > 1) {
      select.remove(1);
    }

    // Afegeix els dominis, marcant els que tenen glossari
    data.dominis.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.domini;
      opt.textContent = item.te_glossari
        ? `${item.domini} (${item.num_entrades} terme${item.num_entrades !== 1 ? 's' : ''})`
        : item.domini;
      opt.dataset.teGlossari  = item.te_glossari;
      opt.dataset.numEntrades = item.num_entrades;
      select.appendChild(opt);
    });

  } catch (e) {
    console.warn('No s\'ha pogut carregar la llista de dominis:', e.message);
  }
}

function mostraDocDominiSelector() {
  const container = document.getElementById('doc-domini-container');
  if (container) {
    container.style.display = 'block';
    inicialitzaDominiSelector();
  }
}

function actualitzaInfoDomini() {
  const select = document.getElementById('doc-domini-select');
  const badge  = document.getElementById('doc-domini-badge');
  const nota   = document.getElementById('doc-domini-nota');

  if (!select || !badge) return;

  const opcioSeleccionada = select.options[select.selectedIndex];

  if (!select.value) {
    badge.style.display = 'none';
    nota.textContent = 'Si selecciones un domini, el motor aplicarà automàticament el glossari d\'especialitat corresponent per millorar la precisió terminològica de la traducció.';
    return;
  }

  const teGlossari  = opcioSeleccionada.dataset.teGlossari === 'true';
  const numEntrades = parseInt(opcioSeleccionada.dataset.numEntrades || '0');

  if (teGlossari && numEntrades > 0) {
    badge.textContent = `✓ ${numEntrades} terme${numEntrades !== 1 ? 's' : ''} al glossari`;
    badge.className   = 'doc-domini-badge doc-domini-badge-ok';
    badge.style.display = 'inline';
    nota.textContent  = `El motor aplicarà els ${numEntrades} terme${numEntrades !== 1 ? 's' : ''} del glossari "${select.value}" per garantir la terminologia correcta en la traducció.`;
  } else {
    badge.textContent = 'Glossari buit';
    badge.className   = 'doc-domini-badge doc-domini-badge-buit';
    badge.style.display = 'inline';
    nota.textContent  = `El domini "${select.value}" encara no té termes al glossari. Pots afegir-ne a la pestanya "Glossaris: actualització".`;
  }
}

// ═══════════════════════════════════════════════════════
// PESTANYA TRADUCCIÓ ANGLÈS ↔ VALENCIÀ
// ═══════════════════════════════════════════════════════

let _anglesOrigen        = 'en'; // 'en' = anglès, 'ca' = valencià
let _anglesDocSeleccionat  = null;
let _anglesDocTraduïtBlob  = null;
let _anglesNomDocTraduït   = '';

function inverteixDireccio() {
  _anglesOrigen = _anglesOrigen === 'en' ? 'ca' : 'en';
  const labelOrigen     = document.getElementById('angles-llengua-origen');
  const labelDesti      = document.getElementById('angles-llengua-destí');
  const nota            = document.getElementById('angles-direccio-nota');
  const labelEntrada    = document.getElementById('angles-label-entrada');
  const labelSortida    = document.getElementById('angles-label-sortida');
  const placeholderEntrada = document.getElementById('angles-text-entrada');

  if (_anglesOrigen === 'en') {
    labelOrigen.textContent = 'Anglès';
    labelDesti.textContent  = 'Valencià';
    nota.innerHTML = 'Traduint de <strong>anglès</strong> a <strong>valencià</strong>';
    labelEntrada.textContent = 'Text en anglès';
    labelSortida.textContent = 'Traducció al valencià';
    placeholderEntrada.placeholder = 'Introdueix el text en anglès a traduir...';
  } else {
    labelOrigen.textContent = 'Valencià';
    labelDesti.textContent  = 'Anglès';
    nota.innerHTML = 'Traduint de <strong>valencià</strong> a <strong>anglès</strong>';
    labelEntrada.textContent = 'Text en valencià';
    labelSortida.textContent = 'Traducció a l\'anglès';
    placeholderEntrada.placeholder = 'Introdueix el text en valencià a traduir...';
  }

  // Neteja les àrees de text
  document.getElementById('angles-text-entrada').value = '';
  document.getElementById('angles-text-sortida').value = '';
  document.getElementById('angles-sortida-accions').style.display = 'none';
}

async function tradueixTextAngles() {
  const text = document.getElementById('angles-text-entrada').value.trim();
  if (!text) {
    mostraMissatgeAngles('error', 'Introdueix un text per a traduir.');
    return;
  }
  const btn = document.getElementById('btn-traduir-text-angles');
  btn.disabled = true;
  btn.textContent = '⏳ Traduint...';
  actualitzaProgress('angles', 20, 'Preparant la traducció...', '');

  try {
    // PENDENT D'IMPLEMENTACIÓ: motor EN↔CA
    actualitzaProgress('angles', 50, 'Traduint el text...', 'Motor EN↔CA en desenvolupament');
    await new Promise(r => setTimeout(r, 1000)); // Simulació
    actualitzaProgress('angles', 100, 'Completat', '');

    document.getElementById('angles-text-sortida').value =
      '[Traducció anglès ↔ valencià en desenvolupament. Properament disponible.]';
    document.getElementById('angles-sortida-accions').style.display = 'flex';
    mostraMissatgeAngles('info', 'ℹ️ La traducció anglès ↔ valencià s\'implementarà properament.');
    setTimeout(() => amagaProgress('angles'), 2000);
  } catch (e) {
    mostraMissatgeAngles('error', `Error: ${e.message}`);
    amagaProgress('angles');
  } finally {
    btn.disabled = false;
    btn.textContent = '🌐 Traduir text';
  }
}

function handleAnglesDocSelect(event) {
  const fitxer = event.target.files[0];
  if (!fitxer) return;
  const ext = fitxer.name.split('.').pop().toLowerCase();
  if (!['docx', 'pptx'].includes(ext)) {
    mostraMissatgeAngles('error', 'Només s\'admeten fitxers .docx i .pptx.');
    return;
  }
  _anglesDocSeleccionat = fitxer;
  _anglesDocTraduïtBlob = null;
  const icones = { docx: '📝', pptx: '📊' };
  document.getElementById('angles-doc-icona').textContent = icones[ext] || '📄';
  document.getElementById('angles-doc-nom').textContent   = fitxer.name;
  document.getElementById('angles-doc-mida').textContent  =
    `(${(fitxer.size / 1024).toFixed(0)} KB)`;
  document.getElementById('angles-doc-info').style.display    = 'flex';
  document.getElementById('angles-doc-accions').style.display = 'flex';
  document.getElementById('btn-descarrega-doc-angles').style.display = 'none';

  // Estadístiques PPTX (anàlisi al navegador sense servidor)
  const statsAd = document.getElementById('pptx-stats-ad');
  if (statsAd) { statsAd.style.display = 'none'; statsAd.innerHTML = ''; }
  if (ext === 'pptx' && statsAd && typeof analyzePptx === 'function') {
    analyzePptx(fitxer)
      .then(stats => renderPptxStats(stats, statsAd, fitxer.name))
      .catch(() => {});
  }

  event.target.value = '';
}

function eliminaAnglesDoc() {
  _anglesDocSeleccionat = null;
  _anglesDocTraduïtBlob = null;
  document.getElementById('angles-doc-info').style.display    = 'none';
  document.getElementById('angles-doc-accions').style.display = 'none';
  document.getElementById('angles-doc-input').value = '';
  const statsAd = document.getElementById('pptx-stats-ad');
  if (statsAd) { statsAd.style.display = 'none'; statsAd.innerHTML = ''; }
}

async function tradueixDocAngles() {
  if (!_anglesDocSeleccionat) {
    mostraMissatgeAngles('error', 'Apuja un document primer.');
    return;
  }
  const btn = document.getElementById('btn-traduir-doc-angles');
  btn.disabled = true;
  btn.textContent = '⏳ Traduint...';
  actualitzaProgress('angles', 10, 'Processant el document...', 'Motor EN↔CA en desenvolupament');

  // PENDENT D'IMPLEMENTACIÓ
  await new Promise(r => setTimeout(r, 1500));
  actualitzaProgress('angles', 100, 'Completat', '');
  mostraMissatgeAngles('info', 'ℹ️ La traducció de documents anglès ↔ valencià s\'implementarà properament.');
  setTimeout(() => amagaProgress('angles'), 2000);
  btn.disabled = false;
  btn.textContent = '🌐 Traduir document';
}

function descarregaAnglesDoc() {
  if (!_anglesDocTraduïtBlob) return;
  const urlBlob = URL.createObjectURL(_anglesDocTraduïtBlob);
  const a = document.createElement('a');
  a.href     = urlBlob;
  a.download = _anglesNomDocTraduït;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(urlBlob);
}

function copiaAngles() {
  const text = document.getElementById('angles-text-sortida').value;
  if (text) navigator.clipboard.writeText(text);
}

function mostraMissatgeAngles(tipus, text) {
  const el = document.getElementById('angles-missatge');
  el.textContent = text;
  el.className   = `correccio-missatge correccio-missatge-${tipus}`;
  el.style.display = 'block';
  if (tipus !== 'info') setTimeout(() => { el.style.display = 'none'; }, 5000);
}

// ═══════════════════════════════════════════════════════
// ÀUDIO: RETROALIMENTACIÓ SONORA (CANVI 4)
// ═══════════════════════════════════════════════════════

/**
 * Reprodueix un so de retroalimentació discret via Web Audio API.
 * @param {string} tipus - 'clic' | 'ok' | 'error'
 */
function reprodueixBeep(tipus) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    if (tipus === 'clic') {
      osc.type      = 'sine';
      osc.frequency.setValueAtTime(660, ctx.currentTime);
      gain.gain.setValueAtTime(0.07, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.08);
      osc.start();
      osc.stop(ctx.currentTime + 0.08);
    } else if (tipus === 'ok') {
      osc.type      = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.28);
      osc.start();
      osc.stop(ctx.currentTime + 0.28);
    } else if (tipus === 'error') {
      osc.type      = 'sawtooth';
      osc.frequency.setValueAtTime(220, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(110, ctx.currentTime + 0.25);
      gain.gain.setValueAtTime(0.07, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
      osc.start();
      osc.stop(ctx.currentTime + 0.25);
    }
    osc.onended = () => ctx.close();
  } catch (_) {
    // Navegadors sense Web Audio API — silenci
  }
}

// Clic suau en tots els botons i pestanyes
document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button, .nav-btn, .tab-btn, .btn-tradueix, .btn-apujar');
    if (btn && !btn.disabled) {
      reprodueixBeep('clic');
    }
  });
});
