/**
 * How It Works section — agent pipeline documentation with diagrams.
 * Owner-only. Exported: load(container, ctx)
 */

function saveHiwStep() {
  try {
    const p = JSON.parse(localStorage.getItem('gs_progress') || '{}');
    p['how-it-works'] = true;
    localStorage.setItem('gs_progress', JSON.stringify(p));
  } catch { /* ignore */ }
}

function badge(text, cls) {
  return `<span class="hiw-badge ${cls}">${text}</span>`;
}

function agentNode(icon, label, cls) {
  return `<div class="hiw-agent-node ${cls}">
    <div style="font-size:18px;">${icon}</div>
    <div style="font-size:11px;margin-top:4px;">${label}</div>
  </div>`;
}

function arrow() {
  return `<span class="hiw-arrow">→</span>`;
}

function buildPipeline(agents) {
  if (!agents || !agents.length) return '';
  const nodes = agents.map((a, i) => {
    const icon = a.icon || '🤖';
    const label = a.name || a.role || `Agent ${i + 1}`;
    const cls = i === 0 ? 'research' : i === agents.length - 1 ? 'output' : 'report';
    return agentNode(icon, label, cls);
  });
  return nodes.join(arrow());
}

function capabilityCard(style, t) {
  const isCanonical = style.is_canonical !== false;
  const label = isCanonical
    ? t('DEFAULT AGENT', 'AGENTE PREDETERMINADO')
    : t('CUSTOM AGENT', 'AGENTE PERSONALIZADO');
  const pipeline = buildPipeline(style.agents || style.stages || []);

  return `<div class="hiw-agent-card">
    <div class="hiw-agent-header">
      <div>
        <div style="font-size:10px;color:var(--text-muted);margin-bottom:3px;">${label}</div>
        <div style="font-weight:600;font-size:14px;">${style.name || style.key}</div>
      </div>
      <div style="display:flex;gap:6px;align-items:center;">
        ${badge('● ' + t('Active', 'Activo'), 'active')}
        ${isCanonical
          ? badge('🔒 ' + t('Canonical', 'Canónico'), 'canonical')
          : badge('✏️ ' + t('Custom', 'Custom'), 'custom')}
      </div>
    </div>
    ${pipeline
      ? `<div class="hiw-pipeline-diagram">${pipeline}</div>`
      : `<div class="hiw-pipeline-diagram" style="color:var(--text-muted);font-size:12px;">${t('No agents defined', 'Sin agentes definidos')}</div>`}
    <div class="hiw-meta">
      ${style.agent_count != null ? `<span>🤖 ${style.agent_count} ${t('agents', 'agentes')}</span>` : ''}
      ${style.credit_cost != null ? `<span>💳 ${style.credit_cost} ${t('credits', 'créditos')}</span>` : ''}
      ${style.estimated_duration ? `<span>⏱ ${style.estimated_duration}</span>` : ''}
    </div>
  </div>`;
}

function pipelineTypes(t) {
  const seqDiagram = `<div class="hiw-pipeline-diagram" style="margin:10px 0;">
    ${agentNode('📥', 'Input', 'research')}${arrow()}${agentNode('🔍', 'Search', 'report')}${arrow()}${agentNode('📝', 'Report', 'output')}
  </div>`;

  const parDiagram = `<div class="hiw-pipeline-diagram" style="margin:10px 0;flex-wrap:nowrap;">
    ${agentNode('📥', 'Input', 'research')}${arrow()}
    <div class="hiw-parallel-group">
      ${agentNode('🔍', 'Web', 'report')}
      ${agentNode('📰', 'News', 'report')}
    </div>
    ${arrow()}${agentNode('🧩', 'Merge', 'report')}${arrow()}${agentNode('📝', 'Report', 'output')}
  </div>`;

  const seqPrompt = t(
    '"Analyze the company Acme Corp: research their financials, then write a risk report"',
    '"Analiza la empresa Acme Corp: investiga sus finanzas, luego redacta un informe de riesgo"'
  );
  const parPrompt = t(
    '"Research the latest news AND stock data for Tesla simultaneously, then merge into a summary"',
    '"Investiga las últimas noticias Y datos bursátiles de Tesla simultáneamente, luego combínalos en un resumen"'
  );

  return `<div class="hiw-pipeline-types">
    <div class="hiw-type-card">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">${t('Sequential Pipeline', 'Pipeline Secuencial')}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;">${t('Each agent runs after the previous one completes.', 'Cada agente corre tras completar el anterior.')}</div>
      ${seqDiagram}
      <div class="gs-prompt-card" style="margin-top:8px;">
        <p class="gs-prompt-label">${t('Example prompt:', 'Prompt de ejemplo:')}</p>
        <p class="gs-prompt-text">${seqPrompt}</p>
      </div>
    </div>
    <div class="hiw-type-card">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px;">${t('Parallel Pipeline', 'Pipeline Paralelo')}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;">${t('Multiple agents run at the same time, results are merged.', 'Varios agentes corren a la vez, los resultados se combinan.')}</div>
      ${parDiagram}
      <div class="gs-prompt-card" style="margin-top:8px;">
        <p class="gs-prompt-label">${t('Example prompt:', 'Prompt de ejemplo:')}</p>
        <p class="gs-prompt-text">${parPrompt}</p>
      </div>
    </div>
  </div>`;
}

function didacticExample(t) {
  const vibeCodingPrompt = t(
    '"Create a Weather Forecast product: run 🌤 Weather agent and 📰 News agent in parallel, pass both results to 🧠 Analyst, then generate a 📝 Report"',
    '"Crea un producto Weather Forecast: ejecuta el agente 🌤 Clima y el agente 📰 Noticias en paralelo, pasa los resultados al 🧠 Analista, luego genera un 📝 Reporte"'
  );

  const diagram = `<div class="hiw-pipeline-diagram" style="margin:12px 0;flex-wrap:wrap;">
    ${agentNode('📥', t('User Input', 'Entrada'), 'research')}${arrow()}
    <div class="hiw-parallel-group">
      ${agentNode('🌤', t('Weather', 'Clima'), 'report')}
      ${agentNode('📰', t('News', 'Noticias'), 'report')}
    </div>
    ${arrow()}${agentNode('🧠', t('Analyst', 'Analista'), 'report')}${arrow()}${agentNode('📝', t('Reporter', 'Reporter'), 'report')}${arrow()}${agentNode('✓', t('Report', 'Reporte'), 'output')}
  </div>`;

  return `<div class="hiw-agent-card">
    <div style="font-weight:600;font-size:14px;margin-bottom:4px;">🌦 ${t('Didactic Example: Weather Forecast Product', 'Ejemplo Didáctico: Producto Weather Forecast')}</div>
    <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">${t('A mixed pipeline combining parallel research with sequential analysis.', 'Pipeline mixto que combina investigación paralela con análisis secuencial.')}</div>
    ${diagram}
    <div style="margin-top:10px;">
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">${t('Vibe coding prompt that creates this:', 'Prompt vibe coding que crea esto:')}</div>
      <div class="gs-prompt-card">
        <p class="gs-prompt-label">${t('Try in your IDE:', 'Prueba en tu IDE:')}</p>
        <p class="gs-prompt-text">${vibeCodingPrompt}</p>
      </div>
    </div>
  </div>`;
}

async function fetchCapabilities() {
  try {
    const res = await fetch('/api/v1/research/capabilities');
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function load(container, ctx) {
  const { t } = ctx;

  saveHiwStep();

  container.innerHTML = `<div style="max-width:760px;">
    <p style="font-size:22px;font-weight:700;margin:0 0 4px;">${t('How It Works', 'Cómo Funciona')}</p>
    <p style="font-size:13px;color:var(--text-muted);margin:0 0 24px;">${t('Your agent pipelines, explained.', 'Tus pipelines de agentes, explicados.')}</p>

    <h3 style="font-size:14px;font-weight:600;margin:0 0 12px;color:var(--text-secondary);">${t('Pipeline Types', 'Tipos de Pipeline')}</h3>
    ${pipelineTypes(t)}

    <h3 style="font-size:14px;font-weight:600;margin:0 0 12px;color:var(--text-secondary);">${t('Didactic Example', 'Ejemplo Didáctico')}</h3>
    ${didacticExample(t)}

    <h3 style="font-size:14px;font-weight:600;margin:24px 0 12px;color:var(--text-secondary);">${t('Your Agent Styles', 'Tus Estilos de Agente')}</h3>
    <div id="hiw-capabilities">${t('Loading…', 'Cargando…')}</div>
  </div>`;

  const data = await fetchCapabilities();
  const capEl = container.querySelector('#hiw-capabilities');
  if (!data || !data.styles || !data.styles.length) {
    capEl.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">${t('Could not load capabilities. Check back later.', 'No se pudieron cargar las capacidades. Intenta más tarde.')}</p>`;
    return;
  }
  capEl.innerHTML = data.styles.map(s => capabilityCard(s, t)).join('');
}
