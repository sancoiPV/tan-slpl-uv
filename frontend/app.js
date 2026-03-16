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
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('act'));
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
    await fetch(TAN.getUrl() + '/desa-postedicio', {
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
  } catch (e) { alert('Error en desar: ' + e.message); }
}

async function desaPostCorr() {
  const btn = document.getElementById('btnDesaC');
  try {
    await fetch(TAN.getUrl() + '/desa-postedicio', {
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
  } catch (e) { alert('Error en desar: ' + e.message); }
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
    const r = await fetch(TAN.getUrl() + '/recompte-paraules', {
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
    const r = await fetch(TAN.getUrl() + '/tradueix-document', {
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
    clearInterval(interval);
    pc.style.display = 'none';
    document.getElementById('fitxer-info-' + s).style.display = 'flex';
    alert('Error en la traducció: ' + e.message);
  }
}

// ─── CANVI 7 · Imatges ────────────────────────────────────────────────────────
function onDropImatge(e) {
  e.preventDefault();
  if (e.dataTransfer.files[0]) seleccionaImatge(e.dataTransfer.files[0]);
}

function seleccionaImatge(fitxer) {
  if (!fitxer) return;
  if (fitxer.size > 10 * 1024 * 1024) {
    alert('La imatge supera el límit de 10 MB'); return;
  }
  const reader = new FileReader();
  reader.onload = ev => {
    document.getElementById('imatge-img').src = ev.target.result;
    document.getElementById('imatge-meta').textContent =
      fitxer.name + ' · ' + (fitxer.size / 1024).toFixed(0) + ' KB';
    document.getElementById('imatge-preview').style.display  = 'block';
    document.getElementById('imatge-resultat').style.display = 'none';
  };
  reader.readAsDataURL(fitxer);
}

function ocrITradueix() {
  const res = document.getElementById('imatge-resultat');
  res.style.display = 'block';
  res.textContent   =
    'Funcionalitat pendent d\'integració OCR. Properament disponible.';
}

// ─── Inici ────────────────────────────────────────────────────────────────────
comprova();
setInterval(comprova, 30000);

