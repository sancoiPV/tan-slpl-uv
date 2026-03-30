'use strict';

// ─── Autenticació ────────────────────────────────────────────────────────────
let _authToken = localStorage.getItem('tan_token') || '';
let _authUser  = JSON.parse(localStorage.getItem('tan_user') || 'null');

async function loginUsuari() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errorEl  = document.getElementById('login-error');

  if (!username || !password) {
    errorEl.textContent = 'Introdueix l\'usuari i la contrasenya.';
    errorEl.style.display = 'block';
    return;
  }

  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      errorEl.textContent = err.detail || 'Error d\'autenticació.';
      errorEl.style.display = 'block';
      return;
    }

    const dades = await resp.json();
    _authToken = dades.token;
    _authUser  = dades;
    localStorage.setItem('tan_token', _authToken);
    localStorage.setItem('tan_user', JSON.stringify(_authUser));

    document.getElementById('login-overlay').style.display = 'none';

    // Mostra "El meu compte" per a TOTS els usuaris
    const btnCompte = document.getElementById('btn-tab-admin');
    if (btnCompte) btnCompte.style.display = '';

    // Mostra "Gestió d'usuaris" NOMÉS per a admin
    const btnGestio = document.getElementById('btn-tab-gestio');
    if (btnGestio) {
      btnGestio.style.display = (dades.rol === 'admin') ? '' : 'none';
    }

  } catch (e) {
    errorEl.textContent = 'No s\'ha pogut connectar al servidor.';
    errorEl.style.display = 'block';
  }
}

async function verificaSessio() {
  if (!_authToken) {
    document.getElementById('login-overlay').style.display = 'flex';
    return;
  }
  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/validar', {
      headers: { 'Authorization': 'Bearer ' + _authToken },
    });
    if (!resp.ok) throw new Error('Sessió expirada');
    const dades = await resp.json();
    _authUser = dades;
    document.getElementById('login-overlay').style.display = 'none';
    // Mostra "El meu compte" per a TOTS els usuaris
    const btnCompte = document.getElementById('btn-tab-admin');
    if (btnCompte) btnCompte.style.display = '';
    // Mostra "Gestió d'usuaris" NOMÉS per a admin
    const btnGestio = document.getElementById('btn-tab-gestio');
    if (btnGestio) {
      btnGestio.style.display = (dades.rol === 'admin') ? '' : 'none';
    }
  } catch (e) {
    _authToken = '';
    localStorage.removeItem('tan_token');
    localStorage.removeItem('tan_user');
    document.getElementById('login-overlay').style.display = 'flex';
  }
}

async function logoutUsuari() {
  try {
    const baseUrl = await TAN.getUrlAvancada();
    await fetch(baseUrl + '/auth/logout', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + _authToken },
    });
  } catch (e) { /* ignora errors de xarxa */ }
  _authToken = '';
  _authUser  = null;
  localStorage.removeItem('tan_token');
  localStorage.removeItem('tan_user');
  document.getElementById('login-overlay').style.display = 'flex';
}

// ─── Admin: gestió d'usuaris ─────────────────────────────────────────────────

async function carregaUsuarisAdmin() {
  const contenidor = document.getElementById('admin-llista-usuaris');
  if (!contenidor) return;
  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/usuaris', {
      headers: { 'Authorization': 'Bearer ' + _authToken },
    });
    if (!resp.ok) throw new Error('Error carregant usuaris');
    const usuaris = await resp.json();

    let html = '<table style="width:100%; border-collapse:collapse; font-size:14px; table-layout:fixed;">';
    html += '<colgroup><col style="width:20%"><col style="width:35%"><col style="width:15%"><col style="width:30%"></colgroup>';
    html += '<tr style="background:#002E52; color:white;">'
         + '<th style="padding:10px 12px; text-align:left;">Usuari</th>'
         + '<th style="padding:10px 12px; text-align:left;">Nom</th>'
         + '<th style="padding:10px 12px; text-align:center;">Rol</th>'
         + '<th style="padding:10px 12px; text-align:center;">Accions</th></tr>';
    for (const u of usuaris) {
      html += '<tr style="border-bottom:1px solid #ddd;">';
      html += '<td style="padding:10px 12px; text-align:left;">' + escapeHtml(u.username) + '</td>';
      html += '<td style="padding:10px 12px; text-align:left;">' + escapeHtml(u.nom) + '</td>';
      html += '<td style="padding:10px 12px; text-align:center;">' + escapeHtml(u.rol) + '</td>';
      html += '<td style="padding:10px 12px; text-align:center;">';
      if (u.username !== 'coitor') {
        html += '<button onclick="eliminaUsuariAdmin(\'' + escapeHtml(u.username) + '\')" style="background:#d32f2f; color:white; border:none; padding:5px 12px; border-radius:4px; cursor:pointer; font-size:12px;">Eliminar</button>';
      } else {
        html += '<span style="color:#6A7A9B; font-size:12px; font-style:italic;">Admin principal</span>';
      }
      html += '</td></tr>';
    }
    html += '</table>';
    contenidor.innerHTML = html;
  } catch (e) {
    contenidor.textContent = 'Error: ' + e.message;
  }
}

async function crearUsuariAdmin() {
  const username = document.getElementById('admin-nou-username').value.trim();
  const password = document.getElementById('admin-nou-password').value;
  const nom      = document.getElementById('admin-nou-nom').value.trim();
  const msgEl    = document.getElementById('admin-crear-msg');

  if (!username || !password) {
    msgEl.textContent = 'Usuari i contrasenya obligatoris.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }

  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/usuaris', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + _authToken,
      },
      body: JSON.stringify({ username, password, nom, rol: 'user' }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Error creant usuari');
    }
    msgEl.textContent = 'Usuari creat correctament.';
    msgEl.style.color = '#27500A';
    msgEl.style.display = 'block';
    document.getElementById('admin-nou-username').value = '';
    document.getElementById('admin-nou-password').value = '';
    document.getElementById('admin-nou-nom').value = '';
    carregaUsuarisAdmin();
  } catch (e) {
    msgEl.textContent = 'Error: ' + e.message;
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
  }
}

async function eliminaUsuariAdmin(username) {
  if (!confirm('Segur que voleu eliminar l\'usuari "' + username + '"?')) return;
  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/usuaris/' + username, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + _authToken },
    });
    if (!resp.ok) throw new Error('Error eliminant usuari');
    carregaUsuarisAdmin();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ─── Gestió d'usuaris (pestanya separada per a admin) ────────────────────────

async function carregaUsuarisGestio() {
  const contenidor = document.getElementById('gestio-llista-usuaris');
  if (!contenidor) return;
  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/usuaris', {
      headers: { 'Authorization': 'Bearer ' + _authToken },
    });
    if (!resp.ok) throw new Error('Error carregant usuaris');
    const usuaris = await resp.json();

    let html = '<table style="width:100%; border-collapse:collapse; font-size:14px; table-layout:fixed;">';
    html += '<colgroup><col style="width:20%"><col style="width:35%"><col style="width:15%"><col style="width:30%"></colgroup>';
    html += '<tr style="background:#002E52; color:white;">'
         + '<th style="padding:10px 12px; text-align:left;">Usuari</th>'
         + '<th style="padding:10px 12px; text-align:left;">Nom</th>'
         + '<th style="padding:10px 12px; text-align:center;">Rol</th>'
         + '<th style="padding:10px 12px; text-align:center;">Accions</th></tr>';
    for (const u of usuaris) {
      html += '<tr style="border-bottom:1px solid #ddd;">';
      html += '<td style="padding:10px 12px; text-align:left;">' + escapeHtml(u.username) + '</td>';
      html += '<td style="padding:10px 12px; text-align:left;">' + escapeHtml(u.nom || '') + '</td>';
      html += '<td style="padding:10px 12px; text-align:center;">' + escapeHtml(u.rol) + '</td>';
      html += '<td style="padding:10px 12px; text-align:center;">';
      if (u.username !== 'coitor') {
        html += '<button onclick="eliminaUsuariGestio(\'' + escapeHtml(u.username) + '\')" style="background:#d32f2f; color:white; border:none; padding:5px 12px; border-radius:4px; cursor:pointer; font-size:12px; margin-right:4px;">Eliminar</button>';
      } else {
        html += '<span style="color:#6A7A9B; font-size:12px; font-style:italic;">Admin principal</span>';
      }
      html += '</td></tr>';
    }
    html += '</table>';
    contenidor.innerHTML = html;
  } catch (e) {
    contenidor.textContent = 'Error: ' + e.message;
  }
}

async function crearUsuariGestio() {
  const username = document.getElementById('gestio-nou-username').value.trim();
  const password = document.getElementById('gestio-nou-password').value;
  const nom      = document.getElementById('gestio-nou-nom').value.trim();
  const msgEl    = document.getElementById('gestio-crear-msg');

  if (!username || !password) {
    msgEl.textContent = 'Usuari i contrasenya obligatoris.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }

  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/usuaris', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + _authToken,
      },
      body: JSON.stringify({ username, password, nom, rol: 'user' }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Error creant usuari');
    }
    msgEl.textContent = 'Usuari creat correctament.';
    msgEl.style.color = '#27500A';
    msgEl.style.display = 'block';
    document.getElementById('gestio-nou-username').value = '';
    document.getElementById('gestio-nou-password').value = '';
    document.getElementById('gestio-nou-nom').value = '';
    carregaUsuarisGestio();
  } catch (e) {
    const missatge = typeof e === 'string' ? e : (e.message || JSON.stringify(e));
    msgEl.textContent = 'Error: ' + missatge;
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
  }
}

async function eliminaUsuariGestio(username) {
  if (!confirm('Segur que voleu eliminar l\'usuari "' + username + '"?')) return;
  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/usuaris/' + username, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + _authToken },
    });
    if (!resp.ok) throw new Error('Error eliminant usuari');
    carregaUsuarisGestio();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ─── Canvi de contrasenya propi ──────────────────────────────────────────────

async function canviaPasswordPropia() {
  const actual   = document.getElementById('perfil-password-actual').value;
  const nova     = document.getElementById('perfil-password-nova').value;
  const confirma = document.getElementById('perfil-password-confirma').value;
  const msgEl    = document.getElementById('perfil-password-msg');

  if (!actual || !nova || !confirma) {
    msgEl.textContent = 'Tots els camps són obligatoris.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }
  if (nova !== confirma) {
    msgEl.textContent = 'Les contrasenyes noves no coincideixen.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }
  if (nova.length < 4) {
    msgEl.textContent = 'La contrasenya ha de tindre almenys 4 caràcters.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }

  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/auth/canvi-password', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + _authToken,
      },
      body: JSON.stringify({
        password_actual: actual,
        password_nova: nova,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Error canviant la contrasenya');
    }

    msgEl.textContent = 'Contrasenya actualitzada correctament.';
    msgEl.style.color = '#27500A';
    msgEl.style.display = 'block';
    document.getElementById('perfil-password-actual').value = '';
    document.getElementById('perfil-password-nova').value = '';
    document.getElementById('perfil-password-confirma').value = '';

  } catch (e) {
    const missatge = typeof e === 'string' ? e : (e.message || JSON.stringify(e));
    msgEl.textContent = 'Error: ' + missatge;
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
  }
}

// ─── Estat global ─────────────────────────────────────────────────────────────
let traduitMemoria   = '';
let fitxerActualTd   = null;   // fitxer pendent a "Traducció de documents"
let fitxerActualCd   = null;   // fitxer pendent a "Correcció de documents"

// Motor seleccionat: 'aina' (per defecte), 'apertium' o 'claude'
let _motorActiu = 'aina';
// Retrocompatibilitat: _motorText i _motorDocs apunten al motor actiu global
let _motorText = 'aina';
let _motorDocs = 'aina';
// Direcció EN↔VA: 'en_va' (per defecte) o 'va_en'
let _anglesDireccio = 'en_va';
// Dades de correccions per a la pestanya de correcció
let _dadesCorreccioV2 = null;

/**
 * Canvia el motor de traducció (selector de 3 opcions).
 * @param {string} motor - 'aina', 'apertium' o 'claude'
 */
function canviaMotor3(motor) {
  _motorActiu = motor;
  _motorText = motor;
  _motorDocs = motor;

  // Actualitza tots els botons de motor (a les dues pestanyes)
  document.querySelectorAll('.motor-btn').forEach(btn => {
    btn.classList.remove('motor-btn-actiu');
    if (btn.getAttribute('data-motor') === motor) {
      btn.classList.add('motor-btn-actiu');
    }
  });

  // Textos descriptius segons el motor
  const textos = {
    'aina': 'Eina de traducció automàtica neuronal basada en el motor TAN aina-translator-ca-es desenvolupat pel LangTechLab del BSC-CNS en el marc del Projecte Aina i afinat contínuament pel Servei de Llengües i Política Lingüística de la UV.',
    'apertium': 'Traducció automàtica basada en regles amb Apertium (Universitat d\'Alacant). Motor de codi obert amb transferència morfològica castellà → català (valencià).',
    'claude': 'Traducció castellà → valencià amb Claude Sonnet. Aplica les normes de valencià estàndard universitari (Criteris lingüístics de les universitats valencianes).',
  };

  const descText = document.getElementById('motor-descripcio-text');
  const descDocs = document.getElementById('motor-descripcio-docs');
  if (descText) descText.textContent = textos[motor] || '';
  if (descDocs) descDocs.textContent = textos[motor] || '';
}

// Retrocompatibilitat
function canviaMotor(pestanya, esClaude) {
  canviaMotor3(esClaude ? 'claude' : 'aina');
}
function seleccionaMotor(pestanya, motor) {
  canviaMotor3(motor);
}

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

// (Funcions actualCompCorr i actualCompDestiCorr eliminades — la secció antiga de correcció ja no existeix)

// ─── Neteja ───────────────────────────────────────────────────────────────────
function neteja() {
  document.getElementById('origen').value = '';
  document.getElementById('desti').value  = '';
  document.getElementById('temps').textContent = '';
  document.getElementById('btnDesa').style.display = 'none';
  actualComp();
  actualCompDesti();
}

// (Funció netejaCorr eliminada — la secció antiga de correcció ja no existeix)

// ─── Traducció de text ────────────────────────────────────────────────────────
async function tradueixText() {
  const textOriginal = document.getElementById('origen').value.trim();
  if (!textOriginal) return;
  const btn = document.getElementById('btnT');
  btn.disabled = true;
  btn.textContent = '⏳';
  try {
    const t0 = performance.now();
    let traduccio, temps_ms;

    if (_motorText === 'apertium') {
      // Traducció amb Apertium (API pública)
      const formData = new URLSearchParams();
      formData.append('langpair', 'es|ca_valencia');
      formData.append('q', textOriginal);
      formData.append('markUnknown', 'no');
      const resp = await fetch('https://apertium.org/apy/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      });
      const dades = await resp.json();
      traduccio = dades.responseData?.translatedText || '';
      temps_ms = Math.round(performance.now() - t0);
    } else if (_motorText === 'claude') {
      // Traducció amb Claude Sonnet
      const baseUrl = await TAN.getUrlAvancada();
      const resp = await fetch(`${baseUrl}/tradueix-claude`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textOriginal }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || err.error || 'Error del servidor');
      }
      const dades = await resp.json();
      traduccio = dades.translation;
      temps_ms = dades.temps_ms || Math.round(performance.now() - t0);
    } else {
      // Traducció amb motor AINA (comportament original)
      traduccio = await TAN.translate(textOriginal, 'es', 'ca');
      temps_ms = Math.round(performance.now() - t0);
    }

    const dest = document.getElementById('desti');
    dest.value = traduccio;
    traduitMemoria = traduccio;
    document.getElementById('temps').textContent = temps_ms + ' ms';
    dest.readOnly = true;
    actualCompDesti();
  } catch (e) {
    document.getElementById('desti').value = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Tradueix';
  }
}

// (Funció corregeixText antiga eliminada — substituïda per la versió v2 a la secció CORRECCIÓ)

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

// (Funcions editaCorr i copiaCorr eliminades — la secció antiga de correcció ja no existeix)

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

// (Funció desaPostCorr eliminada — la secció antiga de correcció ja no existeix)

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
  if (!['docx', 'pptx', 'rtf'].includes(ext)) {
    alert('Format no suportat. Usa .docx, .pptx o .rtf'); return;
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

  // Recompte client-side per a .docx i .rtf (mostra el resultat immediatament, sense backend).
  // Per a .docx i .rtf NO cridem el backend: el recompte client-side és fiable i evita que
  // una resposta tardana del servidor sobreescriga el resultat ja mostrat (race condition).
  if (['docx', 'rtf'].includes(ext) && typeof contarParaulesDocument === 'function') {
    contarParaulesDocument(fitxer).then(n => {
      document.getElementById('fitxer-meta-' + s).innerHTML =
        (fitxer.size / 1024).toFixed(0) + ' KB · <strong>' +
        n.toLocaleString('ca-ES') + ' paraules</strong>';
    }).catch(() => {
      document.getElementById('fitxer-meta-' + s).textContent =
        (fitxer.size / 1024).toFixed(0) + ' KB';
    });
  }

  // Recompte de paraules via backend — només per a .pptx
  // (per a .docx i .rtf el recompte client-side és suficient i evita conflictes)
  if (ext === 'pptx') {
    try {
      const form = new FormData();
      form.append('fitxer', fitxer);
      const r = await fetch(await TAN.getUrlAvancada() + '/recompte-paraules', {
        method: 'POST', body: form
      });
      if (r.ok) {
        const d = await r.json();
        document.getElementById('fitxer-meta-' + s).innerHTML =
          (fitxer.size / 1024).toFixed(0) + ' KB · <strong>' +
          d.paraules.toLocaleString() + ' paraules</strong>';
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

  // Mostra el selector de domini quan es carrega un fitxer per a traducció
  if (mode === 'traduccio') mostraDocDominiSelector();

  // Mostra/amaga el botó d'extracció d'imatges (només en traducció i per .docx/.pptx)
  if (mode === 'traduccio') {
    const btnExtreu = document.getElementById('btn-extreu-imatges-doc');
    if (btnExtreu) btnExtreu.style.display = ['docx', 'pptx'].includes(ext) ? 'inline-block' : 'none';
    const msgImatges = document.getElementById('missatge-imatges-doc');
    if (msgImatges) msgImatges.style.display = 'none';
  }

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
        document.getElementById('fitxer-meta-' + s).innerHTML =
          (fitxer.size / 1024).toFixed(0) + ' KB · <strong>' +
          stats.totalWords.toLocaleString('ca-ES') + ' paraules (incl. notes)</strong>';
      })
      .catch(() => { /* en cas d'error, simplement no mostrem les estadístiques */ });
  }
}

// ─── Extreu imatges amb text d'un document .docx/.pptx ───────────────────────
async function extreuITradueIxImatges() {
  const fitxer = fitxerActualTd;
  if (!fitxer) return;

  const btn = document.getElementById('btn-extreu-imatges-doc');
  const msgDiv = document.getElementById('missatge-imatges-doc');
  btn.disabled = true;
  btn.textContent = '⏳ Analitzant imatges...';

  try {
    const baseUrl = await TAN.getUrlAvancada();
    const formData = new FormData();
    formData.append('fitxer', fitxer);

    const resp = await fetch(baseUrl + '/extreu-imatges-document', {
      method: 'POST',
      body: formData,
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      if (resp.status === 404) {
        msgDiv.textContent = 'No s\'han trobat imatges amb text real en aquest document.';
        msgDiv.style.display = 'block';
        return;
      }
      if (resp.status === 503) {
        msgDiv.textContent = 'El servei OCR (Tesseract) no està disponible.';
        msgDiv.style.display = 'block';
        return;
      }
      throw new Error(err.detail || 'Error del servidor');
    }

    const blob = await resp.blob();

    // Compta imatges: intenta header, fallback compta del ZIP
    let numImatges = parseInt(resp.headers.get('X-Num-Imatges') || '0');
    if (!numImatges || isNaN(numImatges)) {
      try {
        const JSZipLib = window.JSZip;
        if (JSZipLib) {
          const zipTemp = await JSZipLib.loadAsync(blob.slice());
          const manifestFile = zipTemp.files['_manifest.json'];
          if (manifestFile) {
            const manifest = JSON.parse(await manifestFile.async('string'));
            numImatges = manifest.num_imatges || 0;
          }
          if (!numImatges) {
            numImatges = Object.keys(zipTemp.files).filter(
              n => /\.(png|jpg|jpeg|gif|bmp|tiff?)$/i.test(n)
            ).length;
          }
        }
      } catch (e) { numImatges = 0; }
    }

    // Descarrega el ZIP
    const nomZip = resp.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1]
                   || 'Imatges amb text.zip';
    const urlBlob = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = urlBlob;
    a.download = nomZip;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(urlBlob);

    // Missatge informatiu
    const numStr = numImatges === 1 ? '1 imatge' : numImatges + ' imatges';
    msgDiv.innerHTML = '🖼 <strong>' + numStr + ' amb text descarregades.</strong> '
      + 'Per a traduir-les al valencià, apugeu-les a la pestanya '
      + '<a href="#" onclick="mostra(\'imatges\', document.querySelector(\'button.nav-btn'
      + '[onclick*=imatges]\')); return false;" '
      + 'style="color:var(--uv-blau-accent,#0082C5);text-decoration:underline;font-weight:600;">'
      + 'Traducció d\'imatges amb text</a>.';
    msgDiv.style.display = 'block';

  } catch (e) {
    if (msgDiv) {
      msgDiv.textContent = '❌ Error: ' + e.message;
      msgDiv.style.display = 'block';
    }
  } finally {
    btn.disabled = false;
    btn.textContent = '🖼 Descarregar imatges amb text';
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
  // Amaga botó d'extracció d'imatges durant la traducció
  const _btnExtreu = document.getElementById('btn-extreu-imatges-doc');
  if (_btnExtreu) _btnExtreu.style.display = 'none';
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

  // Apertium no té API per a documents: obre la pàgina en una altra pestanya
  if (mode === 'traduccio' && _motorDocs === 'apertium') {
    clearInterval(interval);
    pc.style.display = 'none';
    document.getElementById('fitxer-info-' + s).style.display = 'flex';
    window.open('https://apertium.ua.es/docs.php', '_blank');
    alert('Apertium no permet traduir documents via API. S\'ha obert la pàgina d\'Apertium per a documents en una altra pestanya. Apugeu-hi el document manualment.');
    return;
  }

  try {
    // Determinar endpoint segons motor seleccionat
    let endpoint = '/tradueix-document';
    if (mode === 'traduccio' && _motorDocs === 'claude') {
      endpoint = '/tradueix-document-claude';
    }
    const r = await fetch(await TAN.getUrlAvancada() + endpoint, {
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

  // Mostra el botó d'extracció d'imatges si el document és .docx/.pptx
  // L'extracció és manual — l'usuari la llança amb el botó.
  if (mode === 'traduccio' && ['docx', 'pptx'].includes(ext)) {
    const btnExtreu = document.getElementById('btn-extreu-imatges-doc');
    if (btnExtreu) btnExtreu.style.display = 'inline-block';
  }
}

// ─── SUBSTITUÏT per la implementació completa de Gemini (vegeu més avall) ────
// Les funcions onDropImatge / seleccionaImatge / ocrITradueix han estat
// reemplaçades per handleImageDrop / handleImageSelect / tradueixImatges.

// ─── Inici ────────────────────────────────────────────────────────────────────
verificaSessio();
comprova();
setInterval(comprova, 30000);

// Inicialitza estat visual dels selectors de motor (AINA per defecte)
(function inicialitzaToggles() {
  canviaMotor3('aina');
})();

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
  if (id === 'admin-usuaris') {
    // Mostra les dades de l'usuari (per a tots, inclòs l'admin)
    document.getElementById('perfil-username').textContent = _authUser ? _authUser.username : '';
    document.getElementById('perfil-nom').textContent = _authUser ? (_authUser.nom || '') : '';
  }
  if (id === 'gestio-usuaris') {
    carregaUsuarisGestio();
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
    // Sincronitza el selector d'extracció amb els mateixos dominis
    const selectExtraccio = document.getElementById('glossari-domini-extraccio');
    if (selectExtraccio && selectExtraccio.options.length <= 1) {
      data.dominis.forEach(domini => {
        const opt = document.createElement('option');
        opt.value = domini;
        opt.textContent = domini;
        selectExtraccio.appendChild(opt);
      });
    }
    // Sincronitza el selector de domini de correcció
    const selectorCorreccio = document.getElementById('correccio-domini');
    if (selectorCorreccio) {
      selectorCorreccio.innerHTML = select.innerHTML;
    }
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
  const btnTotsZip = document.getElementById('btn-descarregar-totes-imatges');
  if (btnTotsZip) btnTotsZip.style.display = 'none';

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
    const btnZip = document.getElementById('btn-descarregar-totes-imatges');
    if (btnZip) btnZip.style.display = 'inline-flex';
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

function descarregaImatgesTradudes() {
  if (imatgesTradudes.length === 0) {
    mostraMissatgeImatge('error', 'No hi ha imatges traduïdes per descarregar.');
    return;
  }
  imatgesTradudes.forEach((img, i) => {
    setTimeout(() => descarregaImatgeIndividual(i), i * 300);
  });
}

// Descarrega totes les imatges traduïdes empaquetades en un fitxer .zip
async function descarregaTolesImatgesZip() {
  if (imatgesTradudes.length === 0) {
    mostraMissatgeImatge('error', 'No hi ha imatges traduïdes per descarregar.');
    return;
  }

  const btn = document.getElementById('btn-descarregar-totes-imatges');
  const textOriginal = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Generant ZIP...'; }

  try {
    const zip = new JSZip();

    for (let i = 0; i < imatgesTradudes.length; i++) {
      const img = imatgesTradudes[i];
      try {
        // Convertir base64 a Uint8Array per afegir-la al zip
        const byteChars = atob(img.base64);
        const byteArray = new Uint8Array(byteChars.length);
        for (let j = 0; j < byteChars.length; j++) {
          byteArray[j] = byteChars.charCodeAt(j);
        }
        zip.file(img.nom, byteArray);
      } catch (e) {
        console.warn(`Error afegint "${img.nom}" al zip:`, e);
        mostraMissatgeImatge('error', `No s'ha pogut afegir "${img.nom}" al zip.`);
      }
    }

    const blob = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'imatges_traduides.zip';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

  } catch (e) {
    mostraMissatgeImatge('error', `Error generant el zip: ${e.message}`);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = textOriginal; }
  }
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

    // Crida al endpoint v2 (correcció millorada amb JSON estructurat)
    const dominiCorreccio = document.getElementById('correccio-domini')?.value || '';
    const resp = await fetch(`${url}/corregeix-v2`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        text:              text,
        usar_languagetool: usarLT,
        usar_claude:       usarClaude,
        domini:            dominiCorreccio,
      }),
    });

    const dades = await resp.json();

    if (!resp.ok) {
      throw new Error(dades.detail || `Error ${resp.status}`);
    }

    actualitzaProgress('correccio', 100, 'Correcció completada!', '');
    setTimeout(() => amagaProgress('correccio'), 2000);

    _dadesCorreccio = dades;
    _dadesCorreccioV2 = dades;
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

  // Resum (compatible amb v1:string i v2:objecte)
  const resumBloc = document.getElementById('correccio-resum-bloc');
  if (dades.resum) {
    const resumEl = document.getElementById('correccio-resum-text');
    if (typeof dades.resum === 'string') {
      resumEl.textContent = dades.resum;
    } else if (typeof dades.resum === 'object' && dades.resum.diagnostic) {
      resumEl.textContent = dades.resum.diagnostic;
    } else {
      resumEl.textContent = '';
    }
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

  // Taula detallada (format v2 amb correccions estructurades)
  const correccionsV2 = dades.correccions_claude || dades.correccions || [];
  const taulaCont = document.getElementById('correccio-taula-contingut');
  const resumCont = document.getElementById('correccio-resum-estadistic');
  const badgeTaula = document.getElementById('badge-taula');

  if (taulaCont && Array.isArray(correccionsV2) && correccionsV2.length > 0) {
    taulaCont.innerHTML = generaTaulaCorreccions(correccionsV2);
    if (badgeTaula) badgeTaula.textContent = correccionsV2.length;
  } else if (taulaCont) {
    taulaCont.innerHTML = '<p class="correccio-buit">Cap correcció estructurada disponible.</p>';
    if (badgeTaula) badgeTaula.textContent = '0';
  }

  // Resum estadístic (format v2)
  if (resumCont && dades.resum && typeof dades.resum === 'object') {
    resumCont.innerHTML = generaResumCorreccions(dades.resum);
  } else if (resumCont) {
    resumCont.innerHTML = '';
  }

  // Activa la pestanya de text i mostra resultats
  activaCorreccioTab('text');
  document.getElementById('correccio-resultats').style.display = 'block';
}

function renderitzaLlistaClaude(correccions) {
  const el = document.getElementById('correccio-cl-llista');
  if (!correccions || correccions.length === 0) {
    el.innerHTML = '<p class="correccio-buit">Cap correcció addicional per Claude Sonnet. ✅</p>';
    return;
  }
  el.innerHTML = correccions.map((c, i) => {
    // Compatibilitat v1 (tipus/corregit) i v2 (categoria/correccio)
    const cat = c.categoria || c.tipus || '';
    const corregit = c.correccio || c.corregit || '';
    const catLower = cat.toLowerCase();
    // Mapejar categories v2 (SINT/MORF/LÈX/ORTO) a classes CSS
    const catCSS = cat.match(/^(SINT|MORF|L[ÈE]X|ORTO)$/i)
      ? `cat-badge cat-${cat.toUpperCase().replace('È','E')}`
      : `correccio-tipus-badge correccio-tipus-${catLower || 'estil'}`;
    return `
    <div class="correccio-item correccio-item-cl" data-tipus="${escapeHtmlC(catLower)}">
      <div class="correccio-item-cap">
        <span class="${catCSS}">${escapeHtmlC(cat || '—')}</span>
        <span class="correccio-item-original">${escapeHtmlC(c.original || '')}</span>
        ${corregit ? `→ <span class="correccio-item-corregit">${escapeHtmlC(corregit)}</span>` : ''}
      </div>
      <div class="correccio-item-justificacio">${escapeHtmlC(c.justificacio || '')}</div>
    </div>`;
  }).join('');
}

// ── Filtra correccions Claude per tipus ───────────────────────────────────

function filtraCorreccions() {
  if (!_dadesCorreccio) return;
  const filtre = document.getElementById('correccio-filtre-tipus').value.toLowerCase();
  const correccions = (_dadesCorreccio.correccions_claude || []).filter(c => {
    if (!filtre) return true;
    // Compatibilitat v1 (tipus) i v2 (categoria)
    const cat = (c.categoria || c.tipus || '').toLowerCase();
    return cat === filtre;
  });
  renderitzaLlistaClaude(correccions);
}

// ── Pestanyes de resultats ─────────────────────────────────────────────────

function activaCorreccioTab(id) {
  const panels = ['text', 'lt', 'cl', 'taula'];
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
  activaCorreccioTab('text');
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
  if (!['docx', 'pptx', 'rtf'].includes(ext)) {
    mostraMissatgeCorreccio('error', 'Només s\'admeten fitxers .docx, .pptx i .rtf.');
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

  const icones = { docx: '📝', pptx: '📊', rtf: '📄' };
  document.getElementById('correccio-doc-icona').textContent = icones[ext] || '📄';
  document.getElementById('correccio-doc-nom').textContent   = fitxer.name;
  document.getElementById('correccio-doc-mida').textContent  =
    `(${(fitxer.size / 1024).toFixed(0)} KB)`;
  document.getElementById('correccio-doc-info').style.display      = 'flex';
  document.getElementById('btn-corregir-document').style.display   = 'inline-flex';
  document.getElementById('btn-descarregar-document').style.display = 'none';

  // Recompte client-side per a .docx i .rtf
  if (['docx', 'rtf'].includes(ext) && typeof contarParaulesDocument === 'function') {
    contarParaulesDocument(fitxer).then(n => {
      document.getElementById('correccio-doc-mida').innerHTML =
        `(${(fitxer.size / 1024).toFixed(0)} KB · <strong>${n.toLocaleString('ca-ES')} paraules</strong>)`;
    }).catch(() => {});
  }

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

  // Simula progrés incremental suau mentre es corregeix
  let _progresActual = 10;
  let _progressInterval = setInterval(() => {
    if (_progresActual < 30) _progresActual += 3;
    else if (_progresActual < 60) _progresActual += 2;
    else if (_progresActual < 85) _progresActual += 1;
    else if (_progresActual < 95) _progresActual += 0.2;
    else if (_progresActual < 99) _progresActual += 0.05;
    actualitzaProgress('correccio', _progresActual, 'Corregint el document...', 'Aplicant normes AVL i Gramàtica Zero');
  }, 1500);

  try {
    const url      = await TAN.getUrlAvancada();
    const formData = new FormData();
    formData.append('fitxer', _documentSeleccionat);
    const dominiCorreccio = document.getElementById('correccio-domini')?.value || '';
    if (dominiCorreccio) formData.append('domini', dominiCorreccio);

    // Timeout de 10 minuts per a documents grans
    const _controladorAbort = new AbortController();
    const _timerAbort = setTimeout(() => _controladorAbort.abort(), 600000);

    const resp = await fetch(`${url}/corregeix-document`, {
      method: 'POST',
      body:   formData,
      signal: _controladorAbort.signal,
    });

    clearTimeout(_timerAbort);

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
    const msg = e.name === 'AbortError'
      ? 'La correcció ha superat el temps màxim (10 minuts). Proveu amb un document més curt.'
      : e.message;
    mostraMissatgeCorreccio('error', `Error en la correcció del document: ${msg}`);
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

// (Variable _anglesOrigen i primera versió d'inverteixDireccio eliminades — substituïdes per la versió v2 al final del fitxer que usa _anglesDireccio)
let _anglesDocSeleccionat  = null;
let _anglesDocTraduïtBlob  = null;
let _anglesNomDocTraduït   = '';

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
    actualitzaProgress('angles', 50, 'Traduint el text amb Claude Sonnet...', '');

    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(`${baseUrl}/tradueix-angles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, direccio: _anglesDireccio }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || err.error || 'Error del servidor');
    }

    const dades = await resp.json();
    actualitzaProgress('angles', 100, `Completat en ${dades.temps_ms || 0} ms`, '');

    document.getElementById('angles-text-sortida').value = dades.translation;
    document.getElementById('angles-sortida-accions').style.display = 'flex';
    mostraMissatgeAngles('info', `Traducció completada (${dades.temps_ms || 0} ms, ${dades.paraules || 0} paraules)`);
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
  if (!['docx', 'pptx', 'rtf'].includes(ext)) {
    mostraMissatgeAngles('error', 'Només s\'admeten fitxers .docx, .pptx i .rtf.');
    return;
  }
  _anglesDocSeleccionat = fitxer;
  _anglesDocTraduïtBlob = null;
  const icones = { docx: '📝', pptx: '📊', rtf: '📄' };
  document.getElementById('angles-doc-icona').textContent = icones[ext] || '📄';
  document.getElementById('angles-doc-nom').textContent   = fitxer.name;
  document.getElementById('angles-doc-mida').textContent  =
    `(${(fitxer.size / 1024).toFixed(0)} KB)`;
  document.getElementById('angles-doc-info').style.display    = 'flex';
  document.getElementById('angles-doc-accions').style.display = 'flex';
  document.getElementById('btn-descarrega-doc-angles').style.display = 'none';

  // Recompte client-side per a .docx i .rtf
  if (['docx', 'rtf'].includes(ext) && typeof contarParaulesDocument === 'function') {
    contarParaulesDocument(fitxer).then(n => {
      document.getElementById('angles-doc-mida').innerHTML =
        `(${(fitxer.size / 1024).toFixed(0)} KB · <strong>${n.toLocaleString('ca-ES')} paraules</strong>)`;
    }).catch(() => {});
  }

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
  actualitzaProgress('angles', 10, 'Processant el document amb Claude Sonnet...', '');

  try {
    const formData = new FormData();
    formData.append('fitxer', _anglesDocSeleccionat);
    formData.append('direccio', _anglesDireccio);

    const baseUrl = await TAN.getUrlAvancada();
    const url = `${baseUrl}/tradueix-document-angles`;
    actualitzaProgress('angles', 40, 'Enviant al servidor...', '');

    const resp = await fetch(url, { method: 'POST', body: formData });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || err.error || 'Error del servidor');
    }

    actualitzaProgress('angles', 90, 'Preparant el document traduït...', '');
    const blob = await resp.blob();
    const nomOriginal = _anglesDocSeleccionat.name;
    const ext = nomOriginal.split('.').pop();
    const sufix = _anglesDireccio === 'en_va' ? '_en-va' : '_va-en';
    _anglesNomDocTraduït = nomOriginal.replace(`.${ext}`, `${sufix}.${ext}`);
    _anglesDocTraduïtBlob = blob;

    actualitzaProgress('angles', 100, 'Completat', '');
    document.getElementById('btn-descarrega-doc-angles').style.display = 'inline-flex';
    mostraMissatgeAngles('info', `Document traduït correctament.`);
    setTimeout(() => amagaProgress('angles'), 2000);
  } catch (e) {
    mostraMissatgeAngles('error', `Error: ${e.message}`);
    amagaProgress('angles');
  } finally {
    btn.disabled = false;
    btn.textContent = '🌐 Traduir document';
  }
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
// FUNCIONS AUXILIARS: Taula de correccions i estadístiques
// ═══════════════════════════════════════════════════════

/**
 * Genera la taula HTML de correccions.
 * @param {Array} correccions - llista de correccions [{num, paragraf, original, correccio, categoria, justificacio}]
 * @returns {string} HTML de la taula
 */
function generaTaulaCorreccions(correccions) {
  if (!correccions || !correccions.length) return '<p>Cap correcció detectada.</p>';
  let html = '<div class="correccions-taula-wrap"><table class="correccions-taula">';
  html += '<thead><tr><th>#</th><th>§</th><th>Original</th><th>Correcció</th><th>Cat.</th><th>Justificació</th></tr></thead><tbody>';
  correccions.forEach((c, i) => {
    const cat = (c.categoria || 'ORTO').toUpperCase().replace('È', 'E');
    html += `<tr>
      <td>${c.num || i + 1}</td>
      <td>${c.paragraf || '—'}</td>
      <td><del>${_esc(c.original || '')}</del></td>
      <td><strong>${_esc(c.correccio || c.corregit || '')}</strong></td>
      <td><span class="cat-badge cat-${cat}">${cat}</span></td>
      <td>${_esc(c.justificacio || '')}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  return html;
}

/**
 * Genera el resum estadístic HTML.
 * @param {Object} resum - {total_errors, sint, morf, lex, orto, total_paraules, densitat, diagnostic, recomanacions}
 * @returns {string} HTML del resum
 */
function generaResumCorreccions(resum) {
  if (!resum || typeof resum !== 'object') return '';
  let html = '<div class="correccions-resum">';
  const items = [
    { lbl: 'Total errors', val: resum.total_errors || 0 },
    { lbl: 'Sintàctics', val: resum.sint || 0 },
    { lbl: 'Morfològics', val: resum.morf || 0 },
    { lbl: 'Lèxics', val: resum.lex || 0 },
    { lbl: 'Ortogràfics', val: resum.orto || 0 },
    { lbl: 'Paraules', val: resum.total_paraules || 0 },
    { lbl: 'Densitat', val: resum.densitat || '—' },
  ];
  items.forEach(it => {
    html += `<div class="resum-item"><span class="resum-num">${it.val}</span><span class="resum-lbl">${it.lbl}</span></div>`;
  });
  html += '</div>';
  if (resum.diagnostic) {
    html += `<div class="resum-diagnostic"><strong>Diagnòstic:</strong> ${_esc(resum.diagnostic)}`;
    if (resum.recomanacions) html += `<br><strong>Recomanacions:</strong> ${_esc(resum.recomanacions)}`;
    html += '</div>';
  }
  return html;
}

function _esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/**
 * Inverteix la direcció de traducció EN↔VA.
 */
function inverteixDireccio() {
  _anglesDireccio = _anglesDireccio === 'en_va' ? 'va_en' : 'en_va';
  const lblOrigen = document.getElementById('angles-llengua-origen');
  const lblDesti  = document.getElementById('angles-llengua-destí');
  const nota      = document.getElementById('angles-direccio-nota');
  const lblEntrada = document.getElementById('angles-label-entrada');
  const lblSortida = document.getElementById('angles-label-sortida');
  const txtEntrada = document.getElementById('angles-text-entrada');
  const txtSortida = document.getElementById('angles-text-sortida');

  if (_anglesDireccio === 'en_va') {
    lblOrigen.textContent = 'Anglès';
    lblDesti.textContent  = 'Valencià';
    nota.innerHTML = 'Traduint de <strong>anglès</strong> a <strong>valencià</strong>';
    if (lblEntrada) lblEntrada.textContent = 'Text en anglès';
    if (lblSortida) lblSortida.textContent = 'Traducció al valencià';
    if (txtEntrada) txtEntrada.placeholder = 'Introdueix el text en anglès...';
    if (txtSortida) txtSortida.placeholder = 'La traducció al valencià apareixerà aquí...';
  } else {
    lblOrigen.textContent = 'Valencià';
    lblDesti.textContent  = 'Anglès';
    nota.innerHTML = 'Traduint de <strong>valencià</strong> a <strong>anglès</strong>';
    if (lblEntrada) lblEntrada.textContent = 'Text en valencià';
    if (lblSortida) lblSortida.textContent = 'Translation to English';
    if (txtEntrada) txtEntrada.placeholder = 'Introdueix el text en valencià...';
    if (txtSortida) txtSortida.placeholder = 'The English translation will appear here...';
  }
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

// ─── RECONNEXIÓ AUTOMÀTICA ──────────────────────────────────────────────────
let _reconnectInterval = null;

function iniciaReconnexio() {
  if (_reconnectInterval) return; // ja està en marxa
  console.log('Connexió perduda, iniciant reintents cada 10 s...');

  _reconnectInterval = setInterval(async () => {
    try {
      const endpoint = await TAN.detectActiveEndpoint();
      if (endpoint) {
        clearInterval(_reconnectInterval);
        _reconnectInterval = null;
        console.log('Servidor reconnectat:', endpoint.name);
      }
    } catch (e) {
      // Segueix intentant
    }
  }, 10000);
}

// Sobreescriu showServerStatus per detectar pèrdua de connexió
(function() {
  const _originalShowStatus = TAN.showServerStatus;
  TAN.showServerStatus = function(name, status) {
    _originalShowStatus(name, status);
    if (status === 'error') {
      iniciaReconnexio();
    }
  };
})();

// ─── EXTRACCIÓ DE GLOSSARI BILINGÜE ─────────────────────────────────────────

let _glossariExtret = []; // Emmagatzema els termes extrets temporalment

async function carregaFitxerGlossari(input, textareaId) {
  const fitxer = input.files[0];
  if (!fitxer) return;
  const ext = fitxer.name.split('.').pop().toLowerCase();

  if (ext === 'txt') {
    const text = await fitxer.text();
    document.getElementById(textareaId).value = text;
  } else if (ext === 'docx') {
    try {
      const JSZipLib = window.JSZip;
      if (!JSZipLib) { alert('JSZip no disponible'); return; }
      const zip = await JSZipLib.loadAsync(fitxer);
      const docXml = await zip.file('word/document.xml').async('text');
      const parser = new DOMParser();
      const doc = parser.parseFromString(docXml, 'text/xml');
      const ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
      const paragrafs = [];
      const ps = doc.getElementsByTagNameNS(ns, 'p');
      for (const p of ps) {
        const ts = p.getElementsByTagNameNS(ns, 't');
        let textP = '';
        for (const t of ts) textP += t.textContent || '';
        if (textP.trim()) paragrafs.push(textP.trim());
      }
      document.getElementById(textareaId).value = paragrafs.join('\n');
    } catch (e) {
      alert('Error llegint el fitxer .docx: ' + e.message);
    }
  } else if (ext === 'pptx') {
    try {
      const JSZipLib = window.JSZip;
      if (!JSZipLib) { alert('JSZip no disponible'); return; }
      const zip = await JSZipLib.loadAsync(fitxer);

      const textos = [];
      // Itera sobre totes les diapositives
      for (const nom of Object.keys(zip.files)) {
        if (nom.match(/^ppt\/slides\/slide\d+\.xml$/)) {
          const xml = await zip.files[nom].async('text');
          const parser = new DOMParser();
          const doc = parser.parseFromString(xml, 'text/xml');
          // Extrau text dels elements <a:t>
          const ns = 'http://schemas.openxmlformats.org/drawingml/2006/main';
          const ps = doc.getElementsByTagNameNS(ns, 'p');
          for (const p of ps) {
            const ts = p.getElementsByTagNameNS(ns, 't');
            let textP = '';
            for (const t of ts) textP += t.textContent || '';
            if (textP.trim()) textos.push(textP.trim());
          }
        }
      }
      document.getElementById(textareaId).value = textos.join('\n');
    } catch (e) {
      alert('Error llegint el fitxer .pptx: ' + e.message);
    }
  } else {
    alert('Format no admès. Useu .txt, .docx o .pptx.');
  }
}

async function extreuGlossariBilingue() {
  const textOriginal  = document.getElementById('glossari-text-original').value.trim();
  const textTraduccio = document.getElementById('glossari-text-traduccio').value.trim();
  const domini        = document.getElementById('glossari-domini-extraccio').value;
  const btn           = document.getElementById('btn-extreu-glossari');
  const msgEl         = document.getElementById('glossari-extraccio-msg');
  const resultatDiv   = document.getElementById('glossari-extraccio-resultat');

  if (!textOriginal || !textTraduccio) {
    msgEl.textContent = 'Cal introduir tant el text original com la traducció.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }
  if (!domini) {
    msgEl.textContent = 'Seleccioneu un domini lingüístic.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }

  btn.disabled = true;
  btn.textContent = '⏳ Analitzant textos...';
  msgEl.style.display = 'none';
  resultatDiv.style.display = 'none';

  try {
    const baseUrl = await TAN.getUrlAvancada();
    const resp = await fetch(baseUrl + '/extreu-glossari', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + (_authToken || ''),
      },
      body: JSON.stringify({
        text_original: textOriginal,
        text_traduccio: textTraduccio,
        domini: domini,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Error del servidor');
    }

    const dades = await resp.json();
    _glossariExtret = dades.termes || [];

    // Renderitza la taula de termes
    _renderitzaTaulaGlossariExtret();

    resultatDiv.style.display = 'block';
    msgEl.textContent = _glossariExtret.length + ' termes especialitzats extrets per al domini "' + domini + '".';
    msgEl.style.color = '#27500A';
    msgEl.style.display = 'block';

  } catch (e) {
    msgEl.textContent = 'Error: ' + e.message;
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = '📚 Extraure glossari es↔va';
  }
}

function _renderitzaTaulaGlossariExtret() {
  const taulaDiv = document.getElementById('glossari-extraccio-taula');
  const termesVisibles = _glossariExtret.filter(t => t !== null);
  if (termesVisibles.length === 0) {
    taulaDiv.innerHTML = '<p style="color:#6A7A9B;">No s\'han trobat termes especialitzats.</p>';
    return;
  }
  let html = '<table style="width:100%; border-collapse:collapse; font-size:13px; table-layout:fixed;">';
  html += '<colgroup><col style="width:5%"><col style="width:43%"><col style="width:43%"><col style="width:9%"></colgroup>';
  html += '<tr style="background:#002E52; color:white;">'
       + '<th style="padding:8px; text-align:center;">#</th>'
       + '<th style="padding:8px; text-align:left;">Castellà</th>'
       + '<th style="padding:8px; text-align:left;">Valencià</th>'
       + '<th style="padding:8px; text-align:center;">✗</th></tr>';
  let num = 0;
  for (let i = 0; i < _glossariExtret.length; i++) {
    const t = _glossariExtret[i];
    if (t === null) continue;
    num++;
    html += '<tr style="border-bottom:1px solid #ddd;" id="terme-row-' + i + '">';
    html += '<td style="padding:6px 8px; text-align:center; color:#6A7A9B;">' + num + '</td>';
    html += '<td style="padding:6px 8px;">' + escapeHtml(t.es || '') + '</td>';
    html += '<td style="padding:6px 8px;"><input type="text" value="' + (t.va || '').replace(/"/g, '&quot;') + '" '
         + 'onchange="_glossariExtret[' + i + '].va = this.value" '
         + 'style="width:100%; padding:4px 6px; border:1px solid #ccc; border-radius:3px; font-size:13px; box-sizing:border-box;"></td>';
    html += '<td style="padding:6px 8px; text-align:center;">'
         + '<button onclick="eliminaTermeExtret(' + i + ')" style="background:none; border:none; color:#d32f2f; cursor:pointer; font-size:16px;" title="Eliminar">✗</button>'
         + '</td></tr>';
  }
  html += '</table>';
  taulaDiv.innerHTML = html;
}

function eliminaTermeExtret(index) {
  _glossariExtret[index] = null;
  _renderitzaTaulaGlossariExtret();
}

async function desaGlossariExtret() {
  const dominiSelect = document.getElementById('glossari-domini-extraccio');
  const domini = dominiSelect ? dominiSelect.value : '';
  const msgEl = document.getElementById('glossari-extraccio-msg');

  // Filtra termes eliminats (nulls)
  const termesValids = (_glossariExtret || []).filter(function(t) { return t !== null && t !== undefined; });

  if (termesValids.length === 0) {
    msgEl.textContent = 'No hi ha termes per desar.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }

  if (!domini) {
    msgEl.textContent = 'Seleccioneu un domini lingüístic.';
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
    return;
  }

  try {
    var baseUrl = await TAN.getUrlAvancada();
    var resp = await fetch(baseUrl + '/glossari/desa-massiu', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + (_authToken || ''),
      },
      body: JSON.stringify({
        domini: domini,
        termes: termesValids
      }),
    });

    // Parseja la resposta una sola vegada com a text
    var respostaText = await resp.text();
    var dades;
    try {
      dades = JSON.parse(respostaText);
    } catch (parseErr) {
      throw new Error('Resposta invàlida del servidor: ' + respostaText.substring(0, 200));
    }

    if (!resp.ok) {
      // Error del servidor — detail pot ser string o array d'objectes (validació Pydantic)
      var detall = dades.detail;
      if (Array.isArray(detall)) {
        detall = detall.map(function(d) { return d.msg || JSON.stringify(d); }).join('; ');
      }
      throw new Error(detall || dades.message || dades.error || JSON.stringify(dades));
    }

    // Èxit
    var nous = dades.nous || 0;
    var total = dades.total || 0;
    msgEl.textContent = nous + ' termes nous afegits al glossari "' + domini + '" (' + total + ' totals).';
    msgEl.style.color = '#27500A';
    msgEl.style.display = 'block';

  } catch (e) {
    var missatgeError;
    if (typeof e === 'string') {
      missatgeError = e;
    } else if (e instanceof Error) {
      missatgeError = e.message;
    } else if (e && typeof e === 'object') {
      missatgeError = e.detail || e.message || JSON.stringify(e);
    } else {
      missatgeError = String(e);
    }
    msgEl.textContent = 'Error: ' + missatgeError;
    msgEl.style.color = '#d32f2f';
    msgEl.style.display = 'block';
  }
}

function exportaGlossariTSV() {
  const termesValids = _glossariExtret.filter(t => t !== null);
  if (termesValids.length === 0) { alert('No hi ha termes per exportar.'); return; }

  let tsv = 'castellà\tvalencià\n';
  for (const t of termesValids) {
    tsv += (t.es || '') + '\t' + (t.va || '') + '\n';
  }

  const blob = new Blob([tsv], { type: 'text/tab-separated-values;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const domini = document.getElementById('glossari-domini-extraccio').value || 'general';
  a.href = url;
  a.download = 'glossari_' + domini.replace(/\s+/g, '_') + '.tsv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
