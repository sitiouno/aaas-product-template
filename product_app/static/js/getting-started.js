/**
 * Getting Started section — vibe coding onboarding guide.
 * Owner-only. Exported: load(container, ctx)
 */

const STEPS = [
  { id: 'explore',      title_en: 'Explore your workspace',       title_es: 'Explora tu workspace',          desc_en: 'Familiarize yourself with the dashboard and sections', desc_es: 'Familiarízate con el panel y las secciones', auto: true },
  { id: 'how-it-works', title_en: 'Check How It Works',           title_es: 'Revisa Cómo Funciona',          desc_en: 'Understand your default agent pipeline',               desc_es: 'Entiende tu pipeline de agentes por defecto',  auto: true },
  { id: 'api-key',      title_en: 'Get your API key',             title_es: 'Obtén tu clave API',            desc_en: 'Create an API key for external integrations',          desc_es: 'Crea una clave API para integraciones externas', auto: true },
  { id: 'ide',          title_en: 'Open in your IDE & customize', title_es: 'Abre en tu IDE y personaliza',  desc_en: 'Use vibe coding to add your own interfaces',           desc_es: 'Usa vibe coding para agregar tus interfaces',   auto: false },
  { id: 'deploy',       title_en: 'Deploy and go live',           title_es: 'Despliega y publica',           desc_en: 'Push to main to trigger automatic deployment',         desc_es: 'Push a main para despliegue automático',        auto: false },
];

const COMPONENTS = [
  { label: 'Card',         hint_en: 'Add a card grid showing...',       hint_es: 'Agrega una cuadrícula de tarjetas...' },
  { label: 'Chat Window',  hint_en: 'Add a chat interface for...',      hint_es: 'Agrega una interfaz de chat para...' },
  { label: 'Data Table',   hint_en: 'Add a data table showing...',      hint_es: 'Agrega una tabla de datos mostrando...' },
  { label: 'Form',         hint_en: 'Add a form to collect...',         hint_es: 'Agrega un formulario para recopilar...' },
  { label: 'Chart',        hint_en: 'Add a chart displaying...',        hint_es: 'Agrega un gráfico mostrando...' },
  { label: 'Map',          hint_en: 'Add an interactive map...',        hint_es: 'Agrega un mapa interactivo...' },
];

function loadProgress() {
  try { return JSON.parse(localStorage.getItem('gs_progress') || '{}'); } catch { return {}; }
}

function saveStep(id) {
  const p = loadProgress();
  p[id] = true;
  localStorage.setItem('gs_progress', JSON.stringify(p));
}

function progressBar(done) {
  const pct = Math.round((done / STEPS.length) * 100);
  return `<div style="margin-bottom:20px;">
    <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-muted);margin-bottom:6px;">
      <span>${done} / ${STEPS.length}</span><span>${pct}%</span>
    </div>
    <div class="gs-progress-bar"><div class="gs-progress-fill" style="width:${pct}%"></div></div>
  </div>`;
}

function ideBody(t) {
  const prompts = [
    t('"Add a chat window section where users can interact with the Hello World agent in real-time"',
      '"Agrega una sección de chat donde los usuarios interactúen con el agente Hello World en tiempo real"'),
    t('"Redesign the landing page for a weather forecast service with hero section and pricing"',
      '"Rediseña la landing page para un servicio de pronóstico del tiempo con hero y precios"'),
    t('"Create a new agent in product_app/research/ that recommends restaurants based on location using Google Search"',
      '"Crea un nuevo agente en product_app/research/ que recomiende restaurantes según la ubicación usando Google Search"'),
  ];
  return `<p style="font-size:13px;color:var(--text-muted);margin:0 0 10px;">${t('Clone and open in Cursor:', 'Clona y abre en Cursor:')}</p>
    <pre style="background:var(--bg-secondary);border-radius:6px;padding:10px;font-size:12px;overflow-x:auto;margin:0 0 12px;">git clone ... &amp;&amp; cursor .</pre>
    <p style="font-size:12px;color:var(--text-muted);margin:0 0 8px;">${t('Example prompts:', 'Prompts de ejemplo:')}</p>
    ${prompts.map(p => `<div class="gs-prompt-card">
      <p class="gs-prompt-label">${t('Try:', 'Prueba:')}</p>
      <p class="gs-prompt-text">${p}</p>
    </div>`).join('')}
    <button class="primary-button" style="margin-top:10px;" data-complete="ide">${t('Mark as done', 'Marcar como hecho')}</button>`;
}

function deployBody(t) {
  return `<p style="font-size:13px;color:var(--text-muted);margin:0 0 10px;">${t('Push to deploy:', 'Push para desplegar:')}</p>
    <pre style="background:var(--bg-secondary);border-radius:6px;padding:10px;font-size:12px;overflow-x:auto;margin:0 0 12px;">git add -A &amp;&amp; git commit &amp;&amp; git push origin main</pre>
    <p style="font-size:13px;color:var(--text-muted);margin:0 0 10px;">${t('GitHub Actions will build and deploy to Cloud Run automatically.', 'GitHub Actions compilará y desplegará en Cloud Run automáticamente.')}</p>
    <button class="primary-button" data-complete="deploy">${t('Mark as done', 'Marcar como hecho')}</button>`;
}

function renderStep(step, state, idx, t) {
  const done = !!state[step.id];
  const currentIdx = STEPS.findIndex(s => !state[s.id]);
  const isCurrent = !done && idx === currentIdx;
  const title = t(step.title_en, step.title_es);
  const desc = t(step.desc_en, step.desc_es);

  let cls = 'gs-step';
  let icon, badge, body = '';

  if (done) {
    cls += ' completed';
    icon = `<span class="gs-step-icon" style="color:var(--accent-green);">&#10003;</span>`;
    badge = `<span class="gs-step-badge done">${t('Done', 'Hecho')}</span>`;
  } else if (isCurrent) {
    cls += ' current';
    icon = `<span class="gs-step-icon" style="color:var(--accent-blue);">${idx + 1}</span>`;
    badge = `<span class="gs-step-badge active">${t('Current', 'Actual')}</span>`;
    const bodyContent = step.id === 'ide' ? ideBody(t) : step.id === 'deploy' ? deployBody(t) : '';
    if (bodyContent) body = `<div class="gs-step-body">${bodyContent}</div>`;
  } else {
    cls += ' pending';
    icon = `<span class="gs-step-icon" style="color:var(--text-muted);">${idx + 1}</span>`;
    badge = '';
  }

  return `<div class="${cls}">
    <div class="gs-step-header">
      <div style="display:flex;align-items:center;gap:6px;">
        ${icon}
        <div>
          <div style="font-size:14px;font-weight:600;">${title}</div>
          ${!done ? `<div style="font-size:12px;color:var(--text-muted);">${desc}</div>` : ''}
        </div>
      </div>
      ${badge}
    </div>
    ${body}
  </div>`;
}

function componentGallery(t) {
  const cards = COMPONENTS.map(c => `
    <div class="gs-component-card">
      <div class="gs-component-label">${c.label}</div>
      <div class="gs-component-preview"></div>
      <div class="gs-component-hint">${t(c.hint_en, c.hint_es)}</div>
    </div>`).join('');
  return `<div style="margin-top:28px;">
    <h3 style="font-size:14px;margin:0 0 12px;">${t('Component Gallery', 'Galería de Componentes')}</h3>
    <div class="gs-component-grid">${cards}</div>
  </div>`;
}

function render(container, ctx) {
  const { t } = ctx;
  const state = loadProgress();
  const done = Object.values(state).filter(Boolean).length;
  const steps = STEPS.map((s, i) => renderStep(s, state, i, t)).join('');

  container.innerHTML = `
    <div style="max-width:680px;">
      <p style="font-size:22px;font-weight:700;margin:0 0 4px;">${t('Getting Started', 'Primeros Pasos')}</p>
      <p style="font-size:13px;color:var(--text-muted);margin:0 0 20px;">${t('Complete these steps to set up your product.', 'Completa estos pasos para configurar tu producto.')}</p>
      ${progressBar(done)}
      <div id="gs-steps">${steps}</div>
      ${componentGallery(t)}
    </div>`;

  container.querySelectorAll('[data-complete]').forEach(btn => {
    btn.addEventListener('click', () => {
      saveStep(btn.dataset.complete);
      render(container, ctx);
    });
  });
}

export async function load(container, ctx) {
  saveStep('explore');
  render(container, ctx);
}
