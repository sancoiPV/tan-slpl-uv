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
  if (fitxer.size > 20 * 1024 * 1024) {
    alert('El fitxer supera el límit de 20 MB'); return;
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
  document.querySelectorAll('.seccio').forEach(s => s.classList.remove('vis'));
  document.querySelectorAll('.nav-btn, .tab-btn').forEach(b => b.classList.remove('act'));
  const seccio = document.getElementById('tab-' + id);
  if (seccio) seccio.style.display = 'block';
  const btn = document.querySelector('[data-tab="' + id + '"]');
  if (btn) btn.classList.add('act');
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

async function configurarGeminiKey() {
  const key = document.getElementById('gemini-api-key').value.trim();
  const status = document.getElementById('gemini-key-status');

  if (!key.startsWith('AIza')) {
    status.textContent = '✗ La clau no té el format correcte (ha de començar per AIza).';
    status.className = 'imatge-key-status error';
    return;
  }

  try {
    const url = await TAN.getUrlAvancada();
    const resp = await fetch(`${url}/configura-gemini`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key })
    });
    if (!resp.ok) throw new Error(`Error ${resp.status}`);
    status.textContent = '✓ Clau API configurada correctament per a aquesta sessió.';
    status.className = 'imatge-key-status ok';
    // Tanca el panell de configuració
    document.getElementById('imatge-config-panel').removeAttribute('open');
  } catch (e) {
    status.textContent = `✗ Error configurant la clau: ${e.message}`;
    status.className = 'imatge-key-status error';
  }
}

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
      <img src="${img.dataUrl}" alt="${escapeHtml(img.nom)}" class="imatge-preview-thumb">
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

    for (let i = 0; i < imatgesSeleccionades.length; i++) {
      const img = imatgesSeleccionades[i];
      mostraMissatgeImatge('info', `Traduint imatge ${i + 1} de ${imatgesSeleccionades.length}...`);

      const resp = await fetch(`${url}/tradueix-imatge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imatge_base64: img.base64,
          tipus_mime: img.tipus,
          prompt_addicional: promptAddicional,
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

    renderitzaResultats();
    document.getElementById('btn-descarregar-imatge').style.display = 'inline-flex';
    mostraMissatgeImatge('ok', `✓ ${imatgesTradudes.length} imatge${imatgesTradudes.length !== 1 ? 's' : ''} traduïda${imatgesTradudes.length !== 1 ? 's' : ''} correctament.`);

  } catch (e) {
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
               class="imatge-preview imatge-preview-gran">
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
          prompt_addicional: `Aquesta imatge ja ha estat traduïda al valencià. Aplica les modificacions següents sobre el text de la imatge sense canviar cap altre element visual:\n\n${modificacions}`,
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
