/* PixiJS neural visualization for CopaMatchNet.
   Uses PIXI when available and falls back to a local Canvas renderer when offline. */
(function () {
  const nodePalette = {
    input: 0x1f2937,
    team: 0x0f766e,
    hidden: 0x1d4ed8,
    blend: 0x7c3aed,
    output: 0x15803d,
    line: 0x334155,
    pulse: 0x22c55e
  };

  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
  function pct(value) { return value === undefined || value === null || value === '' ? '—' : `${value}%`; }
  function number(value, fallback = '—') { return value === undefined || value === null || value === '' ? fallback : value; }

  function getModelSummary() {
    const metrics = window.WC2026_ACTIVE_METRICAS || window.WC2026_MODELO_DIARIO_METRICAS || window.WC2026_REDE_NEURAL_METRICAS || {};
    const val = metrics.validacao_cronologica || {};
    const train = metrics.treino || {};
    const schema = window.WC2026_REDE_NEURAL_SCHEMA || [];
    const predictions = window.WC2026_ACTIVE_PREVISOES || window.WC2026_MODELO_DIARIO_PREVISOES || window.WC2026_REDE_NEURAL_PREVISOES || [];
    const teams = window.WC2026_MODELO_DIARIO_ESTADO_TIMES || window.WC2026_REDE_NEURAL_TEAMS || [];
    const history = window.WC2026_REDE_NEURAL_HISTORICO || [];
    const topTeam = [...teams].sort((a, b) => Number((b.rating_atual_0_100 ?? b.forca_modelo_0_100) || 0) - Number((a.rating_atual_0_100 ?? a.forca_modelo_0_100) || 0))[0] || {};
    const latestPrediction = predictions.find((row) => row.possui_real !== 'Sim') || predictions[predictions.length - 1] || {};
    const latestEpoch = history[history.length - 1] || {};
    return {
      metrics,
      val,
      train,
      schema,
      predictions,
      teams,
      history,
      topTeam,
      latestPrediction,
      latestEpoch
    };
  }

  function writeInfoCards() {
    const target = document.getElementById('pixi-neural-details');
    if (!target) return;
    const summary = getModelSummary();
    const rows = [
      ['Modelo ativo', summary.metrics.modelo_ativo || summary.metrics.modelo || 'Modelo diário incremental'],
      ['Fonte', summary.metrics.fonte_previsao || 'modelo_diario'],
      ['Usa desempenho Copa', summary.metrics.usa_desempenho_copa ? 'Sim' : '—'],
      ['Validação', `${pct(summary.metrics.acuracia_vencedor_percentual || summary.val.acuracia_vencedor)} vencedor · ${pct(summary.metrics.placar_exato_percentual || summary.val.placar_exato)} placar`],
      ['Sem vazamento', summary.metrics.validacao_sem_vazamento ? 'Sim' : '—'],
      ['Time mais forte', summary.topTeam.selecao ? `${summary.topTeam.selecao} · ${summary.topTeam.rating_atual_0_100 || summary.topTeam.forca_modelo_0_100}` : '—']
    ];
    target.innerHTML = rows.map(([label, value]) => `<div class="pixi-info-row"><span>${label}</span><b>${value}</b></div>`).join('');
  }

  function buildGraphData() {
    const summary = getModelSummary();
    const val = summary.val || {};
    const train = summary.train || {};
    const features = [
      ['forca', 'Força do elenco', `${number(summary.metrics.variaveis_numericas)} features`],
      ['liga', 'Competitividade liga', 'peso inicial do elenco'],
      ['jogadores', 'Desempenho jogadores', 'proxy + destaques'],
      ['calendario', 'Calendário', 'fase + data']
    ];
    const nodes = [];
    const add = (id, label, subtitle, col, row, type) => nodes.push({ id, label, subtitle, col, row, type });

    features.forEach((item, i) => add(item[0], item[1], item[2], 0, i, 'input'));
    add('teamA', 'Embedding seleção A', `${number(summary.metrics.times_com_embedding)} times`, 1, 1.1, 'team');
    add('teamB', 'Embedding seleção B', 'vetores treináveis', 1, 3.4, 'team');
    add('dense1', 'Dense 65 → 128', 'LayerNorm + SiLU', 2, .8, 'hidden');
    add('dense2', 'Dense 128 → 64', 'Dropout anti-overfit', 2, 2.65, 'hidden');
    add('dense3', 'Dense 64 → 32', `val_loss ${number(summary.latestEpoch.val_loss)}`, 2, 4.5, 'hidden');
    add('outputLayer', 'Saída neural', 'saída neural direta', 3, 2.65, 'blend');
    add('golsA', 'Gols time A', `treino ${pct(train.acuracia_vencedor)}`, 4, 1.2, 'output');
    add('golsB', 'Gols time B', `erro médio ${number(val.erro_medio_total_gols)}`, 4, 2.65, 'output');
    add('winner', 'Vencedor', `validação ${pct(val.acuracia_vencedor)}`, 4, 4.1, 'output');

    const edges = [];
    const toTeam = ['forca', 'liga', 'jogadores'];
    toTeam.forEach((id) => { edges.push([id, 'teamA']); edges.push([id, 'teamB']); });
    ['teamA', 'teamB', 'calendario'].forEach((id) => edges.push([id, 'dense1']));
    edges.push(['dense1', 'dense2'], ['dense2', 'dense3'], ['dense3', 'outputLayer']);
    edges.push(['outputLayer', 'golsA'], ['outputLayer', 'golsB'], ['outputLayer', 'winner']);
    return { nodes, edges };
  }

  function initFallbackCanvas(container) {
    container.classList.add('pixi-stage--fallback');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    container.appendChild(canvas);
    let raf = 0;
    function draw() {
      const rect = container.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);
      const { nodes, edges } = buildGraphData();
      const marginX = 46;
      const marginY = 34;
      const colW = (rect.width - marginX * 2) / 4;
      const rowH = (rect.height - marginY * 2) / 5.2;
      const pos = new Map();
      nodes.forEach((n) => pos.set(n.id, { x: marginX + n.col * colW, y: marginY + n.row * rowH }));
      ctx.lineWidth = 1.2;
      edges.forEach(([from, to], index) => {
        const a = pos.get(from); const b = pos.get(to);
        if (!a || !b) return;
        ctx.strokeStyle = index % 3 === 0 ? 'rgba(34,197,94,.35)' : 'rgba(148,163,184,.22)';
        ctx.beginPath();
        const mid = (a.x + b.x) / 2;
        ctx.moveTo(a.x + 98, a.y + 24);
        ctx.bezierCurveTo(mid, a.y + 24, mid, b.y + 24, b.x, b.y + 24);
        ctx.stroke();
      });
      nodes.forEach((n) => {
        const p = pos.get(n.id);
        const w = 196, h = 50;
        ctx.fillStyle = n.type === 'output' ? 'rgba(22,101,52,.20)' : n.type === 'blend' ? 'rgba(88,28,135,.22)' : 'rgba(15,23,42,.74)';
        ctx.strokeStyle = 'rgba(255,255,255,.12)';
        ctx.beginPath();
        ctx.roundRect(p.x, p.y, w, h, 12);
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#f8fafc';
        ctx.font = '700 13px Inter, system-ui, sans-serif';
        ctx.fillText(n.label, p.x + 12, p.y + 21);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '11px Inter, system-ui, sans-serif';
        ctx.fillText(n.subtitle, p.x + 12, p.y + 38);
      });
    }
    const ro = new ResizeObserver(() => { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); });
    ro.observe(container);
    draw();
  }

  function pixiText(text, style) {
    try { return new PIXI.Text({ text, style }); }
    catch (error) { return new PIXI.Text(text, style); }
  }

  function roundedRect(g, x, y, w, h, r, fill, alpha, stroke, strokeAlpha) {
    if (typeof g.beginFill === 'function') {
      g.lineStyle(1, stroke, strokeAlpha);
      g.beginFill(fill, alpha);
      g.drawRoundedRect(x, y, w, h, r);
      g.endFill();
    } else {
      g.roundRect(x, y, w, h, r).fill({ color: fill, alpha }).stroke({ color: stroke, alpha: strokeAlpha, width: 1 });
    }
  }

  function drawLine(g, a, b, pulse = 0) {
    const sx = a.x + 202;
    const sy = a.y + 28;
    const ex = b.x;
    const ey = b.y + 28;
    const mx = (sx + ex) / 2;
    if (typeof g.moveTo !== 'function') return;
    if (typeof g.lineStyle === 'function') g.lineStyle(1.35, nodePalette.line, .46);
    else g.stroke({ color: nodePalette.line, alpha: .46, width: 1.35 });
    g.moveTo(sx, sy);
    if (typeof g.bezierCurveTo === 'function') g.bezierCurveTo(mx, sy, mx, ey, ex, ey);
    else g.lineTo(ex, ey);
    const px = sx + (ex - sx) * pulse;
    const py = sy + (ey - sy) * pulse;
    if (typeof g.beginFill === 'function') {
      g.beginFill(nodePalette.pulse, .78); g.drawCircle(px, py, 3.5); g.endFill();
    } else g.circle(px, py, 3.5).fill({ color: nodePalette.pulse, alpha: .78 });
  }

  async function initPixiStage(container) {
    if (!window.PIXI) {
      initFallbackCanvas(container);
      return;
    }

    const app = new PIXI.Application();
    try {
      await app.init({ backgroundAlpha: 0, antialias: true, autoDensity: true, resolution: Math.min(2, window.devicePixelRatio || 1), resizeTo: container });
      container.appendChild(app.canvas);
    } catch (error) {
      initFallbackCanvas(container);
      return;
    }

    const world = new PIXI.Container();
    const lines = new PIXI.Graphics();
    const cards = new PIXI.Container();
    world.addChild(lines, cards);
    app.stage.addChild(world);
    const data = buildGraphData();
    const nodeMap = new Map();
    let scale = 1;
    let dragging = false;
    let dragStart = { x: 0, y: 0 };
    let offset = { x: 0, y: 0 };

    function layout() {
      cards.removeChildren();
      lines.clear();
      nodeMap.clear();
      const w = Math.max(980, container.clientWidth - 40);
      const h = Math.max(440, container.clientHeight - 40);
      const marginX = 20;
      const marginY = 10;
      const colW = (w - marginX * 2) / 4;
      const rowH = (h - marginY * 2) / 5.2;
      data.nodes.forEach((n) => {
        const x = marginX + n.col * colW;
        const y = marginY + n.row * rowH;
        nodeMap.set(n.id, { x, y });
        const group = new PIXI.Container();
        group.x = x; group.y = y;
        const bg = new PIXI.Graphics();
        const fill = nodePalette[n.type] || 0x1f2937;
        roundedRect(bg, 0, 0, 204, 56, 14, fill, n.type === 'input' ? .22 : .32, 0xffffff, .12);
        const title = pixiText(n.label, { fill: '#f8fafc', fontSize: 13, fontWeight: '700', fontFamily: 'Inter, system-ui, sans-serif' });
        title.x = 12; title.y = 9;
        const subtitle = pixiText(n.subtitle, { fill: '#94a3b8', fontSize: 11, fontFamily: 'Inter, system-ui, sans-serif' });
        subtitle.x = 12; subtitle.y = 31;
        group.addChild(bg, title, subtitle);
        cards.addChild(group);
      });
      fitToContainer();
    }

    function fitToContainer() {
      const bounds = { width: 1040, height: 520 };
      const sx = container.clientWidth / bounds.width;
      const sy = container.clientHeight / bounds.height;
      scale = clamp(Math.min(sx, sy), .62, 1.08);
      offset = { x: (container.clientWidth - bounds.width * scale) / 2, y: (container.clientHeight - bounds.height * scale) / 2 };
      applyTransform();
    }

    function applyTransform() {
      world.scale.set(scale);
      world.position.set(offset.x, offset.y);
    }

    function renderLines(tickerValue) {
      lines.clear();
      const pulse = (tickerValue % 120) / 120;
      data.edges.forEach(([from, to], index) => {
        const a = nodeMap.get(from); const b = nodeMap.get(to);
        if (!a || !b) return;
        drawLine(lines, a, b, (pulse + index * .065) % 1);
      });
    }

    app.ticker.add(() => renderLines(app.ticker.lastTime / 16.6));
    window.addEventListener('resize', layout);
    layout();

    container.addEventListener('wheel', (event) => {
      event.preventDefault();
      const rect = container.getBoundingClientRect();
      const mx = event.clientX - rect.left;
      const my = event.clientY - rect.top;
      const beforeX = (mx - offset.x) / scale;
      const beforeY = (my - offset.y) / scale;
      const factor = event.deltaY < 0 ? 1.08 : .92;
      scale = clamp(scale * factor, .45, 2.2);
      offset.x = mx - beforeX * scale;
      offset.y = my - beforeY * scale;
      applyTransform();
    }, { passive: false });

    container.addEventListener('pointerdown', (event) => {
      dragging = true;
      dragStart = { x: event.clientX - offset.x, y: event.clientY - offset.y };
      container.setPointerCapture?.(event.pointerId);
      container.classList.add('is-dragging');
    });
    container.addEventListener('pointermove', (event) => {
      if (!dragging) return;
      offset = { x: event.clientX - dragStart.x, y: event.clientY - dragStart.y };
      applyTransform();
    });
    const stop = (event) => {
      dragging = false;
      container.classList.remove('is-dragging');
      if (event?.pointerId !== undefined) container.releasePointerCapture?.(event.pointerId);
    };
    container.addEventListener('pointerup', stop);
    container.addEventListener('pointercancel', stop);
    container.addEventListener('dblclick', fitToContainer);
  }

  function init() {
    const container = document.getElementById('pixi-neural-stage');
    if (!container) return;
    writeInfoCards();
    initPixiStage(container);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
