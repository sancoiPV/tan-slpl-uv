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
let activeEndpoint = null;

async function detectActiveEndpoint() {
  for (const endpoint of ENDPOINTS) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
      const response = await fetch(endpoint.url + endpoint.health, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (response.ok) {
        activeEndpoint = endpoint;
        showServerStatus(endpoint.name, 'ok');
        return endpoint;
      }
    } catch {
      // Aquest endpoint no respon, prova el següent
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

window.TAN = { translate, detectActiveEndpoint, showServerStatus, getUrl };
