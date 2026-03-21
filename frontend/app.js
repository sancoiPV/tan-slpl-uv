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

    _dadesCorreccio = dades;
    renderitzaCorreccions(dades);

  } catch (e) {
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
  if (fitxer.size > 20 * 1024 * 1024) {
    mostraMissatgeCorreccio('error', 'El fitxer supera el límit de 20 MB.');
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

  event.target.value = '';
}

function eliminaDocument() {
  _documentSeleccionat  = null;
  _documentCorregitBlob = null;
  document.getElementById('correccio-doc-info').style.display      = 'none';
  document.getElementById('btn-corregir-document').style.display   = 'none';
  document.getElementById('btn-descarregar-document').style.display = 'none';
  document.getElementById('correccio-doc-input').value = '';
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

  try {
    const url      = await TAN.getUrlAvancada();
    const formData = new FormData();
    formData.append('fitxer', _documentSeleccionat);

    const resp = await fetch(`${url}/corregeix-document`, {
      method: 'POST',
      body:   formData,
    });

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

    document.getElementById('btn-descarregar-document').style.display = 'inline-flex';
    mostraMissatgeCorreccio('ok',
      '✅ Document corregit. Clica "⬇ Descarregar document corregit" per obtenir-lo.'
    );

  } catch (e) {
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
