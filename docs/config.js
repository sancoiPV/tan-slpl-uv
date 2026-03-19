// config.js — Configuració d'endpoints del motor TAN
// Desplegament: https://sancoipv.github.io/tan-slpl-uv/
// Cap referència a netlify.app — tots els endpoints apunten a servidors locals o ngrok.

const ENDPOINTS = [
  {
    name: 'Motor local optimitzat (CTranslate2)',
    url: 'http://127.0.0.1:5001',
    health: '/health',
    translate: '/translate',
  },
  {
    name: 'Servidor local (uvicorn)',
    url: 'http://127.0.0.1:8000',
    health: '/health',
    translate: '/translate',
  },
  {
    name: 'Servidor UV (ngrok / remot)',
    url: 'https://floatiest-unfeudally-dilan.ngrok-free.dev',
    health: '/health',
    translate: '/translate',
  },
];

const TIMEOUT_MS = 2000;
const TIMEOUT_AVANCAT_MS = 5000; // uvicorn/ngrok: pot trigar a carregar el model
let activeEndpoint = null;

// Endpoints avançats: uvicorn (port 8000) o ngrok.
// S'usen exclusivament per a /tradueix-document, /desa-postedicio, /recompte-paraules.
// Mai s'usa localhost:5001 (CTranslate2) per a operacions amb documents.
const ENDPOINTS_AVANCATS = [
  {
    name: 'Servidor local uvicorn',
    url: 'http://127.0.0.1:8000',
    health: '/health',
  },
  {
    name: 'Servidor UV (ngrok)',
    url: 'https://floatiest-unfeudally-dilan.ngrok-free.dev',
    health: '/health',
  },
];

let activeEndpointAvancat = null;

// Comprova que el servidor és realment l'API TANEU (retorna JSON amb camp d'estat).
// Evita falsos positius de ngrok (que retorna HTML 200 quan el túnel no està actiu).
async function comprova_health(url, health, timeout) {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const response = await fetch(url + health, {
      method: 'GET',
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) return false;
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return false;
    const data = await response.json();
    return data.estat !== undefined || data.status !== undefined || data.backend !== undefined;
  } catch {
    return false;
  }
}

async function detectEndpointAvancat() {
  for (const endpoint of ENDPOINTS_AVANCATS) {
    if (await comprova_health(endpoint.url, endpoint.health, TIMEOUT_AVANCAT_MS)) {
      activeEndpointAvancat = endpoint;
      return endpoint;
    }
  }
  activeEndpointAvancat = null;
  return null;
}

async function getUrlAvancada() {
  if (!activeEndpointAvancat) {
    const detected = await detectEndpointAvancat();
    if (!detected) {
      throw new Error('Cap servidor avançat disponible (uvicorn o ngrok). ' +
        'Comprova que uvicorn està en marxa al port 8000.');
    }
  }
  return activeEndpointAvancat.url;
}

async function detectActiveEndpoint() {
  for (const endpoint of ENDPOINTS) {
    if (await comprova_health(endpoint.url, endpoint.health, TIMEOUT_MS)) {
      activeEndpoint = endpoint;
      showServerStatus(endpoint.name, 'ok');
      return endpoint;
    }
  }
  activeEndpoint = null;
  showServerStatus('Cap servidor disponible', 'error');
  return null;
}

async function translate(text, src = 'es', tgt = 'ca') {
  if (!activeEndpoint) {
    const detected = await detectActiveEndpoint();
    if (!detected) {
      throw new Error(
        'No s\'ha pogut connectar a cap servidor de traducció. ' +
        'Comprova la VPN o activa el motor local.'
      );
    }
  }
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const response = await fetch(activeEndpoint.url + activeEndpoint.translate, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, src, tgt }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) throw new Error('Error del servidor');
    const data = await response.json();
    return data.translation;
  } catch (err) {
    activeEndpoint = null;
    return await translate(text, src, tgt);
  }
}

function showServerStatus(name, status) {
  const indicator = document.getElementById('server-status');
  if (!indicator) return;
  const colors = {
    ok:      { bg: '#EAF3DE', text: '#27500A', border: '#C0DD97' },
    error:   { bg: '#FCEBEB', text: '#791F1F', border: '#F7C1C1' },
    loading: { bg: '#E6F1FB', text: '#0C447C', border: '#B5D4F4' },
  };
  const c = colors[status] || colors.loading;
  indicator.style.cssText = `
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 12px;
    background: ${c.bg};
    color: ${c.text};
    border: 0.5px solid ${c.border};
  `;
  indicator.textContent = name;
}

// Accessor per a app.js: retorna la URL base de l'endpoint actiu
function getUrl() {
  return activeEndpoint ? activeEndpoint.url : '';
}

// Reset manual de l'endpoint avançat (cridat des d'app.js quan l'endpoint falla)
function resetEndpointAvancat() {
  activeEndpointAvancat = null;
}

window.TAN = { translate, detectActiveEndpoint, showServerStatus, getUrl, getUrlAvancada, resetEndpointAvancat };
